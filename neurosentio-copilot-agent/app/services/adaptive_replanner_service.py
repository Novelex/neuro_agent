"""
Adaptive Replanner Service.

Adjusts the remaining day plan based on triggers without destroying progress.
Refactored to use Supabase raw queries and removed legacy dependencies.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.morning_plan_schema import PlannedMicroAction, RecoveryBlock
from app.schemas.replan_schema import ReplanRequest

logger = logging.getLogger(__name__)


def replan_day(
    db: Connection,
    user_id: str,
    request: ReplanRequest,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date()

    # ── Determine mode ─────────────────────────────────────────────────
    current_energy = request.current_energy
    sensory_state = request.sensory_state
    trigger = request.trigger_type

    mode_before = "normal"
    mode_after = "normal"

    if current_energy is None:
        current_energy = sq.get_latest_energy_level(db, user_id)

    if current_energy is not None and current_energy < 30:
        mode_after = "recovery"
    elif trigger in ("recovery_mode", "low_energy"):
        mode_after = "recovery"

    previous_plan = sq.get_today_morning_plan(db, user_id, today)
    if previous_plan:
        mode_before = previous_plan.get("mode", "normal")

    # ── Fetch current micro-actions ────────────────────────────────────
    open_tasks = sq.get_open_tasks(db, user_id)
    all_open_mas = []
    completed_mas = []

    for task in open_tasks:
        task_mas = sq.get_micro_actions_for_task(db, user_id, task["id"])
        for ma in task_mas:
            if ma["status"] in ("done", "skipped"):
                if request.preserve_completed:
                    completed_mas.append(ma)
            elif ma["status"] == "open":
                all_open_mas.append(ma)

    # ── Apply trigger-specific rules ───────────────────────────────────
    selected_mas = []
    deferred_mas = []
    added_actions = []
    recovery_blocks: List[RecoveryBlock] = []

    if mode_after == "recovery" or trigger == "low_energy":
        low_friction = [
            ma for ma in all_open_mas
            if ma.get("energy_cost") in (None, "low", "medium")
        ]
        if request.defer_high_energy:
            high_energy_mas = [
                ma for ma in all_open_mas
                if ma.get("energy_cost") == "high"
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
        skipped_count = 0
        for task in open_tasks:
            task_mas = sq.get_micro_actions_for_task(db, user_id, task["id"])
            skipped_count += sum(1 for ma in task_mas if ma["status"] == "skipped")
        if skipped_count >= 3 or len(completed_mas) == 0:
            selected_mas = all_open_mas[:2]
        else:
            selected_mas = all_open_mas[:3]

    elif trigger == "calendar_overload":
        selected_mas = all_open_mas[:2]
        recovery_blocks.append(RecoveryBlock(
            title="Relief break",
            reason="Your day is heavily loaded. A buffer break helps.",
            suggested_duration_minutes=15,
        ))

    elif trigger == "urgent_message" and request.include_urgent_messages:
        selected_mas = all_open_mas[:3]

    elif trigger == "stuck_tasks":
        # Simplified stuck task handling: just take one high priority or oldest task
        if all_open_mas:
            selected_mas = [all_open_mas[0]] + all_open_mas[1:3]
        else:
            selected_mas = all_open_mas[:3]

    else:
        selected_mas = all_open_mas[:3]

    # ── Create new Plan Record ─────────────────────────────────────────
    summary = _build_summary(trigger, mode_after, len(selected_mas), len(deferred_mas))
    
    # Save the updated plan
    new_plan_id = sq.save_morning_plan(
        conn=db,
        user_id=user_id,
        plan_date=today,
        mode=mode_after,
        summary=summary,
        message=summary,
        total_minutes=sum([ma.get("duration_minutes", 5) for ma in selected_mas]),
        risk_score=previous_plan.get("overload_risk_score", 0) if previous_plan else 0
    )

    # ── Build PlannedMicroAction list for response ─────────────────────
    selected_action_responses = []
    for ma in selected_mas:
        selected_action_responses.append(PlannedMicroAction(
            micro_action_id=ma["id"],
            task_id=ma["task_id"],
            title=ma["title"],
            description=ma.get("description"),
            scheduled_time=None,
            duration_minutes=ma.get("duration_minutes"),
            energy_cost=ma.get("energy_cost"),
            sensory_cost=ma.get("sensory_cost"),
            friction_level=ma.get("friction_level"),
            status=ma["status"],
        ))

    return {
        "event": {
            "trigger_type": trigger,
            "mode_before": mode_before,
            "mode_after": mode_after,
            "summary": summary
        },
        "new_plan_id": str(new_plan_id),
        "summary": summary,
        "selected_actions": selected_action_responses,
        "deferred_actions_count": len(deferred_mas),
        "recovery_blocks": recovery_blocks,
        "next_action": None,
    }


def _build_summary(
    trigger: str,
    mode_after: str,
    selected_count: int,
    deferred_count: int,
) -> str:
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
