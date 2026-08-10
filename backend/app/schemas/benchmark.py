from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BenchmarkRequest(BaseModel):
    """Request body for POST /benchmark/stream.

    Was previously GET query params — moved to a JSON body so an optional,
    potentially long `context` (retrieved RAG passages, for faithfulness
    scoring) isn't subject to URL length limits.
    """

    prompt: str = Field(..., min_length=1)
    provider: str = Field("cloud", pattern="^(cloud|local)$")
    provider_type: Optional[str] = Field(
        None, description="openai|anthropic|google|groq|ollama"
    )
    model_id: Optional[str] = Field(
        None, description="Model ID override, e.g. claude-sonnet-4-5"
    )
    context: Optional[str] = Field(
        None, description="Retrieved RAG passages to score the response's faithfulness against"
    )
