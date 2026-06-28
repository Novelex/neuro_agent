"""Pydantic schemas for Message Monitor."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, model_validator
from app.schemas.reply_schema import ReplyDraft


# ────────────────────────────────────────────────
# Request schemas
# ────────────────────────────────────────────────

class MessageItemCreate(BaseModel):
    source: str = Field(default="manual")
    external_message_id: Optional[str] = None
    channel: str = Field(default="manual")
    sender: Optional[str] = Field(default=None, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=300)
    snippet: Optional[str] = Field(default=None, max_length=500)
    received_at: Optional[datetime] = None
    is_read: bool = False
    metadata: Optional[dict] = None


class MessageImportRequest(BaseModel):
    messages: List[MessageItemCreate]


class MessageDraftRequest(BaseModel):
    message_id: str
    user_intent: Optional[str] = None
    preferred_tone: Optional[str] = None
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)


# ────────────────────────────────────────────────
# Response schemas
# ────────────────────────────────────────────────

class MessageItem(BaseModel):
    id: str
    user_id: str
    source: str
    external_message_id: Optional[str] = None
    channel: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    snippet: Optional[str] = None
    received_at: datetime
    is_read: bool
    needs_reply: bool
    urgency_score: int
    detected_intent: str
    detected_keywords: Optional[list] = None
    metadata: Optional[dict] = None
    linked_reply_draft_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def map_extra_metadata(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        if hasattr(data, "extra_metadata"):
            res = {}
            for field_name in cls.model_fields.keys():
                if field_name == "metadata":
                    res["metadata"] = getattr(data, "extra_metadata", None)
                else:
                    res[field_name] = getattr(data, field_name, None)
            return res
        return data


class MessageImportResponse(BaseModel):
    imported_count: int
    updated_count: int
    messages: List[MessageItem]


class TopUrgentMessage(BaseModel):
    id: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    urgency_score: int
    detected_intent: str


class MessageSummary(BaseModel):
    total_count: int
    unread_count: int
    needs_reply_count: int
    urgent_count: int
    top_urgent_messages: List[TopUrgentMessage] = []
    recommendation: str


class MessageUpdate(BaseModel):
    is_read: Optional[bool] = None
    needs_reply: Optional[bool] = None
    linked_reply_draft_id: Optional[str] = None
