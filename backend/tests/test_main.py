import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.main import app

@pytest.mark.anyio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}