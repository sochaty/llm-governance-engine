from __future__ import annotations

import logging
from typing import Optional, Protocol, Tuple

from .schema import (
    GovernanceContext,
    GovernancePolicy,
    PolicyCondition,
    PolicyVerdict,
    ViolatedRule,
)

logger = logging.getLogger(__name__)


class PolicyEngine(Protocol):
    def evaluate(self, context: GovernanceContext) -> PolicyVerdict: ...


class DefaultPolicyEngine:
    def __init__(self, policy: GovernancePolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> GovernancePolicy:
        return self._policy

    def evaluate(self, context: GovernanceContext) -> PolicyVerdict:
        violated: list[ViolatedRule] = []
        warnings: list[str] = []

        for rule in self._policy.rules:
            # Apply model filter — skip rule if it targets specific models
            # and the current model is not in that list.
            if rule.models:
                if context.model_id not in rule.models and context.provider not in rule.models:
                    continue

            fired, message = self._check_condition(rule.condition, rule.threshold, context)

            if not fired:
                continue

            violation = ViolatedRule(
                rule_id=rule.id,
                rule_name=rule.name,
                action=rule.action,
                severity=rule.severity,
                message=message,
            )
            violated.append(violation)

            if rule.action == "warn":
                warnings.append(f"[{rule.severity.upper()}] {rule.name}: {message}")
            elif rule.action in ("block", "alert"):
                logger.warning(
                    "Governance policy violated | rule=%s action=%s severity=%s | %s",
                    rule.id,
                    rule.action,
                    rule.severity,
                    message,
                )

        blocking = next((v for v in violated if v.action == "block"), None)

        return PolicyVerdict(
            passed=blocking is None,
            violated_rules=violated,
            blocking_rule=blocking,
            warnings=warnings,
        )

    @staticmethod
    def _check_condition(
        condition: PolicyCondition,
        threshold: Optional[float],
        ctx: GovernanceContext,
    ) -> Tuple[bool, str]:
        """Returns (fired, human-readable message)."""
        if condition == PolicyCondition.PII_DETECTED:
            if not ctx.pii_detected:
                return False, ""
            min_confidence = threshold if threshold is not None else 0.0
            if ctx.pii_max_confidence < min_confidence:
                return False, ""
            types_str = ", ".join(ctx.pii_entity_types) or "unknown"
            return (
                True,
                f"PII detected (confidence {ctx.pii_max_confidence:.2f}): {types_str}",
            )

        if condition == PolicyCondition.SAFETY_SCORE_BELOW:
            limit = threshold if threshold is not None else 0.5
            if ctx.safety_score < limit:
                return (
                    True,
                    f"Safety score {ctx.safety_score:.2f} is below threshold {limit:.2f}",
                )
            return False, ""

        if condition == PolicyCondition.COST_EXCEEDS:
            limit = threshold if threshold is not None else 0.0
            if ctx.estimated_prompt_cost_usd > limit:
                return (
                    True,
                    f"Estimated cost ${ctx.estimated_prompt_cost_usd:.4f} exceeds limit ${limit:.2f}",
                )
            return False, ""

        if condition == PolicyCondition.FAITHFULNESS_SCORE_BELOW:
            if ctx.faithfulness_score is None:
                # Not yet known (pre-response pass) — never fires here.
                return False, ""
            limit = threshold if threshold is not None else 0.5
            if ctx.faithfulness_score < limit:
                return (
                    True,
                    f"Faithfulness score {ctx.faithfulness_score:.2f} is below "
                    f"threshold {limit:.2f} — response may be hallucinated",
                )
            return False, ""

        if condition == PolicyCondition.MODEL_IS:
            # The model filter is already handled above; this condition
            # fires whenever the model filter matches.
            return True, f"Model '{ctx.model_id}' is on the restricted list"

        return False, ""
