"""Model catalog and Ollama model management.

Provides:
  - OLLAMA_CATALOG   : curated list of popular models available to pull
  - CLOUD_PROVIDERS  : per-provider model lists with pricing metadata
  - OllamaModelManager : async client for the Ollama Docker container API
"""
from __future__ import annotations

import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama-service:11434/v1")
# The management API lives on port 11434 (without /v1 suffix)
_OLLAMA_MGMT_URL = OLLAMA_BASE_URL.replace("/v1", "").replace(":11434/v1", ":11434")

# ---------------------------------------------------------------------------
# Ollama model catalog — curated list users can browse and pull
# ---------------------------------------------------------------------------

OLLAMA_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "llama3.2",
        "display_name": "Llama 3.2 (3B)",
        "size": "2.0 GB",
        "description": "Meta's compact everyday model. Fast responses, great reasoning for its size.",
        "tags": ["chat", "fast", "popular"],
    },
    {
        "name": "llama3.2:1b",
        "display_name": "Llama 3.2 (1B)",
        "size": "1.3 GB",
        "description": "Ultra-lightweight Llama model. Ideal for low-RAM environments.",
        "tags": ["chat", "tiny", "fast"],
    },
    {
        "name": "llama3.1",
        "display_name": "Llama 3.1 (8B)",
        "size": "4.7 GB",
        "description": "Strong general-purpose model with 128K context window.",
        "tags": ["chat", "general", "large-context"],
    },
    {
        "name": "mistral",
        "display_name": "Mistral 7B",
        "size": "4.1 GB",
        "description": "Mistral AI's flagship open model. Excellent instruction following.",
        "tags": ["chat", "instruction"],
    },
    {
        "name": "gemma2",
        "display_name": "Gemma 2 (9B)",
        "size": "5.5 GB",
        "description": "Google's open model, optimised for dialogue and text tasks.",
        "tags": ["chat", "google"],
    },
    {
        "name": "gemma2:2b",
        "display_name": "Gemma 2 (2B)",
        "size": "1.6 GB",
        "description": "Lightweight Gemma for resource-constrained deployments.",
        "tags": ["chat", "tiny", "google"],
    },
    {
        "name": "phi3",
        "display_name": "Phi-3 Mini (3.8B)",
        "size": "2.2 GB",
        "description": "Microsoft's small but surprisingly capable phi model.",
        "tags": ["chat", "microsoft", "fast"],
    },
    {
        "name": "phi3.5",
        "display_name": "Phi-3.5 Mini (3.8B)",
        "size": "2.2 GB",
        "description": "Updated phi model with improved reasoning and multi-lingual support.",
        "tags": ["chat", "microsoft", "multilingual"],
    },
    {
        "name": "codellama",
        "display_name": "Code Llama (7B)",
        "size": "3.8 GB",
        "description": "Meta's code-specialised model. Best for programming benchmarks.",
        "tags": ["code", "programming"],
    },
    {
        "name": "deepseek-r1",
        "display_name": "DeepSeek R1 (7B)",
        "size": "4.7 GB",
        "description": "DeepSeek's reasoning model, strong at maths and logical tasks.",
        "tags": ["reasoning", "maths", "popular"],
    },
    {
        "name": "qwen2.5",
        "display_name": "Qwen 2.5 (7B)",
        "size": "4.4 GB",
        "description": "Alibaba's multilingual model, particularly strong on Chinese/English tasks.",
        "tags": ["chat", "multilingual", "alibaba"],
    },
    {
        "name": "nomic-embed-text",
        "display_name": "Nomic Embed Text",
        "size": "274 MB",
        "description": "Embedding model for semantic search and RAG pipelines.",
        "tags": ["embedding", "rag", "tiny"],
    },
]

# ---------------------------------------------------------------------------
# Cloud provider catalog
# ---------------------------------------------------------------------------

