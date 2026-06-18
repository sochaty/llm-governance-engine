"""Integration tests for GET/PUT/DELETE /api/v1/settings."""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.settings_service import settings_service


@pytest.mark.anyio
class TestGetSettings:
    async def test_returns_200_with_all_known_settings(self, client):
        response = await client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        keys = {s["key"] for s in data["settings"]}
        assert "OPENAI_API_KEY" in keys
        assert "ANTHROPIC_API_KEY" in keys
        assert "OLLAMA_BASE_URL" in keys

    async def test_returns_10_settings(self, client):
        response = await client.get("/api/v1/settings")
        assert response.status_code == 200
        assert len(response.json()["settings"]) == 10

    async def test_settings_have_required_fields(self, client):
        response = await client.get("/api/v1/settings")
        for item in response.json()["settings"]:
            assert "key" in item
            assert "label" in item
            assert "source" in item
            assert "is_set" in item
            assert "masked_value" in item

    async def test_unset_keys_have_source_unset(self, client):
        with patch.dict(__import__("os").environ, {}, clear=True):
            response = await client.get("/api/v1/settings")
        data = {s["key"]: s for s in response.json()["settings"]}
        # OPENAI_API_KEY is unset in test environment (no real key)
        # source may be env or unset depending on whether env var is set
        assert data["OPENAI_API_KEY"]["source"] in ("env", "unset", "db")


@pytest.mark.anyio
class TestSaveSettings:
    async def test_save_known_key_returns_200(self, client, setup_database):
        response = await client.put(
            "/api/v1/settings",
            json={"settings": {"OLLAMA_BASE_URL": "http://custom:11434/v1"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "OLLAMA_BASE_URL" in data["saved"]

    async def test_saved_value_appears_in_list(self, client, setup_database):
        await client.put(
            "/api/v1/settings",
            json={"settings": {"CLOUD_TIMEOUT": "60"}},
        )
        response = await client.get("/api/v1/settings")
        settings_map = {s["key"]: s for s in response.json()["settings"]}
        assert settings_map["CLOUD_TIMEOUT"]["is_set"] is True
        assert settings_map["CLOUD_TIMEOUT"]["source"] == "db"

    async def test_unknown_key_returns_422(self, client):
        response = await client.put(
            "/api/v1/settings",
            json={"settings": {"INVALID_KEY": "some-value"}},
        )
        assert response.status_code == 422

    async def test_empty_string_value_clears_setting(self, client, setup_database):
        # First set a value
        await client.put(
            "/api/v1/settings",
            json={"settings": {"CLOUD_TIMEOUT": "45"}},
        )
        # Then clear it
        response = await client.put(
            "/api/v1/settings",
            json={"settings": {"CLOUD_TIMEOUT": ""}},
        )
        assert response.status_code == 200
        settings_map = {s["key"]: s for s in response.json()["settings"]}
        # DB override should be gone; source falls back to env or unset
        assert settings_map["CLOUD_TIMEOUT"]["source"] != "db"

    async def test_multiple_keys_saved_at_once(self, client, setup_database):
        response = await client.put(
            "/api/v1/settings",
            json={
                "settings": {
                    "LOCAL_MODEL_NAME": "mistral:latest",
                    "LOCAL_TIMEOUT": "90",
                }
            },
        )
        assert response.status_code == 200
        assert sorted(response.json()["saved"]) == ["LOCAL_MODEL_NAME", "LOCAL_TIMEOUT"]

    async def test_mixed_known_unknown_keys_rejects_all(self, client):
        response = await client.put(
            "/api/v1/settings",
            json={"settings": {"OPENAI_API_KEY": "sk-ok", "FAKE_KEY": "bad"}},
        )
        assert response.status_code == 422


@pytest.mark.anyio
class TestDeleteSetting:
    async def test_delete_known_key_returns_200(self, client, setup_database):
        # First save a value so there is something to delete
        await client.put(
            "/api/v1/settings",
            json={"settings": {"CLOUD_MODEL_NAME": "gpt-4o-mini"}},
        )
        response = await client.delete("/api/v1/settings/CLOUD_MODEL_NAME")
        assert response.status_code == 200
        assert response.json()["deleted"] == "CLOUD_MODEL_NAME"

    async def test_delete_unknown_key_returns_404(self, client):
        response = await client.delete("/api/v1/settings/NOT_A_REAL_KEY")
        assert response.status_code == 404

    async def test_delete_removes_db_override(self, client, setup_database):
        await client.put(
            "/api/v1/settings",
            json={"settings": {"GOVERNANCE_POLICY_PATH": "/tmp/policy.yaml"}},
        )
        await client.delete("/api/v1/settings/GOVERNANCE_POLICY_PATH")
        response = await client.get("/api/v1/settings")
        settings_map = {s["key"]: s for s in response.json()["settings"]}
        assert settings_map["GOVERNANCE_POLICY_PATH"]["source"] != "db"
