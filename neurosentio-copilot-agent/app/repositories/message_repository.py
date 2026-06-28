"""MessageItem database repository."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.message_item import MessageItem


class MessageRepository:
    """All methods filter by user_id."""

    def upsert_messages(
        self, db: Session, user_id: str, messages_data: List[dict]
    ) -> Tuple[int, int, List[MessageItem]]:
        """
        Upsert a list of message items.

        Rules:
        - If external_message_id exists, upsert by user_id + source + external_message_id.
        - If external_message_id is null, always create a new message.
        """
        imported_count = 0
        updated_count = 0
        saved = []

        for data in messages_data:
            data_copy = dict(data)
            if "metadata" in data_copy:
                data_copy["extra_metadata"] = data_copy.pop("metadata")

            ext_id = data_copy.get("external_message_id")
            source = data_copy.get("source", "manual")

            existing = None
            if ext_id is not None:
                existing = db.query(MessageItem).filter(
                    and_(
                        MessageItem.user_id == user_id,
                        MessageItem.source == source,
                        MessageItem.external_message_id == ext_id,
                    )
                ).first()

            if existing:
                for key, val in data_copy.items():
                    if hasattr(existing, key):
                        setattr(existing, key, val)
                existing.updated_at = datetime.now(timezone.utc)
                updated_count += 1
                saved.append(existing)
            else:
                new_item = MessageItem(user_id=user_id, **data_copy)
                db.add(new_item)
                imported_count += 1
                saved.append(new_item)

        db.commit()
        for item in saved:
            db.refresh(item)

        return imported_count, updated_count, saved

    def list_messages(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        needs_reply: Optional[bool] = None,
        is_read: Optional[bool] = None,
    ) -> List[MessageItem]:
        q = db.query(MessageItem).filter(MessageItem.user_id == user_id)
        if needs_reply is not None:
            q = q.filter(MessageItem.needs_reply == needs_reply)
        if is_read is not None:
            q = q.filter(MessageItem.is_read == is_read)
        return (
            q.order_by(desc(MessageItem.received_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_recent(self, db: Session, user_id: str, days: int = 7) -> List[MessageItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            db.query(MessageItem)
            .filter(
                MessageItem.user_id == user_id,
                MessageItem.received_at >= cutoff,
            )
            .order_by(desc(MessageItem.received_at))
            .all()
        )

    def list_urgent(self, db: Session, user_id: str, limit: int = 10) -> List[MessageItem]:
        return (
            db.query(MessageItem)
            .filter(
                MessageItem.user_id == user_id,
                MessageItem.urgency_score >= 40,
            )
            .order_by(desc(MessageItem.urgency_score))
            .limit(limit)
            .all()
        )

    def get_by_id(self, db: Session, user_id: str, message_id: str) -> Optional[MessageItem]:
        return (
            db.query(MessageItem)
            .filter(
                MessageItem.user_id == user_id,
                MessageItem.id == message_id,
            )
            .first()
        )

    def update(
        self, db: Session, user_id: str, message_id: str, payload: dict
    ) -> Optional[MessageItem]:
        item = self.get_by_id(db, user_id, message_id)
        if not item:
            return None
        payload_copy = dict(payload)
        if "metadata" in payload_copy:
            payload_copy["extra_metadata"] = payload_copy.pop("metadata")
        for key, val in payload_copy.items():
            if hasattr(item, key):
                setattr(item, key, val)
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item

    def delete(self, db: Session, user_id: str, message_id: str) -> bool:
        item = self.get_by_id(db, user_id, message_id)
        if not item:
            return False
        db.delete(item)
        db.commit()
        return True

    def count_needs_reply(self, db: Session, user_id: str) -> int:
        return (
            db.query(MessageItem)
            .filter(MessageItem.user_id == user_id, MessageItem.needs_reply == True)
            .count()
        )

    def count_urgent(self, db: Session, user_id: str) -> int:
        return (
            db.query(MessageItem)
            .filter(MessageItem.user_id == user_id, MessageItem.urgency_score >= 40)
            .count()
        )

    def count_unread(self, db: Session, user_id: str) -> int:
        return (
            db.query(MessageItem)
            .filter(MessageItem.user_id == user_id, MessageItem.is_read == False)
            .count()
        )

    def count_total(self, db: Session, user_id: str) -> int:
        return db.query(MessageItem).filter(MessageItem.user_id == user_id).count()


message_repository = MessageRepository()
