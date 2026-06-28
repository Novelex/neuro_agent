"""Data Delete Service."""

from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile
from app.models.privacy_preferences import PrivacyPreferences
from app.models.privacy_audit_log import PrivacyAuditLog
from app.models.task import Task
from app.models.energy_log import EnergyLog
from app.models.micro_action import MicroAction
from app.models.copilot_plan import CopilotPlan
from app.models.transition_script import TransitionScript
from app.models.reply_draft import ReplyDraft
from app.models.calendar_event import CalendarEvent
from app.models.overload_event import OverloadEvent
from app.models.message_item import MessageItem
from app.models.next_action_prompt import NextActionPrompt
from app.models.replan_event import ReplanEvent
from app.models.llm_usage_log import LLMUsageLog
from app.repositories.privacy_audit_repository import privacy_audit_repository


def delete_user_data(db: Session, user_id: str, delete_profile: bool = True) -> Dict[str, Any]:
    """
    Safely erase all current user's owned data in proper dependency order.
    Returns count of deleted items per category.
    """
    counts = {}

    # 1. next action prompts
    counts["next_action_prompts"] = db.query(NextActionPrompt).filter(NextActionPrompt.user_id == user_id).delete()

    # 2. replan events
    counts["replan_events"] = db.query(ReplanEvent).filter(ReplanEvent.user_id == user_id).delete()

    # 3. overload events
    counts["overload_events"] = db.query(OverloadEvent).filter(OverloadEvent.user_id == user_id).delete()

    # 4. message items
    counts["message_items"] = db.query(MessageItem).filter(MessageItem.user_id == user_id).delete()

    # 5. reply drafts
    counts["reply_drafts"] = db.query(ReplyDraft).filter(ReplyDraft.user_id == user_id).delete()

    # 6. calendar events
    counts["calendar_events"] = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id).delete()

    # 7. transition scripts
    counts["transition_scripts"] = db.query(TransitionScript).filter(TransitionScript.user_id == user_id).delete()

    # 8. micro-actions
    counts["micro_actions"] = db.query(MicroAction).filter(MicroAction.user_id == user_id).delete()

    # 9. copilot plans
    counts["copilot_plans"] = db.query(CopilotPlan).filter(CopilotPlan.user_id == user_id).delete()

    # 10. energy logs
    counts["energy_logs"] = db.query(EnergyLog).filter(EnergyLog.user_id == user_id).delete()

    # 11. tasks
    counts["tasks"] = db.query(Task).filter(Task.user_id == user_id).delete()

    # 12. llm usage logs
    counts["llm_usage_logs"] = db.query(LLMUsageLog).filter(LLMUsageLog.user_id == user_id).delete()

    # 13. privacy audit logs (wipe out history to avoid user trace)
    counts["privacy_audit_logs"] = db.query(PrivacyAuditLog).filter(PrivacyAuditLog.user_id == user_id).delete()

    # 14. privacy preferences
    counts["privacy_preferences"] = db.query(PrivacyPreferences).filter(PrivacyPreferences.user_id == user_id).delete()

    # 15. profile if delete_profile=true
    if delete_profile:
        counts["user_profiles"] = db.query(UserProfile).filter(UserProfile.user_id == user_id).delete()

    # Commit all deletions in a single transaction
    db.commit()

    return counts
