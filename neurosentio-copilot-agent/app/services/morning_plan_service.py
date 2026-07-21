"""
Morning Plan Service.

Fetches the user's open tasks from Supabase and passes them to the LLM
to generate a concrete, step-by-step plan for the entire day.

No risk scoring, no recovery mode, no sensory/energy logic.
Just tasks in → actionable steps out.
"""

import logging
import time as time_module
from datetime import date, datetime, timezone
from typing import Optional, List, Dict, Any

from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.core.llm_config import get_llm_settings
from app.llm.base import LLMError
from app.llm.client_factory import get_llm_client
from app.prompts import morning_plan as morning_plan_prompts
from app.utils.llm_costs import estimate_llm_cost
from app.services.llm_rate_limit_service import check_rate_limit
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


# ──────────────────────────────────────────────────────────────────────
# LLM helper
# ──────────────────────────────────────────────────────────────────────

async def _generate_llm_plan_text(
    db: Connection,
    user_id: str,
    open_tasks: List[Dict[str, Any]],
    fallback_summary: str,
    fallback_message: str,
) -> tuple[str, str, List[Dict[str, Any]]]:
    """
    Call the LLM with the user's tasks to generate a step-by-step day plan.

    Returns (summary, message, steps) where steps is a list of dicts with:
      task_id, task_title, title, description, duration_minutes.

    Falls back to (fallback_summary, fallback_message, []) on any failure.
    """
    settings = get_llm_settings()
    model = settings.llm_model or ""
    provider = "unknown"
    latency_ms = None

    try:
        llm_client = get_llm_client()
        provider = llm_client.__class__.__name__.lower().replace("client", "")

        rate_result = check_rate_limit(db, user_id)
        if not rate_result["allowed"]:
            logger.warning(
                "Morning plan LLM skipped — rate limit for user %s: %s",
                user_id,
                rate_result["reason"],
            )
            sq.log_llm_usage(
                conn=db, user_id=user_id, feature="morning_plan",
                provider=provider, model=model, status="skipped_rate_limit",
            )
            return fallback_summary, fallback_message, []

        user_prompt = morning_plan_prompts.build_user_prompt(open_tasks=open_tasks)

        t0 = time_module.monotonic()
        raw = await llm_client.generate_json(
            system_prompt=morning_plan_prompts.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_name="MorningPlanSteps",
        )
        latency_ms = int((time_module.monotonic() - t0) * 1000)

        summary = raw.get("summary", "").strip()
        message = raw.get("message", "").strip()
        steps = raw.get("steps", [])

        if not summary or not message:
            raise ValueError("LLM response missing 'summary' or 'message' field")
        if not isinstance(steps, list):
            raise ValueError("LLM response 'steps' is not a list")

        cost = estimate_llm_cost(provider, model, None, None)
        sq.log_llm_usage(
            conn=db, user_id=user_id, feature="morning_plan",
            provider=provider, model=model, status="success",
            latency_ms=latency_ms, cost=cost,
        )
        return summary, message, steps

    except Exception as exc:
        logger.warning(
            "Morning plan LLM call failed — using fallback. Reason: %s", exc
        )
        sq.log_llm_usage(
            conn=db, user_id=user_id, feature="morning_plan",
            provider=provider, model=model, status="fallback",
            latency_ms=latency_ms or 0,
        )
        return fallback_summary, fallback_message, []


# ──────────────────────────────────────────────────────────────────────
# Public service function
# ──────────────────────────────────────────────────────────────────────

