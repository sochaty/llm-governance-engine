import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import logging
from openai import AsyncOpenAI
from typing import AsyncGenerator, Optional, Dict
from dataclasses import dataclass
import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.benchmark import BenchmarkResult

# Setup Enterprise Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ModelConfig:
    name: str
    timeout: float
    base_url: Optional[str] = None
    api_key: Optional[str] = None

class LLMOrchestrator:
    def __init__(self):
        # Configuration is loaded once from environment variables
        self.configs: Dict[str, ModelConfig] = {
            "cloud": ModelConfig(
                name=os.getenv("CLOUD_MODEL_NAME", "gpt-4o"),
                timeout=float(os.getenv("CLOUD_TIMEOUT", "30.0")),
                api_key=os.getenv("OPENAI_API_KEY")
            ),
            "local": ModelConfig(
                name=os.getenv("LOCAL_MODEL_NAME", "llama3.2:latest"),
                timeout=float(os.getenv("LOCAL_TIMEOUT", "120.0")),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama-service:11434/v1"),
                api_key="ollama" # Placeholder for local
            )
        }
        
        self._clients: Dict[str, AsyncOpenAI] = {}

    def _get_client(self, provider: str) -> AsyncOpenAI:
        """
        Generalized client factory with lazy loading.
        """
        if provider not in self._clients:
            config = self.configs.get(provider)
            if not config:
                raise ValueError(f"Unsupported provider: {provider}")
            
            if provider == "cloud" and not config.api_key:
                logger.error("Cloud API Key missing in environment.")
                raise RuntimeError("Cloud configuration error.")

            self._clients[provider] = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )
            logger.info(f"Initialized {provider} client.")
            
        return self._clients[provider]

    async def get_streaming_response(self, prompt: str, provider: str) -> AsyncGenerator[str, None]:
        """
        Generic entry point for streaming. Bypasses hardcoded provider logic.
        """
        try:
            config = self.configs.get(provider)
            if not config:
                yield f"Error: Provider {provider} not configured."
                return

            client = self._get_client(provider)
            
            logger.info(f"Requesting stream from {provider} using model {config.name}")

            stream = await client.chat.completions.create(
                model=config.name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                timeout=config.timeout
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            # Log the full error internally, return a sanitized version to the UI
            logger.error(f"Stream failure for {provider}: {type(e).__name__} - {str(e)}")
            yield f"Error: {provider.capitalize()} service is currently unavailable."

    async def run_and_record_benchmark(
    self, 
    db: AsyncSession, 
    prompt: str, 
    provider: str
) -> AsyncGenerator[str, None]:
        start_time = time.time()
        full_content = ""
        config = self.configs.get(provider)
        
        try:
            # 1. Yield the stream to the UI in real-time
            async for chunk in self.get_streaming_response(prompt, provider):
                full_content += chunk
                yield chunk

            # 2. Calculate Metrics after the stream finishes
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Simple Enterprise Cost Logic
            # Cloud: ~$0.03 per 1k words | Local: $0.00
            word_count = len(full_content.split())
            estimated_cost = (word_count * 0.00003) if provider == "cloud" else 0.0

            # 3. Create Database Record
            new_result = BenchmarkResult(
                prompt=prompt,
                provider=provider,
                model_name=config.name if config else "unknown",
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                response_preview=full_content[:200] # Store a snippet for the UI history
            )

            db.add(new_result)
            await db.commit()
            logger.info(f"Benchmark saved: {provider} | {latency_ms}ms")

        except Exception as e:
            logger.error(f"Failed to record benchmark: {e}")