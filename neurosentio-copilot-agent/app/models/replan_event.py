"""ReplanEvent ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class ReplanEvent(Base):
    __tablename__ = "replan_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Allowed: low_energy, skipped_actions, calendar_overload, urgent_message,
    #          manual, recovery_mode, stuck_tasks
    trigger_type = Column(String, nullable=False)
    trigger_details = Column(JSON, nullable=True)

    previous_plan_id = Column(String, nullable=True)
    new_plan_id = Column(String, nullable=True)

    mode_before = Column(String, nullable=True)
    mode_after = Column(String, nullable=True)

    actions_preserved_count = Column(Integer, nullable=False, default=0)
    actions_deferred_count = Column(Integer, nullable=False, default=0)
    actions_added_count = Column(Integer, nullable=False, default=0)

    summary = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_replan_events_trigger_type", "trigger_type"),
        Index("ix_replan_events_created_at", "created_at"),
    )
