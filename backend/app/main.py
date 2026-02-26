import os
import sys

from sqlalchemy import func, select
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import get_db,engine
from app.models.benchmark import Base, BenchmarkResult
from .services.llm_orchestrator import LLMOrchestrator

# Enable Load environment variables from .env file for local development
from dotenv import load_dotenv

load_dotenv(override=True) 
# Note: In production, environment variables should be set securely and not stored in .env files.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This block runs when the app starts
    async with engine.begin() as conn:
        # run_sync is required because create_all is not natively async
        await conn.run_sync(Base.metadata.create_all)
    yield
    # This block runs when the app shuts down (clean up if needed)
    
app = FastAPI(title="LLM Governance Engine API", lifespan=lifespan)
orchestrator = LLMOrchestrator()

api_router = APIRouter(prefix="/api")

# Enable CORS for Angular (Port 4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection
def get_orchestrator():
    return LLMOrchestrator()

@api_router.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@api_router.get("/benchmark/stream")
async def stream_llm(
    prompt: str = Query(..., min_length=1),
    provider: str = Query("cloud", regex="^(cloud|local)$"),
    # orchestrator: LLMOrchestrator = Depends(get_orchestrator)
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint that streams tokens back to the client.
    """
    return StreamingResponse(
        orchestrator.run_and_record_benchmark(db, prompt, provider),
        media_type="text/event-stream"
    )

# 2. Add the History and Stats logic directly or import from endpoints.py
@api_router.get("/benchmark/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    query = select(BenchmarkResult).order_by(BenchmarkResult.created_at.desc()).limit(50)
    result = await db.execute(query)
    return result.scalars().all()

@api_router.get("/benchmark/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    query_savings = select(func.sum(BenchmarkResult.estimated_cost)).where(BenchmarkResult.provider == 'local')
    query_cloud_lat = select(func.avg(BenchmarkResult.latency_ms)).where(BenchmarkResult.provider == 'cloud')
    query_local_lat = select(func.avg(BenchmarkResult.latency_ms)).where(BenchmarkResult.provider == 'local')

    savings = (await db.execute(query_savings)).scalar() or 0.0
    avg_cloud = (await db.execute(query_cloud_lat)).scalar() or 0.0
    avg_local = (await db.execute(query_local_lat)).scalar() or 0.0

    return {
        "total_savings": round(savings, 4),
        "avg_cloud_latency": int(avg_cloud),
        "avg_local_latency": int(avg_local),
        "total_requests": (await db.execute(select(func.count(BenchmarkResult.id)))).scalar()
    }

# 3. Mount the router to the app
app.include_router(api_router)