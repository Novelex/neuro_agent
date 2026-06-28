"""Optional Postgres Integration and Compatibility Tests.

Runs only when explicitly opted in and Postgres is reachable.
"""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.models.user_profile import UserProfile
from app.models.message_item import MessageItem
from app.models.calendar_event import CalendarEvent
from app.models.llm_usage_log import LLMUsageLog
from app.models.next_action_prompt import NextActionPrompt

# Retrieve Postgres connection details from settings
settings = get_settings()
postgres_url = os.environ.get("POSTGRES_DATABASE_URL") or settings.postgres_database_url

# Gracefully check reachability of Postgres
postgres_reachable = False
if postgres_url:
    try:
        # Fast connection timeout
        engine = create_engine(postgres_url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres_reachable = True
    except Exception:
        postgres_reachable = False

# Skip all tests in this file if Postgres is not reachable
pytestmark = pytest.mark.skipif(
    not postgres_reachable,
    reason="PostgreSQL database is not reachable. Ensure the Docker container is running."
)


@pytest.fixture(scope="module")
def pg_session():
    """Sets up a clean temporary Postgres schema for integration testing."""
    engine = create_engine(postgres_url)
    
    # Clean up schema
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS pg_test_schema CASCADE;"))
        conn.execute(text("CREATE SCHEMA pg_test_schema;"))
        # Set search path to our custom test schema
        conn.execute(text("SET search_path TO pg_test_schema;"))
        conn.commit()
        
    # Bind metadata and create all tables
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop schema afterwards to clean up
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS pg_test_schema CASCADE;"))
            conn.commit()


def test_postgres_metadata_compatibility(pg_session):
    """Verifies that JSON/Metadata and reserved column names work correctly on Postgres."""
    db = pg_session
    uid = "pg-test-user-fixture"
    
    # 1. MessageItem extra_metadata & detected_keywords mapping check
    msg = MessageItem(
        user_id=uid,
        source="mock",
        channel="sms",
        sender="E2E Tester",
        snippet="Checking Postgres compatibility",
        detected_keywords=["compat", "postgres"],
        extra_metadata={"env": "testing", "runner": "pytest"}
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    assert msg.id is not None
    assert msg.detected_keywords == ["compat", "postgres"]
    assert msg.extra_metadata == {"env": "testing", "runner": "pytest"}

    # 2. CalendarEvent raw_metadata index and JSON check
    from datetime import datetime, timezone, timedelta
    evt = CalendarEvent(
        user_id=uid,
        provider="manual",
        external_event_id="pg-test-evt-1",
        title="Sync Test",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
        raw_metadata={"importance": "critical"}
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    
    assert evt.raw_metadata == {"importance": "critical"}

    # 3. LLMUsageLog request_metadata verification
    ulog = LLMUsageLog(
        user_id=uid,
        feature="task_decomposition",
        provider="mock",
        status="success",
        request_metadata={"schema": "v1"}
    )
    db.add(ulog)
    db.commit()
    db.refresh(ulog)
    
    assert ulog.request_metadata == {"schema": "v1"}

    # 4. NextActionPrompt metadata keyword column mapping check
    nap = NextActionPrompt(
        user_id=uid,
        source_type="system",
        action_type="review_plan",
        title="Review Plan",
        message="Please check your day's schedule.",
        status="active",
        extra_metadata={"category": "audit"}
    )
    db.add(nap)
    db.commit()
    db.refresh(nap)
    
    assert nap.extra_metadata == {"category": "audit"}
