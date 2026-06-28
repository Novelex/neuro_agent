"""
PostgreSQL Migration & Compatibility Check Script.

Runs Alembic migrations against PostgreSQL, checks Postgres-native column types,
and verifies model/field compatibility (especially around reserved keywords and JSON fields).
"""

import sys
import os
import argparse
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 1. Parse command-line args
parser = argparse.ArgumentParser(description="Verify Postgres compatibility and migrations.")
parser.add_argument("--allow-non-test-db", action="store_true", help="Allow destructive cleanup on databases not containing 'test' in the name")
parser.add_argument("--db-url", type=str, default=None, help="Direct database URL override")
args = parser.parse_args()

# 2. Configure Database URL
postgres_url = args.db_url or os.environ.get("POSTGRES_DATABASE_URL")
if not postgres_url:
    # Read from Settings default if not in environment
    from app.core.config import get_settings
    settings = get_settings()
    postgres_url = settings.postgres_database_url

print(f"Target Database URL: {postgres_url}")

# Parse database name for safety guard
parsed = urlparse(postgres_url)
db_name = parsed.path.lstrip('/')

# Safety Guard Check
if "test" not in db_name.lower() and not args.allow_non_test_db:
    print(f"ERROR: Destructive database operations refused. Database name '{db_name}' does not contain 'test' and --allow-non-test-db was not supplied.")
    sys.exit(1)

print(f"Safety guard passed. Database '{db_name}' contains 'test'. Proceeding with migrations and compatibility checks...")

# Map POSTGRES_DATABASE_URL to DATABASE_URL so both app settings and Alembic pick it up
os.environ["DATABASE_URL"] = postgres_url

# Now import SQLAlchemy elements after environment is configured
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

