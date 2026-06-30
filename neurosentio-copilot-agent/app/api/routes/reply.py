"""
Reply Drafter API routes.

POST   /reply/draft              → generate and save reply drafts

IMPORTANT:
- This service NEVER sends messages.
- No Gmail, SMS, or messaging integration.
"""

from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.reply_schema import (
    ReplyDraft as ReplyDraftSchema,
    ReplyDraftRequest,
)
from app.services.reply_drafter_service import draft_reply

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
    db: Connection = Depends(get_db),
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
