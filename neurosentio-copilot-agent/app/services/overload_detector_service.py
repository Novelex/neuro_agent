import logging
from datetime import datetime, timezone
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.overload_detector_schema import OverloadDetectorResponse

logger = logging.getLogger(__name__)

async def detect_overload(db: Connection, user_id: str) -> OverloadDetectorResponse:
    """
    Checks if the user's energy is low and they are failing tasks.
    If so, switches the morning plan mode to 'recovery'.
    """
    # 1. Check energy (last 24 hours, or just latest)
    current_level = sq.get_latest_energy_level(db, user_id)
    if current_level is None:
        current_level = 50  # default
        
    # 2. Check failed task count (deferred or snoozed in last 24h)
    failed_tasks = sq.get_failed_task_count_last_24h(db, user_id)
    
    overload_detected = False
    message = "You seem to be doing okay. Mode remains normal."
    current_mode = "normal"
    
    # 3. Logic: If energy < 30 and failed tasks > 1 (meaning they are struggling)
    if current_level < 30 and failed_tasks > 1:
        overload_detected = True
        
    if overload_detected:
        today = datetime.now(timezone.utc).date()
        # Ensure a morning plan exists to update
        plan = sq.get_today_morning_plan(db, user_id, today)
        if plan:
            if plan["mode"] != "recovery":
                sq.set_morning_plan_recovery_mode(db, user_id, today)
                message = "Overload detected: Energy is critically low and tasks are being deferred. Switched today's plan to Recovery Mode."
                current_mode = "recovery"
            else:
                message = "Overload detected, but you are already in Recovery Mode."
                current_mode = "recovery"
        else:
            message = "Overload detected, but no active morning plan found for today to update."
            current_mode = "normal"
            
    return OverloadDetectorResponse(
        overload_detected=overload_detected,
        message=message,
        current_mode=current_mode
    )
