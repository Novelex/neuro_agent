"""CalendarEvent ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    provider = Column(String, nullable=False, default="manual")
    external_event_id = Column(String, nullable=True)
    calendar_id = Column(String, nullable=True)

    title = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String, nullable=True)
    location = Column(String, nullable=True)

    attendee_count = Column(Integer, nullable=False, default=0)
    meeting_type = Column(String, nullable=False, default="unknown", index=True)
    load_score = Column(Integer, nullable=False, default=0)
    energy_cost = Column(String, nullable=False, default="low")
    sensory_cost = Column(String, nullable=False, default="low")

    is_back_to_back = Column(Boolean, nullable=False, default=False, index=True)
    is_busy = Column(Boolean, nullable=False, default=True)

    raw_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


# Create composite and unique indexes
# Uniqueness: user_id + provider + external_event_id
# Note: SQLite treats NULL values as distinct, which allows multiple manual/NULL events safely.
Index("idx_user_start_time", CalendarEvent.user_id, CalendarEvent.start_time)
Index(
    "idx_user_provider_ext_event_id",
    CalendarEvent.user_id,
    CalendarEvent.provider,
    CalendarEvent.external_event_id,
    unique=True
)
