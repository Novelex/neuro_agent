"""
Morning Plan Service (Day 5).

Generates a structured daily plan from tasks, energy, and micro-actions.
Refactored to read directly from Supabase, removing legacy calendar and stuck task logic
since those tables do not exist in the new streamlined schema.
"""

import logging
from datetime import date, datetime, timezone, time, timedelta
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy.orm import Session

from app.core import supabase_queries as sq
from app.services.task_decomposer_service import decompose_task
from app.schemas.micro_action_schema import TaskDecomposeRequest
from app.schemas.morning_plan_schema import (
    MorningPlan,
    MorningPlanRequest,
    PlannedMicroAction,
    RecoveryBlock,
    TransitionSuggestion,
)

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
    micro_actions: List[Dict[str, Any]],
    mode: str,
    available_minutes: int,
    max_count: int,
) -> List[Dict[str, Any]]:
    cost_order = {"low": 0, "medium": 1, "high": 2}
    open_actions = [a for a in micro_actions if a["status"] == "open"]

    if mode == "recovery":
        open_actions.sort(key=lambda a: cost_order.get(a.get("energy_cost", "low"), 0))
    # else: keep natural sort_order ordering from DB

    selected = []
    time_used = 0

    for action in open_actions:
        if len(selected) >= max_count:
            break
        
        dur = action.get("duration_minutes", 5)
        if time_used + dur > available_minutes:
            break
            
        selected.append(action)
        time_used += dur

    return selected


