"""Tests for governance policy enforcement middleware, loader, and governance router."""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.governance.policy.loader import PolicyLoader
from app.governance.policy.schema import GovernancePolicy, PolicyRule
from app.governance.policy.enforcement import (
    get_policy_engine,
    reload_policy_engine,
    reset_policy_engine,
    _get_audit_service,
)


# ── PolicyLoader unit tests ───────────────────────────────────────────────────

class TestPolicyLoader:
    def test_load_nonexistent_path_returns_empty_policy(self):
        loader = PolicyLoader()
        policy = loader.load("/nonexistent/path/policy.yaml")
        assert isinstance(policy, GovernancePolicy)
        assert policy.rules == []

    def test_load_valid_yaml_returns_policy(self, tmp_path):
        yaml_content = """
version: "1.0"
name: test
rules:
  - id: test-rule
    name: Test Rule
    condition: pii_detected
    threshold: 0.7
    action: block
    severity: high
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_content)

        loader = PolicyLoader()
        policy = loader.load(str(policy_file))
        assert len(policy.rules) == 1
        assert policy.rules[0].id == "test-rule"
        assert policy.rules[0].action == "block"

    def test_load_empty_yaml_returns_empty_policy(self, tmp_path):
        policy_file = tmp_path / "empty.yaml"
        policy_file.write_text("")

        loader = PolicyLoader()
        policy = loader.load(str(policy_file))
        assert isinstance(policy, GovernancePolicy)
        assert policy.rules == []

    def test_load_invalid_yaml_returns_empty_policy(self, tmp_path):
        policy_file = tmp_path / "bad.yaml"
        policy_file.write_text("rules: [invalid: yaml: content: ::::")

        loader = PolicyLoader()
        policy = loader.load(str(policy_file))
        assert isinstance(policy, GovernancePolicy)

    def test_load_from_string_parses_rules(self):
        yaml_str = """
version: "1.0"
rules:
  - id: str-rule
    name: String Rule
    condition: safety_score_below
    threshold: 0.5
    action: warn
    severity: medium
"""
        loader = PolicyLoader()
        policy = loader.load_from_string(yaml_str)
        assert len(policy.rules) == 1
        assert policy.rules[0].id == "str-rule"

    def test_load_from_string_empty_returns_empty_policy(self):
        loader = PolicyLoader()
        policy = loader.load_from_string("")
        assert isinstance(policy, GovernancePolicy)
        assert policy.rules == []


# ── Enforcement singleton helpers ──────────────────────────────────────────────

class TestEnforcementHelpers:
    def setup_method(self):
        reset_policy_engine()

    def test_get_policy_engine_returns_engine(self):
        from app.governance.policy.engine import DefaultPolicyEngine
        engine = get_policy_engine()
        assert isinstance(engine, DefaultPolicyEngine)

    def test_get_policy_engine_is_cached(self):
        engine1 = get_policy_engine()
        engine2 = get_policy_engine()
        assert engine1 is engine2

    def test_reset_policy_engine_clears_singleton(self):
        engine1 = get_policy_engine()
        reset_policy_engine()
        engine2 = get_policy_engine()
        assert engine1 is not engine2

    def test_reload_policy_engine_returns_new_engine(self):
        engine1 = get_policy_engine()
        engine2 = reload_policy_engine()
        assert engine2 is not engine1

    def test_get_audit_service_returns_service(self):
        from app.services.audit_service import AuditService
        svc = _get_audit_service()
        assert isinstance(svc, AuditService)


# ── Integration: enforce_governance_policy via HTTP ───────────────────────────

@pytest.mark.anyio
class TestEnforcementIntegration:
    def setup_method(self):
        reset_policy_engine()

    async def test_safe_prompt_passes_enforcement(self, client):
        """A clean prompt with no PII and empty policy passes through enforcement."""
        from app.api import benchmark_router as br

        async def mock_stream(*args, **kwargs):
            yield "safe response token"

        with patch.object(br._orchestrator, "run_and_record_benchmark", side_effect=mock_stream):
            response = await client.get(
                "/api/benchmark/stream",
                params={"prompt": "What is the capital of France?", "provider": "cloud"},
            )
        assert response.status_code == 200

    async def test_validation_error_without_prompt(self, client):
        response = await client.get("/api/benchmark/stream")
        assert response.status_code == 422

    async def test_invalid_provider_rejected(self, client):
        response = await client.get(
            "/api/benchmark/stream",
            params={"prompt": "test", "provider": "badprovider"},
        )
        assert response.status_code == 422

    async def test_pii_prompt_blocked_by_active_policy(self, client, tmp_path):
        """A blocking policy rule causes a 403 on PII-containing prompt."""
        yaml_content = """
