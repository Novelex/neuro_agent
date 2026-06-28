"""Repository for TransitionScript data access (Day 6)."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.transition_script import TransitionScript as TransitionScriptModel
from app.schemas.transition_script_schema import TransitionScriptCreate


class TransitionScriptRepository:
    """
    All methods filter by user_id.
    A user can never access another user's scripts.
    """

    # ──────────────────────────────────────────────────────────────────
    # Reads
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(
        self, db: Session, user_id: str, script_id: str
    ) -> Optional[TransitionScriptModel]:
        return (
            db.query(TransitionScriptModel)
            .filter(
                TransitionScriptModel.id == script_id,
                TransitionScriptModel.user_id == user_id,
            )
            .first()
        )

    def get_by_type(
        self, db: Session, user_id: str, transition_type: str
    ) -> List[TransitionScriptModel]:
        return (
            db.query(TransitionScriptModel)
            .filter(
                TransitionScriptModel.user_id == user_id,
                TransitionScriptModel.transition_type == transition_type,
            )
            .order_by(TransitionScriptModel.created_at.desc())
            .all()
        )

    def get_latest_by_type(
        self, db: Session, user_id: str, transition_type: str
    ) -> Optional[TransitionScriptModel]:
        return (
            db.query(TransitionScriptModel)
            .filter(
                TransitionScriptModel.user_id == user_id,
                TransitionScriptModel.transition_type == transition_type,
            )
            .order_by(TransitionScriptModel.created_at.desc())
            .first()
        )

    def list_for_user(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TransitionScriptModel]:
        return (
            db.query(TransitionScriptModel)
            .filter(TransitionScriptModel.user_id == user_id)
            .order_by(TransitionScriptModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    # ──────────────────────────────────────────────────────────────────
    # Writes
    # ──────────────────────────────────────────────────────────────────

    def create(
        self, db: Session, user_id: str, data: TransitionScriptCreate
    ) -> TransitionScriptModel:
        row = TransitionScriptModel(
            user_id=user_id,
            transition_type=data.transition_type,
            title=data.title,
            script_steps=data.script_steps,
            context=data.context,
            tone=data.tone,
            source=data.source,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update_rating(
        self, db: Session, user_id: str, script_id: str, rating: int
    ) -> Optional[TransitionScriptModel]:
        row = self.get_by_id(db, user_id, script_id)
        if not row:
            return None
        row.success_rating = rating
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def mark_used(
        self, db: Session, user_id: str, script_id: str
    ) -> Optional[TransitionScriptModel]:
        row = self.get_by_id(db, user_id, script_id)
        if not row:
            return None
        row.last_used_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def delete(
        self, db: Session, user_id: str, script_id: str
    ) -> bool:
        row = self.get_by_id(db, user_id, script_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True


transition_script_repository = TransitionScriptRepository()
