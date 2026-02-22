import os
import logging
from openai import AsyncOpenAI
from typing import AsyncGenerator, Optional, Dict
from dataclasses import dataclass

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