"""NextActionPrompt ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class NextActionPrompt(Base):
    __tablename__ = "next_action_prompts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Allowed: micro_action, message, transition, recovery, task, system
    source_type = Column(String, nullable=False)
    source_id = Column(String, nullable=True)

    # Allowed: do_micro_action, draft_reply, take_recovery_break, generate_transition,
    #          decompose_task, log_energy, review_plan
    action_type = Column(String, nullable=False)

    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)

    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    energy_cost = Column(String, nullable=True)
    sensory_cost = Column(String, nullable=True)
    friction_level = Column(String, nullable=True)

    # Allowed: active, done, snoozed, skipped, deferred, expired
    status = Column(String, nullable=False, default="active")

    snoozed_until = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_nap_status", "status"),
        Index("ix_nap_scheduled_for", "scheduled_for"),
        Index("ix_nap_source_type", "source_type"),
        Index("ix_nap_action_type", "action_type"),
    )
