from __future__ import annotations

import logging
from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII scan result types — used by the governance policy engine.
# ---------------------------------------------------------------------------

@dataclass
class PIIEntity:
    entity_type: str
    score: float


@dataclass
class PIIScanResult:
    detected: bool
    entities: list[PIIEntity] = field(default_factory=list)
    max_confidence: float = 0.0


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------

class AuditService:
    def __init__(self) -> None:
        # Loading the spaCy NLP model takes a few seconds — done once at init.
        self.engine = AnalyzerEngine()

    # ------------------------------------------------------------------
    # Original interface (kept for backward compatibility with existing code
    # and tests that mock these methods directly).
    # ------------------------------------------------------------------

    def scan_for_pii(self, text: str) -> bool:
        """Return True if any PII entity is detected in text."""
        if not text:
            return False
        try:
            results = self.engine.analyze(text=text, entities=[], language="en")
            if results:
                logger.warning(
                    "PII detected! Types: %s", [r.entity_type for r in results]
                )
                return True
            return False
        except Exception as exc:
            logger.error("PII scan failed: %s", exc)
            return False

    def calculate_safety_score(self, text: str) -> float:
        """Compute a 0.0-1.0 safety score for text via Presidio confidence inversion.

        Returns 0.98 for clean text. Caps at 0.50 if any PII is detected.
        Note: expects a string — passing a non-string raises TypeError.
        """
        results = self.engine.analyze(text=text, entities=[], language="en")
        if not results:
            return 0.98
        max_pii_confidence = max(r.score for r in results)
        safety_base = 1.0 - max_pii_confidence
        return round(min(safety_base, 0.50), 2)

    # ------------------------------------------------------------------
    # Rich scan — used by the governance policy engine.
    # ------------------------------------------------------------------

    def scan_for_pii_details(self, text: str) -> PIIScanResult:
        """Return a PIIScanResult with entity types and confidence scores.

        Used by the policy enforcement layer so rules can apply per-entity
        thresholds without re-scanning the text a second time.
        """
        if not text:
            return PIIScanResult(detected=False)
        try:
            results = self.engine.analyze(text=text, entities=[], language="en")
            if not results:
                return PIIScanResult(detected=False)
            entities = [PIIEntity(entity_type=r.entity_type, score=r.score) for r in results]
            max_conf = max(e.score for e in entities)
            logger.warning(
                "PII detected (detailed scan)! Types: %s",
                [e.entity_type for e in entities],
            )
            return PIIScanResult(detected=True, entities=entities, max_confidence=max_conf)
        except Exception as exc:
            logger.error("PII detailed scan failed: %s", exc)
            return PIIScanResult(detected=False)
