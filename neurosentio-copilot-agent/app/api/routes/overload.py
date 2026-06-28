"""Overload Events API Router."""

from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.copilot_schema import OverloadEventResponse
from app.repositories.overload_event_repository import overload_event_repository

router = APIRouter(prefix="/overload", tags=["overload"])


@router.get("/events", response_model=List[OverloadEventResponse], status_code=status.HTTP_200_OK)
def get_recent_overload_events(
    days: int = Query(default=14, description="Filter overload events in the last N days"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get all overload events logged for the user in the last N days.
    """
    return overload_event_repository.list_recent(db, user_id, days)
