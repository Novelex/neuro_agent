"""
Tests for Next Action Prompter.
Execution Automation Pack Part Q.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.task import Task as TaskModel
from app.models.micro_action import MicroAction as MicroActionModel
from app.models.copilot_plan import CopilotPlan
from app.models.next_action_prompt import NextActionPrompt

TEST_DB_URL = "sqlite:///./test_next_action_prompter.db"
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


def h(uid: str = "nap-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


def test_next_action_log_energy_when_energy_missing():
    """8. test_next_action_log_energy_when_energy_missing"""
    uid = "nap-user-missing-energy"
    response = client.get("/copilot/next-action", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"]["action_type"] == "log_energy"
    assert data["prompt"]["source_type"] == "system"


def test_next_action_recovery_when_risk_high():
    """9. test_next_action_recovery_when_risk_high"""
    uid = "nap-user-high-risk"
    # Log low energy (battery_level = 20) -> recovery mode
    client.post(
        "/energy/log",
        json={"battery_level": 20, "sensory_state": "shutdown"},
        headers=h(uid)
    )
    response = client.get("/copilot/next-action", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"]["action_type"] == "take_recovery_break"
    assert data["prompt"]["source_type"] == "recovery"


def test_next_action_planned_micro_action_priority():
    """10. test_next_action_planned_micro_action_priority"""
    uid = "nap-user-planned-ma"
    # Log high energy
    client.post(
        "/energy/log",
        json={"battery_level": 80, "sensory_state": "calm"},
        headers=h(uid)
    )
    # Create task
    t_resp = client.post("/tasks", json={"title": "Planned task", "priority": "high"}, headers=h(uid))
    assert t_resp.status_code == 201
    task_id = t_resp.json()["id"]

    # Decompose
    client.post(f"/tasks/{task_id}/decompose", json={}, headers=h(uid))

    # Generate plan
    today_str = datetime.now().date().isoformat()
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={"plan_date": today_str, "available_minutes": 60, "force_regenerate": True},
        headers=h(uid)
    )
    assert plan_resp.status_code == 200

    response = client.get("/copilot/next-action", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"]["action_type"] == "do_micro_action"
    assert data["prompt"]["source_type"] == "micro_action"


def test_next_action_urgent_message_priority():
    """11. test_next_action_urgent_message_priority"""
    uid = "nap-user-urgent-msg"
    # Log high energy
    client.post(
        "/energy/log",
        json={"battery_level": 80, "sensory_state": "calm"},
        headers=h(uid)
    )
    # Import urgent message
    msg_payload = {
        "messages": [
            {
                "external_message_id": "urgent_nap_msg",
                "source": "mock",
                "channel": "email",
                "sender": "Boss",
                "subject": "URGENT review needed ASAP",
                "snippet": "Can you check this immediately?",
                "is_read": False
            }
        ]
    }
    client.post("/messages/import/mock", json=msg_payload, headers=h(uid))

    response = client.get("/copilot/next-action", headers=h(uid))
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"]["action_type"] == "draft_reply"
    assert data["prompt"]["source_type"] == "message"


def test_next_action_snooze():
    """12. test_next_action_snooze"""
    uid = "nap-user-snooze"
    response = client.get("/copilot/next-action", headers=h(uid))
    prompt_id = response.json()["prompt"]["id"]

    # Snooze for 30 minutes
    snooze_resp = client.post(f"/copilot/next-action/{prompt_id}/snooze", json={"minutes": 30}, headers=h(uid))
    assert snooze_resp.status_code == 200
    assert snooze_resp.json()["status"] == "snoozed"
    assert snooze_resp.json()["snoozed_until"] is not None


def test_next_action_skip():
    """13. test_next_action_skip"""
    uid = "nap-user-skip"
    response = client.get("/copilot/next-action", headers=h(uid))
    prompt_id = response.json()["prompt"]["id"]

    skip_resp = client.post(f"/copilot/next-action/{prompt_id}/skip", headers=h(uid))
    assert skip_resp.status_code == 200
    assert skip_resp.json()["status"] == "skipped"


def test_next_action_defer():
    """14. test_next_action_defer"""
    uid = "nap-user-defer"
    response = client.get("/copilot/next-action", headers=h(uid))
    prompt_id = response.json()["prompt"]["id"]

    defer_until = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    defer_resp = client.post(
        f"/copilot/next-action/{prompt_id}/defer",
        json={"defer_until": defer_until},
        headers=h(uid)
    )
    assert defer_resp.status_code == 200
    assert defer_resp.json()["status"] == "deferred"


def test_next_action_done_updates_micro_action():
    """15. test_next_action_done_updates_micro_action"""
    uid = "nap-user-done-ma"
    db = TestingSessionLocal()
    try:
        # Create a task and a micro-action
        t = TaskModel(id="task-done-ma", user_id=uid, title="Done Test Task", priority="medium")
        db.add(t)
        ma = MicroActionModel(
            id="ma-done-test",
            user_id=uid,
            task_id="task-done-ma",
            title="Action to done",
            status="open"
        )
        db.add(ma)
        db.commit()
    finally:
        db.close()

    # Create active prompt manually for this micro-action
    p_data = {
        "source_type": "micro_action",
        "source_id": "ma-done-test",
        "action_type": "do_micro_action",
        "title": "Action to done",
        "message": "Start now.",
        "status": "active"
    }
    db = TestingSessionLocal()
    try:
        p = NextActionPrompt(user_id=uid, **p_data)
        db.add(p)
        db.commit()
        prompt_id = p.id
    finally:
        db.close()

    # Mark done
    done_resp = client.post(f"/copilot/next-action/{prompt_id}/done", headers=h(uid))
    assert done_resp.status_code == 200
    assert done_resp.json()["status"] == "done"

    # Verify micro-action in database is now done
    db = TestingSessionLocal()
    try:
        retrieved_ma = db.query(MicroActionModel).filter_by(id="ma-done-test").first()
        assert retrieved_ma.status == "done"
    finally:
        db.close()


def test_next_action_does_not_duplicate_active_prompt():
    """16. test_next_action_does_not_duplicate_active_prompt"""
    uid = "nap-user-no-dup"
    # Call next-action twice
    resp1 = client.get("/copilot/next-action", headers=h(uid))
    resp2 = client.get("/copilot/next-action", headers=h(uid))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["prompt"]["id"] == resp2.json()["prompt"]["id"]


def test_next_action_respects_snoozed_until():
    """17. test_next_action_respects_snoozed_until"""
    uid = "nap-user-respect-snooze"
    # Initial get
    resp1 = client.get("/copilot/next-action", headers=h(uid))
    prompt_id = resp1.json()["prompt"]["id"]

    # Snooze it
    client.post(f"/copilot/next-action/{prompt_id}/snooze", json={"minutes": 10}, headers=h(uid))

    # Getting next-action again within 10 minutes should fallback or return something else, 
    # not the snoozed active prompt.
    resp2 = client.get("/copilot/next-action", headers=h(uid))
    assert resp2.status_code == 200
    # Because there are no energy logs for this user, it should still be log_energy but as a NEW prompt,
    # or a different prompt type. Actually, get_or_create_next_action has logic:
    # "If the existing active prompt is snoozed and snoozed_until is in future, skip it and choose another."
    # Since log_energy is system/None, let's see. It will create a fallback review_plan or another system prompt.
    assert resp2.json()["prompt"]["id"] != prompt_id
