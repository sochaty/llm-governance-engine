from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel


class PolicyCondition(str, Enum):
    PII_DETECTED = "pii_detected"
    SAFETY_SCORE_BELOW = "safety_score_below"
    COST_EXCEEDS = "cost_exceeds"
    MODEL_IS = "model_is"


class PolicyRule(BaseModel):
    id: str
    name: str
    description: str = ""
    condition: PolicyCondition
    # threshold meaning depends on condition:
    #   pii_detected      → minimum PII confidence to trigger (0.0 = any PII)
    #   safety_score_below → score must be below this value
    #   cost_exceeds      → USD amount per request
    #   model_is          → unused (filter via `models`)
    threshold: Optional[float] = None
    models: Optional[List[str]] = None  # None = applies to all models
    action: Literal["block", "warn", "alert"]
    severity: Literal["low", "medium", "high", "critical"]
    webhook_url: Optional[str] = None


class GovernancePolicy(BaseModel):
    version: str = "1.0"
    name: str = "default"
    rules: List[PolicyRule] = []


@dataclass
class GovernanceContext:
    """All data available to the policy engine for a single inference request."""
    prompt: str
    provider: str
    model_id: str
    pii_detected: bool
    pii_entity_types: List[str]
    pii_max_confidence: float
    safety_score: float
    estimated_prompt_cost_usd: float


class ViolatedRule(BaseModel):
    rule_id: str
    rule_name: str
    action: str
    severity: str
    message: str


class PolicyVerdict(BaseModel):
    passed: bool
    violated_rules: List[ViolatedRule] = []
    blocking_rule: Optional[ViolatedRule] = None
    warnings: List[str] = []