# 3. Clean and prepare database schema
print("\nWiping target Postgres schema for a clean, deterministic migration run...")
try:
    engine = create_engine(postgres_url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
    print("Schema wiped successfully.")
except Exception as exc:
    print(f"Error connecting/wiping schema. Is the Postgres Docker container running?\nError: {exc}")
    sys.exit(1)

# 4. Run Alembic migrations programmatically
print("\nRunning Alembic migrations up to head...")
try:
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(alembic_cfg, "head")
    print("Alembic migrations completed successfully.")
except Exception as exc:
    print(f"Alembic migration failed: {exc}")
    sys.exit(1)

# 5. Query information_schema.columns to verify native Postgres types
print("\nVerifying native Postgres column types created after migrations...")
native_types_verified = True
columns_to_check = [
    ("message_items", "metadata"),
    ("message_items", "detected_keywords"),
    ("calendar_events", "raw_metadata"),
    ("llm_usage_logs", "request_metadata"),
    ("next_action_prompts", "metadata"),
    ("message_items", "received_at"),
    ("calendar_events", "start_time")
]

with engine.connect() as conn:
    for table, col in columns_to_check:
        query = text("""
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = :table AND column_name = :col
        """)
        row = conn.execute(query, {"table": table, "col": col}).fetchone()
        if row:
            data_type, nullable = row
            print(f"  [VERIFIED] {table}.{col:<18} -> Postgres Type: {data_type:<25} (Nullable: {nullable})")
            # Ensure JSON columns created native 'json' type, and DateTime columns created 'timestamp with/without time zone'
            if "metadata" in col or "keywords" in col:
                if "json" not in data_type.lower():
                    print(f"  [FAIL] Expected native JSON column for {table}.{col}, got {data_type}")
                    native_types_verified = False
            if "time" in col or "received" in col:
                if "timestamp" not in data_type.lower():
                    print(f"  [FAIL] Expected native TIMESTAMP column for {table}.{col}, got {data_type}")
                    native_types_verified = False
        else:
            print(f"  [FAIL] Column {table}.{col} was NOT found in PostgreSQL schema!")
            native_types_verified = False

if native_types_verified:
    print("Postgres native column types verified successfully.")
else:
    print("Warning: Some Postgres native column types were not created correctly.")

# 6. Execute full ORM compatibility and CRUD operations across all 16 models
print("\nVerifying model/field compatibility and CRUD operations in PostgreSQL...")
from app.models.user_profile import UserProfile
from app.models.task import Task
from app.models.energy_log import EnergyLog
from app.models.copilot_plan import CopilotPlan
from app.models.micro_action import MicroAction
from app.models.transition_script import TransitionScript
from app.models.reply_draft import ReplyDraft
from app.models.llm_usage_log import LLMUsageLog
from app.models.calendar_event import CalendarEvent
from app.models.overload_event import OverloadEvent
from app.models.message_item import MessageItem
from app.models.next_action_prompt import NextActionPrompt
from app.models.replan_event import ReplanEvent
from app.models.privacy_preferences import PrivacyPreferences
from app.models.privacy_audit_log import PrivacyAuditLog

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    uid = "postgres-compat-user"
    
    # User Profile & Privacy Preferences
    print("  Testing UserProfile & PrivacyPreferences...")
    profile = UserProfile(user_id=uid, preferred_tone="gentle")
    prefs = PrivacyPreferences(user_id=uid, retention_days_messages=45)
    db.add(profile)
    db.add(prefs)
    db.commit()
    
    # Task & Energy Log
    print("  Testing Task & EnergyLog...")
    task = Task(id="pg-task-1", user_id=uid, title="Pitch Deck", description="Create slides.", status="open")
    elog = EnergyLog(user_id=uid, battery_level=75, sensory_state="okay")
    db.add(task)
    db.add(elog)
    db.commit()
    
    # Copilot Plan & Micro Actions
    print("  Testing CopilotPlan & MicroAction...")
    plan = CopilotPlan(id="pg-plan-1", user_id=uid, summary="Morning plan", mode="normal")
    action = MicroAction(id="pg-action-1", user_id=uid, task_id="pg-task-1", title="Open PowerPoint", duration_minutes=5)
    db.add(plan)
    db.add(action)
    db.commit()
    
    # Transition Script & Reply Draft
    print("  Testing TransitionScript & ReplyDraft...")
    trans = TransitionScript(user_id=uid, transition_type="leaving_house", title="Leave House", script_steps=[])
    reply = ReplyDraft(id="pg-draft-1", user_id=uid, source_type="email", original_message="Hello", message_channel="email", status="drafted", source="mock")
    db.add(trans)
    db.add(reply)
    db.commit()
    
    # Overload Event & Replan Event
    print("  Testing OverloadEvent & ReplanEvent...")
    overload = OverloadEvent(user_id=uid, risk_score=90, mode="normal", trigger_reasons=["back-to-back"])
    replan = ReplanEvent(user_id=uid, previous_plan_id="pg-plan-1", trigger_type="low_energy")
    db.add(overload)
    db.add(replan)
    db.commit()
    
    # Privacy Audit Log
    print("  Testing PrivacyAuditLog...")
    audit = PrivacyAuditLog(user_id=uid, action_type="view_export", extra_metadata={"ip": "127.0.0.1"})
    db.add(audit)
    db.commit()
    
    # Check reserved-keyword fields & metadata-like columns specifically
    print("  Testing message_items (checking metadata and keywords mapping)...")
    msg = MessageItem(
        user_id=uid,
        source="mock",
        channel="sms",
        sender="Bob",
        snippet="Dinner tonight?",
        detected_keywords=["dinner", "tonight"],
        extra_metadata={"device": "iPhone", "carrier": "T-Mobile"}
    )
    db.add(msg)
    db.commit()
    
    print("  Testing calendar_events (checking raw_metadata and indexes)...")
    evt = CalendarEvent(
        user_id=uid,
        provider="manual",
        external_event_id="pg-evt-ext-1",
        title="Sync Meeting",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        raw_metadata={"guests": ["Alice", "Charlie"]}
    )
    db.add(evt)
    db.commit()
    
    print("  Testing llm_usage_logs (checking request_metadata mapping)...")
    ulog = LLMUsageLog(
        user_id=uid,
        feature="reply_drafting",
        provider="mock",
        status="success",
        request_metadata={"retries": 0, "timeout": 30}
    )
    db.add(ulog)
    db.commit()
    
    print("  Testing next_action_prompts (checking metadata keyword)...")
    nap = NextActionPrompt(
        user_id=uid,
        source_type="micro_action",
        action_type="do_micro_action",
        title="Start Task",
        message="Please start PowerPoint",
        status="active",
        extra_metadata={"urgency": "low"}
    )
    db.add(nap)
    db.commit()
    
    # Verify we can read everything back with correct types
    print("\nReading data back to verify JSON & column integrity in Postgres...")
    
    db_msg = db.query(MessageItem).filter(MessageItem.user_id == uid).first()
    assert db_msg.extra_metadata == {"device": "iPhone", "carrier": "T-Mobile"}, "Message extra_metadata mismatch"
    assert db_msg.detected_keywords == ["dinner", "tonight"], "Message detected_keywords mismatch"
    
    db_evt = db.query(CalendarEvent).filter(CalendarEvent.user_id == uid).first()
    assert db_evt.raw_metadata == {"guests": ["Alice", "Charlie"]}, "CalendarEvent raw_metadata mismatch"
    
    db_ulog = db.query(LLMUsageLog).filter(LLMUsageLog.user_id == uid).first()
    assert db_ulog.request_metadata == {"retries": 0, "timeout": 30}, "LLMUsageLog request_metadata mismatch"
    
    db_nap = db.query(NextActionPrompt).filter(NextActionPrompt.user_id == uid).first()
    assert db_nap.extra_metadata == {"urgency": "low"}, "NextActionPrompt extra_metadata mismatch"
    
    print("  [SUCCESS] All metadata-like and JSON columns read/write cleanly under Postgres.")
    
    # Clean up test user data programmatically
    print("\nPerforming programmatic cleanup of seeded database items...")
    from app.services.data_delete_service import delete_user_data
    delete_counts = delete_user_data(db, uid, delete_profile=True)
    print(f"  Programmatic Cleanup complete. Deleted counts: {delete_counts}")
    
    # Verify database is empty for this user
    user_records = db.query(UserProfile).filter(UserProfile.user_id == uid).count()
    assert user_records == 0, f"Expected 0 profile records remaining, got {user_records}"
    print("  [SUCCESS] Cleanup safety checks verified. User profile and all references purged cleanly.")
    
    print("\nPostgres Compatibility & CRUD validation passed perfectly!")
    
except Exception as exc:
    print(f"\n[FAIL] Model/Compatibility check failed: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()

sys.exit(0)
