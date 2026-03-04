import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_orchestrator import LLMOrchestrator

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

    # --- 4. Unsupported Provider Handling ---
    async def test_benchmark_unsupported_provider(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        
        responses = []
        async for chunk in orchestrator.run_and_record_benchmark(db_session, "test", "unknown_provider"):
            responses.append(chunk)
        
        assert "Error: Provider unknown_provider not configured." in responses[0]

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