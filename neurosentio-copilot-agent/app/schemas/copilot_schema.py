"""Pydantic schemas for Copilot dashboard, context, and plan."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.task_schema import Task
from app.schemas.energy_log_schema import Energy
from app.schemas.user_profile_schema import Profile
from app.schemas.calendar_schema import CalendarDaySummary



# ──────────────────────────────────────────────
# Shared building blocks
# ──────────────────────────────────────────────
class NextAction(BaseModel):
    type: str                                   # planned_micro_action | existing_micro_action | needs_decomposition | add_task | log_energy | recovery
    message: str
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    micro_action_id: Optional[str] = None
    micro_action_title: Optional[str] = None
    duration_minutes: Optional[int] = None
    energy_cost: Optional[str] = None
    sensory_cost: Optional[str] = None
    friction_level: Optional[str] = None


class Recovery(BaseModel):
    message: str
    suggestions: List[str] = []


# ──────────────────────────────────────────────
# GET /copilot/dashboard
# ──────────────────────────────────────────────
class Dashboard(BaseModel):
    user_id: str
    mode: str  # normal | recovery
    latest_energy: Optional[Energy] = None
    open_tasks_count: int
    high_priority_tasks_count: int
    open_tasks: List[Task]
    suggested_next_action: Optional[NextAction] = None
    recovery_recommendation: Optional[Recovery] = None
    # Reply drafter integration (Day 8) — optional, never breaks dashboard if absent
    reply_drafts_count: int = 0
    latest_reply_draft_id: Optional[str] = None
    latest_reply_draft_subject: Optional[str] = None
    # Day 10 addition: llm usage transparent reporting
    llm_usage_summary: Optional[dict] = None
    
    # Context Intelligence Pack (Day 9-10)
    calendar_day_summary: Optional[CalendarDaySummary] = None
    energy_patterns_summary: Optional[dict] = None
    stuck_tasks_count: Optional[int] = 0
    recent_overload_events_count: Optional[int] = 0

    # Execution Automation Pack
    message_summary: Optional[dict] = None
    next_action_prompt: Optional[dict] = None
    recent_replan_events_count: Optional[int] = 0
    urgent_messages_count: Optional[int] = 0
    needs_reply_count: Optional[int] = 0



# ──────────────────────────────────────────────
# GET /copilot/context
# ──────────────────────────────────────────────
class Context(BaseModel):
    profile: Optional[Profile] = None
    latest_energy: Optional[Energy] = None
    open_tasks: List[Task]
    recent_energy_logs: List[Energy]


# ──────────────────────────────────────────────
# POST /copilot/quick-plan
# ──────────────────────────────────────────────
class Plan(BaseModel):
    mode: str  # normal | recovery
    summary: str
    suggested_next_action: Optional[NextAction] = None
    recovery_recommendation: Optional[Recovery] = None
    selected_tasks: List[Task]


class OverloadEventResponse(BaseModel):
    id: str
    user_id: str
    detected_at: datetime
    risk_score: int
    mode: str
    trigger_reasons: List[str]
    energy_score: Optional[int] = None
    calendar_load_score: Optional[int] = None
    open_task_count: Optional[int] = None
    high_priority_task_count: Optional[int] = None
    stuck_task_count: Optional[int] = None
    message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

