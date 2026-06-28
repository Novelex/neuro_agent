"""
LLM Rate Limit Service (Day 9).

Checks whether a user can make an LLM call based on daily/monthly limits.
Limits are configurable via LLM_DAILY_USER_LIMIT and LLM_MONTHLY_USER_LIMIT.

If the user is rate-limited:
- The calling service should use fallback output
- A log entry is created with status="skipped_rate_limit"
- The API does NOT crash — returns a degraded but valid response
"""

from typing import TypedDict, Optional
from sqlalchemy.orm import Session

from app.core.llm_config import get_llm_settings
from app.repositories.llm_usage_repository import llm_usage_repository


class RateLimitResult(TypedDict):
    allowed: bool
    reason: Optional[str]           # None | "daily_limit_exceeded" | "monthly_limit_exceeded"
    daily_used: int
    daily_limit: int
    monthly_used: int
    monthly_limit: int


def check_rate_limit(db: Session, user_id: str) -> RateLimitResult:
    """
    Check whether this user can make an LLM call right now.

    Returns RateLimitResult with allowed=True/False.
    Does NOT call the LLM or write anything to the DB.
    """
    settings = get_llm_settings()
    daily_limit = settings.llm_daily_user_limit
    monthly_limit = settings.llm_monthly_user_limit

    daily_used = llm_usage_repository.count_user_logs_today(db, user_id)
    monthly_used = llm_usage_repository.count_user_logs_this_month(db, user_id)

    if daily_used >= daily_limit:
        return RateLimitResult(
            allowed=False,
            reason="daily_limit_exceeded",
            daily_used=daily_used,
            daily_limit=daily_limit,
            monthly_used=monthly_used,
            monthly_limit=monthly_limit,
        )

    if monthly_used >= monthly_limit:
        return RateLimitResult(
            allowed=False,
            reason="monthly_limit_exceeded",
            daily_used=daily_used,
            daily_limit=daily_limit,
            monthly_used=monthly_used,
            monthly_limit=monthly_limit,
        )

    return RateLimitResult(
        allowed=True,
        reason=None,
        daily_used=daily_used,
        daily_limit=daily_limit,
        monthly_used=monthly_used,
        monthly_limit=monthly_limit,
    )


def log_rate_limit_skip(
    db: Session,
    user_id: str,
    feature: str,
    provider: str,
    reason: str,
    prompt_version: Optional[str] = None,
) -> None:
    """Record a skipped call in usage logs."""
    llm_usage_repository.create_log(
        db=db,
        user_id=user_id,
        feature=feature,
        provider=provider,
        status="skipped_rate_limit",
        prompt_version=prompt_version,
        error_type=reason,
        request_metadata={"reason": reason},
    )
