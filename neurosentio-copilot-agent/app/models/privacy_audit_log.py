"""PrivacyAuditLog ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class PrivacyAuditLog(Base):
    __tablename__ = "privacy_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
