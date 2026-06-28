"""
Adaptive Replanner Service.

Adjusts the remaining day plan based on triggers without destroying progress.
Rule-based. No LLM. Explainable.

Triggers:
- low_energy: reduce actions, defer high-energy, add recovery block
- skipped_actions: simplify to top 2 actions
- calendar_overload: reduce action count, add recovery block
- urgent_message: include at most one draft_reply action
- manual: general replan
- recovery_mode: recovery-first plan
- stuck_tasks: include at most one stuck task action
"""

import logging
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.repositories.copilot_repository import copilot_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.repositories.replan_event_repository import replan_event_repository
from app.repositories.energy_repository import energy_repository
from app.repositories.task_repository import task_repository
from app.models.copilot_plan import CopilotPlan
from app.schemas.morning_plan_schema import PlannedMicroAction, RecoveryBlock
from app.schemas.replan_schema import ReplanRequest
from app.services.next_action_service import get_or_create_next_action

logger = logging.getLogger(__name__)


def replan_day(
    db: Session,
    user_id: str,
    request: ReplanRequest,
) -> Dict[str, Any]:
    """
    Adaptive replan. Returns a dict compatible with ReplanResult schema.
    """
    now = datetime.now(timezone.utc)
    today = date.today()

    # ── Determine mode ─────────────────────────────────────────────────
    current_energy = request.current_energy
    sensory_state = request.sensory_state
    trigger = request.trigger_type

    mode_before = "normal"
    mode_after = "normal"

    # Fetch existing energy if not provided
    if current_energy is None:
        latest_energy = energy_repository.get_latest(db, user_id)
        if latest_energy:
            current_energy = latest_energy.battery_level
    else:
        from app.schemas.energy_log_schema import EnergyCreate
        try:
            latest_energy = energy_repository.create(db, user_id, EnergyCreate(
                battery_level=current_energy,
                sensory_state=sensory_state or "unknown",
                note=f"Logged automatically during replan (trigger: {trigger})"
            ))
        except Exception as e:
            logger.warning("Failed to automatically log energy during replan: %s", e)
            latest_energy = None

    # Determine mode_after
    if current_energy is not None and current_energy < 30:
        mode_after = "recovery"
    elif trigger in ("recovery_mode", "low_energy"):
        mode_after = "recovery"

    # Fetch previous plan
    previous_plan = copilot_repository.get_today_plan(db, user_id)
    if previous_plan:
        mode_before = previous_plan.mode

    # ── Fetch current micro-actions ────────────────────────────────────
    open_tasks = task_repository.get_open(db, user_id)
    all_open_mas = []
    completed_mas = []

    for task in open_tasks:
        task_mas = micro_action_repository.get_by_task(db, user_id, task.id)
        for ma in task_mas:
            if ma.status in ("done", "skipped"):
                if request.preserve_completed:
                    completed_mas.append(ma)
            elif ma.status == "open":
                all_open_mas.append(ma)

    # ── Apply trigger-specific rules ───────────────────────────────────
    selected_mas = []
    deferred_mas = []
    added_actions = []
    recovery_blocks: List[RecoveryBlock] = []

    if mode_after == "recovery" or trigger == "low_energy":
        # Select max 1-2 low-friction actions
        low_friction = [
            ma for ma in all_open_mas
            if ma.energy_cost in (None, "low", "medium")
        ]
        if request.defer_high_energy:
            high_energy_mas = [
                ma for ma in all_open_mas
                if ma.energy_cost == "high"
            ]
            deferred_mas = high_energy_mas
            selected_mas = low_friction[:2]
        else:
            selected_mas = all_open_mas[:2]

        recovery_blocks.append(RecoveryBlock(
            title="Recovery break",
            reason="Your energy is low — rest is part of the plan.",
            suggested_duration_minutes=15,
        ))

    elif trigger == "skipped_actions":
        # Count how many were skipped today from all micro-actions of open tasks
        skipped_count = 0
        for task in open_tasks:
            task_mas = micro_action_repository.get_by_task(db, user_id, task.id)
            skipped_count += sum(1 for ma in task_mas if ma.status == "skipped")
        all_open_in_plan = all_open_mas
        if skipped_count >= 3 or len(completed_mas) == 0:
            # Simplify to top 2
            selected_mas = all_open_in_plan[:2]
        else:
            selected_mas = all_open_in_plan[:3]

    elif trigger == "calendar_overload":
        # Reduce action count, add recovery block
        selected_mas = all_open_mas[:2]
        recovery_blocks.append(RecoveryBlock(
            title="Calendar relief break",
            reason="Your calendar is heavily loaded today. A buffer break helps.",
            suggested_duration_minutes=15,
        ))

    elif trigger == "urgent_message" and request.include_urgent_messages:
        # Include actions but add a note about urgent messages
        selected_mas = all_open_mas[:3]
        # The draft_reply action will be added via next_action service

    elif trigger == "stuck_tasks":
        # Include at most one stuck task action, prefer make-smaller
        stuck_mas = []
        non_stuck_mas = []
        try:
            from app.services.stuck_task_service import detect_stuck_tasks
            stuck = detect_stuck_tasks(db, user_id, threshold_days=3)
            stuck_ids = {s["task"].id for s in stuck}
            for ma in all_open_mas:
                if ma.task_id in stuck_ids:
                    stuck_mas.append(ma)
                else:
                    non_stuck_mas.append(ma)
            # At most 1 stuck task action, rest from non-stuck
            selected_mas = stuck_mas[:1] + non_stuck_mas[:3]
        except Exception as e:
            logger.warning("Failed to detect stuck tasks: %s", e)
            selected_mas = all_open_mas[:3]

    else:
        # Manual or other trigger: light replan
        selected_mas = all_open_mas[:3]

    # ── Create new CopilotPlan ─────────────────────────────────────────
    summary = _build_summary(trigger, mode_after, len(selected_mas), len(deferred_mas))
    new_plan_id = str(uuid.uuid4())
    new_plan = CopilotPlan(
        id=new_plan_id,
        user_id=user_id,
        plan_date=today,
        mode=mode_after,
        summary=summary,
        generated_payload={
            "trigger": trigger,
            "mode_before": mode_before,
            "mode_after": mode_after,
            "replanned_at": now.isoformat(),
            "current_energy": current_energy,
        },
    )
    db.add(new_plan)

    # Link selected micro-actions to new plan
    for ma in selected_mas:
        ma.plan_id = new_plan_id

    db.commit()
    db.refresh(new_plan)

    # ── Log ReplanEvent ────────────────────────────────────────────────
    event_payload = {
        "trigger_type": trigger,
        "trigger_details": {
            "reason": request.reason,
            "current_energy": current_energy,
            "sensory_state": sensory_state,
        },
        "previous_plan_id": previous_plan.id if previous_plan else None,
        "new_plan_id": new_plan_id,
        "mode_before": mode_before,
        "mode_after": mode_after,
        "actions_preserved_count": len(completed_mas),
        "actions_deferred_count": len(deferred_mas),
        "actions_added_count": len(added_actions),
        "summary": summary,
    }
    replan_event = replan_event_repository.create(db, user_id, event_payload)

    # ── Build PlannedMicroAction list for response ─────────────────────
    selected_action_responses = []
    for ma in selected_mas:
        selected_action_responses.append(PlannedMicroAction(
            micro_action_id=ma.id,
            task_id=ma.task_id,
            title=ma.title,
            description=ma.description,
            scheduled_time=None,  # Not scheduled in replan; let next-action handle it
            duration_minutes=ma.duration_minutes,
            energy_cost=ma.energy_cost,
            sensory_cost=ma.sensory_cost,
            friction_level=ma.friction_level,
            status=ma.status,
        ))

    # ── Get next action prompt ─────────────────────────────────────────
    next_prompt = None
    try:
        prompt, _, _ = get_or_create_next_action(db, user_id)
        next_prompt = prompt
    except Exception as e:
        logger.warning("Failed to get next action in replan: %s", e)

    # ── Build replan event schema ──────────────────────────────────────
    from app.schemas.replan_schema import ReplanEvent as ReplanEventSchema
    replan_event_schema = ReplanEventSchema.model_validate(replan_event)

    # ── Next action prompt schema ──────────────────────────────────────
    next_prompt_schema = None
    if next_prompt:
        from app.schemas.next_action_schema import NextActionPrompt as NAPSchema
        next_prompt_schema = NAPSchema.model_validate(next_prompt)

    return {
        "event": replan_event_schema,
        "new_plan_id": new_plan_id,
        "summary": summary,
        "selected_actions": selected_action_responses,
        "deferred_actions_count": len(deferred_mas),
        "recovery_blocks": recovery_blocks,
        "next_action": next_prompt_schema,
    }


def _build_summary(
    trigger: str,
    mode_after: str,
    selected_count: int,
    deferred_count: int,
) -> str:
    """Build a gentle, explainable summary for the replan."""
    if mode_after == "recovery":
        return (
            "Your plan has been reduced so the next step is easier to start. "
            "Rest is part of the plan."
        )
    if trigger == "urgent_message":
        return (
            "One urgent reply was added, but the rest of the plan stays light."
        )
    if deferred_count > 0:
        return (
            f"High-energy tasks were moved out of the way for now. "
            f"{selected_count} lighter actions remain."
        )
    if trigger == "skipped_actions":
        return (
            "Your plan has been simplified to make the next step easier to start."
        )
    return (
        f"Your plan has been adjusted. "
        f"{selected_count} action{'s' if selected_count != 1 else ''} selected for the rest of the day."
    )
