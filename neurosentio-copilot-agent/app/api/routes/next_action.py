from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.next_action_schema import NextActionResponse
from app.services.next_action_service import get_next_action

router = APIRouter(prefix="/micro-actions", tags=["Next Action Prompter"])

@router.get("/next-action", response_model=NextActionResponse, summary="Get the single next best micro-action")
async def next_action(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Cuts through the noise and returns only the single next step the user should take right now.
    Filters out high-energy tasks if the user's current energy is low.
    """
    return await get_next_action(db, user_id)
