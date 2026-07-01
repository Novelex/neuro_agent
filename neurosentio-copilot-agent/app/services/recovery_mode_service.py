import logging
from datetime import datetime, timezone
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.recovery_mode_schema import RecoveryModeResponse

logger = logging.getLogger(__name__)

async def activate_recovery_mode(db: Connection, user_id: str) -> RecoveryModeResponse:
    """
    Activates recovery mode by:
    1. Snoozing all open high-energy tasks.
    2. Inserting basic self-care tasks into today's plan.
    3. Changing today's morning plan mode to 'recovery'.
    """
    today = datetime.now(timezone.utc).date()
    
    # Ensure there is an active morning plan to tie the new tasks to
    plan = sq.get_today_morning_plan(db, user_id, today)
    plan_id = plan["id"] if plan else None
    
    # 1. Bulk update: Snooze high-energy tasks
    snoozed_count = sq.snooze_high_energy_micro_actions(db, user_id)
    
    # 2. Insert basic recovery tasks
    recovery_actions = [
        {
            "title": "Drink a glass of water",
            "description": "Hydration helps clear brain fog.",
            "duration_minutes": 5,
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": -2
        },
        {
            "title": "Rest or disconnect for 15 minutes",
            "description": "Step away from screens and reduce sensory input.",
            "duration_minutes": 15,
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": -1
        }
    ]
    
    sq.save_micro_actions(db, user_id, task_id=None, plan_id=plan_id, actions=recovery_actions)
    
    # 3. Update the morning plan mode to 'recovery' if it exists
    if plan and plan["mode"] != "recovery":
        sq.set_morning_plan_recovery_mode(db, user_id, today)
        
    return RecoveryModeResponse(
        success=True,
        message="Recovery mode activated. Hard tasks have been snoozed and self-care tasks have been added.",
        snoozed_count=snoozed_count,
        recovery_tasks_added=[a["title"] for a in recovery_actions]
    )
