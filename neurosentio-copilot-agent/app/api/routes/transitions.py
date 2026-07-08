"""
Transition script routes.

POST   /transitions/generate                   → generate a new script
"""

from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.transition_script_schema import (
    TransitionScriptGenerateRequest,
    TransitionScriptGenerateResponse,
)
from app.services.transition_script_service import generate_transition_script

router = APIRouter(prefix="/transitions", tags=["Transitions"])


@router.post(
    "/generate",
    response_model=TransitionScriptGenerateResponse,
    summary="Generate a transition script",
)
async def generate_transition(
    body: TransitionScriptGenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Generates a gentle, neurodivergent-friendly transition script.

    Supported types: leaving_house, starting_work, making_call, ending_day,
    context_switch, recovery_break, custom.

    If current_energy < 30, generates a shorter recovery version (≤ 3 steps).
    """
    return await generate_transition_script(db=db, user_id=user_id, request=body)
