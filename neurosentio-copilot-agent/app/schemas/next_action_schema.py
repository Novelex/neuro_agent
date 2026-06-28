"""Pydantic schemas for Next Action Prompter."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator


class NextActionPrompt(BaseModel):
    id: str
    user_id: str
    source_type: str
    source_id: Optional[str] = None
    action_type: str
    title: str
    message: str
    scheduled_for: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    energy_cost: Optional[str] = None
    sensory_cost: Optional[str] = None
    friction_level: Optional[str] = None
    status: str
    snoozed_until: Optional[datetime] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def map_extra_metadata(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        if hasattr(data, "extra_metadata"):
            res = {}
            for field_name in cls.model_fields.keys():
                if field_name == "metadata":
                    res["metadata"] = getattr(data, "extra_metadata", None)
                else:
                    res[field_name] = getattr(data, field_name, None)
            return res
        return data


class NextActionSnoozeRequest(BaseModel):
    minutes: int = Field(default=30, ge=5, le=1440)


class NextActionDeferRequest(BaseModel):
    defer_until: datetime


class NextActionResult(BaseModel):
    prompt: NextActionPrompt
    reason: str
    mode: Optional[str] = None
    source: str = "rule_based"
