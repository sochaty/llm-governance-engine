from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.governance.policy.enforcement import get_policy_engine, reload_policy_engine
from app.models.policy_violation import PolicyViolation

router = APIRouter(prefix="/policies", tags=["governance"])


@router.get("")
def list_policies():
    """Return the currently loaded governance policy and its rules."""
    engine = get_policy_engine()
    policy = engine.policy
    return {
        "version": policy.version,
        "name": policy.name,
        "rule_count": len(policy.rules),
        "rules": [r.model_dump() for r in policy.rules],
    }


@router.post("/reload")
def reload_policies(path: Optional[str] = Query(default=None)):
    """Hot-reload the governance policy from disk without restarting the server."""
    engine = reload_policy_engine(path)
    return {
        "status": "reloaded",
        "rule_count": len(engine.policy.rules),
        "rules_loaded": [r.id for r in engine.policy.rules],
    }


@router.get("/violations")
async def list_violations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    severity: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of recorded policy violations from the audit log."""
    query = select(PolicyViolation).order_by(PolicyViolation.created_at.desc())

    if severity:
        query = query.where(PolicyViolation.severity == severity)
    if action:
        query = query.where(PolicyViolation.action == action)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    return {
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "violations": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "action": r.action,
                "severity": r.severity,
                "message": r.message,
                "provider": r.provider,
                "model_id": r.model_id,
                "pii_detected": bool(r.pii_detected),
                "safety_score": r.safety_score,
                "webhook_status": r.webhook_status,
            }
            for r in rows
        ],
    }
