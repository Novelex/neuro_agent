"""UserProfile ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False, index=True)

    # Tone & communication preferences
    preferred_tone = Column(String, nullable=False, default="gentle_direct")
    max_reply_length = Column(String, nullable=False, default="short")

    # Energy windows
    peak_energy_hours = Column(JSON, nullable=False, default=list)
    low_energy_hours = Column(JSON, nullable=False, default=list)

    # Sensory & support preferences
    sensory_triggers = Column(JSON, nullable=False, default=list)
    recovery_preferences = Column(JSON, nullable=False, default=list)
    transition_support_needed = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
