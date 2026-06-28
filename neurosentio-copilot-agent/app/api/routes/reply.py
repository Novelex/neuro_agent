"""
Reply Drafter API routes (Day 8).

POST   /reply/draft              → generate and save reply drafts
GET    /reply/drafts             → list all drafts for current user
GET    /reply/drafts/{draft_id}  → get one draft by id
PATCH  /reply/drafts/{draft_id}  → update (select option, edit text, change status)
DELETE /reply/drafts/{draft_id}  → soft delete

IMPORTANT:
- This service NEVER sends messages.
- No Gmail, SMS, or messaging integration.
- All drafts are stored locally only.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.reply_schema import (
    ReplyDraft as ReplyDraftSchema,
    ReplyDraftRequest,
    ReplyDraftUpdate,
    ReplyDraftListItem,
    ReplyDraftDeleteResponse,
)
from app.services.reply_drafter_service import draft_reply
from app.repositories.reply_draft_repository import reply_draft_repository

router = APIRouter(prefix="/reply", tags=["ReplyDrafter"])


@router.post(
    "/draft",
    response_model=ReplyDraftSchema,
    status_code=201,
    summary="Generate reply draft options",
)
async def create_reply_draft(
    body: ReplyDraftRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Paste any message text and receive 3 neurodivergent-friendly reply options:
    short, warm, and detailed. A boundary option is included when:
    - current_energy < 40
    - user_intent includes decline/delay/boundary/not available
    - include_boundary_option=true (default)

    **This endpoint NEVER sends messages.**
    All drafts are stored locally. No external connections.
    """
    return await draft_reply(db=db, user_id=user_id, request=body)


@router.get(
    "/drafts",
    response_model=List[ReplyDraftListItem],
    summary="List reply drafts",
)
def list_reply_drafts(
    status: Optional[str] = Query(default=None, description="Filter by status. Deleted drafts are excluded by default."),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the current user's reply drafts.
    Deleted drafts are excluded by default — use `status=deleted` to retrieve them.
    """
    return reply_draft_repository.list_for_user(
        db, user_id, status=status, limit=limit, offset=offset
    )


@router.get(
    "/drafts/{draft_id}",
    response_model=ReplyDraftSchema,
    summary="Get a single reply draft",
)
def get_reply_draft(
    draft_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns one reply draft by ID. Returns 404 if not found or belongs to another user."""
    row = reply_draft_repository.get_by_id(db, user_id, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reply draft not found.")
    return row


@router.patch(
    "/drafts/{draft_id}",
    response_model=ReplyDraftSchema,
    summary="Update a reply draft",
)
def update_reply_draft(
    draft_id: str,
    body: ReplyDraftUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update a draft: select an option, save an edited reply, or change status.
    Valid statuses: drafted | edited | selected | archived | deleted
    The status 'sent' is intentionally not allowed — this service never sends messages.
    """
    row = reply_draft_repository.update(db, user_id, draft_id, body)
    if not row:
        raise HTTPException(status_code=404, detail="Reply draft not found.")
    return row


@router.delete(
    "/drafts/{draft_id}",
    response_model=ReplyDraftDeleteResponse,
    summary="Soft delete a reply draft",
)
def delete_reply_draft(
    draft_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Soft deletes the draft by setting status='deleted'.
    The record is preserved in the database but excluded from default list results.
    Use GET /reply/drafts?status=deleted to retrieve deleted drafts.
    """
    row = reply_draft_repository.soft_delete(db, user_id, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reply draft not found.")
    return ReplyDraftDeleteResponse(deleted=True, id=draft_id)


@router.delete(
    "/drafts/{draft_id}/original-message",
    response_model=ReplyDraftSchema,
    summary="Purge/redact the original message from a reply draft",
)
def redact_original_message(
    draft_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Individually purge the original message stored inside a reply draft,
    replacing it with the placeholder '[redacted]'.
    """
    row = reply_draft_repository.get_by_id(db, user_id, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reply draft not found.")
    
    row.original_message = "[redacted]"
    db.commit()
    db.refresh(row)
    
    # Log the action in privacy audit log
    from app.repositories.privacy_audit_repository import privacy_audit_repository
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="redact_field",
        target_type="reply_draft",
        target_id=draft_id,
        extra_metadata={"field": "original_message"}
    )
    return row

