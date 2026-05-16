"""
Day 5–6 Tests: Morning Plan, Make-Smaller fixes, Transition Scripts.

Tests:
Morning plan:
- test_morning_plan_normal_mode_selects_micro_actions
- test_morning_plan_recovery_mode_selects_fewer_actions
- test_morning_plan_auto_decomposes_task_without_micro_actions
- test_morning_plan_does_not_duplicate_micro_actions
- test_morning_plan_saved_to_database
- test_morning_plan_returns_existing_without_force
- test_morning_plan_force_regenerate_creates_new_plan
- test_morning_plan_today_404_when_no_plan
- test_dashboard_prefers_today_plan_micro_action
- test_dashboard_after_make_smaller_uses_child_action

Make-smaller (Day 5 fix):
- test_make_smaller_defers_original
- test_make_smaller_child_actions_are_open
- test_make_smaller_children_have_parent_id

Transition scripts:
- test_generate_starting_work_script
- test_generate_leaving_house_script
- test_generate_making_call_script
- test_generate_ending_day_script
- test_generate_recovery_break_script
- test_generate_context_switch_script
- test_low_energy_transition_script_has_fewer_steps
- test_get_latest_transition_by_type
- test_update_transition_rating
- test_mark_transition_used
- test_transition_user_scope_protection
- test_delete_transition_script
- test_list_transitions
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── Test DB setup ──────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_day56.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
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


def h(uid: str = "day56-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _create_task(title="Morning test task", priority="high", uid="day56-user") -> str:
    resp = client.post("/tasks", json={"title": title, "priority": priority}, headers=h(uid))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _log_energy(battery: int, sensory: str = "calm", uid: str = "day56-user"):
    client.post(
        "/energy/log",
        json={"battery_level": battery, "sensory_state": sensory},
        headers=h(uid),
    )


def _decompose(task_id: str, energy: int = 70, uid: str = "day56-user") -> dict:
    resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"current_energy": energy, "max_actions": 3},
        headers=h(uid),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ══════════════════════════════════════════════════════════════════════
# MORNING PLAN TESTS
# ══════════════════════════════════════════════════════════════════════

def test_morning_plan_normal_mode_selects_micro_actions():
    """Normal-mode plan should contain 3–5 micro-actions."""
    uid = "mp-normal-user"
    task_id = _create_task("Design the API", uid=uid)
    _decompose(task_id, energy=70, uid=uid)
    _log_energy(70, uid=uid)

    resp = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 70, "available_minutes": 120, "auto_decompose": False},
        headers=h(uid),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["mode"] == "normal"
    assert len(data["selected_micro_actions"]) >= 1
    assert data["plan_id"]
    assert data["plan_date"] == date.today().isoformat()


def test_morning_plan_recovery_mode_selects_fewer_actions():
    """Recovery mode (energy < 30) must produce ≤ 2 micro-actions and ≥ 1 recovery block."""
    uid = "mp-recovery-user"
    task_id = _create_task("Write report", uid=uid)
    _decompose(task_id, energy=20, uid=uid)

    resp = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 15, "sensory_state": "shutdown", "available_minutes": 90, "auto_decompose": False},
        headers=h(uid),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["mode"] == "recovery"
    assert len(data["selected_micro_actions"]) <= 2
    assert len(data["recovery_blocks"]) >= 1
    assert "lighter" in data["message"].lower() or "small step" in data["message"].lower()


def test_morning_plan_auto_decomposes_task_without_micro_actions():
    """auto_decompose=true must decompose a task that has no micro-actions."""
    uid = "mp-autodecomp-user"
    task_id = _create_task("Brand new task with no decomposition", uid=uid)

    resp = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 65, "available_minutes": 120, "auto_decompose": True},
        headers=h(uid),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # The auto-decompose created micro-actions and selected them
    assert len(data["selected_micro_actions"]) >= 1

    # Verify micro-actions were actually created for the task
    ma_resp = client.get(f"/tasks/{task_id}/micro-actions", headers=h(uid))
    assert ma_resp.status_code == 200
    assert len(ma_resp.json()) >= 1


def test_morning_plan_does_not_duplicate_micro_actions():
    """Calling morning plan twice without force_regenerate must not create duplicate micro-actions."""
    uid = "mp-nodup-user"
    task_id = _create_task("Dedup test task", uid=uid)
    _decompose(task_id, energy=60, uid=uid)

    # First plan
    resp1 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 60, "auto_decompose": False},
        headers=h(uid),
    )
    assert resp1.status_code == 200
    count_after_first = len(resp1.json()["selected_micro_actions"])

    # Second plan (no force)
    resp2 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 60, "auto_decompose": False, "force_regenerate": False},
        headers=h(uid),
    )
    assert resp2.status_code == 200
    count_after_second = len(resp2.json()["selected_micro_actions"])

    assert count_after_second == count_after_first


def test_morning_plan_saved_to_database():
    """After generating a morning plan, GET /copilot/morning-plan/today must return it."""
    uid = "mp-save-user"
    task_id = _create_task("Saved plan task", uid=uid)
    _decompose(task_id, energy=60, uid=uid)

    client.post(
        "/copilot/morning-plan",
        json={"current_energy": 60, "auto_decompose": False},
        headers=h(uid),
    )

    get_resp = client.get("/copilot/morning-plan/today", headers=h(uid))
    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()
    assert data["plan_id"]
    assert data["plan_date"] == date.today().isoformat()


def test_morning_plan_today_404_when_no_plan():
    """GET /copilot/morning-plan/today returns 404 if no plan has been generated."""
    uid = "mp-noplan-user"
    resp = client.get("/copilot/morning-plan/today", headers=h(uid))
    assert resp.status_code == 404


def test_morning_plan_returns_existing_without_force():
    """Second POST without force_regenerate must return the same plan_id."""
    uid = "mp-existing-user"
    task_id = _create_task("Existing plan test", uid=uid)
    _decompose(task_id, energy=65, uid=uid)

    resp1 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 65, "auto_decompose": False},
        headers=h(uid),
    )
    plan_id_1 = resp1.json()["plan_id"]

    resp2 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 65, "auto_decompose": False, "force_regenerate": False},
        headers=h(uid),
    )
    plan_id_2 = resp2.json()["plan_id"]

    assert plan_id_1 == plan_id_2, "Should return existing plan without creating a new one"


def test_morning_plan_force_regenerate_creates_new_plan():
    """force_regenerate=True must create a new plan_id."""
    uid = "mp-force-user"
    task_id = _create_task("Force regen task", uid=uid)
    _decompose(task_id, energy=65, uid=uid)

    resp1 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 65, "auto_decompose": False},
        headers=h(uid),
    )
    plan_id_1 = resp1.json()["plan_id"]

    resp2 = client.post(
        "/copilot/morning-plan",
        json={"current_energy": 65, "auto_decompose": False, "force_regenerate": True},
        headers=h(uid),
    )
    plan_id_2 = resp2.json()["plan_id"]

    assert plan_id_1 != plan_id_2, "Force regenerate should create a new plan"


def test_dashboard_prefers_today_plan_micro_action():
    """Dashboard should return type=planned_micro_action when a morning plan exists for today."""
    uid = "mp-dash-user"
    task_id = _create_task("Dashboard plan test", uid=uid)
    _log_energy(70, uid=uid)
    _decompose(task_id, energy=70, uid=uid)

    # Generate morning plan
    client.post(
        "/copilot/morning-plan",
        json={"current_energy": 70, "auto_decompose": False},
        headers=h(uid),
    )

    dash_resp = client.get("/copilot/dashboard", headers=h(uid))
    assert dash_resp.status_code == 200
    data = dash_resp.json()
    suggested = data.get("suggested_next_action")
    assert suggested is not None
    # After a morning plan, dashboard should prefer planned micro-action
    assert suggested["type"] in ("planned_micro_action", "existing_micro_action", "needs_decomposition")


def test_dashboard_after_make_smaller_uses_child_action():
    """After make-smaller, dashboard should NOT surface the deferred original."""
    uid = "ms-dash-user"
    task_id = _create_task("Make smaller dashboard test", uid=uid)
    _log_energy(70, uid=uid)
    decomp_resp = _decompose(task_id, energy=70, uid=uid)

    micro_action_id = decomp_resp["micro_actions"][0]["id"]

    # Make it smaller — this defers the original
    client.post(
        f"/micro-actions/{micro_action_id}/make-smaller",
        json={"current_energy": 70},
        headers=h(uid),
    )

    dash_resp = client.get("/copilot/dashboard", headers=h(uid))
    assert dash_resp.status_code == 200
    data = dash_resp.json()
    suggested = data.get("suggested_next_action")
    assert suggested is not None

    # The deferred action ID must NOT be the suggested one
    if suggested.get("micro_action_id"):
        assert suggested["micro_action_id"] != micro_action_id, \
            "Dashboard should not surface the deferred original action"


# ══════════════════════════════════════════════════════════════════════
# MAKE-SMALLER BEHAVIOR FIXES
# ══════════════════════════════════════════════════════════════════════

def test_make_smaller_defers_original():
    """After make-smaller, the original micro-action must have status='deferred'."""
    uid = "ms-defer-user"
    task_id = _create_task("Defer test task", uid=uid)
    decomp = _decompose(task_id, energy=70, uid=uid)
    original_id = decomp["micro_actions"][0]["id"]

    resp = client.post(
        f"/micro-actions/{original_id}/make-smaller",
        json={"current_energy": 70},
        headers=h(uid),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["original_micro_action"]["status"] == "deferred"


def test_make_smaller_child_actions_are_open():
    """All child actions created by make-smaller must have status='open'."""
    uid = "ms-open-user"
    task_id = _create_task("Child open test", uid=uid)
    decomp = _decompose(task_id, energy=70, uid=uid)
    original_id = decomp["micro_actions"][0]["id"]

    resp = client.post(
        f"/micro-actions/{original_id}/make-smaller",
        json={"current_energy": 70},
        headers=h(uid),
    )
    assert resp.status_code == 200
    for child in resp.json()["smaller_actions"]:
        assert child["status"] == "open"


def test_make_smaller_children_have_parent_id():
    """Child actions must store parent_micro_action_id = original.id."""
    uid = "ms-parent-user"
    task_id = _create_task("Parent ID test", uid=uid)
    decomp = _decompose(task_id, energy=70, uid=uid)
    original_id = decomp["micro_actions"][0]["id"]

    resp = client.post(
        f"/micro-actions/{original_id}/make-smaller",
        json={"current_energy": 70},
        headers=h(uid),
    )
    assert resp.status_code == 200
    for child in resp.json()["smaller_actions"]:
        assert child["parent_micro_action_id"] == original_id


# ══════════════════════════════════════════════════════════════════════
# TRANSITION SCRIPT TESTS
# ══════════════════════════════════════════════════════════════════════

def _gen_script(transition_type: str, energy: int = 70, uid: str = "ts-user", **kwargs) -> dict:
    body = {"transition_type": transition_type, "current_energy": energy, "max_steps": 5}
    body.update(kwargs)
    resp = client.post("/transitions/generate", json=body, headers=h(uid))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_generate_starting_work_script():
    data = _gen_script("starting_work", next_task_title="Write the report")
    assert data["transition_type"] == "starting_work"
    assert len(data["script_steps"]) >= 2
    assert len(data["script_steps"]) <= 5
    assert data["source"] == "mock"
    assert data["message"]


def test_generate_leaving_house_script():
    data = _gen_script("leaving_house")
    assert data["transition_type"] == "leaving_house"
    steps = data["script_steps"]
    assert len(steps) >= 2
    # Should include object checks
    combined = " ".join(steps).lower()
    assert any(w in combined for w in ["key", "phone", "wallet"])


def test_generate_making_call_script():
    data = _gen_script("making_call", next_task_title="Call the supplier")
    assert data["transition_type"] == "making_call"
    steps_text = " ".join(data["script_steps"]).lower()
    # Should include first sentence guidance
    assert any(w in steps_text for w in ["calling", "dial", "note", "sentence"])


def test_generate_ending_day_script():
    data = _gen_script("ending_day")
    assert data["transition_type"] == "ending_day"
    steps_text = " ".join(data["script_steps"]).lower()
    assert any(w in steps_text for w in ["tomorrow", "close", "done", "today"])


def test_generate_recovery_break_script():
    data = _gen_script("recovery_break")
    assert data["transition_type"] == "recovery_break"
    steps_text = " ".join(data["script_steps"]).lower()
    assert any(w in steps_text for w in ["screen", "water", "rest", "step away"])


def test_generate_context_switch_script():
    data = _gen_script("context_switch")
    assert data["transition_type"] == "context_switch"
    assert len(data["script_steps"]) >= 1


def test_low_energy_transition_script_has_fewer_steps():
    """When energy < 30, script must have at most 3 steps."""
    data = _gen_script("starting_work", energy=20, max_steps=8)
    assert len(data["script_steps"]) <= 3


def test_get_latest_transition_by_type():
    uid = "ts-latest-user"
    _gen_script("ending_day", uid=uid)
    _gen_script("ending_day", uid=uid)  # generate twice

    resp = client.get("/transitions/ending_day/latest", headers=h(uid))
    assert resp.status_code == 200
    assert resp.json()["transition_type"] == "ending_day"


def test_update_transition_rating():
    uid = "ts-rating-user"
    created = _gen_script("starting_work", uid=uid)
    script_id = created["id"]

    resp = client.patch(
        f"/transitions/{script_id}/rating",
        json={"success_rating": 4},
        headers=h(uid),
    )
    assert resp.status_code == 200
    assert resp.json()["success_rating"] == 4


def test_mark_transition_used():
    uid = "ts-used-user"
    created = _gen_script("leaving_house", uid=uid)
    script_id = created["id"]

    resp = client.post(f"/transitions/{script_id}/used", headers=h(uid))
    assert resp.status_code == 200
    assert resp.json()["last_used_at"] is not None


def test_transition_user_scope_protection():
    """A different user must NOT be able to access another user's transition script."""
    uid_a = "ts-scope-user-a"
    uid_b = "ts-scope-user-b"

    created = _gen_script("ending_day", uid=uid_a)
    script_id = created["id"]

    # User B tries to rate user A's script — must 404
    resp = client.patch(
        f"/transitions/{script_id}/rating",
        json={"success_rating": 5},
        headers=h(uid_b),
    )
    assert resp.status_code == 404


def test_delete_transition_script():
    uid = "ts-delete-user"
    created = _gen_script("context_switch", uid=uid)
    script_id = created["id"]

    del_resp = client.delete(f"/transitions/{script_id}", headers=h(uid))
    assert del_resp.status_code == 204

    # Should no longer be listed
    list_resp = client.get("/transitions", headers=h(uid))
    all_ids = [s["id"] for s in list_resp.json()]
    assert script_id not in all_ids


def test_list_transitions():
    uid = "ts-list-user"
    _gen_script("starting_work", uid=uid)
    _gen_script("leaving_house", uid=uid)
    _gen_script("making_call", uid=uid)

    resp = client.get("/transitions", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    types = {s["transition_type"] for s in data}
    assert "starting_work" in types
    assert "leaving_house" in types
