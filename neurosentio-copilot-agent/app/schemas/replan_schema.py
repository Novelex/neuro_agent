"""Pydantic schemas for Adaptive Replanner."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.morning_plan_schema import PlannedMicroAction, RecoveryBlock
from app.schemas.next_action_schema import NextActionPrompt


ALLOWED_TRIGGER_TYPES = {
    "low_energy", "skipped_actions", "calendar_overload",
    "urgent_message", "manual", "recovery_mode", "stuck_tasks"
}


class ReplanRequest(BaseModel):
    trigger_type: str
    current_energy: Optional[int] = Field(default=None, ge=0, le=100)
    sensory_state: Optional[str] = None
    reason: Optional[str] = None
    preserve_completed: bool = True
    defer_high_energy: bool = True
    include_urgent_messages: bool = True


class ReplanEvent(BaseModel):
    id: str
    user_id: str
    trigger_type: str
    trigger_details: Optional[dict] = None
    previous_plan_id: Optional[str] = None
    new_plan_id: Optional[str] = None
    mode_before: Optional[str] = None
    mode_after: Optional[str] = None
    actions_preserved_count: int = 0
    actions_deferred_count: int = 0
    actions_added_count: int = 0
    summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReplanResult(BaseModel):
    event: ReplanEvent
    new_plan_id: Optional[str] = None
    summary: str
    selected_actions: List[PlannedMicroAction] = []
    deferred_actions_count: int = 0
    recovery_blocks: List[RecoveryBlock] = []
    next_action: Optional[NextActionPrompt] = None
