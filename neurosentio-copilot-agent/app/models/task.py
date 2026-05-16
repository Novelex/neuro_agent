"""Task ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Date
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    # Allowed: low, medium, high
    priority = Column(String, nullable=False, default="medium")

    # Allowed: open, in_progress, done, skipped, deferred
    status = Column(String, nullable=False, default="open")

    # Allowed: low, medium, high, None
    estimated_energy = Column(String, nullable=True)
    estimated_sensory_cost = Column(String, nullable=True)

    last_touched_at = Column(DateTime(timezone=True), nullable=True)

    # Source of the task: manual, copilot, imported, etc.
    source = Column(String, nullable=False, default="manual")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
