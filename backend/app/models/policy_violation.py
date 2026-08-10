import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.sql import func
from sqlalchemy import DateTime

from app.core.database import Base


class PolicyViolation(Base):
    __tablename__ = "policy_violations"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    rule_id = Column(String, nullable=False)
    rule_name = Column(String, nullable=False)
    action = Column(String, nullable=False)   # "block" | "warn" | "alert"
    severity = Column(String, nullable=False)  # "low" | "medium" | "high" | "critical"
    message = Column(String, nullable=True)
    prompt_preview = Column(String, nullable=True)  # first 200 chars of prompt
    provider = Column(String, nullable=True)
    model_id = Column(String, nullable=True)
    pii_detected = Column(Integer, default=0)  # stored as 0/1 for broad DB compat
    safety_score = Column(Float, nullable=True)
    faithfulness_score = Column(Float, nullable=True)  # set only for post-response violations
    webhook_status = Column(String, nullable=True)  # "sent" | "failed" | "not_configured"
