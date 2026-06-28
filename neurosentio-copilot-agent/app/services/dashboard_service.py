"""
Dashboard service (Day 5 update).

Priority for suggested_next_action:
1. First open micro-action from today's morning plan
2. First open micro-action from top task (any plan)
3. Suggest decomposing the top task if no micro-actions exist
4. Suggest adding a task if none open
5. Suggest logging energy if none available

NextAction type values:
- planned_micro_action    → from today's morning plan
- existing_micro_action   → from a task but not plan-linked
- needs_decomposition     → task exists but no micro-actions
- add_task                → no open tasks
- log_energy              → no energy log
- recovery                → recovery mode, prompt to rest
"""

from datetime import date
from sqlalchemy.orm import Session

from app.repositories.task_repository import task_repository
from app.repositories.energy_repository import energy_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.repositories.copilot_repository import copilot_repository
from app.repositories.llm_usage_repository import llm_usage_repository
from app.services.overload_service import calculate_overload_risk
from app.services.planning_service import (
    select_tasks,
    build_recovery_recommendation,
)
from app.schemas.copilot_schema import Dashboard, NextAction, Recovery
from app.schemas.task_schema import Task as TaskSchema
from app.schemas.energy_log_schema import Energy as EnergySchema

# Context Intelligence Pack imports
from app.repositories.calendar_repository import calendar_repository
from app.services.calendar_analysis_service import build_day_summary, mark_back_to_back
from app.services.energy_pattern_service import get_energy_patterns
from app.services.stuck_task_service import detect_stuck_tasks
from app.repositories.overload_event_repository import overload_event_repository


def get_dashboard(db: Session, user_id: str) -> Dashboard:
    # ── Fetch basic data ───────────────────────────────────────────────
    latest_energy = energy_repository.get_latest(db, user_id)
    open_tasks = task_repository.get_open(db, user_id)
    high_priority = [t for t in open_tasks if t.priority == "high"]

    # ── Fetch calendar context safely ──────────────────────────────────
    day_summary = None
    try:
        day_events = calendar_repository.list_events_for_day(db, user_id, date.today())
        if day_events:
            mark_back_to_back(day_events)
            db.commit()
            day_events = calendar_repository.list_events_for_day(db, user_id, date.today())
        day_summary = build_day_summary(day_events, date.today())
    except Exception:
        pass

    # ── Fetch other context intelligence safely ────────────────────────
    energy_patterns_summary = None
    try:
        energy_patterns_summary = get_energy_patterns(db, user_id, days=14)
    except Exception:
        pass

    stuck_tasks_count = 0
    try:
        stuck_tasks_count = len(detect_stuck_tasks(db, user_id, threshold_days=3))
    except Exception:
        pass

    recent_overload_events_count = 0
    try:
        recent_overload_events_count = overload_event_repository.count_recent(db, user_id, days=14)
    except Exception:
        pass

    # ── Message monitor context (Execution Automation Pack) ───────────
    message_summary_data = None
    urgent_messages_count = 0
    needs_reply_count = 0
    try:
        from app.repositories.message_repository import message_repository
        from app.services.message_analysis_service import build_message_summary
        recent_msgs = message_repository.list_recent(db, user_id, days=7)
        msg_summary = build_message_summary(recent_msgs)
        message_summary_data = msg_summary
        urgent_messages_count = msg_summary.get("urgent_count", 0)
        needs_reply_count = msg_summary.get("needs_reply_count", 0)
    except Exception:
        pass

    # ── Next action prompt context ────────────────────────────────────
    next_action_prompt_data = None
    try:
        from app.services.next_action_service import get_or_create_next_action
        from app.schemas.next_action_schema import NextActionPrompt as NAPSchema
        prompt, _, _ = get_or_create_next_action(db, user_id)
        next_action_prompt_data = NAPSchema.model_validate(prompt).model_dump()
    except Exception:
        pass

    # ── Recent replan events count ────────────────────────────────────
    recent_replan_events_count = 0
    try:
        from app.repositories.replan_event_repository import replan_event_repository
        recent_replan_events_count = replan_event_repository.count_recent(db, user_id, days=14)
    except Exception:
        pass

    # ── Overload risk ──────────────────────────────────────────────────
    risk = calculate_overload_risk(
        latest_energy=latest_energy,
        open_tasks_count=len(open_tasks),
        high_priority_count=len(high_priority),
        event_count=day_summary.event_count if day_summary else None,
        back_to_back_count=day_summary.back_to_back_count if day_summary else None,
        high_load_event_exists=(day_summary.high_load_event_count > 0) if day_summary else None,
        total_meeting_minutes=day_summary.total_meeting_minutes if day_summary else None,
    )
    mode = risk["mode"]

    # ── Planning ───────────────────────────────────────────────────────
    selected_tasks = select_tasks(open_tasks, mode)
    recovery_rec = build_recovery_recommendation(mode, latest_energy, risk["reasons"])

    # ── Build suggested_next_action (Day 5 priority chain) ────────────
    suggested_action = _build_next_action(db, user_id, open_tasks, selected_tasks, mode, latest_energy)

    # ── Reply drafter integration (Day 8) — safe, never breaks dashboard ──
    reply_drafts_count = 0
    latest_reply_draft_id = None
    latest_reply_draft_subject = None
    try:
        from app.repositories.reply_draft_repository import reply_draft_repository
        reply_drafts_count = reply_draft_repository.count_active(db, user_id)
        latest = reply_draft_repository.get_latest(db, user_id)
        if latest:
            latest_reply_draft_id = latest.id
            latest_reply_draft_subject = latest.message_subject
    except Exception:
        pass  # Reply drafter is optional — dashboard must not fail

    # ── LLM Usage summary (Day 10) ─────────────────────────────────────
    llm_usage_summary = llm_usage_repository.summarize_for_user(db, user_id)

    # ── Serialise ──────────────────────────────────────────────────────
    latest_energy_resp = EnergySchema.model_validate(latest_energy) if latest_energy else None
    open_tasks_resp = [TaskSchema.model_validate(t) for t in open_tasks]

    return Dashboard(
        user_id=user_id,
        mode=mode,
        latest_energy=latest_energy_resp,
        open_tasks_count=len(open_tasks),
        high_priority_tasks_count=len(high_priority),
        open_tasks=open_tasks_resp,
        suggested_next_action=suggested_action,
        recovery_recommendation=recovery_rec,
        reply_drafts_count=reply_drafts_count,
        latest_reply_draft_id=latest_reply_draft_id,
        latest_reply_draft_subject=latest_reply_draft_subject,
        llm_usage_summary=llm_usage_summary,
        calendar_day_summary=day_summary,
        energy_patterns_summary=energy_patterns_summary,
        stuck_tasks_count=stuck_tasks_count,
        recent_overload_events_count=recent_overload_events_count,
        # Execution Automation Pack
        message_summary=message_summary_data,
        next_action_prompt=next_action_prompt_data,
        recent_replan_events_count=recent_replan_events_count,
        urgent_messages_count=urgent_messages_count,
        needs_reply_count=needs_reply_count,
    )



