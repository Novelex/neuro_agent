"""
Tests for task endpoints.
Uses a file-based SQLite database per test session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── Test DB setup ──────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_neurosentio.db"

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
HEADERS = {"X-User-ID": "test-user"}


# ── Tests ──────────────────────────────────────────────────────────────
def test_create_task():
    payload = {
        "title": "Write unit tests",
        "description": "Test all critical paths",
        "priority": "high",
        "estimated_energy": "medium",
        "estimated_sensory_cost": "low",
    }
    response = client.post("/tasks", json=payload, headers=HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Write unit tests"
    assert data["priority"] == "high"
    assert data["status"] == "open"


def test_get_all_tasks():
    """GET /tasks with no filter returns all tasks."""
    response = client.get("/tasks", headers=HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_tasks_filtered_by_status_active():
    """GET /tasks?status=active returns only open and in_progress tasks."""
    response = client.get("/tasks?status=active", headers=HEADERS)
    assert response.status_code == 200
    tasks = response.json()
    for task in tasks:
        assert task["status"] in ("open", "in_progress")


def test_get_tasks_filtered_by_status_open():
    """GET /tasks?status=open returns only open tasks."""
    response = client.get("/tasks?status=open", headers=HEADERS)
    assert response.status_code == 200
    tasks = response.json()
    for task in tasks:
        assert task["status"] == "open"


def test_update_task_status():
    # Create a fresh task
    payload = {"title": "Status test task", "priority": "low"}
    create_resp = client.post("/tasks", json=payload, headers=HEADERS)
    task_id = create_resp.json()["id"]

    # Update status via the dedicated status endpoint
    response = client.patch(
        f"/tasks/{task_id}/status",
        json={"status": "done"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_update_task_fields():
    """PATCH /tasks/{id} updates metadata fields only."""
    payload = {"title": "Field update task", "priority": "low"}
    create_resp = client.post("/tasks", json=payload, headers=HEADERS)
    task_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/tasks/{task_id}",
        json={"title": "Updated title", "priority": "high"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["title"] == "Updated title"
    assert data["priority"] == "high"


def test_delete_task():
    payload = {"title": "Task to delete", "priority": "low"}
    create_resp = client.post("/tasks", json=payload, headers=HEADERS)
    task_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/tasks/{task_id}", headers=HEADERS)
    assert delete_resp.status_code == 204

    # Confirm it's gone from all tasks
    tasks = client.get("/tasks", headers=HEADERS).json()
    ids = [t["id"] for t in tasks]
    assert task_id not in ids


def test_task_not_found():
    response = client.patch(
        "/tasks/nonexistent-id/status",
        json={"status": "done"},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_tasks_pagination():
    uid = "pagination-user"
    headers = {"X-User-ID": uid, "Content-Type": "application/json"}

    # Create 3 tasks
    client.post("/tasks", json={"title": "Task 1", "priority": "low"}, headers=headers)
    client.post("/tasks", json={"title": "Task 2", "priority": "medium"}, headers=headers)
    client.post("/tasks", json={"title": "Task 3", "priority": "high"}, headers=headers)

    # 1. Fetch with limit=2 (should return the 2 latest: Task 3, Task 2)
    resp = client.get("/tasks?limit=2", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Task 3"
    assert tasks[1]["title"] == "Task 2"

    # 2. Fetch with limit=2 and offset=1 (should return Task 2, Task 1)
    resp = client.get("/tasks?limit=2&offset=1", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Task 2"
    assert tasks[1]["title"] == "Task 1"

