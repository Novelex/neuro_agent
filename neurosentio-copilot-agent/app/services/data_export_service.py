"""Data Export Service."""

from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile
from app.models.privacy_preferences import PrivacyPreferences
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


def _to_dict(model_instance) -> Optional[Dict[str, Any]]:
    if not model_instance:
        return None
    d = {}
    for col in model_instance.__table__.columns:
        attr_name = col.name
        if attr_name == "metadata" and hasattr(model_instance, "extra_metadata"):
            attr_name = "extra_metadata"
        val = getattr(model_instance, attr_name)
        if isinstance(val, (datetime, date)):
            d[col.name] = val.isoformat()
        else:
            d[col.name] = val
    return d


def export_user_data(db: Session, user_id: str, redacted: bool = False) -> Dict[str, Any]:
    """
    Export all current user's data in structured JSON.
    If redacted=True, removes or masks sensitive text fields strictly in memory (without mutating DB).
    Failures on the 14 known tables are not hidden and will propagate.
    """
    warnings: List[str] = []
    
    # ── 1. Gather all 14 standard sections (failures will propagate) ────
    
    # 1. Profile
    profile_row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    profile_data = _to_dict(profile_row) if profile_row else {}

    # 2. Privacy preferences
    prefs_row = db.query(PrivacyPreferences).filter(PrivacyPreferences.user_id == user_id).first()
    prefs_data = _to_dict(prefs_row) if prefs_row else {}

    # 3. Tasks
    tasks_rows = db.query(Task).filter(Task.user_id == user_id).all()
    tasks_list = [_to_dict(t) for t in tasks_rows]

    # 4. Energy logs
    energy_rows = db.query(EnergyLog).filter(EnergyLog.user_id == user_id).all()
    energy_list = [_to_dict(el) for el in energy_rows]

    # 5. Micro actions
    micro_rows = db.query(MicroAction).filter(MicroAction.user_id == user_id).all()
    micro_list = [_to_dict(ma) for ma in micro_rows]

    # 6. Copilot plans
    plan_rows = db.query(CopilotPlan).filter(CopilotPlan.user_id == user_id).all()
    plan_list = [_to_dict(p) for p in plan_rows]

    # 7. Transition scripts
    script_rows = db.query(TransitionScript).filter(TransitionScript.user_id == user_id).all()
    script_list = [_to_dict(s) for s in script_rows]

    # 8. Reply drafts
    reply_rows = db.query(ReplyDraft).filter(ReplyDraft.user_id == user_id).all()
    reply_list = [_to_dict(rd) for rd in reply_rows]

    # 9. Calendar events
    calendar_rows = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id).all()
    calendar_list = [_to_dict(ce) for ce in calendar_rows]

    # 10. Message items
    message_rows = db.query(MessageItem).filter(MessageItem.user_id == user_id).all()
    message_list = [_to_dict(mi) for mi in message_rows]

    # 11. Overload events
    overload_rows = db.query(OverloadEvent).filter(OverloadEvent.user_id == user_id).all()
    overload_list = [_to_dict(oe) for oe in overload_rows]

    # 12. Next action prompts
    nap_rows = db.query(NextActionPrompt).filter(NextActionPrompt.user_id == user_id).all()
    nap_list = [_to_dict(nap) for nap in nap_rows]

    # 13. Replan events
    replan_rows = db.query(ReplanEvent).filter(ReplanEvent.user_id == user_id).all()
    replan_list = [_to_dict(re) for re in replan_rows]

    # 14. LLM usage logs
    llm_rows = db.query(LLMUsageLog).filter(LLMUsageLog.user_id == user_id).all()
    llm_list = [_to_dict(llm) for llm in llm_rows]

    # ── 2. Redaction Logic (In-Memory Only) ────────────────────────────
    if redacted:
        # tasks description
        for t in tasks_list:
            if t and t.get("description") is not None:
                t["description"] = "[redacted]"

        # reply drafts: original_message, edited_reply, draft_options
        for rd in reply_list:
            if rd:
                if rd.get("original_message") is not None:
                    rd["original_message"] = "[redacted]"
                if rd.get("edited_reply") is not None:
                    rd["edited_reply"] = "[redacted]"
                # draft_options is JSON list: [{"type": ..., "text": ...}]
                if isinstance(rd.get("draft_options"), list):
                    rd["draft_options"] = [
                        {"type": opt.get("type"), "text": "[redacted]"} if isinstance(opt, dict) else opt
                        for opt in rd["draft_options"]
                    ]

        # calendar events title
        for ce in calendar_list:
            if ce and ce.get("title") is not None:
                ce["title"] = "[redacted]"

        # message items snippet
        for mi in message_list:
            if mi and mi.get("snippet") is not None:
                mi["snippet"] = "[redacted]"

        # transition scripts steps + context
        for s in script_list:
            if s:
                if isinstance(s.get("script_steps"), list):
                    s["script_steps"] = ["[redacted]" for _ in s["script_steps"]]
                if s.get("context") is not None:
                    s["context"] = "[redacted]"

    # ── 3. Write Privacy Audit Log ─────────────────────────────────────
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="export_data",
        extra_metadata={"redacted": redacted, "warning_count": len(warnings)}
    )

    return {
        "user_id": user_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "profile": profile_data,
        "privacy_preferences": prefs_data,
        "tasks": tasks_list,
        "energy_logs": energy_list,
        "micro_actions": micro_list,
        "copilot_plans": plan_list,
        "transition_scripts": script_list,
        "reply_drafts": reply_list,
        "calendar_events": calendar_list,
        "message_items": message_list,
        "overload_events": overload_list,
        "next_action_prompts": nap_list,
        "replan_events": replan_list,
        "llm_usage_logs": llm_list,
    }
