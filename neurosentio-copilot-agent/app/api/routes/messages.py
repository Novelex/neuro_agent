"""
Message Monitor routes.

POST   /messages/import/mock       → import mock/manual message metadata
GET    /messages                   → list messages for user
GET    /messages/summary           → message urgency/needs-reply summary
PATCH  /messages/{message_id}      → update read/reply/draft link status
DELETE /messages/{message_id}      → delete message
POST   /messages/{message_id}/draft-reply → create a reply draft linked to message

Privacy:
- No full message body stored.
- No Gmail OAuth.
- No SMS integration.
- Metadata is sanitized on import.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.message_repository import message_repository
from app.services.message_analysis_service import analyze_message, build_message_summary
from app.schemas.message_schema import (
    MessageItem,
    MessageImportRequest,
    MessageImportResponse,
    MessageSummary,
    MessageUpdate,
    MessageDraftRequest,
    TopUrgentMessage,
)
from app.schemas.reply_schema import ReplyDraft

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post(
    "/import/mock",
    response_model=MessageImportResponse,
    status_code=200,
    summary="Import mock/manual message metadata",
)
def import_messages(
    body: MessageImportRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Import message metadata (subject, sender, snippet, timestamps only).
    No Gmail. No SMS. No full body.
    Performs urgency analysis and intent detection on import.
    """
    from app.repositories.privacy_preferences_repository import privacy_preferences_repository
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    analyzed = []
    for msg_create in body.messages:
        data = analyze_message(
            source=msg_create.source,
            external_message_id=msg_create.external_message_id,
            channel=msg_create.channel,
            sender=msg_create.sender,
            subject=msg_create.subject,
            snippet=msg_create.snippet,
            received_at=msg_create.received_at,
            is_read=msg_create.is_read,
            metadata=msg_create.metadata,
        )
        if not prefs.store_message_snippets:
            data["snippet"] = None
        analyzed.append(data)

    imported_count, updated_count, saved = message_repository.upsert_messages(
        db, user_id, analyzed
    )

    return MessageImportResponse(
        imported_count=imported_count,
        updated_count=updated_count,
        messages=[MessageItem.model_validate(m) for m in saved],
    )


@router.get(
    "/summary",
    response_model=MessageSummary,
    summary="Get message urgency summary",
)
def get_message_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns urgency, needs-reply, and unread counts with recommendation."""
    recent_messages = message_repository.list_recent(db, user_id, days=7)
    summary_data = build_message_summary(recent_messages)
    return MessageSummary(**summary_data)


@router.get(
    "",
    response_model=List[MessageItem],
    summary="List messages for user",
)
def list_messages(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    needs_reply: Optional[bool] = Query(default=None),
    is_read: Optional[bool] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    messages = message_repository.list_messages(
        db, user_id, limit=limit, offset=offset,
        needs_reply=needs_reply, is_read=is_read,
    )
    return [MessageItem.model_validate(m) for m in messages]


@router.patch(
    "/{message_id}",
    response_model=MessageItem,
    summary="Update message read/reply/draft status",
)
def update_message(
    message_id: str,
    body: MessageUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    payload = body.model_dump(exclude_none=True)
    updated = message_repository.update(db, user_id, message_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageItem.model_validate(updated)


@router.delete(
    "/{message_id}",
    status_code=204,
    summary="Delete a message",
)
def delete_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    deleted = message_repository.delete(db, user_id, message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")


@router.delete(
    "/{message_id}/snippet",
    response_model=MessageItem,
    summary="Purge/redact snippet from a message",
)
def redact_message_snippet(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Purge the snippet text of a message, setting it to None.
    Saves an entry in the privacy audit log.
    """
    msg = message_repository.get_by_id(db, user_id, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    msg.snippet = None
    db.commit()
    db.refresh(msg)
    
    # Log the action in privacy audit log
    from app.repositories.privacy_audit_repository import privacy_audit_repository
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="redact_field",
        target_type="message",
        target_id=message_id,
        extra_metadata={"field": "snippet"}
    )
    return msg


@router.post(

    "/{message_id}/draft-reply",
    response_model=ReplyDraft,
    status_code=201,
    summary="Create a reply draft linked to a message",
)
async def draft_reply_for_message(
    message_id: str,
    body: MessageDraftRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Creates a reply draft from message subject + snippet metadata only.
    No full body. No Gmail. Never sends messages.
    Links the reply draft ID back to the message.
    """
    msg = message_repository.get_by_id(db, user_id, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Build original_message from subject + snippet only
    original_message_parts = []
    if msg.subject:
        original_message_parts.append(f"Subject: {msg.subject}")
    if msg.snippet:
        original_message_parts.append(f"Message: {msg.snippet}")

    if not original_message_parts:
        original_message_parts = ["(No subject or snippet available)"]

    original_message = "\n".join(original_message_parts)

    from app.schemas.reply_schema import ReplyDraftRequest
    from app.services.reply_drafter_service import draft_reply

    draft_request = ReplyDraftRequest(
        original_message=original_message,
        message_sender=msg.sender,
        message_subject=msg.subject,
        message_channel=msg.channel,
        user_intent=body.user_intent,
        preferred_tone=body.preferred_tone,
        current_energy=body.current_energy,
        include_boundary_option=True,
    )

    draft = await draft_reply(db=db, user_id=user_id, request=draft_request)

    # Link the reply draft ID back to the message
    message_repository.update(db, user_id, message_id, {"linked_reply_draft_id": draft.id})

    return ReplyDraft.model_validate(draft)
