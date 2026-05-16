"""EnergyLog ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class EnergyLog(Base):
    __tablename__ = "energy_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # 0–100
    battery_level = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)

    # Allowed: calm, okay, overstimulated, shutdown, anxious, unknown
    sensory_state = Column(String, nullable=False, default="unknown")

    mood = Column(String, nullable=True)
    logged_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
