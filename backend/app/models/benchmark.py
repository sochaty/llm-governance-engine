from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class BenchmarkResult(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(String)
    provider = Column(String) # 'cloud' or 'local'
    model_name = Column(String)
    latency_ms = Column(Integer)
    token_count = Column(Integer, nullable=True)
    estimated_cost = Column(Float, default=0.0) # Calculated ROI
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    response_preview = Column(String, nullable=True)
    pii_detected = Column(Boolean, default=False)
    safety_score = Column(Float)      # 0.0 - 1.0
    faithfulness_score = Column(Float) # 0.0 - 1.0
    context_utilization = Column(Float) # Percentage
    gpu_mem_usage = Column(Integer)    # In MB
    energy_watts = Column(Float)       # Estimated power
    version_tag = Column(String)       # e.g., "gpt-4o-2024-05-13" or "llama3.2:latest"