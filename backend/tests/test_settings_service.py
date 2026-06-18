"""Unit tests for SettingsService — encryption, cache, DB persistence."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.settings_service import (
    SettingsService,
    _encrypt,
    _decrypt,
    _mask,
    KNOWN_SETTINGS,
)


# ── Pure function tests (no DB, no fixtures) ──────────────────────────────────

class TestMask:
    def test_short_value_returns_stars(self):
        assert _mask("abc") == "****"

    def test_exactly_8_chars_returns_stars(self):
        assert _mask("12345678") == "****"

    def test_long_value_shows_last_four(self):
        result = _mask("sk-proj-ABCDEFGH")
        assert result == "****EFGH"

    def test_9_chars_shows_last_four(self):
        assert _mask("123456789") == "****6789"


class TestEncryptDecrypt:
    def test_roundtrip_with_key(self):
        key = "Is40iNSUzYJ4Pv8rojzzZBHOCVpToE6gdkNV4Z5vMHk="
        with patch.dict(os.environ, {"SETTINGS_SECRET_KEY": key}):
            encrypted = _encrypt("my-secret")
            assert encrypted != "my-secret"
            assert _decrypt(encrypted) == "my-secret"

    def test_no_key_stores_plaintext(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SETTINGS_SECRET_KEY", None)
            assert _encrypt("plaintext") == "plaintext"
            assert _decrypt("plaintext") == "plaintext"

    def test_decrypt_non_fernet_token_returns_original(self):
        """When Fernet is active but the token is plain (stored before encryption was on)."""
        key = "Is40iNSUzYJ4Pv8rojzzZBHOCVpToE6gdkNV4Z5vMHk="
        with patch.dict(os.environ, {"SETTINGS_SECRET_KEY": key}):
            # A plain string that is not a valid Fernet token should be returned as-is
            assert _decrypt("not-a-fernet-token") == "not-a-fernet-token"


# ── SettingsService unit tests (mocked DB) ────────────────────────────────────

@pytest.mark.anyio
class TestSettingsServiceGet:
    def test_get_returns_cache_value(self):
        svc = SettingsService()
        svc._cache["OPENAI_API_KEY"] = "cached-key"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            assert svc.get("OPENAI_API_KEY") == "cached-key"

    def test_get_falls_back_to_env_when_cache_empty(self):
        svc = SettingsService()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            assert svc.get("OPENAI_API_KEY") == "env-key"

    def test_get_returns_fallback_when_nothing_set(self):
        svc = SettingsService()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MISSING_KEY", None)
            result = svc.get("MISSING_KEY", "default-value")
            assert result == "default-value"

    def test_get_returns_none_without_fallback(self):
        svc = SettingsService()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MISSING_KEY", None)
            assert svc.get("MISSING_KEY") is None

    def test_cache_takes_priority_over_env(self):
        svc = SettingsService()
        svc._cache["GROQ_API_KEY"] = "db-value"
        with patch.dict(os.environ, {"GROQ_API_KEY": "env-value"}):
            assert svc.get("GROQ_API_KEY") == "db-value"


@pytest.mark.anyio
class TestSettingsServiceSaveDelete:
    async def test_save_updates_cache_immediately(self):
        svc = SettingsService()
        db = AsyncMock()
        db.get.return_value = None  # no existing row

        await svc.save("OPENAI_API_KEY", "sk-test-123", db)

        assert svc._cache["OPENAI_API_KEY"] == "sk-test-123"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_save_updates_existing_row(self):
        svc = SettingsService()
        db = AsyncMock()
        existing_row = MagicMock()
        db.get.return_value = existing_row

        await svc.save("OPENAI_API_KEY", "new-key", db)

        # Should update in place, not add a new row
        db.add.assert_not_called()
        assert existing_row.encrypted_value is not None
        db.commit.assert_called_once()

    async def test_delete_removes_from_cache(self):
        svc = SettingsService()
        svc._cache["GROQ_API_KEY"] = "cached"
        db = AsyncMock()
        db.get.return_value = MagicMock()

        await svc.delete("GROQ_API_KEY", db)

        assert "GROQ_API_KEY" not in svc._cache
        db.commit.assert_called_once()

    async def test_delete_nonexistent_key_is_noop(self):
        svc = SettingsService()
        db = AsyncMock()
        db.get.return_value = None  # no row in DB

        await svc.delete("MISSING_KEY", db)

        db.commit.assert_not_called()

    async def test_initialize_loads_decrypted_values_into_cache(self):
        svc = SettingsService()
        db = AsyncMock()

        # Simulate two rows returned from the DB (stored as plaintext since no key)
        row1 = MagicMock()
        row1.key = "OPENAI_API_KEY"
        row1.encrypted_value = "sk-plain-value"

        row2 = MagicMock()
        row2.key = "GROQ_API_KEY"
        row2.encrypted_value = "gsk-plain"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [row1, row2]
        db.execute.return_value = mock_result

        await svc.initialize(db)

        assert svc._cache["OPENAI_API_KEY"] == "sk-plain-value"
        assert svc._cache["GROQ_API_KEY"] == "gsk-plain"
        assert svc._initialized is True


@pytest.mark.anyio
class TestSettingsServiceListForUI:
    def test_list_for_ui_returns_all_known_keys(self):
        svc = SettingsService()
        result = svc.list_for_ui()
        keys = {item["key"] for item in result}
        assert {s["key"] for s in KNOWN_SETTINGS} == keys

    def test_source_is_db_when_cache_has_value(self):
        svc = SettingsService()
        svc._cache["OPENAI_API_KEY"] = "sk-cached"
        result = {item["key"]: item for item in svc.list_for_ui()}
        assert result["OPENAI_API_KEY"]["source"] == "db"
        assert result["OPENAI_API_KEY"]["is_set"] is True

    def test_source_is_env_when_only_env_set(self):
        svc = SettingsService()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}):
            result = {item["key"]: item for item in svc.list_for_ui()}
        assert result["ANTHROPIC_API_KEY"]["source"] == "env"

    def test_source_is_unset_when_nothing_configured(self):
        svc = SettingsService()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GOOGLE_API_KEY", None)
            result = {item["key"]: item for item in svc.list_for_ui()}
        assert result["GOOGLE_API_KEY"]["source"] == "unset"
        assert result["GOOGLE_API_KEY"]["is_set"] is False

    def test_sensitive_values_are_masked(self):
        svc = SettingsService()
        svc._cache["OPENAI_API_KEY"] = "sk-proj-ABCDEFGHIJKL"
        result = {item["key"]: item for item in svc.list_for_ui()}
        masked = result["OPENAI_API_KEY"]["masked_value"]
        assert masked.startswith("****")
        assert "sk-proj" not in masked

    def test_non_sensitive_values_are_not_masked(self):
        svc = SettingsService()
        svc._cache["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"
        result = {item["key"]: item for item in svc.list_for_ui()}
        assert result["OLLAMA_BASE_URL"]["masked_value"] == "http://localhost:11434/v1"

    def test_empty_sensitive_value_is_empty_string(self):
        svc = SettingsService()
        result = {item["key"]: item for item in svc.list_for_ui()}
        # When unset, masked_value for sensitive key should be empty string
        assert result["OPENAI_API_KEY"]["masked_value"] == ""
