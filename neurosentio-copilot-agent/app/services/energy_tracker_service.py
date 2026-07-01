import logging
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.energy_tracker_schema import EnergyTrendResponse

logger = logging.getLogger(__name__)

async def analyze_energy_trends(db: Connection, user_id: str) -> EnergyTrendResponse:
    logs = sq.get_energy_logs_for_last_7_days(db, user_id)
    
    current_level = sq.get_latest_energy_level(db, user_id)
    if current_level is None:
        current_level = 50  # Default if no logs

    if not logs or len(logs) < 2:
        return EnergyTrendResponse(
            current_level=current_level,
            trend="stable",
            suggestions=["Log your energy more often so we can track your trends!"]
        )

    # Simple trend calculation: average of the first half vs average of the second half
    mid = len(logs) // 2
    first_half = logs[:mid]
    second_half = logs[mid:]

    avg_first = sum(log["level"] for log in first_half) / len(first_half) if first_half else 0
    avg_second = sum(log["level"] for log in second_half) / len(second_half) if second_half else 0

    if avg_second > avg_first + 1:
        trend = "increasing"
        suggestions = ["Your energy has been rising! Great time to tackle higher-friction tasks."]
    elif avg_second < avg_first - 1:
        trend = "decreasing"
        suggestions = ["Your energy has been dropping recently. Focus on recovery mode tasks today."]
    else:
        trend = "stable"
        suggestions = ["Your energy is relatively stable. Keep up a balanced pace."]

    return EnergyTrendResponse(
        current_level=current_level,
        trend=trend,
        suggestions=suggestions
    )
