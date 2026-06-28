"""Tests for Granular Privacy and Data Controls."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.privacy_preferences import PrivacyPreferences
from app.models.privacy_audit_log import PrivacyAuditLog
from app.models.message_item import MessageItem
from app.models.calendar_event import CalendarEvent
from app.models.reply_draft import ReplyDraft
from app.models.task import Task
from app.models.llm_usage_log import LLMUsageLog

# Helper to generate authorization headers (Developer bypass / X-User-ID bypass)
def h(user_id: str) -> dict:
    return {"X-User-ID": user_id}


# ── Test DB setup ──────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_privacy_controls.db"

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


# ──────────────────────────────────────────────
# 1. Privacy Preferences & Audit Log Tests
# ──────────────────────────────────────────────

def test_get_preferences_initializes_default(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-1"
    
    resp = client.get("/privacy/preferences", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == uid
    assert data["store_reply_original_messages"] is True
    assert data["store_message_snippets"] is True
    assert data["store_calendar_titles"] is True
    assert data["store_task_descriptions"] is True
    assert data["retention_days_reply_drafts"] is None


def test_update_preferences_and_audit_log(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-2"
    
    # Initialize defaults
    client.get("/privacy/preferences", headers=h(uid))
    
    # Update preferences
    payload = {
        "store_message_snippets": False,
        "store_calendar_titles": False,
        "retention_days_reply_drafts": 45,
    }
    update_resp = client.patch("/privacy/preferences", json=payload, headers=h(uid))
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["store_message_snippets"] is False
    assert updated_data["store_calendar_titles"] is False
    assert updated_data["retention_days_reply_drafts"] == 45
    
    # Verify audit log was created
    audit_resp = client.get("/privacy/audit-log", headers=h(uid))
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    
    # The latest log should be update_preferences
    latest_log = logs[0]
    assert latest_log["action_type"] == "update_preferences"
    assert latest_log["user_id"] == uid
    assert "updated_fields" in latest_log["extra_metadata"]
    assert "store_message_snippets" in latest_log["extra_metadata"]["updated_fields"]
    assert "store_calendar_titles" in latest_log["extra_metadata"]["updated_fields"]


def test_retention_days_validation_ranges(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-3"
    
    # Valid values
    for val in [1, 30, 3650, None]:
        payload = {"retention_days_reply_drafts": val}
        resp = client.patch("/privacy/preferences", json=payload, headers=h(uid))
        assert resp.status_code == 200
        
    # Invalid values
    for val in [-5, 0, 3651]:
        payload = {"retention_days_reply_drafts": val}
        resp = client.patch("/privacy/preferences", json=payload, headers=h(uid))
        assert resp.status_code == 422  # Pydantic validation error


# ──────────────────────────────────────────────
# 2. Enforced Privacy Controls on Import & Creation
# ──────────────────────────────────────────────

def test_enforced_message_snippets_privacy(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-4"
    
    # Set preference store_message_snippets=False
    client.patch("/privacy/preferences", json={"store_message_snippets": False}, headers=h(uid))
    
    # Import a message
    msg_payload = {
        "messages": [
            {
                "source": "mock",
                "external_message_id": "msg-111",
                "channel": "email",
                "sender": "boss@work.com",
                "subject": "Status report",
                "snippet": "Here is the highly sensitive corporate strategy snippet that shouldn't be saved.",
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    resp = client.post("/messages/import/mock", json=msg_payload, headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["messages"]) == 1
    # Snippet must be None (enforced)
    assert data["messages"][0]["snippet"] is None


def test_enforced_calendar_titles_privacy(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-5"
    
    # Set preference store_calendar_titles=False
    client.patch("/privacy/preferences", json={"store_calendar_titles": False}, headers=h(uid))
    
    # Import calendar event
    cal_payload = {
        "events": [
            {
                "provider": "mock",
                "external_event_id": "cal-222",
                "title": "Discuss firing Alice and restructuring",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            }
        ]
    }
    resp = client.post("/calendar/import/mock", json=cal_payload, headers=h(uid))
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["events"]) == 1
    # Title must be redacted placeholder
    assert data["events"][0]["title"] == "[redacted]"


def test_enforced_reply_original_messages_privacy(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-6"
    
    # Set preference store_reply_original_messages=False
    client.patch("/privacy/preferences", json={"store_reply_original_messages": False}, headers=h(uid))
    
    # Create reply draft
    draft_payload = {
        "original_message": "Can we meet tomorrow at 10 AM to discuss the private financial leak?",
        "message_sender": "investor@venture.com",
        "message_subject": "Meeting",
        "message_channel": "email",
        "user_intent": "Accept the meeting",
    }
    resp = client.post("/reply/draft", json=draft_payload, headers=h(uid))
    assert resp.status_code == 201
    data = resp.json()
    # original_message must be redacted
    assert data["original_message"] == "[redacted]"


def test_enforced_task_descriptions_privacy(db_session):
    client = TestClient(app)
    uid = "test-privacy-user-7"
    
    # Set preference store_task_descriptions=False
    client.patch("/privacy/preferences", json={"store_task_descriptions": False}, headers=h(uid))
    
    # Create task
    task_payload = {
        "title": "Secret Project Launch",
        "description": "This is a super secret launch description that must not be stored.",
        "priority": "high",
    }
    create_resp = client.post("/tasks", json=task_payload, headers=h(uid))
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    assert task_data["description"] is None
    
    # Re-enable description storage
    client.patch("/privacy/preferences", json={"store_task_descriptions": True}, headers=h(uid))
    
    # Create task with description
    task_payload2 = {
        "title": "Another Project",
        "description": "We can store this one.",
        "priority": "low",
    }
    create_resp2 = client.post("/tasks", json=task_payload2, headers=h(uid))
    assert create_resp2.status_code == 201
    task_id2 = create_resp2.json()["id"]
    assert create_resp2.json()["description"] == "We can store this one."
    
    # Re-disable description storage and update task description
    client.patch("/privacy/preferences", json={"store_task_descriptions": False}, headers=h(uid))
    
    # Update task (attempt to modify description)
    update_payload = {"description": "Try to change this."}
    update_resp = client.patch(f"/tasks/{task_id2}", json=update_payload, headers=h(uid))
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] is None


# ──────────────────────────────────────────────
# 3. Targeted Redaction (In-Place Purge) Tests
# ──────────────────────────────────────────────

def test_targeted_redactions_and_ownership(db_session):
    client = TestClient(app)
    uid = "owner-user"
    stranger = "stranger-user"
    
    # 1. Create a reply draft for owner
    draft_resp = client.post("/reply/draft", json={
        "original_message": "Sensitive raw message details.",
        "message_sender": "bob@abc.com",
        "message_channel": "email",
        "user_intent": "delay",
    }, headers=h(uid))
    assert draft_resp.status_code == 201
    draft_id = draft_resp.json()["id"]
    assert draft_resp.json()["original_message"] == "Sensitive raw message details."
    
    # 2. Create message, calendar event, task for owner
    msg_resp = client.post("/messages/import/mock", json={"messages": [{
        "source": "mock",
        "external_message_id": "ext-1",
        "channel": "email",
        "sender": "sender@sender.com",
        "subject": "Sensitive subject",
        "snippet": "Sensitive snippet contents.",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }]}, headers=h(uid))
    msg_id = msg_resp.json()["messages"][0]["id"]
    
    cal_resp = client.post("/calendar/import/mock", json={"events": [{
        "provider": "mock",
        "external_event_id": "cal-1",
        "title": "Secret meeting title",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }]}, headers=h(uid))
    cal_id = cal_resp.json()["events"][0]["id"]
    
    task_resp = client.post("/tasks", json={
        "title": "Confidential Task",
        "description": "Confidential description content.",
        "priority": "medium",
    }, headers=h(uid))
    task_id = task_resp.json()["id"]

    # --- Verify stranger cannot redact other user's records ---
    assert client.delete(f"/reply/drafts/{draft_id}/original-message", headers=h(stranger)).status_code == 404
    assert client.delete(f"/messages/{msg_id}/snippet", headers=h(stranger)).status_code == 404
    assert client.delete(f"/calendar/events/{cal_id}/title", headers=h(stranger)).status_code == 404
    assert client.delete(f"/tasks/{task_id}/description", headers=h(stranger)).status_code == 404

    # --- Perform successful targeted redactions by owner ---
    
    # Redact draft original_message
    redact_draft = client.delete(f"/reply/drafts/{draft_id}/original-message", headers=h(uid))
    assert redact_draft.status_code == 200
    assert redact_draft.json()["original_message"] == "[redacted]"
    
    # Redact message snippet
    redact_msg = client.delete(f"/messages/{msg_id}/snippet", headers=h(uid))
    assert redact_msg.status_code == 200
    assert redact_msg.json()["snippet"] is None
    
    # Redact calendar title
    redact_cal = client.delete(f"/calendar/events/{cal_id}/title", headers=h(uid))
    assert redact_cal.status_code == 200
    assert redact_cal.json()["title"] == "[redacted]"
    
    # Redact task description
    redact_task = client.delete(f"/tasks/{task_id}/description", headers=h(uid))
    assert redact_task.status_code == 200
    assert redact_task.json()["description"] is None

    # Verify audit logs track all 4 redactions
    audit_resp = client.get("/privacy/audit-log", headers=h(uid))
    logs = audit_resp.json()
    redact_logs = [l for l in logs if l["action_type"] == "redact_field"]
    assert len(redact_logs) == 4
    
    # Check details of logs
    fields_redacted = [l["extra_metadata"]["field"] for l in redact_logs]
    assert "original_message" in fields_redacted
    assert "snippet" in fields_redacted
    assert "title" in fields_redacted
    assert "description" in fields_redacted


# ──────────────────────────────────────────────
# 4. Manual Data Retention Pruning
# ──────────────────────────────────────────────

def test_data_retention_policy_execution(db_session):
    client = TestClient(app)
    uid = "retention-user"
    
    # Configure retention policies (e.g. 5 days for messages, 10 days for drafts)
    client.patch("/privacy/preferences", json={
        "retention_days_messages": 5,
        "retention_days_reply_drafts": 10,
    }, headers=h(uid))
    
    # Directly seed records in DB with specific dates
    db = db_session
    
    now = datetime.now(timezone.utc)
    
    # 1. Expired Message (6 days old)
    expired_msg = MessageItem(
        user_id=uid,
        source="mock",
        channel="email",
        subject="Expired Message",
        received_at=now - timedelta(days=6),
        created_at=now - timedelta(days=6),
    )
    # 2. Current Message (3 days old)
    current_msg = MessageItem(
        user_id=uid,
        source="mock",
        channel="email",
        subject="Current Message",
        received_at=now - timedelta(days=3),
        created_at=now - timedelta(days=3),
    )
    
    # 3. Expired Reply Draft (12 days old)
    expired_draft = ReplyDraft(
        user_id=uid,
        original_message="Old draft original",
        message_channel="email",
        draft_options=[],
        created_at=now - timedelta(days=12),
    )
    # 4. Current Reply Draft (8 days old)
    current_draft = ReplyDraft(
        user_id=uid,
        original_message="Current draft original",
        message_channel="email",
        draft_options=[],
        created_at=now - timedelta(days=8),
    )
    
    db.add_all([expired_msg, current_msg, expired_draft, current_draft])
    db.commit()
    
    # Execute manual retention policy
    ret_resp = client.post("/privacy/apply-retention", headers=h(uid))
    assert ret_resp.status_code == 200
    data = ret_resp.json()
    assert data["status"] == "success"
    assert data["pruned_counts"]["pruned_messages"] == 1
    assert data["pruned_counts"]["pruned_reply_drafts"] == 1
    
    # Verify DB state
    remaining_msgs = db.query(MessageItem).filter(MessageItem.user_id == uid).all()
    assert len(remaining_msgs) == 1
    assert remaining_msgs[0].subject == "Current Message"
    
    remaining_drafts = db.query(ReplyDraft).filter(ReplyDraft.user_id == uid).all()
    assert len(remaining_drafts) == 1
    assert remaining_drafts[0].original_message == "Current draft original"
    
    # Verify retention action logged in privacy audit log
    audit_resp = client.get("/privacy/audit-log", headers=h(uid))
    logs = audit_resp.json()
    apply_logs = [l for l in logs if l["action_type"] == "apply_retention"]
    assert len(apply_logs) == 1
    assert apply_logs[0]["extra_metadata"]["pruned_messages"] == 1
    assert apply_logs[0]["extra_metadata"]["pruned_reply_drafts"] == 1
