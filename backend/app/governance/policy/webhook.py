from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookEvent:
    """CloudEvents 1.0 payload for a governance policy violation."""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        severity: str,
        action: str,
        message: str,
        provider: str,
        model_id: str,
    ) -> None:
        self.specversion = "1.0"
        self.type = "io.llm-governance.policy.violation"
        self.source = "llm-governance-engine"
        self.time = datetime.now(timezone.utc).isoformat()
        self.data: dict[str, Any] = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "severity": severity,
            "action": action,
            "message": message,
            "provider": provider,
            "model_id": model_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "specversion": self.specversion,
            "type": self.type,
            "source": self.source,
            "time": self.time,
            "data": self.data,
        }


class WebhookDelivery:
    """Delivers CloudEvents to configured webhook URLs with exponential-backoff retry."""

    def __init__(self, max_retries: int = 3, base_delay_seconds: float = 1.0) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay_seconds

    async def send(self, webhook_url: str, event: WebhookEvent) -> bool:
        payload = event.to_dict()
        headers = {
            "Content-Type": "application/cloudevents+json",
            "User-Agent": "llm-governance-engine/1.0",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    resp = await client.post(webhook_url, json=payload, headers=headers)
                    if resp.status_code < 400:
                        logger.info(
                            "Webhook delivered | url=%s attempt=%d", webhook_url, attempt
                        )
                        return True
                    logger.warning(
                        "Webhook returned %d | url=%s attempt=%d",
                        resp.status_code,
                        webhook_url,
                        attempt,
                    )
                except httpx.RequestError as exc:
                    logger.warning(
                        "Webhook request error | url=%s attempt=%d | %s",
                        webhook_url,
                        attempt,
                        exc,
                    )

                if attempt < self._max_retries:
                    await asyncio.sleep(self._base_delay * (2 ** (attempt - 1)))

        logger.error(
            "Webhook delivery failed after %d attempts | url=%s",
            self._max_retries,
            webhook_url,
        )
        return False
