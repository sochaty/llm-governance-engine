from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.settings_service import KNOWN_SETTINGS, settings_service

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_KEYS = {s["key"] for s in KNOWN_SETTINGS}


class SaveSettingsRequest(BaseModel):
    settings: Dict[str, str]


@router.get("")
def get_settings():
    """Return all known settings with masked values and source (db/env/unset)."""
    return {"settings": settings_service.list_for_ui()}


@router.put("")
async def save_settings(
    body: SaveSettingsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save one or more settings. Unknown keys are rejected."""
    unknown = set(body.settings.keys()) - ALLOWED_KEYS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown keys: {sorted(unknown)}")

    for key, value in body.settings.items():
        stripped = value.strip()
        if stripped:
            await settings_service.save(key, stripped, db)
        # empty string means "clear" — fall back to env var
        else:
            await settings_service.delete(key, db)

    return {"saved": list(body.settings.keys()), "settings": settings_service.list_for_ui()}


@router.delete("/{key}")
async def delete_setting(key: str, db: AsyncSession = Depends(get_db)):
    """Remove a DB override for a single key so the env var takes effect."""
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown key: {key}")
    await settings_service.delete(key, db)
    return {"deleted": key}
