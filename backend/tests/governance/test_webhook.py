"""Async tests for WebhookDelivery and WebhookEvent.

Uses httpx.MockTransport so no real HTTP calls are made.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.governance.policy.webhook import WebhookDelivery, WebhookEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_event() -> WebhookEvent:
    return WebhookEvent(
        rule_id="test-pii",
        rule_name="Test PII Rule",
        severity="critical",
        action="block",
        message="PII detected: EMAIL_ADDRESS",
        provider="cloud",
        model_id="gpt-4o",
    )


# ---------------------------------------------------------------------------
# Tests: WebhookEvent shape
# ---------------------------------------------------------------------------

class TestWebhookEvent:
    def test_to_dict_has_cloudevents_fields(self):
        event = _make_event()
        d = event.to_dict()
        assert d["specversion"] == "1.0"
        assert d["type"] == "io.llm-governance.policy.violation"
        assert d["source"] == "llm-governance-engine"
        assert "time" in d
        assert "data" in d

    def test_data_contains_rule_info(self):
        event = _make_event()
        data = event.to_dict()["data"]
        assert data["rule_id"] == "test-pii"
        assert data["rule_name"] == "Test PII Rule"
        assert data["severity"] == "critical"
        assert data["action"] == "block"
        assert data["provider"] == "cloud"
        assert data["model_id"] == "gpt-4o"

    def test_time_is_iso8601(self):
        from datetime import datetime
        event = _make_event()
        d = event.to_dict()
        # Should parse without raising
        datetime.fromisoformat(d["time"].replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Tests: WebhookDelivery — successful delivery
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestWebhookDeliverySuccess:
    async def test_returns_true_on_200(self):
        delivery = WebhookDelivery(max_retries=3)
        event = _make_event()

        async def mock_post(*args, **kwargs):
            return httpx.Response(200)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is True

    async def test_returns_true_on_201(self):
        delivery = WebhookDelivery(max_retries=3)
        event = _make_event()

        async def mock_post(*args, **kwargs):
            return httpx.Response(201)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is True

    async def test_sends_cloudevents_content_type(self):
        delivery = WebhookDelivery(max_retries=1)
        event = _make_event()
        captured_headers = {}

        async def mock_post(url, *, json, headers, **kwargs):
            captured_headers.update(headers)
            return httpx.Response(200)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            await delivery.send("http://example.com/webhook", event)

        assert captured_headers.get("Content-Type") == "application/cloudevents+json"


# ---------------------------------------------------------------------------
# Tests: WebhookDelivery — retry logic
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestWebhookDeliveryRetry:
    async def test_retries_on_500_and_succeeds_eventually(self):
        delivery = WebhookDelivery(max_retries=3, base_delay_seconds=0.0)
        event = _make_event()
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500)
            return httpx.Response(200)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is True
        assert call_count == 3

    async def test_returns_false_after_max_retries(self):
        delivery = WebhookDelivery(max_retries=3, base_delay_seconds=0.0)
        event = _make_event()

        async def mock_post(*args, **kwargs):
            return httpx.Response(500)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is False

    async def test_retries_on_connection_error(self):
        delivery = WebhookDelivery(max_retries=3, base_delay_seconds=0.0)
        event = _make_event()
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is True
        assert call_count == 3

    async def test_returns_false_after_all_connection_errors(self):
        delivery = WebhookDelivery(max_retries=2, base_delay_seconds=0.0)
        event = _make_event()

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("No route to host")

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            result = await delivery.send("http://example.com/webhook", event)

        assert result is False

    async def test_does_not_retry_on_success(self):
        delivery = WebhookDelivery(max_retries=3, base_delay_seconds=0.0)
        event = _make_event()
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200)

        with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
            await delivery.send("http://example.com/webhook", event)

        assert call_count == 1
