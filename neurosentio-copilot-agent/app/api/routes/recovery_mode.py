from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.recovery_mode_schema import RecoveryModeResponse
from app.services.recovery_mode_service import activate_recovery_mode

router = APIRouter(prefix="/copilot", tags=["Recovery Mode"])

@router.post("/activate-recovery", response_model=RecoveryModeResponse, summary="Manually trigger recovery mode")
async def activate_recovery(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Snoozes all high-energy tasks and immediately injects 
    low-friction, self-care tasks into the current plan.
    """
    return await activate_recovery_mode(db, user_id)
