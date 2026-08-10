import os
import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_orchestrator import LLMOrchestrator, ModelConfig
from app.governance.policy.engine import DefaultPolicyEngine
from app.governance.policy.schema import GovernancePolicy, PolicyCondition, PolicyRule

@pytest.mark.anyio
class TestOrchestratorBenchmarks:

    # --- 1. Successful Benchmark Recording ---
    async def test_run_and_record_benchmark_success(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        
        # Mock AuditService to prevent NLP type errors during testing
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)

        async def mock_stream_yield(*args):
            yield "This "
            yield "is "
            yield "AI"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            responses = []
            async for chunk in orchestrator.run_and_record_benchmark(db_session, "test prompt", "cloud"):
                responses.append(chunk)

            # Use assert_called_once() for better error messages
            db_session.add.assert_called_once()
            added_result = db_session.add.call_args[0][0]
            assert added_result.provider == "cloud"
            assert added_result.estimated_cost > 0  # Should have cost for cloud
            db_session.commit.assert_called_once()

    # --- 2. Local Provider Cost Logic ---
    async def test_benchmark_local_cost_is_zero(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()

        # Mock AuditService to prevent NLP type errors during testing
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        
        async def mock_stream_yield(*args):
            yield "Local response"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            async for _ in orchestrator.run_and_record_benchmark(db_session, "test", "local"):
                pass

            added_result = db_session.add.call_args[0][0]
            assert added_result.provider == "local"
            assert added_result.estimated_cost == 0.0  # Local should always be free

    # --- 3. Database Failure Handling ---
    async def test_benchmark_database_failure(self):
        """Test that if DB fails, the stream still works but logs an error."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        db_session.commit.side_effect = Exception("DB Connection Lost")
        
        async def mock_stream_yield(*args):
            yield "Data"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            # We want to ensure the generator doesn't crash the UI even if DB fails
            responses = []
            async for chunk in orchestrator.run_and_record_benchmark(db_session, "test", "cloud"):
                responses.append(chunk)
            
            assert "Data" in responses
            # The exception is caught internally by your try/except block in orchestrator.py

    # --- 4. Unknown Provider Falls Back to Cloud Config ---
    async def test_benchmark_unknown_provider_falls_back_to_cloud(self):
        """Unknown provider falls back to the cloud config and reports a stream error."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()

        # Patch audit service so it doesn't fail on mock content
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)

        # _build_config_for falls back to cloud config; stream attempt fails → error chunk
        async def mock_stream_error(*args, **kwargs):
            yield "Error: openai service is currently unavailable."

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_error):
            responses = []
            async for chunk in orchestrator.run_and_record_benchmark(
                db_session, "test", "unknown_provider"
            ):
                responses.append(chunk)

        assert len(responses) == 1
        assert "Error:" in responses[0]

    # --- 5. Latency Calculation Logic ---
    async def test_benchmark_latency_calculation(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()

        # Mock AuditService to prevent NLP type errors during testing
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        
        async def mock_stream_yield(*args):
            time.sleep(0.1) # Simulate 100ms delay
            yield "Slow response"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            async for _ in orchestrator.run_and_record_benchmark(db_session, "test", "cloud"):
                pass
            
            added_result = db_session.add.call_args[0][0]
            assert added_result.latency_ms >= 100 # Verify latency is recorded

    # --- 6. Faithfulness scoring is opt-in via `context` ---
    async def test_no_context_skips_faithfulness_scoring(self):
        """Without `context`, faithfulness fields stay None and the judge is never called."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.9, 0.8))

        async def mock_stream_yield(*args):
            yield "response"

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield):
            async for _ in orchestrator.run_and_record_benchmark(db_session, "test", "cloud"):
                pass

        orchestrator.faithfulness_service.score.assert_not_called()
        added_result = db_session.add.call_args[0][0]
        assert added_result.faithfulness_score is None
        assert added_result.context_utilization is None

    async def test_context_provided_triggers_faithfulness_scoring(self):
        """When `context` is supplied, the response is scored and persisted."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.72, 0.65))

        async def mock_stream_yield(*args):
            yield "Paris is the capital of France."

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield):
            async for _ in orchestrator.run_and_record_benchmark(
                db_session, "What is the capital?", "cloud", context="Paris is the capital of France."
            ):
                pass

        orchestrator.faithfulness_service.score.assert_awaited_once()
        added_result = db_session.add.call_args[0][0]
        assert added_result.faithfulness_score == 0.72
        assert added_result.context_utilization == 0.65

    async def test_low_faithfulness_triggers_post_response_policy_check(self):
        """A faithfulness_score_below rule fires the post-response governance check."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.1, 0.2))

        rule = PolicyRule(
            id="low-faithfulness",
            name="Low Faithfulness",
            condition=PolicyCondition.FAITHFULNESS_SCORE_BELOW,
            threshold=0.6,
            action="warn",
            severity="medium",
        )
        engine = DefaultPolicyEngine(GovernancePolicy(version="1.0", name="test", rules=[rule]))

        async def mock_stream_yield(*args):
            yield "hallucinated response"

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield), \
             patch("app.services.llm_orchestrator.get_policy_engine", return_value=engine), \
             patch("app.services.llm_orchestrator.record_violations", new_callable=AsyncMock) as mock_record:
            async for _ in orchestrator.run_and_record_benchmark(
                db_session, "test", "cloud", context="some context"
            ):
                pass

        mock_record.assert_awaited_once()
        _, verdict, gov_ctx, _engine = mock_record.call_args.args
        assert len(verdict.violated_rules) == 1
        assert gov_ctx.faithfulness_score == 0.1
        assert mock_record.call_args.kwargs.get("post_response") is True

    async def test_high_faithfulness_does_not_trigger_policy_check(self):
        """A faithfulness score above every rule's threshold records no violation."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.95, 0.9))

        rule = PolicyRule(
            id="low-faithfulness",
            name="Low Faithfulness",
            condition=PolicyCondition.FAITHFULNESS_SCORE_BELOW,
            threshold=0.6,
            action="warn",
            severity="medium",
        )
        engine = DefaultPolicyEngine(GovernancePolicy(version="1.0", name="test", rules=[rule]))

        async def mock_stream_yield(*args):
            yield "faithful response"

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield), \
             patch("app.services.llm_orchestrator.get_policy_engine", return_value=engine), \
             patch("app.services.llm_orchestrator.record_violations", new_callable=AsyncMock) as mock_record:
            async for _ in orchestrator.run_and_record_benchmark(
                db_session, "test", "cloud", context="some context"
            ):
                pass

        mock_record.assert_not_awaited()

    async def test_no_faithfulness_rules_configured_skips_check_entirely(self):
        """No faithfulness_score_below rule in the policy → no evaluation attempted."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.1, 0.2))

        engine = DefaultPolicyEngine(GovernancePolicy(version="1.0", name="test", rules=[]))

        async def mock_stream_yield(*args):
            yield "response"

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield), \
             patch("app.services.llm_orchestrator.get_policy_engine", return_value=engine), \
             patch("app.services.llm_orchestrator.record_violations", new_callable=AsyncMock) as mock_record:
            async for _ in orchestrator.run_and_record_benchmark(
                db_session, "test", "cloud", context="some context"
            ):
                pass

        mock_record.assert_not_awaited()

    async def test_post_response_policy_check_failure_does_not_crash_stream(self):
        """An exception evaluating the post-response policy is caught, not propagated."""
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        orchestrator.audit_service.scan_for_pii = MagicMock(return_value=False)
        orchestrator.audit_service.calculate_safety_score = MagicMock(return_value=1.0)
        orchestrator.faithfulness_service.score = AsyncMock(return_value=(0.1, 0.2))

        async def mock_stream_yield(*args):
            yield "response"

        with patch.object(orchestrator, "get_streaming_response", side_effect=mock_stream_yield), \
             patch("app.services.llm_orchestrator.get_policy_engine", side_effect=RuntimeError("boom")):
            responses = []
            async for chunk in orchestrator.run_and_record_benchmark(
                db_session, "test", "cloud", context="some context"
            ):
                responses.append(chunk)

        assert "response" in responses
        db_session.commit.assert_awaited_once()  # benchmark row still saved


@pytest.mark.anyio
class TestBuildConfig:
    """Tests for _build_config_for() — provider routing logic."""

    def test_no_overrides_returns_default_cloud_config(self):
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("cloud", None, None)
        assert cfg.provider_type == "openai"
        assert cfg.name is not None

    def test_no_overrides_returns_default_local_config(self):
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("local", None, None)
        assert cfg.provider_type == "ollama"

    def test_provider_type_override_sets_correct_base_url(self):
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("cloud", "groq", "llama-3.1-8b-instant")
        assert cfg.provider_type == "groq"
        assert cfg.name == "llama-3.1-8b-instant"
        assert "groq.com" in (cfg.base_url or "")

    def test_model_id_override_sets_model_name(self):
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("cloud", "openai", "gpt-4o-mini")
        assert cfg.name == "gpt-4o-mini"

    def test_ollama_provider_type_sets_ollama_api_key(self):
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("local", "ollama", "mistral:latest")
        assert cfg.api_key == "ollama"
        assert cfg.provider_type == "ollama"

    def test_anthropic_provider_type_resolved(self):
        orch = LLMOrchestrator()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            cfg = orch._build_config_for("cloud", "anthropic", "claude-3-haiku-20240307")
        assert cfg.provider_type == "anthropic"
        assert cfg.api_key == "sk-ant-test"

    def test_unknown_provider_type_falls_back_to_cloud_base(self):
        """An unknown provider_type still returns a ModelConfig without crashing."""
        orch = LLMOrchestrator()
        cfg = orch._build_config_for("cloud", "unknown-provider", "some-model")
        assert isinstance(cfg, ModelConfig)


@pytest.mark.anyio
class TestStreamingRouting:
    """Tests for get_streaming_response routing to the correct stream method."""

    async def test_anthropic_provider_type_calls_stream_anthropic(self):
        orch = LLMOrchestrator()
        # Patch both stream methods; only one should be called
        anthropic_mock = AsyncMock()
        anthropic_mock.__aiter__ = MagicMock(return_value=iter(["hello"]))

        async def mock_stream_anthropic(prompt, config):
            yield "anthr-token"

        async def mock_stream_openai(prompt, config):
            yield "openai-token"

        with patch.object(orch, "_stream_anthropic", side_effect=mock_stream_anthropic), \
             patch.object(orch, "_stream_openai_compat", side_effect=mock_stream_openai):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
                tokens = []
                async for t in orch.get_streaming_response(
                    "hi", "cloud", provider_type="anthropic", model_id="claude-3-haiku-20240307"
                ):
                    tokens.append(t)

        assert "anthr-token" in tokens

    async def test_stream_anthropic_sdk_not_installed_yields_error(self):
        orch = LLMOrchestrator()
        config = ModelConfig(
            name="claude-3-haiku-20240307",
            timeout=30.0,
            api_key="sk-ant-test",
            provider_type="anthropic",
        )

        with patch.dict("sys.modules", {"anthropic": None}):
            tokens = []
            async for t in orch._stream_anthropic("test prompt", config):
                tokens.append(t)

        assert any("anthropic" in t.lower() for t in tokens)

    async def test_stream_anthropic_no_api_key_yields_error(self):
        orch = LLMOrchestrator()
        config = ModelConfig(
            name="claude-3-haiku-20240307",
            timeout=30.0,
            api_key=None,
            provider_type="anthropic",
        )
        tokens = []
        async for t in orch._stream_anthropic("test", config):
            tokens.append(t)
        # Either the SDK is missing (ImportError path) or the key is absent
        assert len(tokens) >= 1
        assert any("Error" in t for t in tokens)