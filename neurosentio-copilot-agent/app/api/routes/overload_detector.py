from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.overload_detector_schema import OverloadDetectorResponse
from app.services.overload_detector_service import detect_overload

router = APIRouter(prefix="/copilot", tags=["Overload Detector"])

@router.post("/detect-overload", response_model=OverloadDetectorResponse, summary="Detect pattern triggers for overload")
async def check_overload(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Monitors recent energy levels and failed/deferred tasks. 
    Automatically switches today's plan to 'recovery' mode if an overload pattern is detected.
    """
    return await detect_overload(db, user_id)
