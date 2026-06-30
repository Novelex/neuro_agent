"""
Decomposition routes — attached under /tasks/{task_id}/... prefix.

POST /tasks/{task_id}/decompose      → break task into micro-actions
GET  /tasks/{task_id}/micro-actions  → list micro-actions for a task

These are registered in main.py alongside the existing tasks router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.supabase_db import get_supabase_db as get_db
from app.core.auth import get_current_user_id
from app.schemas.micro_action_schema import (
    MicroAction as MicroActionSchema,
    TaskDecomposeRequest,
    TaskDecomposeResponse,
)
from app.core import supabase_queries as sq
from app.services.task_decomposer_service import decompose_task

router = APIRouter(tags=["Decomposition"])


# ──────────────────────────────────────────────────────────────────────
# POST /tasks/{task_id}/decompose
# ──────────────────────────────────────────────────────────────────────
@router.post(
    "/tasks/{task_id}/decompose",
    response_model=TaskDecomposeResponse,
    summary="Decompose a task into micro-actions",
)
async def decompose_task_endpoint(
    task_id: UUID,
    body: TaskDecomposeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Breaks a task into tiny, neurodivergent-friendly micro-actions.

    - If micro-actions already exist for this task, returns them without regenerating
      (unless force_regenerate=true).
    - If current_energy < 30, switches to recovery mode (fewer, smaller actions).
    - Uses mock LLM by default — no API key required.
    - Falls back to rule-based decomposition if LLM fails.
    """
    try:
        result = await decompose_task(
            db=db,
            user_id=user_id,
            task_id=str(task_id),
            request=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ──────────────────────────────────────────────────────────────────────
# GET /tasks/{task_id}/micro-actions
# ──────────────────────────────────────────────────────────────────────
@router.get(
    "/tasks/{task_id}/micro-actions",
    response_model=List[MicroActionSchema],
    summary="Get all micro-actions for a task",
)
def get_task_micro_actions(
    task_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns all micro-actions for the given task, ordered by sort_order.
    Scoped to the current user — another user's tasks return an empty list.
    """
    return sq.get_micro_actions_for_task(db, user_id, str(task_id))
