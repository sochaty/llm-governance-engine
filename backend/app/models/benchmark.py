import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import Column, Integer, String, Float, DateTime
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