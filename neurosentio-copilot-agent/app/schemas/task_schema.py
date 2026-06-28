"""Pydantic schemas for Task."""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, Literal, List
from pydantic import BaseModel

PriorityEnum = Literal["low", "medium", "high"]
StatusEnum = Literal["open", "in_progress", "done", "skipped", "deferred"]
EnergyLevelEnum = Literal["low", "medium", "high"]


# ──────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: PriorityEnum = "medium"
    estimated_energy: Optional[EnergyLevelEnum] = None
    estimated_sensory_cost: Optional[EnergyLevelEnum] = None
    source: str = "manual"


# ──────────────────────────────────────────────
# Create (POST /tasks)
# ──────────────────────────────────────────────
class TaskCreate(TaskBase):
    pass


# ──────────────────────────────────────────────
# Update (PATCH /tasks/{id})
# ──────────────────────────────────────────────
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[PriorityEnum] = None
    status: Optional[StatusEnum] = None
    estimated_energy: Optional[EnergyLevelEnum] = None
    estimated_sensory_cost: Optional[EnergyLevelEnum] = None


# ──────────────────────────────────────────────
# Status-only update (PATCH /tasks/{id}/status)
# ──────────────────────────────────────────────
class TaskStatusUpdate(BaseModel):
    status: StatusEnum


# ──────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────
class Task(TaskBase):
    id: str
    user_id: str
    status: StatusEnum
    last_touched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StuckTaskResponse(BaseModel):
    task: Task
    stuck_reason: Literal["inactive", "overdue"]
    suggestion: str

