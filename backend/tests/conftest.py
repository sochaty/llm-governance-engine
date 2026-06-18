import os
import sys

# Set SQLite URL BEFORE any app import so database.py never tries to load asyncpg
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SETTINGS_SECRET_KEY", "")  # disable Fernet in unit tests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import AsyncClient, ASGITransport
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Single shared in-memory SQLite database for all tests in the session
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

# ── Import app modules then replace their engine references ──────────────────
import app.core.database as _db_module  # noqa: E402
import app.main as _main_module         # noqa: E402
from app.main import app                # noqa: E402
from app.core.database import get_db, Base  # noqa: E402
from app.services.settings_service import settings_service  # noqa: E402

# Replace real engine with the test engine in every namespace that holds it
_db_module.engine = test_engine
_db_module.AsyncSessionLocal = TestSessionLocal
_main_module.engine = test_engine   # used by _wait_for_db in lifespan


# get_db yielded in the lifespan and used by request handlers both end up here
async def _test_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _test_get_db
# Also redirect the name used directly in lifespan (not via DI)
_main_module.get_db = _test_get_db


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Reset the settings cache so tests are isolated
    settings_service._cache.clear()
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """HTTP test client that triggers the FastAPI lifespan."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
