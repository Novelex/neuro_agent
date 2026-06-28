"""
Adaptive Replanner routes.

POST   /copilot/replan            → trigger an adaptive replan
GET    /copilot/replan/events     → list recent replan events
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.replan_event_repository import replan_event_repository
from app.services.adaptive_replanner_service import replan_day
from app.schemas.replan_schema import (
    ReplanRequest,
    ReplanResult,
    ReplanEvent,
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
    db: Session = Depends(get_db),
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


@router.get(
    "/events",
    response_model=list[ReplanEvent],
    summary="List recent replan events",
)
def list_replan_events(
    days: int = Query(default=14, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns recent replan events for the current user."""
    events = replan_event_repository.list_recent(db, user_id, days=days)
    return [ReplanEvent.model_validate(e) for e in events]
