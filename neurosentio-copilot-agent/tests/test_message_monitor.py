"""
Tests for Message Monitor.
Execution Automation Pack Part Q.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.message_item import MessageItem

TEST_DB_URL = "sqlite:///./test_message_monitor.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app)


def h(uid: str = "test-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


def test_mock_message_import_creates_metadata_only():
    """1. test_mock_message_import_creates_metadata_only"""
    payload = {
        "messages": [
            {
                "external_message_id": "msg_1",
                "source": "mock",
                "channel": "email",
                "sender": "Sarah",
                "subject": "Updated report needed today",
                "snippet": "Can you send the updated report by EOD?",
                "received_at": "2026-05-21T10:00:00",
                "is_read": False,
                "metadata": {"some_field": "val"}
            }
        ]
    }
    response = client.post("/messages/import/mock", json=payload, headers=h())
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1
    assert data["updated_count"] == 0
    assert len(data["messages"]) == 1
    msg = data["messages"][0]
    assert msg["external_message_id"] == "msg_1"
    assert msg["sender"] == "Sarah"
    assert msg["subject"] == "Updated report needed today"
    assert msg["snippet"] == "Can you send the updated report by EOD?"
    assert msg["user_id"] == "test-user"


def test_message_privacy_strips_body():
    """2. test_message_privacy_strips_body"""
    payload = {
        "messages": [
            {
                "external_message_id": "msg_privacy_1",
                "source": "mock",
                "channel": "email",
                "sender": "Sarah",
                "subject": "Confidential",
                "snippet": "Let's meet tomorrow.",
                "received_at": "2026-05-21T10:00:00",
                "is_read": False,
                "metadata": {
                    "body": "This is a super long confidential message body that we do not store.",
                    "full_body": "This is the full body",
                    "html": "<p>confidential</p>",
                    "text": "confidential text",
                    "raw": "confidential raw bytes",
                    "attachments": ["attachment_1.pdf"],
                    "auth_tokens": "token123",
                    "access_token": "acc123",
                    "refresh_token": "ref123",
                    "safe_field": "keep_me"
                }
            }
        ]
    }
    response = client.post("/messages/import/mock", json=payload, headers=h())
    assert response.status_code == 200
    data = response.json()
    msg = data["messages"][0]
    meta = msg["metadata"]
    assert "safe_field" in meta
    assert meta["safe_field"] == "keep_me"

    # Verify that stripping worked
    for forbidden in ["body", "full_body", "html", "text", "raw", "attachments", "auth_tokens", "access_token", "refresh_token"]:
        assert forbidden not in meta


def test_message_urgency_detection():
    """3. test_message_urgency_detection"""
    payload = {
        "messages": [
            {
                "external_message_id": "msg_urgent_1",
                "source": "mock",
                "channel": "email",
                "sender": "Manager",
                "subject": "Urgent deadline asap",
                "snippet": "Immediately submit report before EOD.",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "is_read": False,
            },
            {
                "external_message_id": "msg_fyi_1",
                "source": "mock",
                "channel": "email",
                "sender": "Colleague",
                "subject": "FYI reading",
                "snippet": "Just some casual reading for next week.",
                "received_at": "2026-05-10T10:00:00",
                "is_read": True,
            }
        ]
    }
    response = client.post("/messages/import/mock", json=payload, headers=h())
    assert response.status_code == 200
    msgs = response.json()["messages"]
    
    # Sort by external ID
    msgs_by_ext = {m["external_message_id"]: m for m in msgs}
    
    assert msgs_by_ext["msg_urgent_1"]["urgency_score"] > msgs_by_ext["msg_fyi_1"]["urgency_score"]
    assert msgs_by_ext["msg_urgent_1"]["urgency_score"] >= 40


def test_message_needs_reply_detection():
    """4. test_message_needs_reply_detection"""
    payload = {
        "messages": [
            {
                "external_message_id": "msg_question",
                "source": "mock",
                "subject": "Can you review?",
                "snippet": "Are you able to look at this today?",
                "is_read": False,
            },
            {
                "external_message_id": "msg_fyi_2",
                "source": "mock",
                "subject": "Casual info",
                "snippet": "Just FYI, no need to reply.",
                "is_read": True,
            }
        ]
    }
    response = client.post("/messages/import/mock", json=payload, headers=h())
    assert response.status_code == 200
    msgs = response.json()["messages"]
    
    msgs_by_ext = {m["external_message_id"]: m for m in msgs}
    assert msgs_by_ext["msg_question"]["needs_reply"] is True
    assert msgs_by_ext["msg_fyi_2"]["needs_reply"] is False


def test_message_user_scope():
    """5. test_message_user_scope"""
    # Import for user A
    payload_a = {
        "messages": [
            {
                "external_message_id": "msg_user_a",
                "source": "mock",
                "subject": "For user A",
                "snippet": "Secret message for A.",
            }
        ]
    }
    response_a = client.post("/messages/import/mock", json=payload_a, headers=h("user-a"))
    assert response_a.status_code == 200

    # User B list messages should not see it
    response_b_list = client.get("/messages", headers=h("user-b"))
    assert response_b_list.status_code == 200
    assert len(response_b_list.json()) == 0

    # User B summary should not count it
    response_b_sum = client.get("/messages/summary", headers=h("user-b"))
    assert response_b_sum.status_code == 200
    assert response_b_sum.json()["total_count"] == 0


def test_message_summary():
    """6. test_message_summary"""
    # Import some messages for a fresh user
    uid = "summary-user"
    payload = {
        "messages": [
            {
                "external_message_id": "msg_s1",
                "source": "mock",
                "subject": "Urgent review ASAP",
                "snippet": "Deadline is EOD, please sync.",
                "is_read": False,
            },
            {
                "external_message_id": "msg_s2",
                "source": "mock",
                "subject": "Lunch?",
                "snippet": "Are you free today?",
                "is_read": False,
            },
            {
                "external_message_id": "msg_s3",
                "source": "mock",
                "subject": "FYI reading",
                "snippet": "Just regular newsletter.",
                "is_read": True,
            }
        ]
    }
    client.post("/messages/import/mock", json=payload, headers=h(uid))
    
    response = client.get("/messages/summary", headers=h(uid))
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_count"] >= 3
    assert summary["unread_count"] >= 2
    assert summary["needs_reply_count"] >= 2
    assert len(summary["top_urgent_messages"]) > 0
    assert "drafting" in summary["recommendation"] or "reply" in summary["recommendation"]


def test_message_draft_reply_links_reply_draft():
    """7. test_message_draft_reply_links_reply_draft"""
    uid = "draft-link-user"
    payload = {
        "messages": [
            {
                "external_message_id": "msg_d1",
                "source": "mock",
                "subject": "Let's review the mock draft",
                "snippet": "Can you let me know if this works?",
                "is_read": False,
            }
        ]
    }
    import_resp = client.post("/messages/import/mock", json=payload, headers=h(uid))
    assert import_resp.status_code == 200
    msg = import_resp.json()["messages"][0]
    message_id = msg["id"]

    draft_payload = {
        "message_id": message_id,
        "user_intent": "Accept invitation",
        "preferred_tone": "Warm",
        "current_energy": 70,
    }
    draft_resp = client.post(f"/messages/{message_id}/draft-reply", json=draft_payload, headers=h(uid))
    assert draft_resp.status_code == 201
    draft_data = draft_resp.json()
    assert draft_data["id"] is not None

    # Retrieve message again to verify linked_reply_draft_id is stored
    get_msgs_resp = client.get("/messages", headers=h(uid))
    assert get_msgs_resp.status_code == 200
    retrieved_msg = [m for m in get_msgs_resp.json() if m["id"] == message_id][0]
    assert retrieved_msg["linked_reply_draft_id"] == draft_data["id"]
