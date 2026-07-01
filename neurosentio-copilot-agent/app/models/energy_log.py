"""Energy log data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class EnergyLog:
    user_id: str
    battery_level: int
    note: Optional[str] = None

    # Allowed: calm, okay, overstimulated, shutdown, anxious, unknown
    sensory_state: str = "unknown"
    mood: Optional[str] = None
    logged_at: datetime = field(default_factory=_now)
    created_at: datetime = field(default_factory=_now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
