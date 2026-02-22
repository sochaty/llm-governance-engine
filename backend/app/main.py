import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import get_db,engine
from app.models.benchmark import Base
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

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/benchmark/stream")
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