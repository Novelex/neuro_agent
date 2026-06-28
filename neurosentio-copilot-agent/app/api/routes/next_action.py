"""
Next Action Prompter routes.

GET    /copilot/next-action                           → get best next action
POST   /copilot/next-action/{prompt_id}/done          → mark done
POST   /copilot/next-action/{prompt_id}/snooze        → snooze
POST   /copilot/next-action/{prompt_id}/skip          → skip
POST   /copilot/next-action/{prompt_id}/defer         → defer

Backend-only. Prepares for future Supabase Realtime integration.
No production push notifications yet.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.next_action_repository import next_action_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.services.next_action_service import get_or_create_next_action
from app.schemas.next_action_schema import (
    NextActionPrompt,
    NextActionResult,
    NextActionSnoozeRequest,
    NextActionDeferRequest,
)

router = APIRouter(prefix="/copilot/next-action", tags=["Next Action"])


@router.get(
    "",
    response_model=NextActionResult,
    summary="Get the best next action for the user",
)
def get_next_action(
    at_time: Optional[datetime] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns exactly one best next action based on current state.
    Creates and saves a prompt row if one does not already exist.
    Reuses existing active prompts where appropriate.
    """
    prompt, reason, mode = get_or_create_next_action(db, user_id, at_time=at_time)
    return NextActionResult(
        prompt=NextActionPrompt.model_validate(prompt),
        reason=reason,
        mode=mode,
        source="rule_based",
    )


@router.post(
    "/{prompt_id}/done",
    response_model=NextActionPrompt,
    summary="Mark a next action as done",
)
def mark_done(
    prompt_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Marks the prompt as done.
    If source_type is micro_action, marks the linked micro-action as done too.
    """
    prompt = next_action_repository.get_by_id(db, user_id, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Next action prompt not found")

    # Mark linked micro-action done if applicable
    if prompt.source_type == "micro_action" and prompt.source_id:
        try:
            from app.schemas.micro_action_schema import MicroActionStatusUpdate
            ma = micro_action_repository.get_by_id(db, user_id, prompt.source_id)
            if ma and ma.status == "open":
                micro_action_repository.update_status(
                    db, user_id, prompt.source_id,
                    MicroActionStatusUpdate(status="done"),
                )
        except Exception:
            pass  # Don't fail if micro-action update fails

    updated = next_action_repository.mark_done(db, user_id, prompt_id)
    return NextActionPrompt.model_validate(updated)


@router.post(
    "/{prompt_id}/snooze",
    response_model=NextActionPrompt,
    summary="Snooze a next action",
)
def snooze_action(
    prompt_id: str,
    body: NextActionSnoozeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Snoozes the prompt for the specified number of minutes (5-1440)."""
    prompt = next_action_repository.get_by_id(db, user_id, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Next action prompt not found")

    updated = next_action_repository.snooze(db, user_id, prompt_id, body.minutes)
    return NextActionPrompt.model_validate(updated)


@router.post(
    "/{prompt_id}/skip",
    response_model=NextActionPrompt,
    summary="Skip a next action",
)
def skip_action(
    prompt_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Marks the prompt as skipped.
    If source_type is micro_action, optionally marks the micro-action as skipped.
    """
    prompt = next_action_repository.get_by_id(db, user_id, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Next action prompt not found")

    # Optionally skip linked micro-action
    if prompt.source_type == "micro_action" and prompt.source_id:
        try:
            from app.schemas.micro_action_schema import MicroActionStatusUpdate
            ma = micro_action_repository.get_by_id(db, user_id, prompt.source_id)
            if ma and ma.status == "open":
                micro_action_repository.update_status(
                    db, user_id, prompt.source_id,
                    MicroActionStatusUpdate(status="skipped"),
                )
        except Exception:
            pass

    updated = next_action_repository.update_status(db, user_id, prompt_id, "skipped")
    return NextActionPrompt.model_validate(updated)


@router.post(
    "/{prompt_id}/defer",
    response_model=NextActionPrompt,
    summary="Defer a next action to a later time",
)
def defer_action(
    prompt_id: str,
    body: NextActionDeferRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Defers the prompt to the specified datetime."""
    prompt = next_action_repository.get_by_id(db, user_id, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Next action prompt not found")

    updated = next_action_repository.defer(db, user_id, prompt_id, body.defer_until)
    return NextActionPrompt.model_validate(updated)
