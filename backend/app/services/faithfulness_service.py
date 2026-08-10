from __future__ import annotations

import logging
from typing import Optional, Tuple

from openai import AsyncOpenAI

from app.services.settings_service import settings_service

logger = logging.getLogger(__name__)


class FaithfulnessService:
    """Computes RAGAS faithfulness + context utilization scores for a response.

    Both metrics need an LLM to act as judge — resolved live from
    settings_service (OpenAI key), mirroring how llm_orchestrator resolves
    provider keys on every request rather than caching them at startup.

    Scoring is opt-in: callers only invoke this when the caller supplied
    retrieved `context` for the request, so plain prompt-only runs never
    pay the extra judge-model latency/cost.
    """

    def __init__(self, judge_model: str = "gpt-4o-mini") -> None:
        self.judge_model = judge_model
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> Optional[AsyncOpenAI]:
        api_key = settings_service.get("OPENAI_API_KEY")
        if not api_key:
            return None
        if self._client is None:
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def score(
        self, prompt: str, response: str, context: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (faithfulness_score, context_utilization) for a response given
        retrieved `context`, or (None, None) if scoring can't be performed —
        never raises, so a judge-model failure never breaks the response path.
        """
        if not context or not response:
            return None, None

        client = self._get_client()
        if client is None:
            logger.warning("Faithfulness scoring skipped: OPENAI_API_KEY not configured.")
            return None, None

        try:
            from ragas.llms.base import llm_factory
            from ragas.metrics.collections import ContextUtilization, Faithfulness

            judge = llm_factory(self.judge_model, client=client)
            retrieved_contexts = [context]

            faithfulness_result = await Faithfulness(llm=judge).ascore(
                user_input=prompt,
                response=response,
                retrieved_contexts=retrieved_contexts,
            )
            context_result = await ContextUtilization(llm=judge).ascore(
                user_input=prompt,
                response=response,
                retrieved_contexts=retrieved_contexts,
            )

            return self._clean(faithfulness_result.value), self._clean(context_result.value)
        except Exception as exc:
            logger.error("Faithfulness scoring failed: %s", exc)
            return None, None

    @staticmethod
    def _clean(value) -> Optional[float]:
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if value != value:  # NaN check — ragas returns NaN when it can't produce a verdict
            return None
        return round(value, 4)
