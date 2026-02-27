import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from httpx import AsyncClient, ASGITransport
import pytest
import pytest_asyncio
from app.main import app
# Add these lines precisely:
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool # Required for in-memory SQLite
from app.core.database import get_db, Base

# 1. Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}, # Required for SQLite + FastAPI
    poolclass=StaticPool, 
)

TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    """Override for the FastAPI get_db dependency."""
    async with TestSessionLocal() as session:
        yield session

# 2. Tell FastAPI to use the override
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client():
    # This ensures the 'lifespan' (DB creation) runs before tests
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac