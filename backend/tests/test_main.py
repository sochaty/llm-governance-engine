import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from app.main import app

@pytest.mark.anyio
class TestMainAPI:
    
    # --- 1. Basic Health Check ---
    async def test_health_check(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    # --- 2. Benchmark Streaming (Validation) ---
    async def test_stream_llm_validation_error(self, client):
        """Test that missing prompt returns 422 Unprocessable Entity."""
        response = await client.get("/api/benchmark/stream") # No prompt param
        assert response.status_code == 422

    async def test_stream_llm_invalid_provider(self, client):
        """Test that invalid provider regex/pattern triggers 422."""
        params = {"prompt": "test", "provider": "invalid-ai"}
        response = await client.get("/api/benchmark/stream", params=params)
        assert response.status_code == 422

    # --- 3. History & Stats (Database Routes) ---
    async def test_get_history(self, client):
        """Ensures history returns a list (even if empty)."""
        response = await client.get("/api/benchmark/history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_stats(self, client):
        """Ensures stats returns the correct dictionary structure."""
        response = await client.get("/api/benchmark/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_savings" in data
        assert "avg_cloud_latency" in data
        assert "total_requests" in data
        assert isinstance(data["total_requests"], int)

    # --- 4. 404 Error Handling ---
    async def test_not_found(self, client):
        """Verify that hitting the old non-prefixed route returns 404."""
        response = await client.get("/health") # Missing /api
        assert response.status_code == 404