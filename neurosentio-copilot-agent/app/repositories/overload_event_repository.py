"""OverloadEvent database repository."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.overload_event import OverloadEvent


class OverloadEventRepository:

    def create(
        self,
        db: Session,
        user_id: str,
        risk_score: int,
        mode: str,
        trigger_reasons: List[str],
        energy_score: Optional[int] = None,
        calendar_load_score: Optional[int] = None,
        open_task_count: Optional[int] = None,
        high_priority_task_count: Optional[int] = None,
        stuck_task_count: Optional[int] = None,
        message: Optional[str] = None,
        detected_at: Optional[datetime] = None,
    ) -> OverloadEvent:
        """Create a new overload event log."""
        event = OverloadEvent(
            user_id=user_id,
            detected_at=detected_at or datetime.now(timezone.utc),
            risk_score=risk_score,
            mode=mode,
            trigger_reasons=trigger_reasons,
            energy_score=energy_score,
            calendar_load_score=calendar_load_score,
            open_task_count=open_task_count,
            high_priority_task_count=high_priority_task_count,
            stuck_task_count=stuck_task_count,
            message=message,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_latest(self, db: Session, user_id: str) -> Optional[OverloadEvent]:
        """Fetch the single most recent overload event for a user."""
        return (
            db.query(OverloadEvent)
            .filter(OverloadEvent.user_id == user_id)
            .order_by(OverloadEvent.detected_at.desc())
            .first()
        )

    def list_recent(self, db: Session, user_id: str, days: int) -> List[OverloadEvent]:
        """List overload events detected within the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(OverloadEvent)
            .filter(and_(OverloadEvent.user_id == user_id, OverloadEvent.detected_at >= cutoff))
            .order_by(OverloadEvent.detected_at.desc())
            .all()
        )

    def count_recent(self, db: Session, user_id: str, days: int) -> int:
        """Count overload events detected within the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(OverloadEvent)
            .filter(and_(OverloadEvent.user_id == user_id, OverloadEvent.detected_at >= cutoff))
            .count()
        )


overload_event_repository = OverloadEventRepository()
