import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.services.llm_orchestrator import LLMOrchestrator
from dotenv import load_dotenv

load_dotenv(override=True)

@pytest.mark.anyio
async def test_orchestrator_yields_content():
    # 1. Setup environment
    os.environ["OPENAI_API_KEY"] = "fake_key_for_testing"
    orchestrator = LLMOrchestrator()
    
    # 2. Create mock chunk with the structure expected by your generator
    # chunk.choices[0].delta.content
    mock_delta = MagicMock()
    mock_delta.content = "Hello"
    
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    
    mock_chunk = MagicMock()
    mock_chunk.choices = [mock_choice]
    
    # 3. Create the mock stream (Async Iterator)
    async def mock_stream_iterator():
        yield mock_chunk

    # 4. Patch the client creation
    # Since _get_client creates the client, we mock the entire AsyncOpenAI instance
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream_iterator()

    with patch.object(orchestrator, '_get_client', return_value=mock_client):
        responses = []
        async for res in orchestrator.get_streaming_response("Hi", "cloud"):
            responses.append(res)
        
        # 5. Assertions
        assert "Hello" in responses
        mock_client.chat.completions.create.assert_called_once()

@pytest.mark.anyio
async def test_orchestrator_missing_api_key():
    # 1. Setup environment with NO API key
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    
    orchestrator = LLMOrchestrator()
    
    # 2. Execute
    responses = []
    async for res in orchestrator.get_streaming_response("Hi", "cloud"):
        responses.append(res)
    
    # 3. Assert sanitized error message is yielded
    assert "Error: Cloud service is currently unavailable." in responses

@pytest.mark.anyio
async def test_orchestrator_service_exception():
    orchestrator = LLMOrchestrator()
    
    # 1. Mock the client to raise an Exception when called
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("Connection Timeout")

    # 2. Patch _get_client to return our failing mock
    with patch.object(orchestrator, '_get_client', return_value=mock_client):
        responses = []
        async for res in orchestrator.get_streaming_response("Hi", "cloud"):
            responses.append(res)
        
        # 3. Assert the exception was caught and handled
        assert "Error: Cloud service is currently unavailable." in responses