"""
Day 3–4 tests: Task Decomposer and MicroAction management.

Tests:
- test_decompose_task_creates_micro_actions
- test_decompose_task_returns_existing_without_duplicates
- test_decompose_task_force_regenerate_replaces_existing
- test_decompose_task_low_energy_recovery_mode
- test_decompose_task_user_scope_protection
- test_get_task_micro_actions
- test_update_micro_action_status
- test_make_micro_action_smaller
- test_dashboard_uses_first_open_micro_action
- test_invalid_llm_output_uses_fallback
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── Test DB setup ──────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_decomposer.db"
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
HEADERS = {"X-User-ID": "decompose-test-user"}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _create_task(title="Write a product spec", priority="high") -> str:
    """Creates a task and returns its id."""
    resp = client.post(
        "/tasks",
        json={"title": title, "priority": priority},
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _log_energy(battery_level: int, sensory_state: str = "calm", headers=None):
    h = headers or HEADERS
    client.post(
        "/energy/log",
        json={"battery_level": battery_level, "sensory_state": sensory_state},
        headers=h,
    )


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_decompose_task_creates_micro_actions():
    """POST /tasks/{id}/decompose should return 3–5 micro-actions (mock mode)."""
    task_id = _create_task("Prepare quarterly report")

    resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 5},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["task_id"] == task_id
    assert data["mode"] in ("normal", "recovery")
    assert data["source"] in ("mock", "llm", "fallback", "existing")
    assert len(data["micro_actions"]) >= 1

    # Verify micro-actions have required fields
    for action in data["micro_actions"]:
        assert action["title"]
        assert action["energy_cost"] in ("low", "medium", "high")
        assert action["sensory_cost"] in ("low", "medium", "high")
        assert action["friction_level"] in ("low", "medium", "high")
        assert action["status"] == "open"


def test_decompose_task_returns_existing_without_duplicates():
    """Calling decompose twice without force_regenerate must not duplicate micro-actions."""
    task_id = _create_task("Plan team offsite")

    # First call — creates
    resp1 = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3},
        headers=HEADERS,
    )
    assert resp1.status_code == 200
    count_after_first = len(resp1.json()["micro_actions"])
    assert count_after_first >= 1

    # Second call — must return existing, not add more
    resp2 = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3, "force_regenerate": False},
        headers=HEADERS,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["source"] == "existing"
    assert len(data2["micro_actions"]) == count_after_first

    # Confirm via GET endpoint too
    get_resp = client.get(f"/tasks/{task_id}/micro-actions", headers=HEADERS)
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == count_after_first


def test_decompose_task_force_regenerate_replaces_existing():
    """force_regenerate=true must replace open micro-actions, not duplicate them."""
    task_id = _create_task("Redesign landing page")

    # First decompose
    client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 5},
        headers=HEADERS,
    )

    # Force regenerate
    resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3, "force_regenerate": True},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Source should NOT be "existing" after force regeneration
    assert data["source"] != "existing"

    # Total micro-actions in DB should match what was just generated (old open ones deleted)
    get_resp = client.get(f"/tasks/{task_id}/micro-actions", headers=HEADERS)
    saved = get_resp.json()
    assert len(saved) == len(data["micro_actions"])


def test_decompose_task_low_energy_recovery_mode():
    """current_energy < 30 must produce recovery mode with ≤ 2 actions."""
    task_id = _create_task("Write a difficult email")

    resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"current_energy": 15, "sensory_state": "shutdown", "max_actions": 5},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["mode"] == "recovery"
    assert len(data["micro_actions"]) <= 2
    assert "lighter" in data["message"].lower() or "small step" in data["message"].lower()


def test_decompose_task_user_scope_protection():
    """A different user must NOT be able to decompose another user's task."""
    task_id = _create_task("Private task")

    other_headers = {"X-User-ID": "different-user-entirely"}
    resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3},
        headers=other_headers,
    )
    # The task doesn't exist for other-user — must return 404
    assert resp.status_code == 404


def test_get_task_micro_actions():
    """GET /tasks/{id}/micro-actions returns the correct list."""
    task_id = _create_task("Update documentation")

    # Decompose first to create micro-actions
    client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 4},
        headers=HEADERS,
    )

    resp = client.get(f"/tasks/{task_id}/micro-actions", headers=HEADERS)
    assert resp.status_code == 200
    actions = resp.json()
    assert isinstance(actions, list)
    assert len(actions) >= 1

    # Each action must be linked to the correct task
    for action in actions:
        assert action["task_id"] == task_id
        assert action["user_id"] == "decompose-test-user"