def _build_next_action(db, user_id, open_tasks, selected_tasks, mode, latest_energy) -> NextAction | None:
    """
    Priority chain:
    1. Open micro-action from today's morning plan
    2. Open micro-action from top task (any source)
    3. Suggest decomposing the top task
    4. Suggest adding a task
    5. Suggest logging energy
    """
    # ── Priority 1: today's morning plan micro-action ──────────────────
    today_plan = copilot_repository.get_today_plan(db, user_id)
    if today_plan:
        plan_mas = micro_action_repository.get_open_by_plan(db, user_id, today_plan.id)
        if plan_mas:
            first_ma = plan_mas[0]
            return NextAction(
                type="planned_micro_action",
                message=f"Pick one small step: start with '{first_ma.title}'.",
                task_id=first_ma.task_id,
                micro_action_id=first_ma.id,
                micro_action_title=first_ma.title,
                duration_minutes=first_ma.duration_minutes,
                energy_cost=first_ma.energy_cost,
                sensory_cost=first_ma.sensory_cost,
                friction_level=first_ma.friction_level,
            )

    # ── Priority 2: open micro-action from top task ────────────────────
    top_tasks = selected_tasks or open_tasks
    for task in top_tasks:
        task_mas = micro_action_repository.get_open_by_task(db, user_id, task.id)
        if task_mas:
            first_ma = task_mas[0]
            return NextAction(
                type="existing_micro_action",
                message=f"Pick one small step: start with '{first_ma.title}'.",
                task_id=task.id,
                task_title=task.title,
                micro_action_id=first_ma.id,
                micro_action_title=first_ma.title,
                duration_minutes=first_ma.duration_minutes,
                energy_cost=first_ma.energy_cost,
                sensory_cost=first_ma.sensory_cost,
                friction_level=first_ma.friction_level,
            )

    # ── Priority 3: suggest decomposing the top task ───────────────────
    if top_tasks:
        top = top_tasks[0]
        return NextAction(
            type="needs_decomposition",
            message="Break this task into tiny actions to make it easier to start.",
            task_id=top.id,
            task_title=top.title,
        )

    # ── Priority 4: no open tasks at all ──────────────────────────────
    if not open_tasks:
        return NextAction(
            type="add_task",
            message="No open tasks yet. Add one task to get started.",
        )

    # ── Priority 5: no energy logged ──────────────────────────────────
    if not latest_energy:
        return NextAction(
            type="log_energy",
            message="Log your energy level so the plan can adjust to how you feel.",
        )

    # ── Fallback: recovery ─────────────────────────────────────────────
    if mode == "recovery":
        return NextAction(
            type="recovery",
            message="Today may need a lighter version. Rest is part of the plan.",
        )

    return None
