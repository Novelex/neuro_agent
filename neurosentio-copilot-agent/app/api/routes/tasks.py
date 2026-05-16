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
from app.utils.time_utils import get_user_id
from app.repositories.task_repository import task_repository
from app.schemas.task_schema import (
    TaskCreate,
    TaskUpdate,
    TaskStatusUpdate,
    Task,
)

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
    user_id: str = Depends(get_user_id),
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
# POST /tasks  — create
# ──────────────────────────────────────────────────────────────────────
@router.post("", response_model=Task, status_code=201, summary="Create a new task")
def create_task(
    body: TaskCreate,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """Creates a new task for the current user."""
    return task_repository.create(db, user_id, body)


# ──────────────────────────────────────────────────────────────────────
# PATCH /tasks/{id}  — partial field update (everything except status)
# ──────────────────────────────────────────────────────────────────────
@router.patch("/{task_id}", response_model=Task, summary="Update task fields")
def update_task(
    task_id: str,
    body: TaskUpdate,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Partially updates task metadata: title, description, priority, due_date,
    estimated_energy, estimated_sensory_cost.
    Only the fields you provide are changed.
    To change status use PATCH /tasks/{id}/status.
    """
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
    user_id: str = Depends(get_user_id),
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
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """Permanently deletes a task."""
    deleted = task_repository.delete(db, task_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
