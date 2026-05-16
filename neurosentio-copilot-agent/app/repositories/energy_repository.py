"""Repository for EnergyLog data access."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.energy_log import EnergyLog
from app.schemas.energy_log_schema import EnergyCreate


class EnergyRepository:

    def get_latest(self, db: Session, user_id: str) -> Optional[EnergyLog]:
        return (
            db.query(EnergyLog)
            .filter(EnergyLog.user_id == user_id)
            .order_by(EnergyLog.logged_at.desc())
            .first()
        )

    def get_all(self, db: Session, user_id: str, limit: int = 50) -> List[EnergyLog]:
        return (
            db.query(EnergyLog)
            .filter(EnergyLog.user_id == user_id)
            .order_by(EnergyLog.logged_at.desc())
            .limit(limit)
            .all()
        )

    def create(self, db: Session, user_id: str, data: EnergyCreate) -> EnergyLog:
        log = EnergyLog(
            user_id=user_id,
            battery_level=data.battery_level,
            note=data.note,
            sensory_state=data.sensory_state,
            mood=data.mood,
            logged_at=data.logged_at or datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


energy_repository = EnergyRepository()
