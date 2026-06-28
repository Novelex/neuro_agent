"""
Micro-action management routes.

PATCH /micro-actions/{id}/status   → mark done, snooze, skip, defer
POST  /micro-actions/{id}/make-smaller → split into smaller actions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.micro_action_schema import (
    MicroAction as MicroActionSchema,
    MicroActionStatusUpdate,
    MakeSmallerRequest,
    MakeSmallerResponse,
)
from app.repositories.micro_action_repository import micro_action_repository
from app.services.task_decomposer_service import make_micro_action_smaller

router = APIRouter(prefix="/micro-actions", tags=["MicroActions"])


# ──────────────────────────────────────────────────────────────────────
# PATCH /micro-actions/{id}/status
# ──────────────────────────────────────────────────────────────────────
@router.patch(
    "/{micro_action_id}/status",
    response_model=MicroActionSchema,
    summary="Update micro-action status",
)
def update_micro_action_status(
    micro_action_id: str,
    body: MicroActionStatusUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update the status of a single micro-action.
    Allowed values: open, done, snoozed, skipped, deferred.
    """
    updated = micro_action_repository.update_status(db, user_id, micro_action_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Micro-action not found")
    return updated


# ──────────────────────────────────────────────────────────────────────
# POST /micro-actions/{id}/make-smaller
# ──────────────────────────────────────────────────────────────────────
@router.post(
    "/{micro_action_id}/make-smaller",
    response_model=MakeSmallerResponse,
    summary="Split a micro-action into smaller actions",
)
async def make_action_smaller(
    micro_action_id: str,
    body: MakeSmallerRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    This action still feels too big.

    Splits it into 1–3 smaller actions inserted after the original in sort order.
    The original action is NOT deleted — it stays in the list for reference.
    If current_energy < 30, generates a lighter version (recovery mode).
    """
    try:
        result = await make_micro_action_smaller(
            db=db,
            user_id=user_id,
            micro_action_id=micro_action_id,
            request=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result
