"""FastAPI dependency for pre-inference governance policy enforcement.

The enforcement dependency:
1. Scans the prompt for PII using the AuditService.
2. Builds a GovernanceContext with cost estimate and scan results.
3. Evaluates all active policy rules via the PolicyEngine.
4. If a blocking rule fires → saves a PolicyViolation, fires webhook async,
   and raises HTTP 403 with a structured error body.
5. If only warn/alert rules fire → saves violations, fires webhooks async,
   and returns the verdict for the endpoint to log.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.policy_violation import PolicyViolation
from app.schemas.benchmark import BenchmarkRequest
from app.services.audit_service import AuditService

from .engine import DefaultPolicyEngine
from .loader import PolicyLoader
from .schema import GovernanceContext, PolicyVerdict, ViolatedRule
from .webhook import WebhookDelivery, WebhookEvent

# Actions that are still meaningful once the LLM response has already started
# streaming — a "block" verdict can no longer stop delivery post-response, so
# it is recorded as an alert instead (see record_violations()).
_POST_RESPONSE_ACTION_DOWNGRADE = {"block": "alert"}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons — initialised lazily on first request.
# Tests can call reset_policy_engine() to force a reload.
# ---------------------------------------------------------------------------
_policy_engine: DefaultPolicyEngine | None = None
_audit_service: AuditService | None = None
_webhook_delivery = WebhookDelivery()


def get_policy_engine() -> DefaultPolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        loader = PolicyLoader()
        policy = loader.load()
        _policy_engine = DefaultPolicyEngine(policy)
    return _policy_engine


def reload_policy_engine(path: Optional[str] = None) -> DefaultPolicyEngine:
    """Force a reload from disk. Called by the /policies/reload endpoint."""
    global _policy_engine
    loader = PolicyLoader()
    policy = loader.load(path)
    _policy_engine = DefaultPolicyEngine(policy)
    logger.info("Policy engine reloaded: %d rules active.", len(policy.rules))
    return _policy_engine


def reset_policy_engine() -> None:
    """Reset the singleton. Used in tests."""
    global _policy_engine
    _policy_engine = None


def _get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


# ---------------------------------------------------------------------------
# Helper: persist a violation row and fire webhook (non-blocking)
# ---------------------------------------------------------------------------
async def _record_violation(
    db: AsyncSession,
    violation: ViolatedRule,
    context: GovernanceContext,
    webhook_url: str | None,
    *,
    post_response: bool = False,
) -> None:
    action = violation.action
    if post_response and action in _POST_RESPONSE_ACTION_DOWNGRADE:
        logger.warning(
            "Rule '%s' fired post-response with action=%s, which can no longer "
            "block an in-flight stream — recording as '%s' instead.",
            violation.rule_id, action, _POST_RESPONSE_ACTION_DOWNGRADE[action],
        )
        action = _POST_RESPONSE_ACTION_DOWNGRADE[action]

    row = PolicyViolation(
        rule_id=violation.rule_id,
        rule_name=violation.rule_name,
        action=action,
        severity=violation.severity,
        message=violation.message,
        prompt_preview=context.prompt[:200],
        provider=context.provider,
        model_id=context.model_id,
        pii_detected=int(context.pii_detected),
        safety_score=context.safety_score,
        faithfulness_score=context.faithfulness_score,
        webhook_status=None,
    )

    if webhook_url:
        event = WebhookEvent(
            rule_id=violation.rule_id,
            rule_name=violation.rule_name,
            severity=violation.severity,
            action=action,
            message=violation.message,
            provider=context.provider,
            model_id=context.model_id,
        )
        # Fire-and-forget so we don't block the response path.
        asyncio.create_task(_deliver_webhook(row, event, webhook_url))
    else:
        row.webhook_status = "not_configured"

    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        logger.error("Failed to persist policy violation: %s", exc)


async def record_violations(
    db: AsyncSession,
    verdict: PolicyVerdict,
    context: GovernanceContext,
    engine: DefaultPolicyEngine,
    *,
    post_response: bool = False,
) -> None:
    """Persist every violation in `verdict` and fire its webhook (if configured).

    Shared by the pre-response `enforce_governance_policy` dependency and any
    post-response check (e.g. faithfulness scoring in llm_orchestrator, where
    `post_response=True` downgrades a `block` action to `alert` since the
    response has already started streaming).
    """
    for violation in verdict.violated_rules:
        webhook_url = next(
            (r.webhook_url for r in engine.policy.rules if r.id == violation.rule_id),
            None,
        )
        await _record_violation(db, violation, context, webhook_url, post_response=post_response)


async def _deliver_webhook(
    row: PolicyViolation, event: WebhookEvent, webhook_url: str
) -> None:
    ok = await _webhook_delivery.send(webhook_url, event)
    row.webhook_status = "sent" if ok else "failed"


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def enforce_governance_policy(
    body: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyVerdict:
    """
    FastAPI dependency injected into the /benchmark/stream endpoint.
    Returns the PolicyVerdict so the endpoint can log warnings.
    Raises HTTP 403 if a blocking rule fires.

    `body` is the same BenchmarkRequest model the endpoint itself declares —
    FastAPI resolves both to the single parsed request body rather than
    treating each occurrence as a separate nested field.
    """
    engine = get_policy_engine()
    audit = _get_audit_service()
    prompt, provider = body.prompt, body.provider

    # Scan prompt for PII before it touches any model.
    scan = audit.scan_for_pii_details(prompt)

    # Rough cost estimate from prompt length alone (response not available yet).
    word_count = len(prompt.split())
    model_id = (
        "gpt-4o"
        if provider == "cloud"
        else "llama3.2:latest"
    )
    estimated_cost = (word_count * 0.00003) if provider == "cloud" else 0.0

    context = GovernanceContext(
        prompt=prompt,
        provider=provider,
        model_id=model_id,
        pii_detected=scan.detected,
        pii_entity_types=[e.entity_type for e in scan.entities],
        pii_max_confidence=scan.max_confidence,
        safety_score=audit.calculate_safety_score(prompt),
        estimated_prompt_cost_usd=estimated_cost,
    )

    verdict = engine.evaluate(context)

    # Persist all violations and trigger webhooks (fire-and-forget).
    await record_violations(db, verdict, context, engine)

    if not verdict.passed and verdict.blocking_rule:
        br = verdict.blocking_rule
        raise HTTPException(
            status_code=403,
            detail={
                "error": "governance_violation",
                "rule_id": br.rule_id,
                "rule_name": br.rule_name,
                "severity": br.severity,
                "message": br.message,
            },
        )

    # Log any warnings so they appear in server logs.
    for warning in verdict.warnings:
        logger.warning("Governance warning: %s", warning)

    return verdict