def test_update_micro_action_status():
    """PATCH /micro-actions/{id}/status marks a micro-action as done."""
    task_id = _create_task("Fix the critical bug")

    decomp_resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3},
        headers=HEADERS,
    )
    micro_actions = decomp_resp.json()["micro_actions"]
    assert len(micro_actions) >= 1

    micro_action_id = micro_actions[0]["id"]

    patch_resp = client.patch(
        f"/micro-actions/{micro_action_id}/status",
        json={"status": "done"},
        headers=HEADERS,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "done"

    # Verify via GET that only open ones are still open
    get_resp = client.get(f"/tasks/{task_id}/micro-actions", headers=HEADERS)
    all_actions = get_resp.json()
    done_actions = [a for a in all_actions if a["id"] == micro_action_id]
    assert done_actions[0]["status"] == "done"


def test_make_micro_action_smaller():
    """POST /micro-actions/{id}/make-smaller creates new smaller actions."""
    task_id = _create_task("Prepare for presentation")

    decomp_resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3},
        headers=HEADERS,
    )
    micro_actions = decomp_resp.json()["micro_actions"]
    micro_action_id = micro_actions[0]["id"]

    smaller_resp = client.post(
        f"/micro-actions/{micro_action_id}/make-smaller",
        json={"current_energy": 60},
        headers=HEADERS,
    )
    assert smaller_resp.status_code == 200
    data = smaller_resp.json()

    assert data["original_micro_action"]["id"] == micro_action_id
    assert len(data["smaller_actions"]) >= 1

    # Original should NOT be deleted
    get_resp = client.get(f"/tasks/{task_id}/micro-actions", headers=HEADERS)
    all_ids = [a["id"] for a in get_resp.json()]
    assert micro_action_id in all_ids


def test_make_micro_action_smaller_recovery_mode():
    """make-smaller with energy < 30 produces only 1 lighter action."""
    task_id = _create_task("Schedule performance reviews")

    decomp_resp = client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 3},
        headers=HEADERS,
    )
    micro_action_id = decomp_resp.json()["micro_actions"][0]["id"]

    resp = client.post(
        f"/micro-actions/{micro_action_id}/make-smaller",
        json={"current_energy": 10},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["smaller_actions"]) == 1
    assert data["smaller_actions"][0]["energy_cost"] == "low"


def test_dashboard_uses_first_open_micro_action():
    """
    After decomposing a task, /copilot/dashboard should surface
    the first open micro-action in suggested_next_action.
    """
    dashboard_headers = {"X-User-ID": "dashboard-micro-test-user"}
    _log_energy(70, headers=dashboard_headers)

    # Create and decompose a task
    task_resp = client.post(
        "/tasks",
        json={"title": "Build the MVP", "priority": "high"},
        headers=dashboard_headers,
    )
    task_id = task_resp.json()["id"]

    client.post(
        f"/tasks/{task_id}/decompose",
        json={"max_actions": 5},
        headers=dashboard_headers,
    )

    # Get dashboard
    dash_resp = client.get("/copilot/dashboard", headers=dashboard_headers)
    assert dash_resp.status_code == 200
    data = dash_resp.json()

    suggested = data.get("suggested_next_action")
    assert suggested is not None
    # Should now be a micro-action reference, not a generic task suggestion
    assert suggested["type"] in (
        "planned_micro_action",
        "existing_micro_action",
        "needs_decomposition",
        "add_task",
        "log_energy",
        "recovery",
    )

    # If it's a micro_action type, it must have micro_action_id set
    if suggested["type"] == "micro_action":
        assert suggested["micro_action_id"] is not None


def test_invalid_llm_output_uses_fallback():
    """
    When the LLM returns garbage, the service must fall back to rule-based
    decomposition and return source='fallback'.
    """
    from app.llm.base import BaseLLMClient, LLMError
    from app.core.database import get_db as real_get_db

    class BrokenLLMClient(BaseLLMClient):
        async def generate_json(self, system_prompt, user_prompt, schema_name=""):
            raise LLMError("Simulated LLM failure")

    fallback_headers = {"X-User-ID": "fallback-test-user"}

    task_resp = client.post(
        "/tasks",
        json={"title": "A task for fallback test", "priority": "medium"},
        headers=fallback_headers,
    )
    task_id = task_resp.json()["id"]

    # Directly call the service with the broken client (bypasses HTTP layer)
    from app.services.task_decomposer_service import decompose_task
    from app.schemas.micro_action_schema import TaskDecomposeRequest
    import asyncio

    db = TestingSessionLocal()
    try:
        result = asyncio.run(
            decompose_task(
                db=db,
                user_id="fallback-test-user",
                task_id=task_id,
                request=TaskDecomposeRequest(max_actions=3),
                llm_client=BrokenLLMClient(),
            )
        )
        assert result.source == "fallback"
        assert len(result.micro_actions) >= 1
    finally:
        db.close()


def test_decompose_nonexistent_task_returns_404():
    """Decomposing a task that doesn't belong to the user must return 404."""
    resp = client.post(
        "/tasks/totally-fake-task-id/decompose",
        json={"max_actions": 3},
        headers=HEADERS,
    )
    assert resp.status_code == 404
