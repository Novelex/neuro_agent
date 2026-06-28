"""
LLM Usage Log repository (Day 9).

All methods strictly filter by user_id.
Provides counts for rate limiting and summaries for the usage endpoint.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.llm_usage_log import LLMUsageLog


class LLMUsageRepository:

    # ── Writes ─────────────────────────────────────────────────────────

    def create_log(
        self,
        db: Session,
        user_id: str,
        feature: str,
        provider: str,
        status: str,
        model: Optional[str] = None,
        prompt_version: Optional[str] = None,
        error_type: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        estimated_cost_usd: Optional[float] = None,
        latency_ms: Optional[int] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMUsageLog:
        row = LLMUsageLog(
            user_id=user_id,
            feature=feature,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            status=status,
            error_type=error_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
            request_metadata=request_metadata,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    # ── Reads ──────────────────────────────────────────────────────────

    def count_user_logs_today(self, db: Session, user_id: str) -> int:
        """Count of successful/mock calls today (UTC day boundary)."""
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (
            db.query(LLMUsageLog)
            .filter(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= start_of_day,
                LLMUsageLog.status.in_(["success", "fallback"]),
            )
            .count()
        )

    def count_user_logs_this_month(self, db: Session, user_id: str) -> int:
        """Count of successful/mock calls this calendar month."""
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            db.query(LLMUsageLog)
            .filter(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= start_of_month,
                LLMUsageLog.status.in_(["success", "fallback"]),
            )
            .count()
        )

    def list_for_user(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LLMUsageLog]:
        return (
            db.query(LLMUsageLog)
            .filter(LLMUsageLog.user_id == user_id)
            .order_by(LLMUsageLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def summarize_for_user(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Returns usage summary:
        - daily_used, monthly_used
        - total estimated cost
        - breakdown by feature and status
        """
        from app.core.llm_config import get_llm_settings
        settings = get_llm_settings()

        daily_used = self.count_user_logs_today(db, user_id)
        monthly_used = self.count_user_logs_this_month(db, user_id)

        # Cost sum
        cost_result = (
            db.query(func.sum(LLMUsageLog.estimated_cost_usd))
            .filter(LLMUsageLog.user_id == user_id)
            .scalar()
        )
        total_cost = round(cost_result or 0.0, 8)

        # By feature
        feature_rows = (
            db.query(LLMUsageLog.feature, func.count(LLMUsageLog.id))
            .filter(LLMUsageLog.user_id == user_id)
            .group_by(LLMUsageLog.feature)
            .all()
        )
        by_feature = {row[0]: row[1] for row in feature_rows}

        # By status
        status_rows = (
            db.query(LLMUsageLog.status, func.count(LLMUsageLog.id))
            .filter(LLMUsageLog.user_id == user_id)
            .group_by(LLMUsageLog.status)
            .all()
        )
        by_status = {row[0]: row[1] for row in status_rows}

        return {
            "user_id": user_id,
            "daily_used": daily_used,
            "daily_limit": settings.llm_daily_user_limit,
            "monthly_used": monthly_used,
            "monthly_limit": settings.llm_monthly_user_limit,
            "estimated_cost_usd": total_cost,
            "by_feature": by_feature,
            "by_status": by_status,
        }


llm_usage_repository = LLMUsageRepository()
