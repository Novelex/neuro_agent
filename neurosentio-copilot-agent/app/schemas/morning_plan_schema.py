"""Pydantic schemas for Morning Plan (Day 5)."""

from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Request
# ──────────────────────────────────────────────
class MorningPlanRequest(BaseModel):
    plan_date: Optional[date] = None          # defaults to today in service
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)
    sensory_state: Optional[str] = None
    available_minutes: int = Field(default=120, ge=10, le=480)
    start_time: str = "09:00"
    force_regenerate: bool = False
    auto_decompose: bool = True
    include_transition_scripts: bool = True


# ──────────────────────────────────────────────
# Nested items
# ──────────────────────────────────────────────
class PlannedMicroAction(BaseModel):
    micro_action_id: str
    task_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[str] = None      # e.g. "09:00"
    duration_minutes: Optional[int] = None
    energy_cost: Optional[str] = None
    sensory_cost: Optional[str] = None
    friction_level: Optional[str] = None
    status: str = "open"


class RecoveryBlock(BaseModel):
    title: str
    reason: str
    suggested_duration_minutes: int = 10


class TransitionSuggestion(BaseModel):
    transition_type: str
    title: str
    script_preview: str                       # first step only, as a teaser


# ──────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────
class MorningPlan(BaseModel):
    plan_id: str
    plan_date: date
    mode: str                                 # normal | recovery
    summary: str
    total_scheduled_minutes: int = 0          # estimated total minutes
    overload_risk_score: int = 0
    selected_micro_actions: List[PlannedMicroAction] = []
    recovery_blocks: List[RecoveryBlock] = []
    transition_suggestions: List[TransitionSuggestion] = []
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
