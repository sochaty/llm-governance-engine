"""Encrypted settings service.

Keys are stored in the `app_settings` table, encrypted with Fernet symmetric
encryption. The in-memory cache means the orchestrator can do a plain dict
lookup without hitting the DB on every request.

Priority order:
  1. DB value (if present and SETTINGS_SECRET_KEY is configured)
  2. Environment variable
  3. Provided fallback
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

# Human-readable metadata for the settings the UI cares about
KNOWN_SETTINGS = [
    {
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "section": "cloud",
        "provider": "openai",
        "sensitive": True,
    },
    {
        "key": "ANTHROPIC_API_KEY",
        "label": "Anthropic API Key",
        "section": "cloud",
        "provider": "anthropic",
        "sensitive": True,
    },
    {
        "key": "GOOGLE_API_KEY",
        "label": "Google AI API Key",
        "section": "cloud",
        "provider": "google",
        "sensitive": True,
    },
    {
        "key": "GROQ_API_KEY",
        "label": "Groq API Key",
        "section": "cloud",
        "provider": "groq",
        "sensitive": True,
    },
    {
        "key": "OLLAMA_BASE_URL",
        "label": "Ollama Base URL",
        "section": "local",
        "provider": None,
        "sensitive": False,
    },
    {
        "key": "GOVERNANCE_POLICY_PATH",
        "label": "Active Policy File",
        "section": "governance",
        "provider": None,
        "sensitive": False,
    },
    {
        "key": "CLOUD_MODEL_NAME",
        "label": "Default Cloud Model",
        "section": "models",
        "provider": None,
        "sensitive": False,
    },
    {
        "key": "LOCAL_MODEL_NAME",
        "label": "Default Local Model",
        "section": "models",
        "provider": None,
        "sensitive": False,
    },
    {
        "key": "CLOUD_TIMEOUT",
        "label": "Cloud Timeout (seconds)",
        "section": "models",
        "provider": None,
        "sensitive": False,
    },
    {
        "key": "LOCAL_TIMEOUT",
        "label": "Local Timeout (seconds)",
        "section": "models",
        "provider": None,
        "sensitive": False,
    },
]


def _get_fernet():
    """Return a Fernet instance or None if the secret key is missing."""
    secret = os.getenv("SETTINGS_SECRET_KEY", "")
    if not secret:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(secret.encode() if isinstance(secret, str) else secret)
    except Exception as exc:
        logger.warning("Invalid SETTINGS_SECRET_KEY: %s", exc)
        return None


def _encrypt(value: str) -> str:
    f = _get_fernet()
    if not f:
        return value
    return f.encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    f = _get_fernet()
    if not f:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        # Token may be a plain value stored before encryption was enabled
        return token


def _mask(value: str) -> str:
    """Return `****...XXXX` for sensitive values, or the plain value."""
    if len(value) <= 8:
        return "****"
    return "****" + value[-4:]


class SettingsService:
    """Singleton-style service — one instance per process, shared across requests."""

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._initialized = False

    async def initialize(self, db: AsyncSession) -> None:
        """Load all DB settings into the in-memory cache. Called once at startup."""
        rows = (await db.execute(select(AppSetting))).scalars().all()
        for row in rows:
            try:
                self._cache[row.key] = _decrypt(row.encrypted_value)
            except Exception as exc:
                logger.warning("Could not decrypt setting %s: %s", row.key, exc)
        self._initialized = True
        logger.info("Settings cache initialised with %d DB entries.", len(rows))

    def get(self, key: str, fallback: Optional[str] = None) -> Optional[str]:
        """Return value: DB cache → env var → fallback."""
        return self._cache.get(key) or os.getenv(key) or fallback

    async def save(self, key: str, value: str, db: AsyncSession) -> None:
        """Encrypt and persist a value; update the cache immediately."""
        encrypted = _encrypt(value)
        existing = await db.get(AppSetting, key)
        if existing:
            existing.encrypted_value = encrypted
        else:
            db.add(AppSetting(key=key, encrypted_value=encrypted))
        await db.commit()
        self._cache[key] = value
        logger.info("Setting saved: %s", key)

    async def delete(self, key: str, db: AsyncSession) -> None:
        """Remove a DB override; the env var becomes active again."""
        existing = await db.get(AppSetting, key)
        if existing:
            await db.delete(existing)
            await db.commit()
        self._cache.pop(key, None)

    def list_for_ui(self) -> List[dict]:
        """Return all known settings with current source and masked values."""
        result = []
        for meta in KNOWN_SETTINGS:
            key = meta["key"]
            db_value = self._cache.get(key)
            env_value = os.getenv(key)
            raw = db_value or env_value or ""
            result.append(
                {
                    **meta,
                    "source": "db" if db_value else ("env" if env_value else "unset"),
                    "is_set": bool(raw),
                    "masked_value": _mask(raw) if raw and meta["sensitive"] else raw,
                }
            )
        return result


# Module-level singleton — imported by orchestrator and routers
settings_service = SettingsService()
