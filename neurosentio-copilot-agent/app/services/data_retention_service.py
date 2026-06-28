"""Data Retention Service."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.reply_draft import ReplyDraft
from app.models.message_item import MessageItem
from app.models.calendar_event import CalendarEvent
from app.models.llm_usage_log import LLMUsageLog
from app.repositories.privacy_preferences_repository import privacy_preferences_repository
from app.repositories.privacy_audit_repository import privacy_audit_repository


def apply_retention_policies(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Manually prunes old user records based on their preferred retention days.
    - reply_drafts (by created_at)
    - messages (by received_at)
    - calendar_events (by start_time)
    - llm_usage_logs (by created_at)
    Logs non-sensitive action in privacy audit log.
    """
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    now = datetime.now(timezone.utc)
    counts = {
        "pruned_reply_drafts": 0,
        "pruned_messages": 0,
        "pruned_calendar_events": 0,
        "pruned_llm_usage_logs": 0,
    }

    # 1. Prune reply drafts
    if prefs.retention_days_reply_drafts is not None:
        cutoff = now - timedelta(days=prefs.retention_days_reply_drafts)
        deleted = (
            db.query(ReplyDraft)
            .filter(ReplyDraft.user_id == user_id, ReplyDraft.created_at < cutoff)
            .delete()
        )
        counts["pruned_reply_drafts"] = deleted

    # 2. Prune messages
    if prefs.retention_days_messages is not None:
        cutoff = now - timedelta(days=prefs.retention_days_messages)
        deleted = (
            db.query(MessageItem)
            .filter(MessageItem.user_id == user_id, MessageItem.received_at < cutoff)
            .delete()
        )
        counts["pruned_messages"] = deleted

    # 3. Prune calendar events
    if prefs.retention_days_calendar_events is not None:
        cutoff = now - timedelta(days=prefs.retention_days_calendar_events)
        deleted = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.user_id == user_id, CalendarEvent.start_time < cutoff)
            .delete()
        )
        counts["pruned_calendar_events"] = deleted

    # 4. Prune LLM usage logs
    if prefs.retention_days_llm_usage_logs is not None:
        cutoff = now - timedelta(days=prefs.retention_days_llm_usage_logs)
        deleted = (
            db.query(LLMUsageLog)
            .filter(LLMUsageLog.user_id == user_id, LLMUsageLog.created_at < cutoff)
            .delete()
        )
        counts["pruned_llm_usage_logs"] = deleted

    # Commit deletions
    db.commit()

    # Log non-sensitive action audit log
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="apply_retention",
        extra_metadata=counts,
    )

    return counts