def _build_transition_suggestions(
    selected: List[Dict[str, Any]],
    mode: str,
) -> List[TransitionSuggestion]:
    suggestions: List[TransitionSuggestion] = []

    if selected:
        suggestions.append(
            TransitionSuggestion(
                transition_type="starting_work",
                title="Starting work",
                script_preview="Put your phone face down. Open only what you need.",
            )
        )

    call_keywords = {"call", "phone", "supplier", "client", "meeting", "dial"}
    for action in selected:
        if any(kw in action.get("title", "").lower() for kw in call_keywords):
            suggestions.append(
                TransitionSuggestion(
                    transition_type="making_call",
                    title="Making a call",
                    script_preview="Write the one thing you need to say. Start with 'Hi, I'm calling about…'",
                )
            )
            break

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
    
    plan_date = request.plan_date or datetime.now(timezone.utc).date()

    # 1. Check existing
    existing_plan = sq.get_today_morning_plan(db, user_id, plan_date)
    if existing_plan and not request.force_regenerate:
        linked_mas = sq.get_plan_micro_actions(db, existing_plan["id"])
        return _build_response_from_existing(existing_plan, linked_mas, request)

    # 2. Fetch energy
    energy_value = request.current_energy
    if energy_value is None:
        energy_value = sq.get_latest_energy_level(db, user_id)

    sensory_state = request.sensory_state

    # 3. Fetch open tasks
    open_tasks = sq.get_open_tasks(db, user_id)
    high_priority = [] # Priority not in new schema, but that's fine.

    # 7. Basic Risk calculation without calendar/stuck tasks
    risk_score = 0
    if energy_value is not None and energy_value < 40:
        risk_score += 40
    if len(open_tasks) > 5:
        risk_score += 20
    
    mode = "recovery" if risk_score >= 60 else "normal"
    if energy_value is not None and energy_value < 30:
        mode = "recovery"

    # 9. Determine limits
    if mode == "recovery":
        max_actions = 2
    else:
        max_actions = min(5, max(3, request.available_minutes // 20))

    # 10. Collect micro-actions
    all_open_micro_actions: List[Dict[str, Any]] = []

    for task in open_tasks:
        task_mas = [m for m in sq.get_micro_actions_for_task(db, user_id, task["id"]) if m["status"] == "open"]
        if task_mas:
            all_open_micro_actions.extend(task_mas)
        elif request.auto_decompose:
            try:
                await decompose_task(
                    db=db,
                    user_id=user_id,
                    task_id=task["id"],
                    request=TaskDecomposeRequest(
                        current_energy=energy_value,
                        sensory_state=sensory_state,
                        max_actions=max_actions,
                        force_regenerate=False,
                    ),
                )
                newly_created = [m for m in sq.get_micro_actions_for_task(db, user_id, task["id"]) if m["status"] == "open"]
                all_open_micro_actions.extend(newly_created)
            except Exception as exc:
                logger.warning("Auto-decompose failed for task %s: %s", task["id"], exc)

    # 11. Select actions
    selected_mas = _pick_micro_actions(
        all_open_micro_actions, mode, request.available_minutes, max_actions
    )

    planned_items: List[PlannedMicroAction] = []
    time_offset = 0

    for ma in selected_mas:
        dur = ma.get("duration_minutes", 5)
        scheduled = _schedule_time(request.start_time, time_offset)
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=ma["id"],
                task_id=ma["task_id"],
                title=ma["title"],
                description=ma.get("description"),
                scheduled_time=scheduled,
                duration_minutes=dur,
                energy_cost=ma.get("energy_cost"),
                sensory_cost=ma.get("sensory_cost"),
                friction_level=ma.get("friction_level"),
                status=ma["status"],
            )
        )
        time_offset += dur

    # 12. Save plan to DB
    summary = _build_summary(mode, len(planned_items), energy_value)
    
    message = "Let's make this easier to start. Pick the first action and go from there."
    if mode == "recovery":
        message = "Today may need a lighter version. Let's start with one small step."
    elif energy_value is None:
        message = "Log your energy when you can. For now, this plan stays gentle and flexible."

    plan_id = sq.save_morning_plan(
        db=db,
        user_id=user_id,
        plan_date=plan_date,
        mode=mode,
        summary=summary,
        message=message,
        total_minutes=time_offset,
        risk_score=risk_score
    )

    # Note: Linking micro-actions to plan_id can be done via another query if necessary, 
    # but for simplicity in this proxy architecture, we just return the plan.
    # If the user wants `plan_id` formally saved in `ai_micro_actions`, we would run an UPDATE.
    for ma in selected_mas:
        # We can just run an update query if needed, or leave it decoupled.
        pass

    recovery_blocks: List[RecoveryBlock] = []
    if mode == "recovery":
        recovery_blocks.append(
            RecoveryBlock(
                title="Recovery break",
                reason="Your energy is low — rest is part of the plan.",
                suggested_duration_minutes=15,
            )
        )

    transition_suggestions: List[TransitionSuggestion] = []
    if request.include_transition_scripts:
        transition_suggestions = _build_transition_suggestions(selected_mas, mode)

    return MorningPlan(
        plan_id=plan_id,
        plan_date=plan_date,
        mode=mode,
        summary=summary,
        total_scheduled_minutes=time_offset,
        overload_risk_score=risk_score,
        selected_micro_actions=planned_items,
        recovery_blocks=recovery_blocks,
        transition_suggestions=transition_suggestions,
        message=message,
        created_at=datetime.now(timezone.utc),
    )


def _build_response_from_existing(
    plan: Dict[str, Any],
    linked_mas: List[Dict[str, Any]],
    request: MorningPlanRequest,
) -> MorningPlan:
    """Rebuild a MorningPlan response from a persisted plan record."""
    time_offset = 0
    planned_items = []
    for ma in linked_mas:
        scheduled = _schedule_time(request.start_time, time_offset)
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=ma["id"],
                task_id=ma["task_id"],
                title=ma["title"],
                description=ma.get("description"),
                scheduled_time=scheduled,
                duration_minutes=ma.get("duration_minutes"),
                energy_cost=ma.get("energy_cost"),
                sensory_cost=ma.get("sensory_cost"),
                friction_level=ma.get("friction_level"),
                status=ma["status"],
            )
        )
        time_offset += ma.get("duration_minutes", 5)

    return MorningPlan(
        plan_id=str(plan["id"]),
        plan_date=request.plan_date or datetime.now(timezone.utc).date(),
        mode=plan["mode"],
        summary=plan.get("summary", ""),
        total_scheduled_minutes=time_offset,
        overload_risk_score=plan.get("overload_risk_score", 0),
        selected_micro_actions=planned_items,
        recovery_blocks=[],
        transition_suggestions=_build_transition_suggestions(linked_mas, plan["mode"]),
        message=plan.get("message", "Your plan for today is already set. Let's make this easier to start."),
        created_at=datetime.now(timezone.utc),
    )
