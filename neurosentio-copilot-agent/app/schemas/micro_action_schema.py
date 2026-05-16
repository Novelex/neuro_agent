"""Pydantic schemas for MicroAction and Task Decomposition."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

CostEnum = Literal["low", "medium", "high"]
MicroActionStatusEnum = Literal["open", "done", "snoozed", "skipped", "deferred"]


# ──────────────────────────────────────────────
# Core MicroAction entity
# ──────────────────────────────────────────────
class MicroAction(BaseModel):
    id: str
    user_id: str
    task_id: Optional[str] = None
    plan_id: Optional[str] = None
    parent_micro_action_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    energy_cost: Optional[CostEnum] = None
    sensory_cost: Optional[CostEnum] = None
    friction_level: Optional[CostEnum] = None
    status: MicroActionStatusEnum = "open"
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Create (used internally by decomposer)
# ──────────────────────────────────────────────
class MicroActionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    energy_cost: Optional[CostEnum] = None
    sensory_cost: Optional[CostEnum] = None
    friction_level: Optional[CostEnum] = None
    sort_order: int = 0
    parent_micro_action_id: Optional[str] = None


# ──────────────────────────────────────────────
# Update (PATCH /micro-actions/{id})
# ──────────────────────────────────────────────
class MicroActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    energy_cost: Optional[CostEnum] = None
    sensory_cost: Optional[CostEnum] = None
    friction_level: Optional[CostEnum] = None
    sort_order: Optional[int] = None


# ──────────────────────────────────────────────
# Status-only update (PATCH /micro-actions/{id}/status)
# ──────────────────────────────────────────────
class MicroActionStatusUpdate(BaseModel):
    status: MicroActionStatusEnum


# ──────────────────────────────────────────────
# Task decompose request  (POST /tasks/{id}/decompose)
# ──────────────────────────────────────────────
class TaskDecomposeRequest(BaseModel):
    current_energy: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Current battery level 0–100. If omitted, assumes normal mode.",
    )
    sensory_state: Optional[str] = None
    max_actions: int = Field(default=5, ge=1, le=7)
    force_regenerate: bool = False


# ──────────────────────────────────────────────
# Task decompose response
# ──────────────────────────────────────────────
class TaskDecomposeResponse(BaseModel):
    task_id: str
    mode: str            # normal | recovery
    source: str          # mock | llm | fallback
    message: str
    micro_actions: List[MicroAction]


# ──────────────────────────────────────────────
# Make-smaller request/response
# ──────────────────────────────────────────────
class MakeSmallerRequest(BaseModel):
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)
    reason: Optional[str] = None


class MakeSmallerResponse(BaseModel):
    original_micro_action: MicroAction
    smaller_actions: List[MicroAction]
