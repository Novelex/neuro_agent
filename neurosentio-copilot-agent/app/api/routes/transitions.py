"""
Transition script routes (Day 6).

POST   /transitions/generate                   → generate a new script
GET    /transitions                             → list all for user
GET    /transitions/{type}/latest              → latest by type
PATCH  /transitions/{script_id}/rating        → rate a script
POST   /transitions/{script_id}/used          → mark as used
DELETE /transitions/{script_id}               → delete
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.transition_script_schema import (
    TransitionScript as TransitionScriptSchema,
    TransitionScriptGenerateRequest,
    TransitionScriptGenerateResponse,
    TransitionScriptRatingUpdate,
)
from app.services.transition_script_service import generate_transition_script
from app.repositories.transition_script_repository import transition_script_repository

router = APIRouter(prefix="/transitions", tags=["Transitions"])


@router.post(
    "/generate",
    response_model=TransitionScriptGenerateResponse,
    summary="Generate a transition script",
)
def generate_transition(
    body: TransitionScriptGenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Generates a gentle, neurodivergent-friendly transition script.

    Supported types: leaving_house, starting_work, making_call, ending_day,
    context_switch, recovery_break, custom.

    If current_energy < 30, generates a shorter recovery version (≤ 3 steps).
    """
    return generate_transition_script(db=db, user_id=user_id, request=body)


@router.get(
    "",
    response_model=List[TransitionScriptSchema],
    summary="List all transition scripts for the current user",
)
def list_transitions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return transition_script_repository.list_for_user(db, user_id, limit=limit, offset=offset)


@router.get(
    "/{transition_type}/latest",
    response_model=TransitionScriptSchema,
    summary="Get latest script for a transition type",
)
def get_latest_by_type(
    transition_type: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    script = transition_script_repository.get_latest_by_type(db, user_id, transition_type)
    if not script:
        raise HTTPException(
            status_code=404,
            detail=f"No script found for transition type '{transition_type}'",
        )
    return script


@router.patch(
    "/{script_id}/rating",
    response_model=TransitionScriptSchema,
    summary="Rate a transition script (1–5)",
)
def rate_transition(
    script_id: str,
    body: TransitionScriptRatingUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    updated = transition_script_repository.update_rating(db, user_id, script_id, body.success_rating)
    if not updated:
        raise HTTPException(status_code=404, detail="Transition script not found")
    return updated


@router.post(
    "/{script_id}/used",
    response_model=TransitionScriptSchema,
    summary="Mark a transition script as used",
)
def mark_used(
    script_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    updated = transition_script_repository.mark_used(db, user_id, script_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Transition script not found")
    return updated


@router.delete(
    "/{script_id}",
    status_code=204,
    summary="Delete a transition script",
)
def delete_transition(
    script_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    deleted = transition_script_repository.delete(db, user_id, script_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transition script not found")
