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

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
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
) -> List[MicroActionModel]:
    """
    Select open micro-actions sorted by energy_cost (low first) for recovery,
    or by natural sort_order for normal mode.
    Stops when available_minutes would be exceeded.
    """
    cost_order = {"low": 0, "medium": 1, "high": 2}
    open_actions = [a for a in micro_actions if a.status == "open"]

    if mode == "recovery":
        open_actions.sort(key=lambda a: cost_order.get(a.energy_cost or "low", 0))
    # else: keep natural sort_order ordering from DB

    selected = []
    time_used = 0
    for action in open_actions:
        if len(selected) >= max_count:
            break
        dur = action.duration_minutes or 5
        if time_used + dur > available_minutes:
            break
        selected.append(action)
        time_used += dur
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
    plan_date = request.plan_date or date.today()

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

    # ── 4. Calculate overload risk ────────────────────────────────────
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
    )
    risk_score = risk["risk_score"]
    mode = risk["mode"]

    # Override mode based on explicit energy
    if energy_value is not None and energy_value < 30:
        mode = "recovery"

    # ── 5. Determine action limits ────────────────────────────────────
    if mode == "recovery":
        max_actions = 2
    else:
        # Scale with available_minutes: ~1 action per 20 mins, capped at 5
        max_actions = min(5, max(3, request.available_minutes // 20))

    # ── 6. Collect all open micro-actions; auto-decompose if needed ───
    all_open_micro_actions: List[MicroActionModel] = []

    for task in open_tasks:
        task_mas = micro_action_repository.get_open_by_task(db, user_id, task.id)
        if task_mas:
            all_open_micro_actions.extend(task_mas)
        elif request.auto_decompose:
            # Auto-decompose — safe, won't duplicate
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

    # ── 7. Select micro-actions ───────────────────────────────────────
    selected_mas = _pick_micro_actions(
        all_open_micro_actions, mode, request.available_minutes, max_actions
    )

    # ── 8. Save plan to DB ────────────────────────────────────────────
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

    # ── 9. Link micro-actions to plan ─────────────────────────────────
    for ma in selected_mas:
        ma.plan_id = plan_id
    db.commit()

    # ── 10. Build scheduled items ─────────────────────────────────────
    time_offset = 0
    planned_items: List[PlannedMicroAction] = []
    for ma in selected_mas:
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

    # ── 11. Recovery blocks ───────────────────────────────────────────
    recovery_blocks: List[RecoveryBlock] = []
    if mode == "recovery":
        recovery_blocks.append(
            RecoveryBlock(
                title="Recovery break",
                reason="Your energy is low — rest is part of the plan.",
                suggested_duration_minutes=15,
            )
        )

    # ── 12. Transition suggestions ────────────────────────────────────
    transition_suggestions: List[TransitionSuggestion] = []
    if request.include_transition_scripts:
        transition_suggestions = _build_transition_suggestions(selected_mas, mode)

    # ── 13. Message ───────────────────────────────────────────────────
    if mode == "recovery":
        message = "Today may need a lighter version. Let's start with one small step."
    elif energy_value is None:
        message = "Log your energy when you can. For now, this plan stays gentle and flexible."
    else:
        message = "Let's make this easier to start. Pick the first action and go from there."

    return MorningPlan(
        plan_id=plan_id,
        plan_date=plan_date,
        mode=mode,
        summary=_build_summary(mode, len(planned_items), energy_value),
        energy_used=time_offset,
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
        energy_used=time_offset,
        overload_risk_score=payload.get("overload_risk_score", 0),
        selected_micro_actions=planned_items,
        recovery_blocks=[],
        transition_suggestions=_build_transition_suggestions(linked_mas, plan.mode),
        message="Your plan for today is already set. Let's make this easier to start.",
        created_at=plan.created_at,
    )