async def generate_morning_plan(
    db: Connection,
    user_id: str,
    request: MorningPlanRequest,
) -> MorningPlan:

    plan_date = request.plan_date or datetime.now(timezone.utc).date()

    # 1. Return cached plan if it already exists for today
    existing_plan = sq.get_today_morning_plan(db, user_id, plan_date)
    if existing_plan and not request.force_regenerate:
        linked_mas = sq.get_plan_micro_actions(db, existing_plan["id"])
        return _build_response_from_existing(existing_plan, linked_mas, request)

    # 2. Fetch open tasks from Supabase
    open_tasks = sq.get_open_tasks(db, user_id)

    task_count = len(open_tasks)
    fallback_summary = (
        f"You have {task_count} task{'s' if task_count != 1 else ''} for today."
    )
    fallback_message = "Pick the first task and take one step at a time."

    # 3. Call LLM — pass tasks, get back a step-by-step plan
    summary, message, llm_steps = await _generate_llm_plan_text(
        db=db,
        user_id=user_id,
        open_tasks=open_tasks,
        fallback_summary=fallback_summary,
        fallback_message=fallback_message,
    )

    # 4. Save the plan record
    total_minutes = sum(s.get("duration_minutes", 15) for s in llm_steps)
    plan_id = sq.save_morning_plan(
        conn=db,
        user_id=user_id,
        plan_date=plan_date,
        mode="normal",
        summary=summary,
        message=message,
        total_minutes=total_minutes,
        risk_score=0,
    )

    # 5. Persist each LLM step as a micro-action linked to this plan
    for idx, step in enumerate(llm_steps):
        task_id = step.get("task_id")
        action = {
            "title": step.get("title", ""),
            "description": step.get("description"),
            "duration_minutes": step.get("duration_minutes", 15),
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": idx,
        }
        sq.save_micro_actions(db, user_id, task_id, plan_id, [action])

    # 6. Re-fetch saved micro-actions to get real DB IDs + build response
    saved_mas = sq.get_plan_micro_actions(db, plan_id)

    planned_items: List[PlannedMicroAction] = []
    time_offset = 0
    for ma in saved_mas:
        dur = ma.get("duration_minutes") or 15
        scheduled = _schedule_time(request.start_time, time_offset)
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=str(ma["id"]),
                task_id=str(ma["task_id"]) if ma.get("task_id") else None,
                title=ma["title"],
                description=ma.get("description"),
                scheduled_time=scheduled,
                duration_minutes=dur,
                energy_cost=ma.get("energy_cost"),
                sensory_cost=ma.get("sensory_cost"),
                friction_level=ma.get("friction_level"),
                status=ma.get("status", "open"),
            )
        )
        time_offset += dur

    return MorningPlan(
        plan_id=plan_id,
        plan_date=plan_date,
        mode="normal",
        summary=summary,
        total_scheduled_minutes=time_offset,
        overload_risk_score=0,
        selected_micro_actions=planned_items,
        recovery_blocks=[],
        transition_suggestions=[],
        message=message,
        created_at=datetime.now(timezone.utc),
    )


def _build_response_from_existing(
    plan: Dict[str, Any],
    linked_mas: List[Dict[str, Any]],
    request: MorningPlanRequest,
) -> MorningPlan:
    """Rebuild a MorningPlan response from a previously persisted plan."""
    time_offset = 0
    planned_items = []

    for ma in linked_mas:
        dur = ma.get("duration_minutes") or 15
        scheduled = _schedule_time(request.start_time, time_offset)
        planned_items.append(
            PlannedMicroAction(
                micro_action_id=str(ma["id"]),
                task_id=str(ma["task_id"]) if ma.get("task_id") else None,
                title=ma["title"],
                description=ma.get("description"),
                scheduled_time=scheduled,
                duration_minutes=dur,
                energy_cost=ma.get("energy_cost"),
                sensory_cost=ma.get("sensory_cost"),
                friction_level=ma.get("friction_level"),
                status=ma.get("status", "open"),
            )
        )
        time_offset += dur

    raw_plan_date = plan.get("plan_date")
    resolved_plan_date = raw_plan_date if isinstance(raw_plan_date, date) else (request.plan_date or datetime.now(timezone.utc).date())

    return MorningPlan(
        plan_id=str(plan["id"]),
        plan_date=resolved_plan_date,
        mode=plan.get("mode", "normal"),
        summary=plan.get("summary", ""),
        total_scheduled_minutes=time_offset,
        overload_risk_score=plan.get("overload_risk_score", 0),
        selected_micro_actions=planned_items,
        recovery_blocks=[],
        transition_suggestions=[],
        message=plan.get("message", "Pick the first task and begin."),
        created_at=plan.get("created_at") or datetime.now(timezone.utc),
    )
