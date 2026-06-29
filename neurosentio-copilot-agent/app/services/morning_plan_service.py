"""
Morning Plan Service (Day 5).

Generates a structured daily plan from tasks, energy, micro-actions,
and overload risk. Rule-based, explainable, neurodivergent-friendly.

Rules:
- recovery mode if risk_score >= 60 or current_energy < 30
- normal mode: 3–5 micro-actions by available_minutes
- recovery mode: 1–2 micro-actions, at least one recovery block
- auto_decompose: if a task has no micro-actions, decompose it first
- include_transition_scripts: add up to 2 transition suggestions
- saves plan to CopilotPlan table
- links selected micro-actions to plan_id
"""

import logging
import uuid
from datetime import date, datetime, timezone, time, timedelta
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.repositories.task_repository import task_repository
from app.repositories.energy_repository import energy_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.repositories.copilot_repository import copilot_repository
from app.services.overload_service import calculate_overload_risk
from app.services.task_decomposer_service import decompose_task
from app.schemas.micro_action_schema import TaskDecomposeRequest
from app.schemas.morning_plan_schema import (
    MorningPlan,
    MorningPlanRequest,
    PlannedMicroAction,
    RecoveryBlock,
    TransitionSuggestion,
)
from app.models.micro_action import MicroAction as MicroActionModel
from app.models.copilot_plan import CopilotPlan

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _schedule_time(start_time: str, offset_minutes: int) -> str:
    """Compute HH:MM by adding offset_minutes to start_time string."""
    try:
        h, m = map(int, start_time.split(":"))
        total = h * 60 + m + offset_minutes
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        return start_time


def _pick_micro_actions(
    micro_actions: List[MicroActionModel],
    mode: str,
    available_minutes: int,
    max_count: int,
    stuck_task_ids: set,
) -> List[MicroActionModel]:
    """
    Select open micro-actions sorted by energy_cost (low first) for recovery,
    or by natural sort_order for normal mode.
    Stops when available_minutes would be exceeded.
    At most one stuck task micro-action in normal mode.
    """
    cost_order = {"low": 0, "medium": 1, "high": 2}
    open_actions = [a for a in micro_actions if a.status == "open"]

    if mode == "recovery":
        open_actions.sort(key=lambda a: cost_order.get(a.energy_cost or "low", 0))
    # else: keep natural sort_order ordering from DB

    selected = []
    time_used = 0
    stuck_actions_count = 0

    for action in open_actions:
        if len(selected) >= max_count:
            break
        
        # Stuck task logic: at most 1 stuck task micro-action in normal mode
        is_stuck = action.task_id in stuck_task_ids
        if is_stuck and mode != "recovery":
            if stuck_actions_count >= 1:
                continue

        dur = action.duration_minutes or 5
        if time_used + dur > available_minutes:
            break
            
        selected.append(action)
        time_used += dur
        if is_stuck:
            stuck_actions_count += 1

    return selected



def _build_transition_suggestions(
    selected: List[MicroActionModel],
    mode: str,
) -> List[TransitionSuggestion]:
    """
    Build up to 2 transition suggestions based on context.
    """
    suggestions: List[TransitionSuggestion] = []

    # Always suggest starting_work if we have micro-actions
    if selected:
        suggestions.append(
            TransitionSuggestion(
                transition_type="starting_work",
                title="Starting work",
                script_preview="Put your phone face down. Open only what you need.",
            )
        )

    # If any action title suggests a call
    call_keywords = {"call", "phone", "supplier", "client", "meeting", "dial"}
    for action in selected:
        if any(kw in action.title.lower() for kw in call_keywords):
            suggestions.append(
                TransitionSuggestion(
                    transition_type="making_call",
                    title="Making a call",
                    script_preview="Write the one thing you need to say. Start with 'Hi, I'm calling about…'",
                )
            )
            break

    # Recovery break if mode is recovery
    if mode == "recovery" and len(suggestions) < 2:
        suggestions.append(
            TransitionSuggestion(
                transition_type="recovery_break",
                title="Recovery break",
                script_preview="Step away from the screen. Drink water. No tasks right now.",
            )
        )

    return suggestions[:2]


def _build_summary(mode: str, count: int, energy: Optional[int]) -> str:
    if mode == "recovery":
        return (
            "Today may need a lighter version. "
            "The plan has been reduced to one small step and one recovery block."
        )
    if energy is None:
        return (
            "Log your energy when you can. "
            "For now, this plan stays gentle and flexible."
        )
    return (
        f"Here is a light plan to help you start without carrying the whole day at once. "
        f"{count} micro-action{'s' if count != 1 else ''} selected."
    )


