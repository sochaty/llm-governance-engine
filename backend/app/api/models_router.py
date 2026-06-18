"""REST endpoints for model discovery and Ollama model management."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.model_registry import (
    CLOUD_PROVIDERS,
    OLLAMA_CATALOG,
    OllamaModelManager,
)

router = APIRouter(prefix="/models", tags=["models"])
_ollama = OllamaModelManager()


# ---------------------------------------------------------------------------
# Local (Ollama) endpoints
# ---------------------------------------------------------------------------

@router.get("/local")
async def list_installed_models():
    """List models currently downloaded inside the Ollama container."""
    models = await _ollama.list_installed()
    return {"models": models, "count": len(models)}


@router.get("/local/catalog")
def list_model_catalog():
    """Return the curated list of Ollama models available to pull."""
    return {"models": OLLAMA_CATALOG, "count": len(OLLAMA_CATALOG)}


@router.post("/local/pull")
async def pull_model(model_name: str = Query(..., description="e.g. llama3.2 or mistral")):
    """Pull an Ollama model from the registry. Streams progress as SSE."""

    async def _event_stream():
        async for event in _ollama.pull_model(model_name):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: {\"status\": \"done\"}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.delete("/local/{model_name:path}")
async def delete_model(model_name: str):
    """Delete a downloaded Ollama model to free disk space."""
    ok = await _ollama.delete_model(model_name)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to delete {model_name}")
    return {"deleted": model_name}


# ---------------------------------------------------------------------------
# Cloud provider endpoints
# ---------------------------------------------------------------------------

@router.get("/cloud")
def list_cloud_providers():
    """Return all supported cloud providers with their model lists."""
    providers = []
    for provider_id, cfg in CLOUD_PROVIDERS.items():
        import os
        key_set = bool(os.getenv(cfg["key_env"]))
        providers.append(
            {
                "id": provider_id,
                "name": cfg["name"],
                "icon": cfg["icon"],
                "key_env": cfg["key_env"],
                "key_configured": key_set,
                "models": cfg["models"],
            }
        )
    return {"providers": providers}


@router.get("/cloud/{provider_id}")
async def get_provider_models(provider_id: str):
    """Return models for a specific cloud provider.

    For OpenAI, fetches live from the API if the key is configured.
    For others, returns the curated catalog.
    """
    import os

    cfg = CLOUD_PROVIDERS.get(provider_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    api_key = os.getenv(cfg["key_env"])
    models = list(cfg["models"])  # start with curated list

    if provider_id == "openai" and api_key and cfg.get("live_fetch"):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            live = await client.models.list()
            chat_models = [
                m for m in live.data
                if any(m.id.startswith(p) for p in ("gpt-4", "gpt-3.5", "o1", "o3"))
            ]
            chat_models.sort(key=lambda m: m.created, reverse=True)
            # Merge live list with our curated metadata
            curated_ids = {m["id"] for m in cfg["models"]}
            extra = [
                {"id": m.id, "name": m.id, "context": "N/A", "cost_per_1m_output": None}
                for m in chat_models
                if m.id not in curated_ids
            ]
            models = cfg["models"] + extra
        except Exception as exc:
            # Fall back to curated list silently
            import logging
            logging.getLogger(__name__).warning("OpenAI live fetch failed: %s", exc)

    return {
        "provider_id": provider_id,
        "name": cfg["name"],
        "key_configured": bool(api_key),
        "models": models,
    }
