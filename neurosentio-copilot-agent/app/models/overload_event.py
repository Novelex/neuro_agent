"""OverloadEvent ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class OverloadEvent(Base):
    __tablename__ = "overload_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    detected_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    risk_score = Column(Integer, nullable=False)
    mode = Column(String, nullable=False)  # "normal" | "recovery"

    # List of triggers as a JSON array
    trigger_reasons = Column(JSON, nullable=False)

    energy_score = Column(Integer, nullable=True)
    calendar_load_score = Column(Integer, nullable=True)
    open_task_count = Column(Integer, nullable=True)
    high_priority_task_count = Column(Integer, nullable=True)
    stuck_task_count = Column(Integer, nullable=True)

    message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


# composite index for querying recent overload events by user
Index("idx_user_detected_at", OverloadEvent.user_id, OverloadEvent.detected_at)
