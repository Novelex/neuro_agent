"""GET /health — service health check with database connectivity verification."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.supabase_db import get_supabase_db as get_db

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health_check(db: Session = Depends(get_db)):
    """
    Returns service status and verifies database connectivity.
    Returns 200 if healthy, includes db_status for monitoring.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": status,
        "service": "neurosentio-copilot-agent",
        "database": db_status,
    }

