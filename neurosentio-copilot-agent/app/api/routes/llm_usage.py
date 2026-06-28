"""
LLM Usage API endpoints (Day 10).

Users can only see their own logs.
No admin-only endpoints — user-scoped only at this stage.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.repositories.llm_usage_repository import llm_usage_repository

router = APIRouter(prefix="/llm", tags=["LLM Usage"])


@router.get(
    "/usage",
    summary="Get your recent LLM usage logs",
    description=(
        "Returns metadata logs for your recent LLM calls. "
        "Does NOT include full prompt text or original messages — metadata only."
    ),
)
def get_usage_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = llm_usage_repository.list_for_user(db, user_id, limit=limit, offset=offset)
    return [
        {
            "id": r.id,
            "feature": r.feature,
            "provider": r.provider,
            "model": r.model,
            "prompt_version": r.prompt_version,
            "status": r.status,
            "error_type": r.error_type,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "total_tokens": r.total_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "latency_ms": r.latency_ms,
            "request_metadata": r.request_metadata,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get(
    "/usage/summary",
    summary="Get your LLM usage summary",
    description=(
        "Returns daily/monthly usage counts, estimated cost, and breakdowns by feature and status."
    ),
)
def get_usage_summary(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return llm_usage_repository.summarize_for_user(db, user_id)
