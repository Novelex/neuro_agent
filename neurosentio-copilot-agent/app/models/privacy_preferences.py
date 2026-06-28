"""PrivacyPreferences ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class PrivacyPreferences(Base):
    __tablename__ = "privacy_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False, index=True)

    # Granular storage settings
    store_reply_original_messages = Column(Boolean, nullable=False, default=True)
    store_message_snippets = Column(Boolean, nullable=False, default=True)
    store_calendar_titles = Column(Boolean, nullable=False, default=True)
    store_task_descriptions = Column(Boolean, nullable=False, default=True)
    redact_sensitive_metadata = Column(Boolean, nullable=False, default=True)

    # Data retention settings (in days, null means keep indefinitely)
    retention_days_reply_drafts = Column(Integer, nullable=True, default=None)
    retention_days_messages = Column(Integer, nullable=True, default=None)
    retention_days_calendar_events = Column(Integer, nullable=True, default=None)
    retention_days_llm_usage_logs = Column(Integer, nullable=True, default=None)

    allow_usage_analytics = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
