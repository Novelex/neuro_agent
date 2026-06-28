"""
Tests for Adaptive Replanner.
Execution Automation Pack Part Q.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.task import Task as TaskModel
from app.models.micro_action import MicroAction as MicroActionModel
from app.models.replan_event import ReplanEvent as ReplanEventModel

TEST_DB_URL = "sqlite:///./test_adaptive_replanner.db"
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


def h(uid: str = "replan-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


def test_replan_low_energy_creates_recovery_plan():
    """18. test_replan_low_energy_creates_recovery_plan"""
    uid = "replan-user-low-energy"
    
    # Setup some open high energy micro-actions
    db = TestingSessionLocal()
    try:
        t = TaskModel(id="t_low_en", user_id=uid, title="Coding Task", priority="high")
        db.add(t)
        ma1 = MicroActionModel(id="ma_le1", user_id=uid, task_id="t_low_en", title="Write compiler", energy_cost="high", status="open")
        ma2 = MicroActionModel(id="ma_le2", user_id=uid, task_id="t_low_en", title="Write docs", energy_cost="low", status="open")
        db.add_all([ma1, ma2])
        db.commit()
    finally:
        db.close()

    payload = {
        "trigger_type": "low_energy",
        "current_energy": 20,
        "sensory_state": "shutdown",
        "reason": "Burnt out",
        "preserve_completed": True,
        "defer_high_energy": True,
        "include_urgent_messages": True
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["mode_after"] == "recovery"
    assert data["deferred_actions_count"] >= 1
    assert len(data["recovery_blocks"]) >= 1
    assert "reduced" in data["summary"] or "recovery" in data["summary"].lower()


def test_replan_preserves_completed_actions():
    """19. test_replan_preserves_completed_actions"""
    uid = "replan-user-preserve"
    db = TestingSessionLocal()
    try:
        t = TaskModel(id="t_pres", user_id=uid, title="Task", priority="medium")
        db.add(t)
        ma1 = MicroActionModel(id="ma_p1", user_id=uid, task_id="t_pres", title="Done item", status="done")
        ma2 = MicroActionModel(id="ma_p2", user_id=uid, task_id="t_pres", title="Open item", status="open")
        db.add_all([ma1, ma2])
        db.commit()
    finally:
        db.close()

    payload = {
        "trigger_type": "manual",
        "current_energy": 70,
        "preserve_completed": True
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["actions_preserved_count"] == 1


def test_replan_defer_high_energy_actions():
    """20. test_replan_defer_high_energy_actions"""
    uid = "replan-user-defer-high"
    db = TestingSessionLocal()
    try:
        t = TaskModel(id="t_def", user_id=uid, title="Task", priority="medium")
        db.add(t)
        ma1 = MicroActionModel(id="ma_d1", user_id=uid, task_id="t_def", title="High cost", energy_cost="high", status="open")
        ma2 = MicroActionModel(id="ma_d2", user_id=uid, task_id="t_def", title="Low cost", energy_cost="low", status="open")
        db.add_all([ma1, ma2])
        db.commit()
    finally:
        db.close()

    payload = {
        "trigger_type": "low_energy",
        "current_energy": 25,
        "defer_high_energy": True
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["deferred_actions_count"] == 1
    # Low energy action should remain in selection or high energy gets deferred
    assert len(data["selected_actions"]) <= 1


def test_replan_urgent_message_adds_reply_action():
    """21. test_replan_urgent_message_adds_reply_action"""
    uid = "replan-user-urgent"
    # Import an urgent message
    msg_payload = {
        "messages": [
            {
                "external_message_id": "urgent_replan_msg",
                "source": "mock",
                "channel": "email",
                "sender": "Lead Dev",
                "subject": "Merge issue asap",
                "snippet": "Can you check the branch?",
                "is_read": False
            }
        ]
    }
    client.post("/messages/import/mock", json=msg_payload, headers=h(uid))

    payload = {
        "trigger_type": "urgent_message",
        "current_energy": 80,
        "include_urgent_messages": True
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["next_action"]["action_type"] == "draft_reply"


def test_replan_skipped_actions_simplifies_plan():
    """22. test_replan_skipped_actions_simplifies_plan"""
    uid = "replan-user-skipped"
    db = TestingSessionLocal()
    try:
        t = TaskModel(id="t_skip", user_id=uid, title="Task", priority="medium")
        db.add(t)
        # Create 3 skipped micro-actions, and 5 open micro-actions
        for i in range(3):
            db.add(MicroActionModel(id=f"ma_sk_{i}", user_id=uid, task_id="t_skip", title=f"Skipped {i}", status="skipped"))
        for i in range(5):
            db.add(MicroActionModel(id=f"ma_op_{i}", user_id=uid, task_id="t_skip", title=f"Open {i}", status="open"))
        db.commit()
    finally:
        db.close()

    payload = {
        "trigger_type": "skipped_actions",
        "current_energy": 80
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    # It should simplify the plan (select max 2 actions)
    assert len(data["selected_actions"]) == 2
    assert "simplified" in data["summary"].lower() or "reduced" in data["summary"].lower()


def test_replan_event_logged():
    """23. test_replan_event_logged"""
    uid = "replan-user-log"
    payload = {
        "trigger_type": "manual",
        "reason": "Just because"
    }
    response = client.post("/copilot/replan", json=payload, headers=h(uid))
    assert response.status_code == 200

    # Retrieve recent replan events
    events_resp = client.get("/copilot/replan/events", headers=h(uid))
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) >= 1
    assert events[0]["trigger_type"] == "manual"


def test_replan_user_scope():
    """24. test_replan_user_scope"""
    # User A trigger replan
    client.post("/copilot/replan", json={"trigger_type": "manual"}, headers=h("user-a"))

    # User B get events should not see user A's event
    response_b = client.get("/copilot/replan/events", headers=h("user-b"))
    assert response_b.status_code == 200
    assert len(response_b.json()) == 0
