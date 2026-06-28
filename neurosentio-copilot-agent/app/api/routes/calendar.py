"""Calendar API Router."""

from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.calendar_schema import (
    CalendarImportRequest,
    CalendarImportResponse,
    CalendarEvent as CalendarEventSchema,
    CalendarDaySummary,
)
from app.repositories.calendar_repository import calendar_repository
from app.services.calendar_analysis_service import (
    detect_meeting_type,
    calculate_load_score,
    map_costs,
    mark_back_to_back,
    build_day_summary,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _sanitize_and_prepare_event(event_dict: dict) -> dict:
    """Strip description and other privacy-sensitive fields from event and metadata."""
    # Ensure no description field is stored directly
    event_dict.pop("description", None)

    # Sanitize raw_metadata
    if "raw_metadata" in event_dict and isinstance(event_dict["raw_metadata"], dict):
        meta = dict(event_dict["raw_metadata"])
        for key in ["description", "attendees", "attendee_emails", "conferenceData", "hangoutLink", "meeting_link", "notes"]:
            meta.pop(key, None)
        event_dict["raw_metadata"] = meta
    
    # Run heuristics
    # Create a transient object to feed into the detection functions
    class TransientEvent:
        def __init__(self, d):
            self.title = d.get("title", "")
            self.attendee_count = d.get("attendee_count", 0)
            self.is_busy = d.get("is_busy", True)
            self.start_time = d.get("start_time")
            self.end_time = d.get("end_time")
            self.meeting_type = "unknown"

    transient = TransientEvent(event_dict)
    
    meeting_type = detect_meeting_type(transient)
    transient.meeting_type = meeting_type
    
    load_score = calculate_load_score(transient)
    energy_cost, sensory_cost = map_costs(load_score)

    event_dict["meeting_type"] = meeting_type
    event_dict["load_score"] = load_score
    event_dict["energy_cost"] = energy_cost
    event_dict["sensory_cost"] = sensory_cost
    event_dict["is_back_to_back"] = False  # Set initially, updated post-upsert

    return event_dict


@router.post("/import/mock", response_model=CalendarImportResponse, status_code=status.HTTP_201_CREATED)
def import_mock_calendar(
    request: CalendarImportRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Import events with privacy sanitization and post-import back-to-back analysis."""
    from app.repositories.privacy_preferences_repository import privacy_preferences_repository
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    prepared_events = []
    unique_dates = set()

    for event_in in request.events:
        event_dict = event_in.model_dump()
        if not prefs.store_calendar_titles:
            event_dict["title"] = "[redacted]"
        prepared = _sanitize_and_prepare_event(event_dict)
        prepared_events.append(prepared)
        
        # Track dates to update back-to-back flags
        unique_dates.add(prepared["start_time"].date())
        unique_dates.add(prepared["end_time"].date())

    # Upsert using repository
    imported_count, updated_count, saved_events = calendar_repository.upsert_events(
        db, user_id, prepared_events
    )

    # Post-import: Update back-to-back flags for all affected dates
    for d in unique_dates:
        day_events = calendar_repository.list_events_for_day(db, user_id, d)
        if day_events:
            mark_back_to_back(day_events)
            db.commit()

    # Refresh saved events list
    refreshed_events = [calendar_repository.get_event_by_id(db, user_id, e.id) for e in saved_events]
    # Filter out None if any deleted
    refreshed_events = [e for e in refreshed_events if e]

    return CalendarImportResponse(
        imported_count=imported_count,
        updated_count=updated_count,
        events=refreshed_events,
    )


@router.get("/events", response_model=List[CalendarEventSchema])
def list_calendar_events(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get all events overlapping a range, scoped to current user."""
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )
    return calendar_repository.list_events(db, user_id, start_time, end_time)


@router.get("/day-summary", response_model=CalendarDaySummary)
def get_calendar_day_summary(
    date_str: str = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Calculate and return daily summary and scheduling recommendations."""
    try:
        check_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    # Make sure back-to-back flags are updated first
    day_events = calendar_repository.list_events_for_day(db, user_id, check_date)
    if day_events:
        mark_back_to_back(day_events)
        db.commit()
        # Re-fetch
        day_events = calendar_repository.list_events_for_day(db, user_id, check_date)

    return build_day_summary(day_events, check_date)


@router.delete("/events/{event_id}", status_code=status.HTTP_200_OK)
def delete_calendar_event(
    event_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a specific calendar event, scoped to user."""
    success = calendar_repository.delete_event(db, user_id, event_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found.",
        )
    return {"status": "deleted"}


@router.delete("/events/{event_id}/title", response_model=CalendarEventSchema, status_code=status.HTTP_200_OK)
def redact_calendar_title(
    event_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Individually purge/redact the title of a calendar event, setting it to '[redacted]'.
    Logs a 'redact_field' privacy action in privacy audit logs.
    """
    event = calendar_repository.get_event_by_id(db, user_id, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found.",
        )
    
    event.title = "[redacted]"
    db.commit()
    db.refresh(event)
    
    # Log the action in privacy audit log
    from app.repositories.privacy_audit_repository import privacy_audit_repository
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="redact_field",
        target_type="calendar_event",
        target_id=event_id,
        extra_metadata={"field": "title"}
    )
    return event