CLOUD_PROVIDERS: Dict[str, Any] = {
    "openai": {
        "name": "OpenAI",
        "icon": "openai",
        "key_env": "OPENAI_API_KEY",
        "base_url": None,           # uses official openai endpoint
        "live_fetch": True,         # can fetch model list from /v1/models
        "models": [
            {"id": "gpt-4o",            "name": "GPT-4o",              "context": "128K", "cost_per_1m_output": 15.0},
            {"id": "gpt-4o-mini",       "name": "GPT-4o Mini",         "context": "128K", "cost_per_1m_output": 0.60},
            {"id": "gpt-4-turbo",       "name": "GPT-4 Turbo",         "context": "128K", "cost_per_1m_output": 30.0},
            {"id": "gpt-3.5-turbo",     "name": "GPT-3.5 Turbo",       "context": "16K",  "cost_per_1m_output": 2.0},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "icon": "anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "base_url": None,           # uses anthropic SDK
        "live_fetch": False,
        "models": [
            {"id": "claude-opus-4-5",              "name": "Claude Opus 4.5",       "context": "200K", "cost_per_1m_output": 75.0},
            {"id": "claude-sonnet-4-5",            "name": "Claude Sonnet 4.5",     "context": "200K", "cost_per_1m_output": 15.0},
            {"id": "claude-haiku-4-5-20251001",    "name": "Claude Haiku 4.5",      "context": "200K", "cost_per_1m_output": 1.25},
            {"id": "claude-3-5-sonnet-20241022",   "name": "Claude 3.5 Sonnet",     "context": "200K", "cost_per_1m_output": 15.0},
            {"id": "claude-3-opus-20240229",       "name": "Claude 3 Opus",         "context": "200K", "cost_per_1m_output": 75.0},
            {"id": "claude-3-haiku-20240307",      "name": "Claude 3 Haiku",        "context": "200K", "cost_per_1m_output": 1.25},
        ],
    },
    "google": {
        "name": "Google AI (Gemini)",
        "icon": "google",
        "key_env": "GOOGLE_API_KEY",
        # Google exposes an OpenAI-compatible endpoint
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "live_fetch": False,
        "models": [
            {"id": "gemini-2.0-flash-exp",  "name": "Gemini 2.0 Flash",    "context": "1M",   "cost_per_1m_output": 0.0},
            {"id": "gemini-1.5-pro",        "name": "Gemini 1.5 Pro",       "context": "1M",   "cost_per_1m_output": 10.5},
            {"id": "gemini-1.5-flash",      "name": "Gemini 1.5 Flash",     "context": "1M",   "cost_per_1m_output": 0.30},
            {"id": "gemini-1.5-flash-8b",   "name": "Gemini 1.5 Flash-8B",  "context": "1M",   "cost_per_1m_output": 0.075},
        ],
    },
    "groq": {
        "name": "Groq (Ultra-fast)",
        "icon": "groq",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "live_fetch": False,
        "models": [
            {"id": "llama-3.3-70b-versatile",   "name": "Llama 3.3 70B",     "context": "128K", "cost_per_1m_output": 0.89},
            {"id": "llama-3.1-8b-instant",      "name": "Llama 3.1 8B",      "context": "128K", "cost_per_1m_output": 0.08},
            {"id": "mixtral-8x7b-32768",         "name": "Mixtral 8x7B",      "context": "32K",  "cost_per_1m_output": 0.27},
            {"id": "gemma2-9b-it",              "name": "Gemma 2 9B",         "context": "8K",   "cost_per_1m_output": 0.20},
        ],
    },
}

# Cost per word estimates for benchmark recording (derived from per-1M-token rates)
COST_PER_WORD: Dict[str, float] = {
    "gpt-4o":                       0.000020,
    "gpt-4o-mini":                  0.000001,
    "gpt-4-turbo":                  0.000040,
    "gpt-3.5-turbo":                0.000003,
    "claude-opus-4-5":              0.000100,
    "claude-sonnet-4-5":            0.000020,
    "claude-haiku-4-5-20251001":    0.000002,
    "claude-3-5-sonnet-20241022":   0.000020,
    "claude-3-opus-20240229":       0.000100,
    "claude-3-haiku-20240307":      0.000002,
    "gemini-2.0-flash-exp":         0.0,
    "gemini-1.5-pro":               0.000014,
    "gemini-1.5-flash":             0.0000004,
    "llama-3.3-70b-versatile":      0.000001,
    "llama-3.1-8b-instant":         0.0000001,
    "mixtral-8x7b-32768":           0.0000004,
}


def cost_per_word(model_id: str, provider: str) -> float:
    """Return estimated USD cost per word for a given model."""
    if provider == "local":
        return 0.0
    return COST_PER_WORD.get(model_id, 0.00003)


# ---------------------------------------------------------------------------
# Ollama management API client
# ---------------------------------------------------------------------------

class OllamaModelManager:
    """Thin async wrapper around the Ollama management REST API."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self._base = (base_url or _OLLAMA_MGMT_URL).rstrip("/")

    async def list_installed(self) -> List[Dict[str, Any]]:
        """Return models currently downloaded in the Ollama container."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = data.get("models", [])
                return [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                        "modified_at": m.get("modified_at"),
                        "details": m.get("details", {}),
                    }
                    for m in models
                ]
        except Exception as exc:
            logger.warning("Could not reach Ollama API: %s", exc)
            return []

    async def pull_model(self, model_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream pull progress events from Ollama.

        Yields dicts with keys: status, percent, size_downloaded, size_total, error
        """
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._base}/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        import json as _json
                        try:
                            event = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue

                        status = event.get("status", "")
                        total = event.get("total", 0)
                        completed = event.get("completed", 0)
                        percent = int((completed / total * 100)) if total else 0

                        if "error" in event:
                            yield {"status": "error", "error": event["error"], "percent": 0}
                            return

                        yield {
                            "status": status,
                            "percent": percent,
                            "size_downloaded": round(completed / 1e9, 2) if completed else 0,
                            "size_total": round(total / 1e9, 2) if total else 0,
                        }

                        if status == "success":
                            yield {"status": "success", "percent": 100}
                            return
        except Exception as exc:
            logger.error("Ollama pull failed for %s: %s", model_name, exc)
            yield {"status": "error", "error": str(exc), "percent": 0}

    async def delete_model(self, model_name: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    "DELETE", f"{self._base}/api/delete", json={"name": model_name}
                )
                return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error("Ollama delete failed for %s: %s", model_name, exc)
            return False
