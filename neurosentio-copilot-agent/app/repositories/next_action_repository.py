"""NextActionPrompt database repository."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.next_action_prompt import NextActionPrompt


class NextActionRepository:
    """All methods filter by user_id."""

    def create(self, db: Session, user_id: str, payload: dict) -> NextActionPrompt:
        payload_copy = dict(payload)
        if "metadata" in payload_copy:
            payload_copy["extra_metadata"] = payload_copy.pop("metadata")
        item = NextActionPrompt(user_id=user_id, **payload_copy)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def get_by_id(self, db: Session, user_id: str, prompt_id: str) -> Optional[NextActionPrompt]:
        return (
            db.query(NextActionPrompt)
            .filter(
                NextActionPrompt.user_id == user_id,
                NextActionPrompt.id == prompt_id,
            )
            .first()
        )

    def get_active_for_source(
        self, db: Session, user_id: str, source_type: str, source_id: Optional[str]
    ) -> Optional[NextActionPrompt]:
        """Get an active (not done/skipped/deferred/expired) prompt for a given source."""
        q = db.query(NextActionPrompt).filter(
            NextActionPrompt.user_id == user_id,
            NextActionPrompt.source_type == source_type,
            NextActionPrompt.status.in_(["active", "snoozed"]),
        )
        if source_id is not None:
            q = q.filter(NextActionPrompt.source_id == source_id)
        else:
            q = q.filter(NextActionPrompt.source_id == None)
        return q.order_by(desc(NextActionPrompt.created_at)).first()

    def get_current_active(
        self, db: Session, user_id: str
    ) -> Optional[NextActionPrompt]:
        """Get the most recent active (not snoozed) prompt."""
        now = datetime.now(timezone.utc)
        return (
            db.query(NextActionPrompt)
            .filter(
                NextActionPrompt.user_id == user_id,
                NextActionPrompt.status == "active",
            )
            .order_by(desc(NextActionPrompt.created_at))
            .first()
        )

    def list_for_user(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[NextActionPrompt]:
        q = db.query(NextActionPrompt).filter(NextActionPrompt.user_id == user_id)
        if status:
            q = q.filter(NextActionPrompt.status == status)
        return (
            q.order_by(desc(NextActionPrompt.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        db: Session,
        user_id: str,
        prompt_id: str,
        status: str,
        metadata: Optional[dict] = None,
    ) -> Optional[NextActionPrompt]:
        item = self.get_by_id(db, user_id, prompt_id)
        if not item:
            return None
        item.status = status
        item.updated_at = datetime.now(timezone.utc)
        if metadata:
            existing_meta = item.extra_metadata or {}
            existing_meta.update(metadata)
            item.extra_metadata = existing_meta
        db.commit()
        db.refresh(item)
        return item

    def snooze(
        self, db: Session, user_id: str, prompt_id: str, minutes: int
    ) -> Optional[NextActionPrompt]:
        from datetime import timedelta
        item = self.get_by_id(db, user_id, prompt_id)
        if not item:
            return None
        item.status = "snoozed"
        item.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item

    def defer(
        self, db: Session, user_id: str, prompt_id: str, defer_until: datetime
    ) -> Optional[NextActionPrompt]:
        item = self.get_by_id(db, user_id, prompt_id)
        if not item:
            return None
        item.status = "deferred"
        item.extra_metadata = {**(item.extra_metadata or {}), "defer_until": defer_until.isoformat()}
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item

    def mark_done(self, db: Session, user_id: str, prompt_id: str) -> Optional[NextActionPrompt]:
        return self.update_status(db, user_id, prompt_id, "done")

    def expire_old_prompts(self, db: Session, user_id: str, before_time: datetime) -> int:
        """Expire active prompts older than before_time. Returns count expired."""
        items = (
            db.query(NextActionPrompt)
            .filter(
                NextActionPrompt.user_id == user_id,
                NextActionPrompt.status == "active",
                NextActionPrompt.created_at < before_time,
            )
            .all()
        )
        for item in items:
            item.status = "expired"
            item.updated_at = datetime.now(timezone.utc)
        db.commit()
        return len(items)


next_action_repository = NextActionRepository()
