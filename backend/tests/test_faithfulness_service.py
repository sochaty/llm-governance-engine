"""Tests for FaithfulnessService — RAGAS faithfulness/context-utilization scoring.

Ragas itself (and the OpenAI judge call it makes) is always mocked — these
tests never hit the network or require a real API key.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.faithfulness_service import FaithfulnessService


@pytest.mark.anyio
class TestFaithfulnessServiceScore:
    async def test_returns_none_when_context_missing(self):
        svc = FaithfulnessService()
        result = await svc.score("prompt", "response", "")
        assert result == (None, None)

    async def test_returns_none_when_response_missing(self):
        svc = FaithfulnessService()
        result = await svc.score("prompt", "", "some context")
        assert result == (None, None)

    async def test_returns_none_when_no_api_key_configured(self):
        svc = FaithfulnessService()
        with patch("app.services.faithfulness_service.settings_service") as mock_settings:
            mock_settings.get.return_value = None
            result = await svc.score("prompt", "response", "context")
        assert result == (None, None)

    async def test_success_path_returns_rounded_scores(self):
        svc = FaithfulnessService()

        faithfulness_result = MagicMock(value=0.8234567)
        context_result = MagicMock(value=0.71)

        mock_faithfulness_metric = MagicMock()
        mock_faithfulness_metric.ascore = AsyncMock(return_value=faithfulness_result)
        mock_context_metric = MagicMock()
        mock_context_metric.ascore = AsyncMock(return_value=context_result)

        with patch("app.services.faithfulness_service.settings_service") as mock_settings, \
             patch("ragas.llms.base.llm_factory", return_value=MagicMock()), \
             patch("ragas.metrics.collections.Faithfulness", return_value=mock_faithfulness_metric), \
             patch("ragas.metrics.collections.ContextUtilization", return_value=mock_context_metric):
            mock_settings.get.return_value = "sk-test-key"
            faithfulness, context_utilization = await svc.score(
                "What is the capital?", "Paris is the capital.", "Paris is the capital of France."
            )

        assert faithfulness == 0.8235
        assert context_utilization == 0.71

    async def test_ragas_failure_returns_none_none(self):
        svc = FaithfulnessService()

        with patch("app.services.faithfulness_service.settings_service") as mock_settings, \
             patch("ragas.llms.base.llm_factory", side_effect=RuntimeError("judge init failed")):
            mock_settings.get.return_value = "sk-test-key"
            result = await svc.score("prompt", "response", "context")

        assert result == (None, None)

    async def test_client_is_cached_across_calls(self):
        svc = FaithfulnessService()
        with patch("app.services.faithfulness_service.settings_service") as mock_settings:
            mock_settings.get.return_value = "sk-test-key"
            client1 = svc._get_client()
            client2 = svc._get_client()
        assert client1 is client2


class TestFaithfulnessServiceClean:
    def test_clean_none_returns_none(self):
        assert FaithfulnessService._clean(None) is None

    def test_clean_nan_returns_none(self):
        assert FaithfulnessService._clean(float("nan")) is None

    def test_clean_non_numeric_returns_none(self):
        assert FaithfulnessService._clean("not-a-number") is None

    def test_clean_rounds_to_four_places(self):
        assert FaithfulnessService._clean(0.123456789) == 0.1235
