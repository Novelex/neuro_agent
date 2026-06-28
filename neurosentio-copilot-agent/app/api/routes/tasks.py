"""
Task routes.

GET    /tasks              → list tasks, optionally filtered by ?status=
POST   /tasks              → create a new task
PATCH  /tasks/{id}         → update task fields (title, description, priority, etc.)
PATCH  /tasks/{id}/status  → update task status only
DELETE /tasks/{id}         → delete a task
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.task_repository import task_repository
from app.schemas.task_schema import (
    TaskCreate,
    TaskUpdate,
    TaskStatusUpdate,
    Task,
    StuckTaskResponse,
)
from app.services.stuck_task_service import detect_stuck_tasks


router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ──────────────────────────────────────────────────────────────────────
# GET /tasks
# Single listing endpoint — supports optional ?status= query filter.
# Examples:
#   GET /tasks              → all tasks (any status)
#   GET /tasks?status=open  → open tasks only
#   GET /tasks?status=in_progress → in-progress only
# ──────────────────────────────────────────────────────────────────────
@router.get("", response_model=List[Task], summary="List tasks")
def get_tasks(
    status: Optional[str] = Query(
        default=None,
        description=(
            "Filter by status. Allowed values: open, in_progress, done, skipped, deferred. "
            "Pass 'active' as a shorthand for open + in_progress. "
            "Omit to return all tasks."
        ),
    ),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns tasks for the current user.

    - No filter → all tasks (any status)
    - `?status=active` → open + in_progress (shorthand for copilot use)
    - `?status=open`, `?status=done`, etc. → exact status match
    """
    all_tasks = task_repository.get_all(db, user_id)

    if status is None:
        return all_tasks

    if status == "active":
        return [t for t in all_tasks if t.status in ("open", "in_progress")]

    return [t for t in all_tasks if t.status == status]


# ──────────────────────────────────────────────────────────────────────
# GET /tasks/stuck
# ──────────────────────────────────────────────────────────────────────
@router.get("/stuck", response_model=List[StuckTaskResponse], summary="Identify stuck tasks")
def get_stuck_tasks(
    days: int = Query(default=3, description="Threshold of days of inactivity"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Get a list of open/in_progress tasks that are overdue or have been inactive for N days.
    Provides tailored neurodivergent suggestions.
    """
    return detect_stuck_tasks(db, user_id, days)


# ──────────────────────────────────────────────────────────────────────
# POST /tasks  — create
# ──────────────────────────────────────────────────────────────────────
@router.post("", response_model=Task, status_code=201, summary="Create a new task")
def create_task(
    body: TaskCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Creates a new task for the current user."""
    from app.repositories.privacy_preferences_repository import privacy_preferences_repository
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    if not prefs.store_task_descriptions:
        body.description = None
    return task_repository.create(db, user_id, body)


# ──────────────────────────────────────────────────────────────────────
# PATCH /tasks/{id}  — partial field update (everything except status)
# ──────────────────────────────────────────────────────────────────────
@router.patch("/{task_id}", response_model=Task, summary="Update task fields")
def update_task(
    task_id: str,
    body: TaskUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Partially updates task metadata: title, description, priority, due_date,
    estimated_energy, estimated_sensory_cost.
    Only the fields you provide are changed.
    To change status use PATCH /tasks/{id}/status.
    """
    from app.repositories.privacy_preferences_repository import privacy_preferences_repository
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    if not prefs.store_task_descriptions and body.description is not None:
        body.description = None
    task = task_repository.update(db, task_id, user_id, body)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ──────────────────────────────────────────────────────────────────────
# PATCH /tasks/{id}/status  — status-only update
# Intentionally separate from the field update so the caller is explicit.
# ──────────────────────────────────────────────────────────────────────
@router.patch("/{task_id}/status", response_model=Task, summary="Update task status")
def update_task_status(
    task_id: str,
    body: TaskStatusUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Updates only the task status.
    Allowed values: open, in_progress, done, skipped, deferred.
    """
    task = task_repository.update_status(db, task_id, user_id, body)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ──────────────────────────────────────────────────────────────────────
# DELETE /tasks/{id}
# ──────────────────────────────────────────────────────────────────────
@router.delete("/{task_id}", status_code=204, summary="Delete a task")
def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Permanently deletes a task."""
    deleted = task_repository.delete(db, task_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


@router.delete("/{task_id}/description", response_model=Task, summary="Purge/redact description from a task")
def redact_task_description(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Purge the description field from a task, setting it to None.
    Saves an entry in the privacy audit log.
    """
    task = task_repository.get_by_id(db, task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.description = None
    db.commit()
    db.refresh(task)
    
    # Log the action in privacy audit log
    from app.repositories.privacy_audit_repository import privacy_audit_repository
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="redact_field",
        target_type="task",
        target_id=task_id,
        extra_metadata={"field": "description"}
    )
    return task

