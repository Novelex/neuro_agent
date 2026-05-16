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
from app.services.overload_service import calculate_overload_risk
from app.services.planning_service import (
    select_tasks,
    build_recovery_recommendation,
)
from app.schemas.copilot_schema import Dashboard, NextAction, Recovery
from app.schemas.task_schema import Task as TaskSchema
from app.schemas.energy_log_schema import Energy as EnergySchema


def get_dashboard(db: Session, user_id: str) -> Dashboard:
    # ── Fetch data ─────────────────────────────────────────────────────
    latest_energy = energy_repository.get_latest(db, user_id)
    open_tasks = task_repository.get_open(db, user_id)
    high_priority = [t for t in open_tasks if t.priority == "high"]

    # ── Overload risk ──────────────────────────────────────────────────
    risk = calculate_overload_risk(
        latest_energy=latest_energy,
        open_tasks_count=len(open_tasks),
        high_priority_count=len(high_priority),
    )
    mode = risk["mode"]

    # ── Planning ───────────────────────────────────────────────────────
    selected_tasks = select_tasks(open_tasks, mode)
    recovery_rec = build_recovery_recommendation(mode, latest_energy, risk["reasons"])

    # ── Build suggested_next_action (Day 5 priority chain) ────────────
    suggested_action = _build_next_action(db, user_id, open_tasks, selected_tasks, mode, latest_energy)

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
