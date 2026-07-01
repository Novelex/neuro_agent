import logging
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.next_action_schema import NextActionResponse, MicroActionResponse

logger = logging.getLogger(__name__)

async def get_next_action(db: Connection, user_id: str) -> NextActionResponse:
    """
    Finds the single best next action for the user.
    If energy is below 40%, it filters out high-energy tasks.
    """
    # 1. Check current energy
    current_level = sq.get_latest_energy_level(db, user_id)
    if current_level is None:
        current_level = 50
        
    exclude_high_energy = current_level < 40
    
    # 2. Fetch the next appropriate action
    action = sq.get_next_open_micro_action(db, user_id, exclude_high_energy)
    
    if not action:
        # Maybe they are low energy and only have high-energy tasks left?
        if exclude_high_energy:
            # Check if they have ANY task at all
            any_action = sq.get_next_open_micro_action(db, user_id, exclude_high_energy=False)
            if any_action:
                return NextActionResponse(
                    has_action=False,
                    action=None,
                    message="You have tasks left, but your energy is too low to tackle them right now. Consider resting."
                )
                
        return NextActionResponse(
            has_action=False,
            action=None,
            message="No open tasks right now. You are all caught up!"
        )
        
    return NextActionResponse(
        has_action=True,
        action=MicroActionResponse(**action),
        message="Here is your single next step."
    )
