from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as Connection

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.task_aggregator_schema import TaskAggregatorResponse
from app.services.task_aggregator_service import analyze_task_patterns

router = APIRouter(prefix="/context/tasks", tags=["Task Aggregator"])

@router.get("/analysis", response_model=TaskAggregatorResponse, summary="Analyze tasks for patterns and stuck tasks")
async def analyze_tasks(
    user_id: str = Depends(get_current_user_id),
    db: Connection = Depends(get_db),
):
    """
    Pulls open tasks from the planner, identifies 'stuck' tasks (open > 7 days),
    and uses the LLM to detect underlying patterns and suggest actions.
    """
    return await analyze_task_patterns(db, user_id)
