"""Stuck Task Detector Service."""

from datetime import datetime, date, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.repositories.task_repository import task_repository


def detect_stuck_tasks(db: Session, user_id: str, threshold_days: int = 3) -> List[dict]:
    """
    Scan all open or in_progress tasks for a user and return the stuck ones.
    """
    open_tasks = task_repository.get_open(db, user_id)
    stuck_tasks = []

    now_dt = datetime.now(timezone.utc)
    today = date.today()

    for task in open_tasks:
        stuck_reason = None
        suggestion = None

        # 1. Overdue check
        if task.due_date and task.due_date < today:
            stuck_reason = "overdue"
            suggestion = "Consider deferring this task to a lower-load day."
        
        # 2. Inactive check (if not already marked overdue)
        else:
            # We treat naive datetimes as local/UTC matching
            last_touch = task.last_touched_at or task.created_at
            if last_touch:
                # Ensure tzinfo is set for comparison
                if last_touch.tzinfo is None:
                    last_touch = last_touch.replace(tzinfo=timezone.utc)
                
                diff = now_dt - last_touch
                if diff.days >= threshold_days:
                    stuck_reason = "inactive"
                    if task.status == "in_progress":
                        suggestion = "Can you spend just 5 minutes on a tiny action to get started?"
                    else:
                        suggestion = "Try breaking this task into smaller micro-actions."

        if stuck_reason and suggestion:
            stuck_tasks.append({
                "task": task,
                "stuck_reason": stuck_reason,
                "suggestion": suggestion
            })

    return stuck_tasks
