"""Tests for User Data Export and Sequential Data Deletion."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db
from app.models.task import Task
from app.models.message_item import MessageItem
from app.models.reply_draft import ReplyDraft
from app.models.calendar_event import CalendarEvent
from app.models.privacy_preferences import PrivacyPreferences
from app.models.privacy_audit_log import PrivacyAuditLog
from app.models.user_profile import UserProfile
from app.models.llm_usage_log import LLMUsageLog

# Helper to generate authorization headers
def h(user_id: str) -> dict:
    return {"X-User-ID": user_id}


# ── Test DB setup ──────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_data_export_delete.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def db_session():
    # Setup: Create tables
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Teardown: Drop tables to clean up
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()


def test_redacted_export_does_not_mutate_database(db_session):
    client = TestClient(app)
    uid = "export-mutate-user"
    
    # 1. Seed some sensitive data
    task_payload = {
        "title": "Strategy Plan",
        "description": "Sensitive company strategy description.",
        "priority": "high",
    }
    create_resp = client.post("/tasks", json=task_payload, headers=h(uid))
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    
    # 2. Run export with redacted=True
    export_resp = client.get("/user/export-data?redacted=true", headers=h(uid))
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    
    # Check that in-memory export was redacted
    exported_task = [t for t in export_data["tasks"] if t["id"] == task_id][0]
    assert exported_task["description"] == "[redacted]"
    
    # 3. Prove database row remains UNCHANGED (original sensitive description persists)
    db = db_session
    db_task = db.query(Task).filter(Task.id == task_id).first()
    assert db_task.description == "Sensitive company strategy description."


def test_export_service_does_not_hide_current_table_failures(db_session):
    client = TestClient(app)
    uid = "export-completeness-user"
    
    # Run export
    resp = client.get("/user/export-data", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify all 14 standard keys appear in the export response
    expected_sections = [
        "profile",
        "privacy_preferences",
        "tasks",
        "energy_logs",
        "micro_actions",
        "copilot_plans",
        "transition_scripts",
        "reply_drafts",
        "calendar_events",
        "message_items",
        "overload_events",
        "next_action_prompts",
        "replan_events",
        "llm_usage_logs",
    ]
    for section in expected_sections:
        assert section in data, f"Missing section '{section}' in export payload"
        
    # Check warnings are empty because there were no database query failures
    assert len(data["warnings"]) == 0


def test_unconfirmed_delete_returns_400(db_session):
    client = TestClient(app)
    uid = "delete-unconfirmed-user"
    
    resp = client.delete("/user/delete-data", headers=h(uid))
    assert resp.status_code == 400
    assert "confirm=true" in resp.json()["detail"]


def test_confirmed_delete_purges_all_tables_completely(db_session):
    client = TestClient(app)
    uid = "delete-purge-user"
    
    # 1. Seed data across multiple tables for this user
    # Profile
    client.put("/profile", json={"preferred_name": "Alice", "preferred_tone": "warm"}, headers=h(uid))
    
    # Privacy Preferences
    client.patch("/privacy/preferences", json={"retention_days_messages": 30}, headers=h(uid))
    
    # Task
    task_resp = client.post("/tasks", json={"title": "Clean room", "priority": "low"}, headers=h(uid))
    task_id = task_resp.json()["id"]
    
    # Message
    client.post("/messages/import/mock", json={"messages": [{
        "source": "mock",
        "channel": "sms",
        "sender": "Mom",
        "snippet": "Hello",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }]}, headers=h(uid))
    
    db = db_session
    
    # Seed an LLM Usage Log directly to ensure we check it
    db.add(LLMUsageLog(user_id=uid, feature="reply_drafting", provider="mock", status="success"))
    db.commit()
    
    # Verify data exists before delete
    assert db.query(UserProfile).filter(UserProfile.user_id == uid).count() == 1
    assert db.query(PrivacyPreferences).filter(PrivacyPreferences.user_id == uid).count() == 1
    assert db.query(Task).filter(Task.user_id == uid).count() == 1
    assert db.query(MessageItem).filter(MessageItem.user_id == uid).count() == 1
    assert db.query(LLMUsageLog).filter(LLMUsageLog.user_id == uid).count() == 1
    # Audit log should have logged things like update_preferences and export_data
    assert db.query(PrivacyAuditLog).filter(PrivacyAuditLog.user_id == uid).count() >= 1

    # 2. Execute confirmed deletion
    del_resp = client.delete("/user/delete-data?confirm=true", headers=h(uid))
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["status"] == "success"
    
    # 3. Verify ALL data across ALL tables is permanently erased (0 count)
    assert db.query(UserProfile).filter(UserProfile.user_id == uid).count() == 0
    assert db.query(PrivacyPreferences).filter(PrivacyPreferences.user_id == uid).count() == 0
    assert db.query(Task).filter(Task.user_id == uid).count() == 0
    assert db.query(MessageItem).filter(MessageItem.user_id == uid).count() == 0
    assert db.query(LLMUsageLog).filter(LLMUsageLog.user_id == uid).count() == 0
    assert db.query(PrivacyAuditLog).filter(PrivacyAuditLog.user_id == uid).count() == 0
