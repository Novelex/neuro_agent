"""
Tests for stuck task scanner and neurodivergent-friendly tailored advice.
"""

import pytest
from datetime import datetime, date, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.task import Task as TaskModel

TEST_DATABASE_URL = "sqlite:///./test_neurosentio_stuck_tasks.db"
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


def test_stuck_tasks_overdue():
    """Verify that overdue tasks are flagged as overdue with deferral advice."""
    headers = {"X-User-ID": "stuck-user-1"}
    
    # 1. Create a task with due_date in the past
    past_date = date.today() - timedelta(days=1)
    payload = {
        "title": "Overdue Task",
        "due_date": past_date.isoformat(),
        "status": "open",
    }
    resp = client.post("/tasks", json=payload, headers=headers)
    assert resp.status_code == 201
    
    # 2. Query /tasks/stuck
    resp = client.get("/tasks/stuck", headers=headers)
    assert resp.status_code == 200
    stuck_list = resp.json()
    assert len(stuck_list) == 1
    assert stuck_list[0]["stuck_reason"] == "overdue"
    assert stuck_list[0]["suggestion"] == "Consider deferring this task to a lower-load day."
    assert stuck_list[0]["task"]["title"] == "Overdue Task"


def test_stuck_tasks_inactive_open():
    """Verify that open tasks inactive for >= threshold_days are flagged with micro-action advice."""
    headers = {"X-User-ID": "stuck-user-2"}
    
    # 1. Create a task
    resp = client.post("/tasks", json={"title": "Inactive Open Task", "status": "open"}, headers=headers)
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    
    # 2. Update last_touched_at and created_at to 4 days ago in the DB
    db = TestingSessionLocal()
    try:
        db_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        past_time = datetime.now(timezone.utc) - timedelta(days=4)
        db_task.created_at = past_time
        db_task.last_touched_at = past_time
        db.commit()
    finally:
        db.close()
        
    # 3. Query /tasks/stuck with threshold_days = 3
    resp = client.get("/tasks/stuck?days=3", headers=headers)
    assert resp.status_code == 200
    stuck_list = resp.json()
    assert len(stuck_list) == 1
    assert stuck_list[0]["stuck_reason"] == "inactive"
    assert stuck_list[0]["suggestion"] == "Try breaking this task into smaller micro-actions."
    assert stuck_list[0]["task"]["title"] == "Inactive Open Task"


def test_stuck_tasks_inactive_in_progress():
    """Verify that in_progress tasks inactive for >= threshold_days are flagged with 5-minute action advice."""
    headers = {"X-User-ID": "stuck-user-3"}
    
    # 1. Create a task and set to in_progress
    resp = client.post("/tasks", json={"title": "Inactive Progress Task", "status": "in_progress"}, headers=headers)
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    
    # 2. Update status to in_progress (just in case the create did not enforce it, let's use the update endpoint or direct DB edit)
    client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers)
    
    # 3. Update last_touched_at to 5 days ago in the DB
    db = TestingSessionLocal()
    try:
        db_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        past_time = datetime.now(timezone.utc) - timedelta(days=5)
        db_task.created_at = past_time
        db_task.last_touched_at = past_time
        db.commit()
    finally:
        db.close()
        
    # 4. Query /tasks/stuck with threshold_days = 3
    resp = client.get("/tasks/stuck?days=3", headers=headers)
    assert resp.status_code == 200
    stuck_list = resp.json()
    assert len(stuck_list) == 1
    assert stuck_list[0]["stuck_reason"] == "inactive"
    assert stuck_list[0]["suggestion"] == "Can you spend just 5 minutes on a tiny action to get started?"
    assert stuck_list[0]["task"]["title"] == "Inactive Progress Task"


def test_not_stuck_tasks():
    """Verify that active tasks within the threshold and with future due dates are not flagged as stuck."""
    headers = {"X-User-ID": "stuck-user-4"}
    
    # 1. Create a task with future due date
    future_date = date.today() + timedelta(days=5)
    resp = client.post("/tasks", json={"title": "Active Future Task", "due_date": future_date.isoformat()}, headers=headers)
    assert resp.status_code == 201
    
    # 2. Create a recently touched task
    resp2 = client.post("/tasks", json={"title": "Active Recent Task"}, headers=headers)
    assert resp2.status_code == 201
    
    # 3. Query /tasks/stuck
    resp = client.get("/tasks/stuck?days=3", headers=headers)
    assert resp.status_code == 200
    stuck_list = resp.json()
    assert len(stuck_list) == 0
