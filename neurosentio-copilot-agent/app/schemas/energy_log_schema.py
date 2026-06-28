"""Pydantic schemas for EnergyLog."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field

SensoryStateEnum = Literal["calm", "okay", "overstimulated", "shutdown", "anxious", "unknown"]


# ──────────────────────────────────────────────
# Create (POST /energy/log)
# ──────────────────────────────────────────────
class EnergyCreate(BaseModel):
    battery_level: int = Field(..., ge=0, le=100, description="Energy level from 0 to 100")
    note: Optional[str] = None
    sensory_state: SensoryStateEnum = "unknown"
    mood: Optional[str] = None
    logged_at: Optional[datetime] = None  # Defaults to now() if not provided


# ──────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────
class Energy(BaseModel):
    id: str
    user_id: str
    battery_level: int
    note: Optional[str] = None
    sensory_state: str
    mood: Optional[str] = None
    logged_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class EnergyPatternsResponse(BaseModel):
    high_energy_hours: List[int]
    low_energy_hours: List[int]
    best_focus_window: Optional[str] = None
    confidence_tier: Literal["low", "medium", "high"]
    hourly_averages: dict[str, float]

