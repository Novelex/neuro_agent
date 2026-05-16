"""
Copilot routes:
  GET  /copilot/dashboard
  GET  /copilot/context
  POST /copilot/quick-plan
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.utils.time_utils import get_user_id
from app.repositories.user_profile_repository import user_profile_repository
from app.repositories.task_repository import task_repository
from app.repositories.energy_repository import energy_repository
from app.repositories.copilot_repository import copilot_repository
from app.services.dashboard_service import get_dashboard
from app.services.overload_service import calculate_overload_risk
from app.services.planning_service import (
    select_tasks,
    build_suggested_next_action,
    build_recovery_recommendation,
    build_plan_summary,
)
from app.schemas.copilot_schema import Dashboard, Context, Plan, NextAction
from app.schemas.task_schema import Task as TaskSchema
from app.schemas.energy_log_schema import Energy as EnergySchema
from app.schemas.user_profile_schema import Profile as ProfileSchema

router = APIRouter(prefix="/copilot", tags=["Copilot"])


# ──────────────────────────────────────────────────────────────────────
# GET /copilot/dashboard
# ──────────────────────────────────────────────────────────────────────
@router.get(
    "/dashboard",
    response_model=Dashboard,
    summary="Get Copilot dashboard",
)
def copilot_dashboard(
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns a combined dashboard with:
    - Latest energy state
    - Open task counts
    - Suggested next action
    - Recovery recommendation (if in recovery mode)
    """
    return get_dashboard(db, user_id)


# ──────────────────────────────────────────────────────────────────────
# GET /copilot/context
# ──────────────────────────────────────────────────────────────────────
@router.get(
    "/context",
    response_model=Context,
    summary="Get raw Copilot context",
)
def copilot_context(
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the raw structured context that the future AI agent will consume.
    Useful for debugging and LLM integration prep.
    """
    profile = user_profile_repository.get_or_create_default(db, user_id)
    latest_energy = energy_repository.get_latest(db, user_id)
    open_tasks = task_repository.get_open(db, user_id)
    recent_logs = energy_repository.get_all(db, user_id, limit=10)

    return Context(
        profile=ProfileSchema.model_validate(profile),
        latest_energy=EnergySchema.model_validate(latest_energy) if latest_energy else None,
        open_tasks=[TaskSchema.model_validate(t) for t in open_tasks],
        recent_energy_logs=[EnergySchema.model_validate(log) for log in recent_logs],
    )


# ──────────────────────────────────────────────────────────────────────
# POST /copilot/quick-plan
# ──────────────────────────────────────────────────────────────────────
@router.post(
    "/quick-plan",
    response_model=Plan,
    summary="Generate a quick rule-based daily plan",
)
def copilot_quick_plan(
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Generates a rule-based daily plan without LLM.

    Rules:
    - No energy logged → mode = normal, prompt to log energy
    - battery < 30 → mode = recovery (1 task only)
    - battery >= 30 → mode = normal (up to 3 tasks)
    - > 5 open tasks + energy < 50 → lighter plan recommended
    - Task priority: high → nearest due date → oldest created
    """
    latest_energy = energy_repository.get_latest(db, user_id)
    open_tasks = task_repository.get_open(db, user_id)
    high_priority = [t for t in open_tasks if t.priority == "high"]

    # ── Special case: no energy log yet ──────────────────────────────
    if latest_energy is None:
        selected = select_tasks(open_tasks, "normal")
        return Plan(
            mode="normal",
            summary=(
                "We don't have an energy reading yet. "
                "Log how you're feeling first to get a personalised plan. "
                "Here are your open tasks in the meantime."
            ),
            suggested_next_action=NextAction(
                type="log_energy_prompt",
                message="Log your energy level to get a personalised daily plan.",
            ),
            recovery_recommendation=None,
            selected_tasks=[TaskSchema.model_validate(t) for t in selected],
        )

    # ── Risk & mode ───────────────────────────────────────────────────
    risk = calculate_overload_risk(latest_energy, len(open_tasks), len(high_priority))
    mode = risk["mode"]

    selected = select_tasks(open_tasks, mode)
    suggested_action = build_suggested_next_action(selected, mode)
    recovery_rec = build_recovery_recommendation(mode, latest_energy, risk["reasons"])
    summary = build_plan_summary(
        mode=mode,
        open_tasks_count=len(open_tasks),
        selected_tasks=selected,
        latest_energy=latest_energy,
        reasons=risk["reasons"],
    )

    # ── Persist today's plan ──────────────────────────────────────────
    payload = {
        "risk_score": risk["risk_score"],
        "reasons": risk["reasons"],
        "selected_task_ids": [t.id for t in selected],
    }
    copilot_repository.upsert_today(db, user_id, mode, summary, payload)

    return Plan(
        mode=mode,
        summary=summary,
        suggested_next_action=suggested_action,
        recovery_recommendation=recovery_rec,
        selected_tasks=[TaskSchema.model_validate(t) for t in selected],
    )
