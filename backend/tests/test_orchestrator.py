import os
import sys
import pytest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.services.llm_orchestrator import LLMOrchestrator
from dotenv import load_dotenv

load_dotenv(override=True)  # Load environment variables from .env file

@pytest.mark.anyio
async def test_orchestrator_yields_content():
    # Set a fake API key for testing
    os.environ["OPENAI_API_KEY"] = "fake_key_for_testing"
    
    orchestrator = LLMOrchestrator()
    
    # Create a proper mock chunk
    mock_chunk = AsyncMock()
    mock_chunk.choices = [AsyncMock()]
    mock_chunk.choices[0].delta = AsyncMock()
    mock_chunk.choices[0].delta.content = "Hello"
    
    # Create a mock stream that behaves like an async iterator
    class MockAsyncIterator:
        def __init__(self, items):
            self.items = items
        
        def __aiter__(self):
            return self
        
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)
    
    mock_stream = MockAsyncIterator([mock_chunk])
    
    # Mock the create method to return a coroutine that resolves to the stream
    async def mock_create(**kwargs):
        return mock_stream
    
    with patch.object(orchestrator.cloud_client.chat.completions, 'create', side_effect=mock_create):
        responses = []
        async for res in orchestrator.get_streaming_response("Hi", "cloud"):
            responses.append(res)
        
        assert "Hello" in responses