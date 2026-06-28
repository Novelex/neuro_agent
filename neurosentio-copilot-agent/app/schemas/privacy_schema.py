"""Pydantic schemas for Privacy and Data Controls."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
# Privacy Preferences Base
# ──────────────────────────────────────────────
class PrivacyPreferencesBase(BaseModel):
    store_reply_original_messages: bool = True
    store_message_snippets: bool = True
    store_calendar_titles: bool = True
    store_task_descriptions: bool = True
    redact_sensitive_metadata: bool = True

    # Retention days validation (must be between 1 and 3650 or Null/None)
    retention_days_reply_drafts: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_messages: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_calendar_events: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_llm_usage_logs: Optional[int] = Field(None, ge=1, le=3650)

    allow_usage_analytics: bool = True


# ──────────────────────────────────────────────
# Privacy Preferences Update
# ──────────────────────────────────────────────
class PrivacyPreferencesUpdate(BaseModel):
    store_reply_original_messages: Optional[bool] = None
    store_message_snippets: Optional[bool] = None
    store_calendar_titles: Optional[bool] = None
    store_task_descriptions: Optional[bool] = None
    redact_sensitive_metadata: Optional[bool] = None

    retention_days_reply_drafts: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_messages: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_calendar_events: Optional[int] = Field(None, ge=1, le=3650)
    retention_days_llm_usage_logs: Optional[int] = Field(None, ge=1, le=3650)

    allow_usage_analytics: Optional[bool] = None


# ──────────────────────────────────────────────
# Privacy Preferences Response
# ──────────────────────────────────────────────
class PrivacyPreferencesResponse(PrivacyPreferencesBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Privacy Audit Log Response
# ──────────────────────────────────────────────
class PrivacyAuditLogResponse(BaseModel):
    id: str
    user_id: str
    action_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = Field(None)
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }
