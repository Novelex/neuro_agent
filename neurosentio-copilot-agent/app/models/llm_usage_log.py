"""
LLM Usage Log ORM model (Day 9).

Tracks metadata for every LLM call.

Privacy rules:
- NO full prompt text stored
- NO original message text stored
- NO full LLM response text stored
- Only metadata: feature, provider, model, tokens, latency, status
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Index
from sqlalchemy.types import JSON
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # Which product feature triggered this LLM call
    # Allowed: task_decomposition | reply_drafting | transition_script |
    #          make_smaller | morning_plan | unknown
    feature = Column(String, nullable=False, default="unknown")

    # Provider that served the call
    # Allowed: mock | anthropic | openai | fallback
    provider = Column(String, nullable=False)

    # Model name — null for mock
    model = Column(String, nullable=True)

    # Prompt version string — e.g. "task_decomposition_v1"
    prompt_version = Column(String, nullable=True)

    # Outcome
    # Allowed: success | fallback | error | skipped_rate_limit
    status = Column(String, nullable=False, index=True)

    # Error classification — null on success
    error_type = Column(String, nullable=True)

    # Token counts — null for mock or when provider does not report
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Approximate cost in USD — 0.0 for mock, null if unknown
    estimated_cost_usd = Column(Float, nullable=True)

    # End-to-end latency of the LLM call in milliseconds
    latency_ms = Column(Integer, nullable=True)

    # Lightweight non-sensitive metadata dict (e.g. schema_name, retry_count)
    # MUST NOT include prompt text or original message text
    request_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (
        Index("ix_llm_usage_logs_user_feature", "user_id", "feature"),
        Index("ix_llm_usage_logs_user_status", "user_id", "status"),
        Index("ix_llm_usage_logs_provider", "provider"),
    )
