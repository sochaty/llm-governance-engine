"""Unit tests for the governance policy engine.

All tests are synchronous — the engine itself is stateless and pure.
No DB, no HTTP, no Presidio models are loaded.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.governance.policy.engine import DefaultPolicyEngine
from app.governance.policy.schema import (
    GovernanceContext,
    GovernancePolicy,
    PolicyCondition,
    PolicyRule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(*rules: PolicyRule) -> DefaultPolicyEngine:
    policy = GovernancePolicy(version="1.0", name="test", rules=list(rules))
    return DefaultPolicyEngine(policy)


def _clean_context(**overrides) -> GovernanceContext:
    defaults = dict(
        prompt="Tell me about Python.",
        provider="cloud",
        model_id="gpt-4o",
        pii_detected=False,
        pii_entity_types=[],
        pii_max_confidence=0.0,
        safety_score=0.98,
        estimated_prompt_cost_usd=0.001,
    )
    defaults.update(overrides)
    return GovernanceContext(**defaults)


def _pii_rule(action="block", threshold=0.0, models=None) -> PolicyRule:
    return PolicyRule(
        id="test-pii",
        name="Test PII Rule",
        condition=PolicyCondition.PII_DETECTED,
        threshold=threshold,
        models=models,
        action=action,
        severity="critical",
    )


def _safety_rule(threshold=0.5, action="warn") -> PolicyRule:
    return PolicyRule(
        id="test-safety",
        name="Test Safety Rule",
        condition=PolicyCondition.SAFETY_SCORE_BELOW,
        threshold=threshold,
        action=action,
        severity="medium",
    )


def _cost_rule(threshold=1.0, action="block") -> PolicyRule:
    return PolicyRule(
        id="test-cost",
        name="Test Cost Rule",
        condition=PolicyCondition.COST_EXCEEDS,
        threshold=threshold,
        action=action,
        severity="high",
    )


# ---------------------------------------------------------------------------
# Tests: clean request passes all rules
# ---------------------------------------------------------------------------

class TestCleanRequest:
    def test_no_rules_passes(self):
        engine = _make_engine()
        verdict = engine.evaluate(_clean_context())
        assert verdict.passed is True
        assert verdict.violated_rules == []
        assert verdict.blocking_rule is None

    def test_pii_rule_does_not_fire_when_no_pii(self):
        engine = _make_engine(_pii_rule())
        verdict = engine.evaluate(_clean_context(pii_detected=False))
        assert verdict.passed is True

    def test_safety_rule_does_not_fire_above_threshold(self):
        engine = _make_engine(_safety_rule(threshold=0.5))
        verdict = engine.evaluate(_clean_context(safety_score=0.98))
        assert verdict.passed is True

    def test_cost_rule_does_not_fire_below_threshold(self):
        engine = _make_engine(_cost_rule(threshold=1.0))
        verdict = engine.evaluate(_clean_context(estimated_prompt_cost_usd=0.001))
        assert verdict.passed is True


# ---------------------------------------------------------------------------
# Tests: PII rule
# ---------------------------------------------------------------------------

class TestPIIRule:
    def test_pii_block_fires_when_pii_detected(self):
        engine = _make_engine(_pii_rule(action="block", threshold=0.0))
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["EMAIL_ADDRESS"],
            pii_max_confidence=0.85,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False
        assert verdict.blocking_rule is not None
        assert verdict.blocking_rule.rule_id == "test-pii"

    def test_pii_rule_respects_confidence_threshold(self):
        """Rule with threshold=0.9 should NOT fire for confidence=0.8."""
        engine = _make_engine(_pii_rule(action="block", threshold=0.9))
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["EMAIL_ADDRESS"],
            pii_max_confidence=0.8,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True

    def test_pii_rule_fires_at_exact_threshold(self):
        """Rule fires when max_confidence == threshold."""
        engine = _make_engine(_pii_rule(action="block", threshold=0.7))
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["PHONE_NUMBER"],
            pii_max_confidence=0.7,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False

    def test_pii_warn_does_not_block(self):
        engine = _make_engine(_pii_rule(action="warn", threshold=0.0))
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["PERSON"],
            pii_max_confidence=0.75,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True
        assert len(verdict.violated_rules) == 1
        assert verdict.violated_rules[0].action == "warn"

    def test_pii_violation_message_includes_entity_types(self):
        engine = _make_engine(_pii_rule(action="block", threshold=0.0))
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["EMAIL_ADDRESS", "PHONE_NUMBER"],
            pii_max_confidence=0.9,
        )
        verdict = engine.evaluate(ctx)
        assert "EMAIL_ADDRESS" in verdict.violated_rules[0].message
        assert "PHONE_NUMBER" in verdict.violated_rules[0].message


# ---------------------------------------------------------------------------
# Tests: safety score rule
# ---------------------------------------------------------------------------

class TestSafetyScoreRule:
    def test_safety_warn_fires_below_threshold(self):
        engine = _make_engine(_safety_rule(threshold=0.5, action="warn"))
        ctx = _clean_context(safety_score=0.2)
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True  # warn does not block
        assert len(verdict.violations_for("warn")) == 1

    def test_safety_block_fires_below_threshold(self):
        engine = _make_engine(_safety_rule(threshold=0.5, action="block"))
        ctx = _clean_context(safety_score=0.3)
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False

    def test_safety_rule_does_not_fire_at_exact_threshold(self):
        """score == threshold should NOT fire (rule is strictly less-than)."""
        engine = _make_engine(_safety_rule(threshold=0.5, action="block"))
        ctx = _clean_context(safety_score=0.5)
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True


# ---------------------------------------------------------------------------
# Tests: cost rule
# ---------------------------------------------------------------------------

class TestCostRule:
    def test_cost_block_fires_above_limit(self):
        engine = _make_engine(_cost_rule(threshold=0.05, action="block"))
        ctx = _clean_context(estimated_prompt_cost_usd=0.10)
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False
        assert "0.1000" in verdict.blocking_rule.message or "$0.10" in verdict.blocking_rule.message

    def test_cost_rule_does_not_fire_at_exact_threshold(self):
        engine = _make_engine(_cost_rule(threshold=0.10, action="block"))
        ctx = _clean_context(estimated_prompt_cost_usd=0.10)
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True  # not strictly greater


# ---------------------------------------------------------------------------
# Tests: model filter
# ---------------------------------------------------------------------------

class TestModelFilter:
    def test_rule_with_model_filter_only_fires_for_matching_model(self):
        rule = _pii_rule(action="block", models=["gpt-4o"])
        engine = _make_engine(rule)
        pii_ctx = _clean_context(
            pii_detected=True, pii_entity_types=["EMAIL_ADDRESS"], pii_max_confidence=0.9
        )

        # Matches model — should block.
        cloud_ctx = GovernanceContext(**{**pii_ctx.__dict__, "model_id": "gpt-4o"})
        assert engine.evaluate(cloud_ctx).passed is False

    def test_rule_with_model_filter_skips_non_matching_model(self):
        rule = _pii_rule(action="block", models=["gpt-4o"])
        engine = _make_engine(rule)
        ctx = _clean_context(
            model_id="llama3.2:latest",
            provider="local",
            pii_detected=True,
            pii_entity_types=["EMAIL_ADDRESS"],
            pii_max_confidence=0.9,
        )
        # Does NOT match model filter — should pass.
        assert engine.evaluate(ctx).passed is True

    def test_rule_with_provider_in_model_filter(self):
        """Filtering by provider string ('cloud') should also work."""
        rule = _pii_rule(action="block", models=["cloud"])
        engine = _make_engine(rule)
        ctx = _clean_context(
            provider="cloud",
            model_id="gpt-4o",
            pii_detected=True,
            pii_entity_types=["PERSON"],
            pii_max_confidence=0.8,
        )
        assert engine.evaluate(ctx).passed is False

    def test_rule_without_model_filter_applies_to_all(self):
        """A rule with models=None fires regardless of provider."""
        rule = _pii_rule(action="block", models=None)
        engine = _make_engine(rule)
        for model_id in ["gpt-4o", "llama3.2:latest", "claude-3-5-sonnet"]:
            ctx = _clean_context(
                model_id=model_id,
                pii_detected=True,
                pii_entity_types=["EMAIL_ADDRESS"],
                pii_max_confidence=0.9,
            )
            assert engine.evaluate(ctx).passed is False, f"Expected block for {model_id}"


# ---------------------------------------------------------------------------
# Tests: multiple violations
# ---------------------------------------------------------------------------

class TestMultipleViolations:
    def test_all_rules_evaluated_not_short_circuit(self):
        """Both a warn and a block rule should appear in violated_rules."""
        engine = _make_engine(
            _pii_rule(action="warn", threshold=0.0),
            _safety_rule(threshold=0.5, action="block"),
        )
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["EMAIL_ADDRESS"],
            pii_max_confidence=0.8,
            safety_score=0.2,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False
        assert len(verdict.violated_rules) == 2

    def test_blocking_rule_takes_precedence_in_verdict(self):
        engine = _make_engine(
            _safety_rule(threshold=0.9, action="warn"),
            _pii_rule(action="block", threshold=0.0),
        )
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["PHONE_NUMBER"],
            pii_max_confidence=0.7,
            safety_score=0.5,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is False
        assert verdict.blocking_rule.action == "block"

    def test_only_warn_rules_keep_passed_true(self):
        engine = _make_engine(
            _pii_rule(action="warn", threshold=0.0),
            _safety_rule(threshold=0.9, action="warn"),
        )
        ctx = _clean_context(
            pii_detected=True,
            pii_entity_types=["PERSON"],
            pii_max_confidence=0.6,
            safety_score=0.5,
        )
        verdict = engine.evaluate(ctx)
        assert verdict.passed is True
        assert len(verdict.warnings) == 2


# ---------------------------------------------------------------------------
# Helpers on PolicyVerdict
# ---------------------------------------------------------------------------

def _add_violations_for_helper():
    """Monkey-patch a test helper onto PolicyVerdict for readability."""
    from app.governance.policy.schema import PolicyVerdict

    def violations_for(self, action: str):
        return [v for v in self.violated_rules if v.action == action]

    PolicyVerdict.violations_for = violations_for


_add_violations_for_helper()
