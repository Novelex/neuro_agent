"""Pydantic schemas for TransitionScript (Day 6)."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

TransitionTypeEnum = Literal[
    "leaving_house",
    "starting_work",
    "making_call",
    "ending_day",
    "context_switch",
    "recovery_break",
    "custom",
]


# ──────────────────────────────────────────────
# Core entity
# ──────────────────────────────────────────────
class TransitionScript(BaseModel):
    id: str
    user_id: str
    transition_type: str
    title: str
    script_steps: List[str]
    context: Optional[str] = None
    tone: Optional[str] = None
    source: str = "mock"                      # mock | llm | fallback | manual
    success_rating: Optional[int] = None      # 1–5
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Create (internal)
# ──────────────────────────────────────────────
class TransitionScriptCreate(BaseModel):
    transition_type: str
    title: str
    script_steps: List[str]
    context: Optional[str] = None
    tone: Optional[str] = None
    source: str = "mock"


# ──────────────────────────────────────────────
# Generate request  (POST /transitions/generate)
# ──────────────────────────────────────────────
class TransitionScriptGenerateRequest(BaseModel):
    transition_type: TransitionTypeEnum
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)
    sensory_state: Optional[str] = None
    next_task_title: Optional[str] = None
    context_note: Optional[str] = None
    max_steps: int = Field(default=5, ge=2, le=8)


# ──────────────────────────────────────────────
# Generate response
# ──────────────────────────────────────────────
class TransitionScriptGenerateResponse(BaseModel):
    id: str
    transition_type: str
    title: str
    script_steps: List[str]
    source: str
    message: str


# ──────────────────────────────────────────────
# Rating update  (PATCH /transitions/{id}/rating)
# ──────────────────────────────────────────────
class TransitionScriptRatingUpdate(BaseModel):
    success_rating: int = Field(ge=1, le=5)


# ──────────────────────────────────────────────
# Internal LLM Output
# ──────────────────────────────────────────────
class TransitionScriptLLMOutput(BaseModel):
    script_steps: List[str] = Field(min_length=1, max_length=8)

