"""
Tests for Execution Automation Dashboard upgrades.
Execution Automation Pack Part Q.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

TEST_DB_URL = "sqlite:///./test_execution_automation_dashboard.db"
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


def h(uid: str = "dash-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


def test_dashboard_includes_message_summary():
    """25. test_dashboard_includes_message_summary"""
    uid = "dash-user-msg"
    # Import a message
    msg_payload = {
        "messages": [
            {
                "external_message_id": "msg_dash_1",
                "source": "mock",
                "sender": "Alice",
                "subject": "Hello",
                "snippet": "Just saying hello",
                "is_read": False
            }
        ]
    }
    client.post("/messages/import/mock", json=msg_payload, headers=h(uid))

    response = client.get("/copilot/dashboard", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["message_summary"] is not None
    assert data["message_summary"]["total_count"] == 1
    assert data["needs_reply_count"] == 0
    assert data["urgent_messages_count"] == 0


def test_dashboard_includes_next_action_prompt():
    """26. test_dashboard_includes_next_action_prompt"""
    uid = "dash-user-nap"
    # Ensure a next action is computed
    client.get("/copilot/next-action", headers=h(uid))

    response = client.get("/copilot/dashboard", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["next_action_prompt"] is not None
    assert data["next_action_prompt"]["action_type"] == "log_energy"


def test_dashboard_includes_replan_count():
    """27. test_dashboard_includes_replan_count"""
    uid = "dash-user-replan"
    # Trigger replan
    client.post("/copilot/replan", json={"trigger_type": "manual"}, headers=h(uid))

    response = client.get("/copilot/dashboard", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["recent_replan_events_count"] == 1


def test_dashboard_safe_if_message_service_fails():
    """28. test_dashboard_safe_if_message_service_fails"""
    uid = "dash-user-safe"
    
    # Mock message_repository list_recent to raise Exception
    with patch("app.repositories.message_repository.message_repository.list_recent", side_effect=Exception("Database down")):
        response = client.get("/copilot/dashboard", headers=h(uid))
        assert response.status_code == 200
        data = response.json()
        # Should be None or defaults instead of failing
        assert data["message_summary"] is None
        assert data["urgent_messages_count"] == 0
        assert data["needs_reply_count"] == 0
