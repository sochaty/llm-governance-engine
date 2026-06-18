"""Integration tests for the models router (/api/v1/models/*)."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.model_registry import CLOUD_PROVIDERS, OLLAMA_CATALOG, OllamaModelManager


# ── OllamaModelManager unit tests ─────────────────────────────────────────────

@pytest.mark.anyio
class TestOllamaModelManager:
    async def test_list_installed_returns_empty_when_ollama_unreachable(self):
        mgr = OllamaModelManager(base_url="http://localhost:19999")
        result = await mgr.list_installed()
        assert result == []

    async def test_list_installed_parses_response(self):
        mgr = OllamaModelManager()
        fake_response = {
            "models": [
                {"name": "llama3.2:latest", "size": 2_000_000_000, "modified_at": "2025-01-01", "details": {}},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = await mgr.list_installed()

        assert len(result) == 1
        assert result[0]["name"] == "llama3.2:latest"
        assert result[0]["size_gb"] == 2.0

    async def test_delete_model_returns_true_on_success(self):
        mgr = OllamaModelManager()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = await mgr.delete_model("llama3.2:latest")

        assert result is True

    async def test_delete_model_returns_false_when_unreachable(self):
        mgr = OllamaModelManager(base_url="http://localhost:19999")
        result = await mgr.delete_model("llama3.2:latest")
        assert result is False

    async def test_pull_model_yields_error_on_connection_failure(self):
        mgr = OllamaModelManager(base_url="http://localhost:19999")
        events = [e async for e in mgr.pull_model("nonexistent")]
        assert len(events) >= 1
        assert events[-1]["status"] == "error"

    async def test_pull_model_streams_sse_events(self):
        """Mock the httpx streaming client to exercise the SSE parsing loop."""
        mgr = OllamaModelManager()

        # Simulate three SSE lines: progress, blank (skipped), invalid JSON (skipped), success
        sse_lines = [
            json.dumps({"status": "downloading", "total": 1_000_000_000, "completed": 500_000_000}),
            "",                    # blank line — should be skipped
            "not-json-at-all",     # invalid JSON — should be skipped
            json.dumps({"status": "success", "total": 1_000_000_000, "completed": 1_000_000_000}),
        ]

        async def aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            events = [e async for e in mgr.pull_model("llama3.2")]

        # Should yield: downloading progress + success (blank/invalid lines skipped)
        assert len(events) >= 2
        statuses = [e["status"] for e in events]
        assert "downloading" in statuses
        assert "success" in statuses

    async def test_pull_model_yields_error_event_on_ollama_error(self):
        """If Ollama returns an error field in the SSE stream, it should be surfaced."""
        mgr = OllamaModelManager()

        sse_lines = [
            json.dumps({"error": "model not found: badmodel:latest"}),
        ]

        async def aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            events = [e async for e in mgr.pull_model("badmodel:latest")]

        assert events[0]["status"] == "error"
        assert "model not found" in events[0]["error"]


# ── cost_per_word unit tests ───────────────────────────────────────────────────

class TestCostPerWord:
    def test_local_provider_always_zero(self):
        from app.services.model_registry import cost_per_word
        assert cost_per_word("gpt-4o", "local") == 0.0
        assert cost_per_word("llama3.2", "local") == 0.0

    def test_known_cloud_model_returns_nonzero(self):
        from app.services.model_registry import cost_per_word
        assert cost_per_word("gpt-4o", "cloud") > 0.0

    def test_unknown_model_returns_default(self):
        from app.services.model_registry import cost_per_word
        result = cost_per_word("unknown-model-xyz", "cloud")
        assert result == 0.00003


# ── Cloud endpoints ────────────────────────────────────────────────────────────

@pytest.mark.anyio
class TestCloudProviderEndpoints:
    async def test_list_cloud_providers_returns_all(self, client):
        response = await client.get("/api/v1/models/cloud")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        provider_ids = {p["id"] for p in data["providers"]}
        assert provider_ids == {"openai", "anthropic", "google", "groq"}

    async def test_each_provider_has_required_fields(self, client):
        response = await client.get("/api/v1/models/cloud")
        for provider in response.json()["providers"]:
            assert "id" in provider
            assert "name" in provider
            assert "key_configured" in provider
            assert "models" in provider

    async def test_key_configured_false_without_env(self, client):
        import os
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
            os.environ.pop(key, None)
        response = await client.get("/api/v1/models/cloud")
        for provider in response.json()["providers"]:
            assert provider["key_configured"] is False

    async def test_get_known_provider_returns_200(self, client):
        response = await client.get("/api/v1/models/cloud/anthropic")
        assert response.status_code == 200
        data = response.json()
        assert data["provider_id"] == "anthropic"
        assert len(data["models"]) > 0

    async def test_get_unknown_provider_returns_404(self, client):
        response = await client.get("/api/v1/models/cloud/nonexistent")
        assert response.status_code == 404

    async def test_get_anthropic_returns_curated_models(self, client):
        response = await client.get("/api/v1/models/cloud/anthropic")
        model_ids = {m["id"] for m in response.json()["models"]}
        assert "claude-sonnet-4-5" in model_ids

    async def test_get_openai_falls_back_to_curated_without_key(self, client):
        import os
        os.environ.pop("OPENAI_API_KEY", None)
        response = await client.get("/api/v1/models/cloud/openai")
        assert response.status_code == 200
        # Should return curated list without hitting the live API
        model_ids = {m["id"] for m in response.json()["models"]}
        assert "gpt-4o" in model_ids


# ── Local/Ollama endpoints ────────────────────────────────────────────────────

@pytest.mark.anyio
class TestLocalModelEndpoints:
    async def test_catalog_returns_all_entries(self, client):
        response = await client.get("/api/v1/models/local/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == len(OLLAMA_CATALOG)
        assert data["count"] == 12

    async def test_catalog_entries_have_required_fields(self, client):
        response = await client.get("/api/v1/models/local/catalog")
        for model in response.json()["models"]:
            assert "name" in model
            assert "display_name" in model
            assert "size" in model
            assert "description" in model

    async def test_list_installed_returns_empty_when_ollama_down(self, client):
        with patch.object(OllamaModelManager, "list_installed", return_value=[]) as mock_list:
            # monkeypatch doesn't work on the module-level instance; patch the method
            from app.api import models_router as mr
            with patch.object(mr._ollama, "list_installed", new=AsyncMock(return_value=[])):
                response = await client.get("/api/v1/models/local")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
        assert data["count"] == 0

    async def test_list_installed_returns_models_when_ollama_up(self, client):
        fake_models = [{"name": "llama3.2:latest", "size_gb": 2.0, "modified_at": None, "details": {}}]
        from app.api import models_router as mr
        with patch.object(mr._ollama, "list_installed", new=AsyncMock(return_value=fake_models)):
            response = await client.get("/api/v1/models/local")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    async def test_delete_model_returns_500_when_ollama_fails(self, client):
        from app.api import models_router as mr
        with patch.object(mr._ollama, "delete_model", new=AsyncMock(return_value=False)):
            response = await client.delete("/api/v1/models/local/some-model")
        assert response.status_code == 500
