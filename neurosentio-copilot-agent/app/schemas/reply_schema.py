"""Pydantic schemas for Reply Drafter (Day 7)."""

from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ── Allowed enumerations ────────────────────────────────────────────────
DraftOptionType = Literal["short", "warm", "detailed", "boundary"]
DraftStatus = Literal["drafted", "edited", "selected", "archived", "deleted"]
MessageChannel = Literal["manual", "email", "sms", "whatsapp", "slack", "other"]
SourceType = Literal["manual", "email", "text", "other"]
DraftSource = Literal["mock", "llm", "fallback"]


# ── 1. Single draft option ──────────────────────────────────────────────
class ReplyDraftOption(BaseModel):
    type: DraftOptionType
    text: str = Field(min_length=1, max_length=4000)


# ── 2. Request body ─────────────────────────────────────────────────────
class ReplyDraftRequest(BaseModel):
    original_message: str = Field(min_length=3, max_length=10000)
    message_sender: Optional[str] = None
    message_subject: Optional[str] = None
    message_channel: MessageChannel = "manual"
    user_intent: Optional[str] = None
    preferred_tone: Optional[str] = None
    context_note: Optional[str] = None
    include_boundary_option: bool = True
    max_length: Optional[Literal["short", "medium", "detailed"]] = None
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)


# ── 3. Full response entity ─────────────────────────────────────────────
class ReplyDraft(BaseModel):
    id: str
    user_id: str
    source_type: str
    original_message: str
    message_sender: Optional[str] = None
    message_subject: Optional[str] = None
    message_channel: str
    user_intent: Optional[str] = None
    preferred_tone: Optional[str] = None
    context_note: Optional[str] = None
    draft_options: List[ReplyDraftOption]
    selected_option_type: Optional[str] = None
    edited_reply: Optional[str] = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 4. Update request ───────────────────────────────────────────────────
class ReplyDraftUpdate(BaseModel):
    selected_option_type: Optional[DraftOptionType] = None
    edited_reply: Optional[str] = None
    status: Optional[DraftStatus] = None

    @field_validator("status")
    @classmethod
    def status_not_sent(cls, v):
        # The agent never sends messages — "sent" is not a valid status
        if v == "sent":
            raise ValueError("The agent does not send messages. Use 'selected' or 'edited'.")
        return v


# ── 5. List item (lighter shape) ────────────────────────────────────────
class ReplyDraftListItem(BaseModel):
    id: str
    user_id: str
    message_sender: Optional[str] = None
    message_subject: Optional[str] = None
    message_channel: str
    user_intent: Optional[str] = None
    selected_option_type: Optional[str] = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 6. Internal LLM output validation ──────────────────────────────────
class ReplyDraftLLMOutput(BaseModel):
    draft_options: List[ReplyDraftOption]

    @field_validator("draft_options")
    @classmethod
    def required_types_present(cls, v):
        types = {opt.type for opt in v}
        for required in ("short", "warm", "detailed"):
            if required not in types:
                raise ValueError(f"LLM output missing required draft type: '{required}'")
        return v


# ── 7. Soft delete response ─────────────────────────────────────────────
class ReplyDraftDeleteResponse(BaseModel):
    deleted: bool
    id: str
