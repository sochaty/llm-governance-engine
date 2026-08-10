from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.governance.policy.enforcement import enforce_governance_policy
from app.governance.policy.schema import PolicyVerdict
from app.models.benchmark import BenchmarkResult
from app.schemas.benchmark import BenchmarkRequest
from app.services.llm_orchestrator import LLMOrchestrator

router = APIRouter(prefix="/benchmark", tags=["benchmark"])

_orchestrator = LLMOrchestrator()


@router.post("/stream")
async def stream_llm(
    body: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
    verdict: PolicyVerdict = Depends(enforce_governance_policy),
):
    """Stream an LLM response after passing governance policy enforcement.

    `provider` (cloud|local) controls which policy rules apply.
    `provider_type` and `model_id` override which LLM is actually called.
    `context` is optional — when supplied, the response is scored for RAGAS
    faithfulness/context-utilization against it once streaming completes.

    POST + JSON body (rather than GET + query params) so `context` isn't
    subject to URL length limits.
    """
    return StreamingResponse(
        _orchestrator.run_and_record_benchmark(
            db, body.prompt, body.provider, body.provider_type, body.model_id, body.context
        ),
        media_type="text/event-stream",
    )


@router.get("/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    query = (
        select(BenchmarkResult)
        .order_by(BenchmarkResult.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    query_savings = select(func.sum(BenchmarkResult.estimated_cost)).where(
        BenchmarkResult.provider == "local"
    )
    query_cloud_lat = select(func.avg(BenchmarkResult.latency_ms)).where(
        BenchmarkResult.provider == "cloud"
    )
    query_local_lat = select(func.avg(BenchmarkResult.latency_ms)).where(
        BenchmarkResult.provider == "local"
    )

    savings = (await db.execute(query_savings)).scalar() or 0.0
    avg_cloud = (await db.execute(query_cloud_lat)).scalar() or 0.0
    avg_local = (await db.execute(query_local_lat)).scalar() or 0.0

    return {
        "total_savings": round(savings, 4),
        "avg_cloud_latency": int(avg_cloud),
        "avg_local_latency": int(avg_local),
        "total_requests": (
            await db.execute(select(func.count(BenchmarkResult.id)))
        ).scalar(),
    }
