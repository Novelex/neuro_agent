"""Repository for ReplyDraft data access (Day 7).

All methods strictly filter by user_id.
A user can never see, edit, or delete another user's drafts.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.reply_draft import ReplyDraft as ReplyDraftModel
from app.schemas.reply_schema import ReplyDraftUpdate


class ReplyDraftRepository:

    # ── Reads ──────────────────────────────────────────────────────────

    def get_by_id(
        self, db: Session, user_id: str, draft_id: str
    ) -> Optional[ReplyDraftModel]:
        return (
            db.query(ReplyDraftModel)
            .filter(
                ReplyDraftModel.id == draft_id,
                ReplyDraftModel.user_id == user_id,
            )
            .first()
        )

    def list_for_user(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReplyDraftModel]:
        """
        Returns drafts for the user.
        By default excludes deleted drafts unless status='deleted' is explicitly requested.
        """
        q = db.query(ReplyDraftModel).filter(ReplyDraftModel.user_id == user_id)

        if status:
            q = q.filter(ReplyDraftModel.status == status)
        else:
            # Exclude soft-deleted unless explicitly requested
            q = q.filter(ReplyDraftModel.status != "deleted")

        return (
            q.order_by(ReplyDraftModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_active(self, db: Session, user_id: str) -> int:
        """Count of non-deleted drafts — used by dashboard."""
        return (
            db.query(ReplyDraftModel)
            .filter(
                ReplyDraftModel.user_id == user_id,
                ReplyDraftModel.status != "deleted",
            )
            .count()
        )

    def get_latest(self, db: Session, user_id: str) -> Optional[ReplyDraftModel]:
        """Most recent non-deleted draft — used by dashboard."""
        return (
            db.query(ReplyDraftModel)
            .filter(
                ReplyDraftModel.user_id == user_id,
                ReplyDraftModel.status != "deleted",
            )
            .order_by(ReplyDraftModel.created_at.desc())
            .first()
        )

    # ── Writes ─────────────────────────────────────────────────────────

    def create(
        self,
        db: Session,
        user_id: str,
        source_type: str,
        original_message: str,
        message_sender: Optional[str],
        message_subject: Optional[str],
        message_channel: str,
        user_intent: Optional[str],
        preferred_tone: Optional[str],
        context_note: Optional[str],
        draft_options: list,
        source: str,
    ) -> ReplyDraftModel:
        row = ReplyDraftModel(
            user_id=user_id,
            source_type=source_type,
            original_message=original_message,
            message_sender=message_sender,
            message_subject=message_subject,
            message_channel=message_channel,
            user_intent=user_intent,
            preferred_tone=preferred_tone,
            context_note=context_note,
            draft_options=draft_options,
            source=source,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update(
        self,
        db: Session,
        user_id: str,
        draft_id: str,
        data: ReplyDraftUpdate,
    ) -> Optional[ReplyDraftModel]:
        row = self.get_by_id(db, user_id, draft_id)
        if not row:
            return None
        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def soft_delete(
        self, db: Session, user_id: str, draft_id: str
    ) -> Optional[ReplyDraftModel]:
        row = self.get_by_id(db, user_id, draft_id)
        if not row:
            return None
        row.status = "deleted"
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def hard_delete(
        self, db: Session, user_id: str, draft_id: str
    ) -> bool:
        row = self.get_by_id(db, user_id, draft_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True


reply_draft_repository = ReplyDraftRepository()
