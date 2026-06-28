"""ReplyDraft ORM model (Day 7)."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Source of the original message
    # Allowed: manual | email | text | other
    # (email/text are future placeholders — no real integration yet)
    source_type = Column(String, nullable=False, default="manual")

    # The raw message the user pasted in
    original_message = Column(Text, nullable=False)

    # Optional metadata about the original message
    message_sender = Column(String, nullable=True)
    message_subject = Column(String, nullable=True)

    # Channel the message came from
    # Allowed: manual | email | sms | whatsapp | slack | other
    message_channel = Column(String, nullable=False, default="manual")

    # What the user wants to achieve with the reply
    user_intent = Column(Text, nullable=True)

    # Tone the user prefers (pulled from profile or request)
    preferred_tone = Column(String, nullable=True)

    # Extra context the user provided to guide drafting
    context_note = Column(Text, nullable=True)

    # JSON list of draft options: [{type, text}, ...]
    # Types: short | warm | detailed | boundary
    draft_options = Column(JSON, nullable=False, default=list)

    # Which option the user selected (if any)
    selected_option_type = Column(String, nullable=True)

    # The user's edited version of the reply
    edited_reply = Column(Text, nullable=True)

    # Allowed: drafted | edited | selected | archived | deleted
    status = Column(String, nullable=False, default="drafted", index=True)

    # Which system generated the drafts
    # Allowed: mock | llm | fallback
    source = Column(String, nullable=False, default="mock")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_reply_drafts_user_channel", "user_id", "message_channel"),
    )
