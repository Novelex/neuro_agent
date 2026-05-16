"""Pydantic schemas for UserProfile."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────
class ProfileBase(BaseModel):
    preferred_tone: str = "gentle_direct"
    max_reply_length: str = "short"
    peak_energy_hours: List[int] = Field(default_factory=list)
    low_energy_hours: List[int] = Field(default_factory=list)
    sensory_triggers: List[str] = Field(default_factory=list)
    recovery_preferences: List[str] = Field(default_factory=list)
    transition_support_needed: bool = True


# ──────────────────────────────────────────────
# Create (used internally when auto-creating default profile)
# ──────────────────────────────────────────────
class ProfileCreate(ProfileBase):
    user_id: str


# ──────────────────────────────────────────────
# Update (PUT /profile — all fields optional)
# ──────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    preferred_tone: Optional[str] = None
    max_reply_length: Optional[str] = None
    peak_energy_hours: Optional[List[int]] = None
    low_energy_hours: Optional[List[int]] = None
    sensory_triggers: Optional[List[str]] = None
    recovery_preferences: Optional[List[str]] = None
    transition_support_needed: Optional[bool] = None


# ──────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────
class Profile(ProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
