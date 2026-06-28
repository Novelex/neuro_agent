"""MessageItem ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class MessageItem(Base):
    __tablename__ = "message_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Allowed: manual, mock, gmail, sms, whatsapp, slack, other
    source = Column(String, nullable=False, default="manual")

    external_message_id = Column(String, nullable=True)

    # Allowed: manual, email, sms, whatsapp, slack, other
    channel = Column(String, nullable=False, default="manual")

    sender = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    snippet = Column(String, nullable=True)  # max 500 chars — no full body

    received_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    is_read = Column(Boolean, nullable=False, default=False)
    needs_reply = Column(Boolean, nullable=False, default=False)

    urgency_score = Column(Integer, nullable=False, default=0)  # 0-100

    # Allowed: question, request, deadline, scheduling, follow_up, urgent, FYI, unknown
    detected_intent = Column(String, nullable=False, default="unknown")

    detected_keywords = Column(JSON, nullable=True)  # list of keyword strings
    extra_metadata = Column("metadata", JSON, nullable=True)  # sanitized only

    linked_reply_draft_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_message_items_user_received", "user_id", "received_at"),
        Index("ix_message_items_urgency", "urgency_score"),
        Index("ix_message_items_needs_reply", "needs_reply"),
        Index("ix_message_items_detected_intent", "detected_intent"),
    )
