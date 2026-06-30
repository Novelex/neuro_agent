"""
Morning plan routes (Day 5).

POST /copilot/morning-plan        → generate today's morning plan
GET  /copilot/morning-plan/today  → retrieve today's plan if it exists
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.morning_plan_schema import MorningPlan, MorningPlanRequest
from app.core import supabase_queries as sq
from app.services.morning_plan_service import generate_morning_plan

router = APIRouter(prefix="/copilot", tags=["MorningPlan"])


@router.post(
    "/morning-plan",
    response_model=MorningPlan,
    summary="Generate today's morning plan",
)
async def create_morning_plan(
    body: MorningPlanRequest,
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Generates a neurodivergent-friendly morning plan.

    - Selects micro-actions from open tasks (auto-decomposes if auto_decompose=true).
    - Switches to recovery mode when energy < 30 or overload risk >= 60.
    - Saves plan to DB and links selected micro-actions to plan_id.
    - Adds transition suggestions (starting_work, making_call, recovery_break).
    - Returns existing plan without regenerating unless force_regenerate=true.
    """
    plan = await generate_morning_plan(db=db, user_id=user_id, request=body)
    return plan


@router.get(
    "/morning-plan/today",
    response_model=MorningPlan,
    summary="Get today's morning plan",
)
async def get_today_morning_plan(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Returns today's morning plan if one has been generated.
    Returns 404 if no plan exists for today — call POST /copilot/morning-plan to create one.
    """
    today = date.today()
    plan_record = sq.get_today_morning_plan(db, user_id, today)
    if not plan_record:
        raise HTTPException(
            status_code=404,
            detail="No morning plan for today. Call POST /copilot/morning-plan to generate one.",
        )
    linked_mas = sq.get_plan_micro_actions(db, plan_record["id"])
    from app.services.morning_plan_service import _build_response_from_existing
    from app.schemas.morning_plan_schema import MorningPlanRequest
    return _build_response_from_existing(
        plan_record,
        linked_mas,
        MorningPlanRequest(),
    )
