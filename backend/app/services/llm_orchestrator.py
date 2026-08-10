from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.policy.engine import DefaultPolicyEngine
from app.governance.policy.enforcement import get_policy_engine, record_violations
from app.governance.policy.schema import GovernanceContext, GovernancePolicy, PolicyCondition
from app.models.benchmark import BenchmarkResult
from app.services.audit_service import AuditService
from app.services.faithfulness_service import FaithfulnessService
from app.services.model_registry import CLOUD_PROVIDERS, cost_per_word
from app.services.settings_service import settings_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    name: str
    timeout: float
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    provider_type: str = "openai"  # openai | anthropic | google | groq | ollama


class LLMOrchestrator:
    def __init__(self) -> None:
        self.audit_service = AuditService()
        self.faithfulness_service = FaithfulnessService()
        # Names and timeouts only — API keys are always resolved live from
        # settings_service.get() so UI changes take effect on the next request.
        self.configs: Dict[str, ModelConfig] = {
            "cloud": ModelConfig(
                name=settings_service.get("CLOUD_MODEL_NAME", "gpt-4o"),
                timeout=float(settings_service.get("CLOUD_TIMEOUT", "30.0")),
                provider_type="openai",
            ),
            "local": ModelConfig(
                name=settings_service.get("LOCAL_MODEL_NAME", "llama3.2:latest"),
                timeout=float(settings_service.get("LOCAL_TIMEOUT", "120.0")),
                base_url=settings_service.get("OLLAMA_BASE_URL", "http://ollama-service:11434/v1"),
                api_key="ollama",
                provider_type="ollama",
            ),
        }
        self._openai_clients: Dict[str, AsyncOpenAI] = {}

    # ------------------------------------------------------------------
    # Client factories
    # ------------------------------------------------------------------

    def _get_openai_compatible_client(self, config: ModelConfig) -> AsyncOpenAI:
        cache_key = f"{config.provider_type}:{config.base_url}"
        if cache_key not in self._openai_clients:
            self._openai_clients[cache_key] = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            logger.info("Initialized %s client.", config.provider_type)
        return self._openai_clients[cache_key]

    def _build_config_for(
        self,
        provider: str,
        provider_type: Optional[str],
        model_id: Optional[str],
    ) -> ModelConfig:
        """Return a ModelConfig, applying optional overrides from the request."""
        base = self.configs.get(provider, self.configs["cloud"])

        if not provider_type and not model_id:
            return base

        pt = provider_type or base.provider_type
        mid = model_id or base.name

        # Always resolve keys live so UI changes take effect immediately
        cloud_cfg = CLOUD_PROVIDERS.get(pt, {})
        key_env = cloud_cfg.get("key_env")

        if pt == "ollama":
            api_key = "ollama"
            base_url = settings_service.get("OLLAMA_BASE_URL", "http://ollama-service:11434/v1")
        else:
            api_key = settings_service.get(key_env) if key_env else base.api_key
            base_url = cloud_cfg.get("base_url") or base.base_url

        return ModelConfig(
            name=mid,
            timeout=base.timeout,
            api_key=api_key,
            base_url=base_url,
            provider_type=pt,
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def get_streaming_response(
        self,
        prompt: str,
        provider: str,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        config = self._build_config_for(provider, provider_type, model_id)

        try:
            if config.provider_type == "anthropic":
                async for token in self._stream_anthropic(prompt, config):
                    yield token
            else:
                async for token in self._stream_openai_compat(prompt, config):
                    yield token
        except Exception as exc:
            logger.error(
                "Stream failure | provider=%s type=%s model=%s | %s: %s",
                provider, config.provider_type, config.name,
                type(exc).__name__, exc,
            )
            yield f"Error: {config.provider_type} service is currently unavailable."

    async def _stream_openai_compat(
        self, prompt: str, config: ModelConfig
    ) -> AsyncGenerator[str, None]:
        client = self._get_openai_compatible_client(config)
        logger.info("Streaming via %s | model=%s", config.provider_type, config.name)
        stream = await client.chat.completions.create(
            model=config.name,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            timeout=config.timeout,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(
        self, prompt: str, config: ModelConfig
    ) -> AsyncGenerator[str, None]:
        try:
            import anthropic
        except ImportError:
            yield "Error: anthropic SDK not installed. Run: pip install anthropic"
            return

        if not config.api_key:
            yield "Error: ANTHROPIC_API_KEY is not configured."
            return

        client = anthropic.AsyncAnthropic(api_key=config.api_key)
        logger.info("Streaming via Anthropic | model=%s", config.name)
        async with client.messages.stream(
            model=config.name,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ------------------------------------------------------------------
    # Benchmark runner
    # ------------------------------------------------------------------

    async def run_and_record_benchmark(
        self,
        db: AsyncSession,
        prompt: str,
        provider: str,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        full_content = ""
        config = self._build_config_for(provider, provider_type, model_id)

        try:
            async for chunk in self.get_streaming_response(
                prompt, provider, provider_type, model_id
            ):
                full_content += chunk
                yield chunk

            latency_ms = int((time.time() - start_time) * 1000)

            pii_in_prompt = self.audit_service.scan_for_pii(prompt)
            pii_in_content = self.audit_service.scan_for_pii(full_content)
            pii_detected = bool(pii_in_prompt or pii_in_content)
            safety_score = self.audit_service.calculate_safety_score(full_content or prompt)

            # Opt-in: only scored when the caller supplied retrieved context,
            # so plain prompt-only runs never pay the judge-model latency/cost.
            faithfulness_score: Optional[float] = None
            context_utilization: Optional[float] = None
            if context:
                faithfulness_score, context_utilization = await self.faithfulness_service.score(
                    prompt, full_content, context
                )

            word_count = len(full_content.split())
            estimated_cost = cost_per_word(config.name, provider) * word_count

            new_result = BenchmarkResult(
                prompt=prompt,
                provider=provider,
                model_name=config.name,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                response_preview=full_content[:200],
                pii_detected=pii_detected,
                safety_score=safety_score,
                faithfulness_score=faithfulness_score,
                context_utilization=context_utilization,
                version_tag=f"{config.provider_type}/{config.name}",
            )

            db.add(new_result)
            await db.commit()
            logger.info(
                "Benchmark saved | provider=%s type=%s model=%s | PII=%s safety=%.2f faithfulness=%s",
                provider, config.provider_type, config.name, pii_detected, safety_score,
                faithfulness_score,
            )

            if faithfulness_score is not None:
                await self._check_faithfulness_policy(
                    db, prompt, provider, config.name, faithfulness_score
                )

        except Exception as exc:
            logger.error("Failed to record benchmark: %s", exc)

    async def _check_faithfulness_policy(
        self,
        db: AsyncSession,
        prompt: str,
        provider: str,
        model_id: str,
        faithfulness_score: float,
    ) -> None:
        """Post-response governance check — faithfulness is only known after the
        response has streamed back, so this runs after the fact (warn/alert
        only; see record_violations' post_response downgrade)."""
        try:
            engine = get_policy_engine()
            # Only re-evaluate faithfulness rules here — other conditions
            # (PII, safety, cost, model_is) were already fully evaluated
            # pre-response with real data; re-running them here against
            # placeholder values would spuriously re-fire them.
            faithfulness_rules = [
                r for r in engine.policy.rules
                if r.condition == PolicyCondition.FAITHFULNESS_SCORE_BELOW
            ]
            if not faithfulness_rules:
                return

            faithfulness_policy = GovernancePolicy(
                version=engine.policy.version, name=engine.policy.name, rules=faithfulness_rules
            )
            faithfulness_engine = DefaultPolicyEngine(faithfulness_policy)

            gov_context = GovernanceContext(
                prompt=prompt,
                provider=provider,
                model_id=model_id,
                pii_detected=False,
                pii_entity_types=[],
                pii_max_confidence=0.0,
                safety_score=1.0,
                estimated_prompt_cost_usd=0.0,
                faithfulness_score=faithfulness_score,
            )
            verdict = faithfulness_engine.evaluate(gov_context)
            if verdict.violated_rules:
                await record_violations(
                    db, verdict, gov_context, faithfulness_engine, post_response=True
                )
        except Exception as exc:
            logger.error("Post-response faithfulness policy check failed: %s", exc)
