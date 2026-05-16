"""Pydantic schemas for Copilot dashboard, context, and plan."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.task_schema import Task
from app.schemas.energy_log_schema import Energy
from app.schemas.user_profile_schema import Profile


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
