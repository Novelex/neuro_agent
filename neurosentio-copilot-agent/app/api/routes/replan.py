"""
Adaptive Replanner routes.

POST   /copilot/replan            → trigger an adaptive replan
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.services.adaptive_replanner_service import replan_day
from app.schemas.replan_schema import (
    ReplanRequest,
    ReplanResult,
)

router = APIRouter(prefix="/copilot/replan", tags=["Adaptive Replanner"])


@router.post(
    "",
    response_model=ReplanResult,
    status_code=200,
    summary="Trigger an adaptive replan",
)
def trigger_replan(
    body: ReplanRequest,
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Adjusts the remaining day plan based on a trigger.

    Triggers:
    - low_energy: reduces actions, defers high-energy tasks, adds recovery block
    - skipped_actions: simplifies plan to top 2 actions
    - calendar_overload: reduces action count, adds recovery block
    - urgent_message: adds one draft_reply action, keeps plan light
    - manual: general replan
    - recovery_mode: recovery-first plan
    - stuck_tasks: includes at most one stuck task action

    Preserves completed micro-actions.
    """
    result = replan_day(db=db, user_id=user_id, request=body)
    return ReplanResult(**result)
