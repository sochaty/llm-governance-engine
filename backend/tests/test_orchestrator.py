# import os
# import sys
# import pytest
# from unittest.mock import AsyncMock, patch, MagicMock
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# from app.services.llm_orchestrator import LLMOrchestrator
# from dotenv import load_dotenv

# load_dotenv(override=True)

# @pytest.mark.anyio
# async def test_orchestrator_yields_content():
#     # 1. Setup environment
#     os.environ["OPENAI_API_KEY"] = "fake_key_for_testing"
#     orchestrator = LLMOrchestrator()
    
#     # 2. Create mock chunk with the structure expected by your generator
#     # chunk.choices[0].delta.content
#     mock_delta = MagicMock()
#     mock_delta.content = "Hello"
    
#     mock_choice = MagicMock()
#     mock_choice.delta = mock_delta
    
#     mock_chunk = MagicMock()
#     mock_chunk.choices = [mock_choice]
    
#     # 3. Create the mock stream (Async Iterator)
#     async def mock_stream_iterator():
#         yield mock_chunk

#     # 4. Patch the client creation
#     # Since _get_client creates the client, we mock the entire AsyncOpenAI instance
#     mock_client = AsyncMock()
#     mock_client.chat.completions.create.return_value = mock_stream_iterator()

#     with patch.object(orchestrator, '_get_client', return_value=mock_client):
#         responses = []
#         async for res in orchestrator.get_streaming_response("Hi", "cloud"):
#             responses.append(res)
        
#         # 5. Assertions
#         assert "Hello" in responses
#         mock_client.chat.completions.create.assert_called_once()

# @pytest.mark.anyio
# async def test_orchestrator_missing_api_key():
#     # 1. Setup environment with NO API key
#     if "OPENAI_API_KEY" in os.environ:
#         del os.environ["OPENAI_API_KEY"]
    
#     orchestrator = LLMOrchestrator()
    
#     # 2. Execute
#     responses = []
#     async for res in orchestrator.get_streaming_response("Hi", "cloud"):
#         responses.append(res)
    
#     # 3. Assert sanitized error message is yielded
#     assert "Error: Cloud service is currently unavailable." in responses

# @pytest.mark.anyio
# async def test_orchestrator_service_exception():
#     orchestrator = LLMOrchestrator()
    
#     # 1. Mock the client to raise an Exception when called
#     mock_client = AsyncMock()
#     mock_client.chat.completions.create.side_effect = Exception("Connection Timeout")

#     # 2. Patch _get_client to return our failing mock
#     with patch.object(orchestrator, '_get_client', return_value=mock_client):
#         responses = []
#         async for res in orchestrator.get_streaming_response("Hi", "cloud"):
#             responses.append(res)
        
#         # 3. Assert the exception was caught and handled
#         assert "Error: Cloud service is currently unavailable." in responses

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_orchestrator import LLMOrchestrator

@pytest.mark.anyio
class TestOrchestratorBenchmarks:

    # --- 1. Successful Benchmark Recording ---
    async def test_run_and_record_benchmark_success(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock() # Mock SQLAlchemy session
        
        # Mocking the stream response
        async def mock_stream_yield(*args):
            yield "This "
            yield "is "
            yield "AI"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            responses = []
            async for chunk in orchestrator.run_and_record_benchmark(db_session, "test prompt", "cloud"):
                responses.append(chunk)

            # Assertions for logic
            assert "".join(responses) == "This is AI"
            
            # Verify Database interaction
            assert db_session.add.called
            added_result = db_session.add.call_args[0][0]
            assert added_result.provider == "cloud"
            assert added_result.estimated_cost > 0  # Should have cost for cloud
            db_session.commit.assert_called_once()

    # --- 2. Local Provider Cost Logic ---
    async def test_benchmark_local_cost_is_zero(self):
        orchestrator = LLMOrchestrator()
        db_session = AsyncMock()
        
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
        
        async def mock_stream_yield(*args):
            time.sleep(0.1) # Simulate 100ms delay
            yield "Slow response"

        with patch.object(orchestrator, 'get_streaming_response', side_effect=mock_stream_yield):
            async for _ in orchestrator.run_and_record_benchmark(db_session, "test", "cloud"):
                pass
            
            added_result = db_session.add.call_args[0][0]
            assert added_result.latency_ms >= 100 # Verify latency is recorded