from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, func

from app.core.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(120), primary_key=True)
    encrypted_value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
