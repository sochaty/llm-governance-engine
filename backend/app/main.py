import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.benchmark_router import router as benchmark_router
from app.api.governance_router import router as governance_router
from app.api.models_router import router as models_router
from app.api.settings_router import router as settings_router
from app.core.database import Base, engine, get_db
from app.models.app_setting import AppSetting  # noqa: F401 — registers table
from app.models.benchmark import BenchmarkResult  # noqa: F401 — registers table
from app.models.policy_violation import PolicyViolation  # noqa: F401 — registers table
from app.services.settings_service import settings_service

load_dotenv(override=True)


async def _wait_for_db(retries: int = 10, delay: float = 3.0) -> None:
    """Retry DB connection with backoff — handles transient Docker DNS delays."""
    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database ready after %d attempt(s).", attempt)
            return
        except Exception as exc:
            if attempt == retries:
                raise
            logger.warning("DB not ready (attempt %d/%d): %s — retrying in %.0fs…", attempt, retries, exc, delay)
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _wait_for_db()
    async for db in get_db():
        await settings_service.initialize(db)
        break
    yield


app = FastAPI(title="LLM Governance Engine API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(benchmark_router, prefix="/api")
app.include_router(governance_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}
