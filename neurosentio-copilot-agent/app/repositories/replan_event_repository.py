"""ReplanEvent database repository."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.replan_event import ReplanEvent


class ReplanEventRepository:
    """All methods filter by user_id."""

    def create(self, db: Session, user_id: str, payload: dict) -> ReplanEvent:
        item = ReplanEvent(user_id=user_id, **payload)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def list_recent(self, db: Session, user_id: str, days: int = 14) -> List[ReplanEvent]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(ReplanEvent)
            .filter(
                ReplanEvent.user_id == user_id,
                ReplanEvent.created_at >= cutoff,
            )
            .order_by(desc(ReplanEvent.created_at))
            .all()
        )

    def count_recent(self, db: Session, user_id: str, days: int = 14) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(ReplanEvent)
            .filter(
                ReplanEvent.user_id == user_id,
                ReplanEvent.created_at >= cutoff,
            )
            .count()
        )

    def list_by_trigger(
        self, db: Session, user_id: str, trigger_type: str, days: int = 14
    ) -> List[ReplanEvent]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(ReplanEvent)
            .filter(
                ReplanEvent.user_id == user_id,
                ReplanEvent.trigger_type == trigger_type,
                ReplanEvent.created_at >= cutoff,
            )
            .order_by(desc(ReplanEvent.created_at))
            .all()
        )


replan_event_repository = ReplanEventRepository()
