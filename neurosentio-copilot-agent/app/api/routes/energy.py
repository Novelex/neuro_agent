"""
Energy routes.

GET  /energy/latest   → most recent energy log for this user
GET  /energy/history  → last 50 energy logs, newest first
POST /energy/log      → record a new energy state
"""

from typing import List
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.energy_repository import energy_repository
from app.schemas.energy_log_schema import EnergyCreate, Energy, EnergyPatternsResponse
from app.services.energy_pattern_service import get_energy_patterns


router = APIRouter(prefix="/energy", tags=["Energy"])


# ──────────────────────────────────────────────────────────────────────
# GET /energy/latest
# Returns the single most recent energy log.
# ──────────────────────────────────────────────────────────────────────
@router.get("/latest", response_model=Energy, summary="Get latest energy log")
def get_latest_energy(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the most recent energy snapshot.
    Returns 204 No Content if the user has not logged energy yet.
    """
    log = energy_repository.get_latest(db, user_id)
    if log is None:
        return JSONResponse(status_code=204, content=None)
    return log


# ──────────────────────────────────────────────────────────────────────
# GET /energy/history
# Returns a list of past energy logs (read-only, no write side-effect).
# ──────────────────────────────────────────────────────────────────────
@router.get("/history", response_model=List[Energy], summary="Get energy log history")
def get_energy_history(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the last 50 energy logs for the current user, newest first.
    This is a read-only view — it never writes anything.
    """
    return energy_repository.get_all(db, user_id)


# ──────────────────────────────────────────────────────────────────────
# POST /energy/log
# Creates a new energy entry (write-only, no data is returned except the
# newly created record).
# ──────────────────────────────────────────────────────────────────────
@router.post("/log", response_model=Energy, status_code=201, summary="Log current energy state")
def log_energy(
    body: EnergyCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Record how you're feeling right now.
    battery_level must be 0–100.
    sensory_state: calm | okay | overstimulated | shutdown | anxious | unknown
    """
    return energy_repository.create(db, user_id, body)


# ──────────────────────────────────────────────────────────────────────
# GET /energy/patterns
# ──────────────────────────────────────────────────────────────────────
@router.get("/patterns", response_model=EnergyPatternsResponse, summary="Get aggregated energy patterns")
def get_user_energy_patterns(
    days: int = 14,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Get aggregated energy patterns for the current user based on history of the last N days.
    """
    return get_energy_patterns(db, user_id, days)

