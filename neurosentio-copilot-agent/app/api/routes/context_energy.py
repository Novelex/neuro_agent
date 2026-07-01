from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.energy_tracker_schema import EnergyTrendResponse
from app.services.energy_tracker_service import analyze_energy_trends

router = APIRouter(prefix="/context/energy", tags=["Energy Tracker"])

@router.get("/trend", response_model=EnergyTrendResponse, summary="Get energy trend and suggestions")
async def get_energy_trend(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Analyzes the last 7 days of energy logs and provides a trend (increasing/decreasing/stable)
    along with actionable suggestions.
    """
    return await analyze_energy_trends(db, user_id)
