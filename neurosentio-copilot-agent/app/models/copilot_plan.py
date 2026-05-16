"""CopilotPlan ORM model."""

import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Text, DateTime, Date
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class CopilotPlan(Base):
    __tablename__ = "copilot_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    plan_date = Column(Date, nullable=False, default=lambda: date.today())

    # Allowed: normal, recovery
    mode = Column(String, nullable=False, default="normal")

    summary = Column(Text, nullable=True)

    # Stores the full generated payload as JSON blob (future LLM response etc.)
    generated_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