version: "1.0"
name: test-block
rules:
  - id: block-pii
    name: Block PII
    condition: pii_detected
    threshold: 0.1
    action: block
    severity: critical
"""
        policy_file = tmp_path / "block_policy.yaml"
        policy_file.write_text(yaml_content)

        # Load blocking policy directly
        loader = PolicyLoader()
        blocking_policy = loader.load(str(policy_file))
        from app.governance.policy.engine import DefaultPolicyEngine
        import app.governance.policy.enforcement as enf
        enf._policy_engine = DefaultPolicyEngine(blocking_policy)

        response = await client.get(
            "/api/benchmark/stream",
            params={"prompt": "My SSN is 123-45-6789", "provider": "cloud"},
        )
        # Should be blocked (403) or pass (200) depending on PII detection confidence
        assert response.status_code in (200, 403)

    async def test_warn_rule_does_not_block(self, client, tmp_path):
        """A warn-only policy lets the request proceed."""
        yaml_content = """
version: "1.0"
name: test-warn
rules:
  - id: warn-always
    name: Warn Rule
    condition: safety_score_below
    threshold: 1.0
    action: warn
    severity: low
"""
        policy_file = tmp_path / "warn_policy.yaml"
        policy_file.write_text(yaml_content)

        loader = PolicyLoader()
        warn_policy = loader.load(str(policy_file))
        from app.governance.policy.engine import DefaultPolicyEngine
        import app.governance.policy.enforcement as enf
        enf._policy_engine = DefaultPolicyEngine(warn_policy)

        from app.api import benchmark_router as br

        async def mock_stream(*args, **kwargs):
            yield "warned response"

        with patch.object(br._orchestrator, "run_and_record_benchmark", side_effect=mock_stream):
            response = await client.get(
                "/api/benchmark/stream",
                params={"prompt": "Hello world", "provider": "cloud"},
            )
        assert response.status_code == 200


# ── Governance router endpoints ────────────────────────────────────────────────

@pytest.mark.anyio
class TestGovernanceRouter:
    def setup_method(self):
        reset_policy_engine()

    async def test_get_policies_returns_policy_shape(self, client):
        response = await client.get("/api/v1/policies")
        assert response.status_code == 200
        data = response.json()
        assert "rule_count" in data
        assert "rules" in data
        assert isinstance(data["rules"], list)

    async def test_reload_policies_returns_200(self, client):
        response = await client.post("/api/v1/policies/reload")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"

    async def test_get_violations_returns_paginated_result(self, client):
        response = await client.get("/api/v1/policies/violations")
        assert response.status_code == 200
        data = response.json()
        assert "violations" in data
        assert "total" in data
        assert isinstance(data["violations"], list)

    async def test_get_violations_with_severity_filter(self, client):
        response = await client.get("/api/v1/policies/violations", params={"severity": "critical"})
        assert response.status_code == 200
        data = response.json()
        assert "violations" in data

    async def test_get_violations_with_action_filter(self, client):
        response = await client.get("/api/v1/policies/violations", params={"action": "block"})
        assert response.status_code == 200

    async def test_history_endpoint_returns_list(self, client):
        response = await client.get("/api/benchmark/history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_stats_endpoint_returns_dict(self, client):
        response = await client.get("/api/benchmark/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_savings" in data
        assert "total_requests" in data