# ──────────────────────────────────────────────────────────────────────
# Public service function
# ──────────────────────────────────────────────────────────────────────

async def generate_morning_plan(
    db: Session,
    user_id: str,
    request: MorningPlanRequest,
) -> MorningPlan:
    """
    Main entry point for morning plan generation.
    """
    plan_date = request.plan_date or datetime.now(timezone.utc).date()

    # ── 1. Check for existing plan today (unless force_regenerate) ────
    existing_plan = copilot_repository.get_plan_for_date(db, user_id, plan_date)
    if existing_plan and not request.force_regenerate:
        # Return the existing plan rebuilt from persisted micro-actions
        linked_mas = micro_action_repository.get_open_by_plan(db, user_id, existing_plan.id)
        return _build_response_from_existing(existing_plan, linked_mas, request)

    # ── 2. Fetch energy ───────────────────────────────────────────────
    energy_value = request.current_energy
    if energy_value is None:
        latest_energy_log = energy_repository.get_latest(db, user_id)
        if latest_energy_log:
            energy_value = latest_energy_log.battery_level

    sensory_state = request.sensory_state

    # ── 3. Fetch open tasks ───────────────────────────────────────────
    open_tasks = task_repository.get_open(db, user_id)
    high_priority = [t for t in open_tasks if t.priority == "high"]

    # ── 4. Fetch calendar context safely ──────────────────────────────
    day_summary = None
    try:
        from app.repositories.calendar_repository import calendar_repository
        from app.services.calendar_analysis_service import build_day_summary, mark_back_to_back
        day_events = calendar_repository.list_events_for_day(db, user_id, plan_date)
        if day_events:
            mark_back_to_back(day_events)
            db.commit()
            day_events = calendar_repository.list_events_for_day(db, user_id, plan_date)
        day_summary = build_day_summary(day_events, plan_date)
    except Exception as e:
        logger.warning("Failed to fetch calendar summary in morning plan: %s", e)

    # ── 5. Fetch energy patterns safely ───────────────────────────────
    energy_patterns_summary = None
    try:
        from app.services.energy_pattern_service import get_energy_patterns
        energy_patterns_summary = get_energy_patterns(db, user_id, days=14)
    except Exception as e:
        logger.warning("Failed to fetch energy patterns in morning plan: %s", e)

    # ── 6. Fetch stuck tasks safely ───────────────────────────────────
    stuck_tasks = []
    stuck_task_ids = set()
    try:
        from app.services.stuck_task_service import detect_stuck_tasks
        stuck_tasks = detect_stuck_tasks(db, user_id, threshold_days=3)
        stuck_task_ids = {item["task"].id for item in stuck_tasks}
    except Exception as e:
        logger.warning("Failed to fetch stuck tasks in morning plan: %s", e)

    # ── 7. Calculate overload risk ────────────────────────────────────
    from app.models.energy_log import EnergyLog as EnergyLogModel
    energy_obj = None
    if energy_value is not None:
        # Build a transient object for the risk calculator
        energy_obj = type("EnergyObj", (), {
            "battery_level": energy_value,
            "sensory_state": sensory_state or "unknown",
        })()

    risk = calculate_overload_risk(
        latest_energy=energy_obj,
        open_tasks_count=len(open_tasks),
        high_priority_count=len(high_priority),
        event_count=day_summary.event_count if day_summary else None,
        back_to_back_count=day_summary.back_to_back_count if day_summary else None,
        high_load_event_exists=(day_summary.high_load_event_count > 0) if day_summary else None,
        total_meeting_minutes=day_summary.total_meeting_minutes if day_summary else None,
    )
    risk_score = risk["risk_score"]
    mode = risk["mode"]

    # Override mode based on explicit energy
    if energy_value is not None and energy_value < 30:
        mode = "recovery"

    # ── 8. Log Overload Event if risk_score >= 60 ────────────────────
    if risk_score >= 60:
        try:
            from app.repositories.overload_event_repository import overload_event_repository
            latest_overload = overload_event_repository.get_latest(db, user_id)
            should_log = True
            if latest_overload:
                time_diff = datetime.now(timezone.utc) - latest_overload.detected_at.replace(tzinfo=timezone.utc)
                if time_diff.total_seconds() <= 1800:  # 30 minutes
                    if abs(latest_overload.risk_score - risk_score) < 15:
                        should_log = False
            
            if should_log:
                overload_event_repository.create(
                    db=db,
                    user_id=user_id,
                    risk_score=risk_score,
                    mode=mode,
                    trigger_reasons=risk["reasons"],
                    energy_score=energy_value,
                    calendar_load_score=day_summary.high_load_event_count * 20 if day_summary else 0,
                    open_task_count=len(open_tasks),
                    high_priority_task_count=len(high_priority),
                    stuck_task_count=len(stuck_tasks),
                    message="Overload risk detected during morning plan generation.",
                )
        except Exception as exc:
            logger.warning("Failed to log overload event: %s", exc)

    # ── 9. Determine action limits (with scaling for heavy load) ─────
    if mode == "recovery":
        max_actions = 2
    else:
        # Scale with available_minutes: ~1 action per 20 mins, capped at 5
        max_actions = min(5, max(3, request.available_minutes // 20))

    # Scale down limit if calendar is heavy
    is_calendar_heavy = False
    if day_summary:
        if day_summary.event_count >= 4 or day_summary.total_meeting_minutes > 120 or day_summary.back_to_back_count > 0:
            is_calendar_heavy = True
            if mode == "recovery":
                max_actions = 1
            else:
                max_actions = max(2, max_actions - 1)

    # ── 10. Collect all open micro-actions; auto-decompose if needed ──
    all_open_micro_actions: List[MicroActionModel] = []

    for task in open_tasks:
        task_mas = micro_action_repository.get_open_by_task(db, user_id, task.id)
        if task_mas:
            all_open_micro_actions.extend(task_mas)
        elif request.auto_decompose:
            try:
                decomp = await decompose_task(
                    db=db,
                    user_id=user_id,
                    task_id=task.id,
                    request=TaskDecomposeRequest(
                        current_energy=energy_value,
                        sensory_state=sensory_state,
                        max_actions=max_actions,
                        force_regenerate=False,
                    ),
                )
                newly_created = micro_action_repository.get_open_by_task(db, user_id, task.id)
                all_open_micro_actions.extend(newly_created)
            except Exception as exc:
                logger.warning("Auto-decompose failed for task %s: %s", task.id, exc)

    # ── 11. Select micro-actions ──────────────────────────────────────
    selected_mas = _pick_micro_actions(
        all_open_micro_actions, mode, request.available_minutes, max_actions, stuck_task_ids
    )

    # ── 12. Save plan to DB ───────────────────────────────────────────
    plan_id = str(uuid.uuid4())
    plan = CopilotPlan(
        id=plan_id,
        user_id=user_id,
        plan_date=plan_date,
        mode=mode,
        summary=_build_summary(mode, len(selected_mas), energy_value),
        generated_payload={
            "overload_risk_score": risk_score,
            "energy_value": energy_value,
            "mode": mode,
        },
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    # ── 13. Link micro-actions to plan ────────────────────────────────
    for ma in selected_mas:
        ma.plan_id = plan_id
    db.commit()

    # ── 14. Build scheduled items into Free Blocks with Energy Hours ──
    high_energy_hours = []
    if energy_patterns_summary:
        high_energy_hours = energy_patterns_summary.get("high_energy_hours", [])

    # Extract slots from free blocks or fall back to 09:00 - 17:00
    sched_slots = []
    if day_summary and day_summary.free_blocks:
        try:
            req_time = datetime.strptime(request.start_time, "%H:%M").time()
            sched_start = max(
                datetime.combine(plan_date, time(9, 0)),
                datetime.combine(plan_date, req_time)
            )
        except Exception:
            sched_start = datetime.combine(plan_date, time(9, 0))

        for fb in day_summary.free_blocks:
            s = max(fb.start_time.replace(tzinfo=None), sched_start)
            e = fb.end_time.replace(tzinfo=None)
            if s < e:
                sched_slots.append({"start": s, "end": e})
    else:
        try:
            req_time = datetime.strptime(request.start_time, "%H:%M").time()
            sched_start = max(
                datetime.combine(plan_date, time(9, 0)),
                datetime.combine(plan_date, req_time)
            )
        except Exception:
            sched_start = datetime.combine(plan_date, time(9, 0))
            
        day_end = datetime.combine(plan_date, time(17, 0))
        if sched_start < day_end:
            sched_slots.append({"start": sched_start, "end": day_end})

    planned_items: List[PlannedMicroAction] = []
    time_offset = 0

    for ma in selected_mas:
        dur = ma.duration_minutes or 5
        energy_cost = ma.energy_cost or "low"
        
        scheduled_dt = None
        
        # 1. Try peak energy alignment
        if energy_cost in ["medium", "high"] and high_energy_hours:
            for slot in sched_slots:
                s_hour = slot["start"].hour
                avail_dur = (slot["end"] - slot["start"]).total_seconds() / 60
                if s_hour in high_energy_hours and avail_dur >= dur:
                    scheduled_dt = slot["start"]
                    slot["start"] += timedelta(minutes=dur)
                    break
        
        # 2. Fallback to first available free space
        if not scheduled_dt:
            for slot in sched_slots:
                avail_dur = (slot["end"] - slot["start"]).total_seconds() / 60
                if avail_dur >= dur:
                    scheduled_dt = slot["start"]
                    slot["start"] += timedelta(minutes=dur)
                    break
                    
        scheduled_time_str = None
        if scheduled_dt:
            scheduled_time_str = scheduled_dt.strftime("%H:%M")
            time_offset += dur
            
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=ma.id,
                task_id=ma.task_id,
                title=ma.title,
                description=ma.description,
                scheduled_time=scheduled_time_str,
                duration_minutes=ma.duration_minutes,
                energy_cost=ma.energy_cost,
                sensory_cost=ma.sensory_cost,
                friction_level=ma.friction_level,
                status=ma.status,
            )
        )

    # ── 15. Recovery blocks ───────────────────────────────────────────
    recovery_blocks: List[RecoveryBlock] = []
    if mode == "recovery":
        recovery_blocks.append(
            RecoveryBlock(
                title="Recovery break",
                reason="Your energy is low — rest is part of the plan.",
                suggested_duration_minutes=15,
            )
        )

    # Add recovery block if back-to-back meetings exist
    if day_summary and day_summary.back_to_back_count > 0:
        recovery_blocks.append(
            RecoveryBlock(
                title="Post-Meeting Recovery Break",
                reason="You have back-to-back meetings today. Take 15 minutes to decompress.",
                suggested_duration_minutes=15,
            )
        )

    # ── 16. Transition suggestions ────────────────────────────────────
    transition_suggestions: List[TransitionSuggestion] = []
    if request.include_transition_scripts:
        transition_suggestions = _build_transition_suggestions(selected_mas, mode)

    # ── 17. Message & Stuck Task advice ───────────────────────────────
    has_stuck = any(ma.task_id in stuck_task_ids for ma in selected_mas)
    
    if mode == "recovery":
        message = "Today may need a lighter version. Let's start with one small step."
        if has_stuck:
            message += " We recommend using the 'make smaller' action on your stuck task to ease in."
    elif energy_value is None:
        message = "Log your energy when you can. For now, this plan stays gentle and flexible."
    else:
        message = "Let's make this easier to start. Pick the first action and go from there."
        if has_stuck:
            message += " Focus on starting small on the stuck task."

    return MorningPlan(
        plan_id=plan_id,
        plan_date=plan_date,
        mode=mode,
        summary=_build_summary(mode, len(planned_items), energy_value),
        total_scheduled_minutes=time_offset,
        overload_risk_score=risk_score,
        selected_micro_actions=planned_items,
        recovery_blocks=recovery_blocks,
        transition_suggestions=transition_suggestions,
        message=message,
        created_at=plan.created_at,
    )


def _build_response_from_existing(
    plan: CopilotPlan,
    linked_mas: List[MicroActionModel],
    request: MorningPlanRequest,
) -> MorningPlan:
    """Rebuild a MorningPlan response from a persisted plan record."""
    payload = plan.generated_payload or {}
    time_offset = 0
    planned_items = []
    for ma in linked_mas:
        scheduled = _schedule_time(request.start_time, time_offset)
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=ma.id,
                task_id=ma.task_id,
                title=ma.title,
                description=ma.description,
                scheduled_time=scheduled,
                duration_minutes=ma.duration_minutes,
                energy_cost=ma.energy_cost,
                sensory_cost=ma.sensory_cost,
                friction_level=ma.friction_level,
                status=ma.status,
            )
        )
        time_offset += ma.duration_minutes or 5

    return MorningPlan(
        plan_id=plan.id,
        plan_date=plan.plan_date,
        mode=plan.mode,
        summary=plan.summary or "",
        total_scheduled_minutes=time_offset,
        overload_risk_score=payload.get("overload_risk_score", 0),
        selected_micro_actions=planned_items,
        recovery_blocks=[],
        transition_suggestions=_build_transition_suggestions(linked_mas, plan.mode),
        message="Your plan for today is already set. Let's make this easier to start.",
        created_at=plan.created_at,
    )

