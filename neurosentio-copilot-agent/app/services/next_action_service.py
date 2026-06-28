"""
Next Action Service.

Returns exactly one best next action for the user based on their current state.
Rule-based. No LLM. Neurodivergent-friendly copy.

Priority chain:
1. Energy missing -> log_energy
2. Recovery mode / risk >= 60 -> take_recovery_break or lowest-friction micro-action
3. Planned open micro-action due now -> do_micro_action
4. Urgent message needing reply -> draft_reply
5. Stuck high-priority task with no micro-actions -> decompose_task
6. Fallback -> review_plan
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.next_action_repository import next_action_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.repositories.copilot_repository import copilot_repository
from app.repositories.energy_repository import energy_repository
from app.repositories.task_repository import task_repository

logger = logging.getLogger(__name__)


def _make_prompt_data(
    source_type: str,
    source_id: Optional[str],
    action_type: str,
    title: str,
    message: str,
    duration_minutes: Optional[int] = None,
    energy_cost: Optional[str] = None,
    sensory_cost: Optional[str] = None,
    friction_level: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "action_type": action_type,
        "title": title,
        "message": message,
        "duration_minutes": duration_minutes,
        "energy_cost": energy_cost,
        "sensory_cost": sensory_cost,
        "friction_level": friction_level,
        "extra_metadata": metadata or {},
    }


def get_or_create_next_action(
    db: Session,
    user_id: str,
    at_time: Optional[datetime] = None,
) -> tuple:
    """
    Returns (NextActionPrompt, reason_string, mode_string).
    Creates a new prompt row if one does not already exist for the source.
    Reuses existing active prompt if found.
    Skips snoozed prompts whose snoozed_until is still in the future.
    """
    now = at_time or datetime.now(timezone.utc)

    # ── 1. Fetch data ──────────────────────────────────────────────────
    latest_energy = energy_repository.get_latest(db, user_id)
    open_tasks = task_repository.get_open(db, user_id)
    high_priority_tasks = [t for t in open_tasks if t.priority == "high"]

    # ── 2. Overload risk ───────────────────────────────────────────────
    risk_score = 0
    mode = "normal"
    try:
        from app.services.overload_service import calculate_overload_risk
        risk = calculate_overload_risk(
            latest_energy=latest_energy,
            open_tasks_count=len(open_tasks),
            high_priority_count=len(high_priority_tasks),
        )
        risk_score = risk["risk_score"]
        mode = risk["mode"]
    except Exception as e:
        logger.warning("Failed to calculate overload risk: %s", e)

    # Override mode based on explicit energy
    if latest_energy and latest_energy.battery_level < 30:
        mode = "recovery"

    # ── 3. Priority 1: No energy logged ───────────────────────────────
    if latest_energy is None:
        source_type = "system"
        source_id = None
        existing = next_action_repository.get_active_for_source(db, user_id, source_type, source_id)
        if existing and not _is_snoozed(existing, now):
            return existing, "No energy log found. Suggesting energy log.", mode

        data = _make_prompt_data(
            source_type="system",
            source_id=None,
            action_type="log_energy",
            title="Log your energy level",
            message=(
                "We don't have your energy reading yet. "
                "Logging it helps the plan adjust to how you actually feel right now."
            ),
        )
        prompt = next_action_repository.create(db, user_id, data)
        return prompt, "No energy log found.", mode

    # ── 4. Priority 2: Recovery mode or high risk ─────────────────────
    if mode == "recovery" or risk_score >= 60:
        # Try lowest-friction planned micro-action first
        today_plan = copilot_repository.get_today_plan(db, user_id)
        if today_plan:
            plan_mas = micro_action_repository.get_open_by_plan(db, user_id, today_plan.id)
            low_friction = [
                ma for ma in plan_mas
                if ma.energy_cost in (None, "low") and ma.friction_level in (None, "low")
            ]
            if low_friction:
                ma = low_friction[0]
                existing = next_action_repository.get_active_for_source(
                    db, user_id, "micro_action", ma.id
                )
                if existing and not _is_snoozed(existing, now):
                    return existing, "Recovery mode — lowest friction micro-action selected.", mode
                data = _make_prompt_data(
                    source_type="micro_action",
                    source_id=ma.id,
                    action_type="do_micro_action",
                    title=ma.title,
                    message=(
                        f"Your system looks loaded. This small step was chosen for you: "
                        f"'{ma.title}'. Just start with the first movement."
                    ),
                    duration_minutes=ma.duration_minutes,
                    energy_cost=ma.energy_cost,
                    sensory_cost=ma.sensory_cost,
                    friction_level=ma.friction_level,
                )
                prompt = next_action_repository.create(db, user_id, data)
                return prompt, "Recovery mode — lowest friction micro-action.", mode

        # Fall back to recovery break
        existing = next_action_repository.get_active_for_source(db, user_id, "recovery", None)
        if existing and not _is_snoozed(existing, now):
            return existing, "Recovery mode — recovery break suggested.", mode

        data = _make_prompt_data(
            source_type="recovery",
            source_id=None,
            action_type="take_recovery_break",
            title="Take a recovery break",
            message=(
                "Your system looks loaded. A recovery break comes first. "
                "Step away, drink water, and come back when you're ready."
            ),
            duration_minutes=15,
            energy_cost="low",
            friction_level="low",
        )
        prompt = next_action_repository.create(db, user_id, data)
        return prompt, "Recovery mode — break suggested.", mode

    # ── 5. Priority 3: Planned open micro-action ───────────────────────
    today_plan = copilot_repository.get_today_plan(db, user_id)
    if today_plan:
        plan_mas = micro_action_repository.get_open_by_plan(db, user_id, today_plan.id)
        if plan_mas:
            ma = plan_mas[0]
            existing = next_action_repository.get_active_for_source(
                db, user_id, "micro_action", ma.id
            )
            if existing and not _is_snoozed(existing, now):
                return existing, "Planned micro-action from morning plan.", mode
            data = _make_prompt_data(
                source_type="micro_action",
                source_id=ma.id,
                action_type="do_micro_action",
                title=ma.title,
                message=(
                    f"Next: '{ma.title}'. Just start with the first movement."
                ),
                duration_minutes=ma.duration_minutes,
                energy_cost=ma.energy_cost,
                sensory_cost=ma.sensory_cost,
                friction_level=ma.friction_level,
            )
            prompt = next_action_repository.create(db, user_id, data)
            return prompt, "Planned micro-action from today's morning plan.", mode

    # ── 6. Priority 4: Urgent message needing reply ────────────────────
    try:
        from app.repositories.message_repository import message_repository
        urgent_messages = message_repository.list_urgent(db, user_id, limit=5)
        # Filter to those needing reply that are not snoozed
        for msg in urgent_messages:
            if msg.needs_reply and msg.urgency_score >= 40:
                existing = next_action_repository.get_active_for_source(
                    db, user_id, "message", msg.id
                )
                if existing and not _is_snoozed(existing, now):
                    return existing, "Urgent message needing reply.", mode
                if not existing:
                    data = _make_prompt_data(
                        source_type="message",
                        source_id=msg.id,
                        action_type="draft_reply",
                        title=f"Reply to: {msg.subject or msg.sender or 'urgent message'}",
                        message=(
                            "A short reply may be enough here. "
                            f"From: {msg.sender or 'unknown'}. "
                            f"Subject: {msg.subject or '(no subject)'}."
                        ),
                        metadata={"urgency_score": msg.urgency_score},
                    )
                    prompt = next_action_repository.create(db, user_id, data)
                    return prompt, "Urgent message needing reply.", mode
    except Exception as e:
        logger.warning("Failed to check urgent messages: %s", e)

    # ── 7. Priority 5: Stuck high-priority task needing decomposition ──
    try:
        from app.services.stuck_task_service import detect_stuck_tasks
        stuck = detect_stuck_tasks(db, user_id, threshold_days=3)
        hp_stuck = [s for s in stuck if s["task"].priority == "high"]
        for item in hp_stuck:
            task = item["task"]
            existing_mas = micro_action_repository.get_open_by_task(db, user_id, task.id)
            if not existing_mas:
                existing = next_action_repository.get_active_for_source(
                    db, user_id, "task", task.id
                )
                if existing and not _is_snoozed(existing, now):
                    return existing, "Stuck high-priority task needs decomposition.", mode
                data = _make_prompt_data(
                    source_type="task",
                    source_id=task.id,
                    action_type="decompose_task",
                    title=f"Break down: {task.title}",
                    message=(
                        f"This task has been sitting for a while. "
                        f"Let's make it smaller. Breaking '{task.title}' "
                        "into tiny steps will make it easier to start."
                    ),
                    metadata={"task_id": task.id},
                )
                prompt = next_action_repository.create(db, user_id, data)
                return prompt, "Stuck high-priority task needs decomposition.", mode
    except Exception as e:
        logger.warning("Failed to check stuck tasks: %s", e)

    # ── 8. Fallback: review plan ───────────────────────────────────────
    existing = next_action_repository.get_active_for_source(db, user_id, "system", "review_plan")
    if existing and not _is_snoozed(existing, now):
        return existing, "No specific action found — reviewing plan.", mode

    data = _make_prompt_data(
        source_type="system",
        source_id="review_plan",
        action_type="review_plan",
        title="Review your plan",
        message=(
            "Things look manageable right now. "
            "Take a moment to review your plan and pick what feels right."
        ),
    )
    prompt = next_action_repository.create(db, user_id, data)
    return prompt, "No specific action found — reviewing plan.", mode


def _is_snoozed(prompt, now: datetime) -> bool:
    """Check if a snoozed prompt's snooze period is still active."""
    if prompt.status == "snoozed" and prompt.snoozed_until is not None:
        snoozed_until = prompt.snoozed_until
        if snoozed_until.tzinfo is None:
            snoozed_until = snoozed_until.replace(tzinfo=timezone.utc)
        now_tz = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return now_tz < snoozed_until
    return False
