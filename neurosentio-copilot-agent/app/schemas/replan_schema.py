"""Pydantic schemas for Adaptive Replanner."""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

from app.schemas.morning_plan_schema import PlannedMicroAction, RecoveryBlock


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


class ReplanResult(BaseModel):
    event: Dict[str, Any]
    new_plan_id: Optional[str] = None
    summary: str
    selected_actions: List[PlannedMicroAction] = []
    deferred_actions_count: int = 0
    recovery_blocks: List[RecoveryBlock] = []
