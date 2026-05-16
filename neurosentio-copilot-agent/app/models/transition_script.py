"""TransitionScript ORM model (Day 6)."""

import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class TransitionScript(Base):
    __tablename__ = "transition_scripts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Allowed: leaving_house, starting_work, making_call, ending_day,
    #          context_switch, recovery_break, custom
    transition_type = Column(String, nullable=False, index=True)

    title = Column(String, nullable=False)

    # Stored as JSON list of step strings
    script_steps = Column(JSON, nullable=False, default=list)

    # Optional user-facing context or note
    context = Column(Text, nullable=True)

    # Tone hint: gentle | direct | calm | energising
    tone = Column(String, nullable=True, default="gentle")

    # Allowed: mock | llm | fallback | manual
    source = Column(String, nullable=False, default="mock")

    # User-rated 1–5 after using the script
    success_rating = Column(Integer, nullable=True)

    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
