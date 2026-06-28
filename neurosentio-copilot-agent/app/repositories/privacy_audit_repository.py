"""Repository for PrivacyAuditLog data access."""

from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session

from app.models.privacy_audit_log import PrivacyAuditLog


class PrivacyAuditRepository:

    def log_privacy_action(
        self,
        db: Session,
        user_id: str,
        action_type: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> PrivacyAuditLog:
        audit_log = PrivacyAuditLog(
            user_id=user_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            extra_metadata=extra_metadata
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

    def get_audit_logs(self, db: Session, user_id: str) -> List[PrivacyAuditLog]:
        return db.query(PrivacyAuditLog).filter(PrivacyAuditLog.user_id == user_id).order_by(PrivacyAuditLog.created_at.desc()).all()

    def delete_all_for_user(self, db: Session, user_id: str) -> int:
        """Deletes all audit logs for a user during a complete wipe."""
        deleted_count = db.query(PrivacyAuditLog).filter(PrivacyAuditLog.user_id == user_id).delete()
        db.commit()
        return deleted_count


privacy_audit_repository = PrivacyAuditRepository()
