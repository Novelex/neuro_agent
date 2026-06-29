"""MicroAction ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class MicroAction(Base):
    __tablename__ = "micro_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Optional references (soft FK — not enforced at DB level for portability)
    # WARNING: Because there are no Foreign Key constraints, there is a risk of orphaned data.
    # The application layer (data_delete_service.py) is entirely responsible for cascading deletes.
    task_id = Column(String, nullable=True)
    plan_id = Column(String, nullable=True)

    # Self-reference: when make-smaller creates children, they store the parent id
    parent_micro_action_id = Column(String, nullable=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Allowed: low, medium, high, None
    energy_cost = Column(String, nullable=True)
    sensory_cost = Column(String, nullable=True)
    friction_level = Column(String, nullable=True)

    # Allowed: open, done, snoozed, skipped, deferred
    status = Column(String, nullable=False, default="open")

    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
