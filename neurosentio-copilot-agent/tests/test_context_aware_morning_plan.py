"""
Tests for context-aware morning plan generation.
Covers:
- Calendar-aware slot placement (no overlap with busy events, no mutual overlap)
- Energy-pattern focus hour prioritization
- Stuck task capping and tailored advice
- Heavy load scaling of action limits
- Fully booked day test (actions left unscheduled)
"""

import pytest
from datetime import datetime, date, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.task import Task as TaskModel
from app.models.micro_action import MicroAction as MicroActionModel

TEST_DATABASE_URL = "sqlite:///./test_neurosentio_context_plan.db"
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


def test_calendar_aware_slot_placement():
    """Verify micro-actions are not scheduled during busy events and do not overlap each other."""
    headers = {"X-User-ID": "context-user-1"}
    plan_date = date(2026, 5, 20)
    
    # 1. Import a busy calendar event from 10:00 to 11:00 on 2026-05-20
    resp_cal = client.post(
        "/calendar/import/mock",
        json={
            "events": [
                {
                    "title": "Busy Team Standup",
                    "start_time": "2026-05-20T10:00:00",
                    "end_time": "2026-05-20T11:00:00",
                    "attendee_count": 5
                }
            ]
        },
        headers=headers
    )
    assert resp_cal.status_code == 201

    # 2. Create a task and decompose it to generate micro-actions (e.g. three 15-minute actions)
    resp_task = client.post("/tasks", json={"title": "Important Document Write"}, headers=headers)
    assert resp_task.status_code == 201
    task_id = resp_task.json()["id"]
    
    # Decompose to populate micro-actions in the database
    resp_decomp = client.post(f"/tasks/{task_id}/decompose", json={}, headers=headers)
    assert resp_decomp.status_code == 200
    
    # 3. Request a morning plan starting at 09:30 for 120 available minutes
    # Since there's a busy standup 10:00-11:00, the available free blocks inside 09:00-17:00 starting at 09:30 are:
    # 09:30 - 10:00 (30 mins free)
    # 11:00 - 17:00 (360 mins free)
    # Actions should be scheduled in these free spaces.
    # Micro-action 1 (e.g. 10 mins) -> 09:30
    # Micro-action 2 (e.g. 10 mins) -> 09:40
    # Micro-action 3 (e.g. 10 mins) -> 09:50
    # Or if a micro-action does not fit, it should jump to 11:00!
    # Standup is 10:00 - 11:00, so absolutely nothing should be scheduled between 10:00 and 11:00!
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={
            "plan_date": plan_date.isoformat(),
            "available_minutes": 120,
            "start_time": "09:30",
            "force_regenerate": True
        },
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    
    # Assert times: none of the scheduled times are between 10:00 and 11:00 (exclusive of 11:00 start)
    scheduled_times = []
    for action in plan_data["selected_micro_actions"]:
        t_str = action["scheduled_time"]
        if t_str:
            scheduled_times.append(t_str)
            h, m = map(int, t_str.split(":"))
            total_minutes = h * 60 + m
            # 10:00 is 600 mins, 11:00 is 660 mins
            assert not (600 <= total_minutes < 660), f"Action scheduled inside busy event: {t_str}"
            
    # Ensure they don't overlap (all scheduled times are unique)
    assert len(scheduled_times) == len(set(scheduled_times)), f"Duplicate start times: {scheduled_times}"


def test_energy_pattern_focus_hour_prioritization():
    """Verify high/medium energy cost actions prioritize high energy hours."""
    headers = {"X-User-ID": "context-user-2"}
    plan_date = date(2026, 5, 20)
    
    # 1. Populate energy logs to make Hour 11 a high energy hour (avg >= 65)
    # Log 6 times on recent days, each exactly at hour 11
    now = datetime.now(timezone.utc)
    for i in range(6):
        log_time = (now - timedelta(days=i)).replace(hour=11, minute=0, second=0)
        client.post(
            "/energy/log",
            json={
                "battery_level": 90,
                "sensory_state": "calm",
                "logged_at": log_time.isoformat(),
            },
            headers=headers
        )
        
    # 2. Create a meeting from 09:00 to 11:00, so the first free block starts exactly at 11:00!
    client.post(
        "/calendar/import/mock",
        json={
            "events": [
                {
                    "title": "Morning Sync",
                    "start_time": "2026-05-20T09:00:00",
                    "end_time": "2026-05-20T11:00:00",
                }
            ]
        },
        headers=headers
    )
        
    # 3. Create a task with a high energy cost micro-action
    resp_task = client.post("/tasks", json={"title": "High Focus Coding"}, headers=headers)
    task_id = resp_task.json()["id"]
    
    # Let's add a medium/high energy micro-action directly to the database for this task
    db = TestingSessionLocal()
    try:
        ma = MicroActionModel(
            id="ma-high-energy-1",
            user_id="context-user-2",
            task_id=task_id,
            title="Write core algorithm",
            duration_minutes=30,
            energy_cost="high",
            status="open"
        )
        db.add(ma)
        db.commit()
    finally:
        db.close()
        
    # 4. Generate morning plan
    # High energy hours should contain [11]. The first free block starts at 11:00, which aligns with hour 11.
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={
            "plan_date": plan_date.isoformat(),
            "available_minutes": 120,
            "start_time": "09:00",
            "force_regenerate": True
        },
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    
    # Find the high energy action and verify it's scheduled at 11:00
    coding_action = [a for a in plan_data["selected_micro_actions"] if a["micro_action_id"] == "ma-high-energy-1"][0]
    assert coding_action["scheduled_time"] == "11:00"


def test_stuck_task_capping_and_advice():
    """Verify that in normal mode, at most 1 stuck task micro-action is scheduled, and advice is returned."""
    headers = {"X-User-ID": "context-user-3"}
    plan_date = date(2026, 5, 20)
    
    # 1. Create a stuck task in the database (make it overdue)
    past_date = date.today() - timedelta(days=2)
    resp_task = client.post(
        "/tasks", 
        json={"title": "Stuck Coding Task", "due_date": past_date.isoformat(), "status": "open"}, 
        headers=headers
    )
    task_id = resp_task.json()["id"]
    
    # Decompose stuck task to produce multiple micro-actions
    client.post(f"/tasks/{task_id}/decompose", json={}, headers=headers)
    
    # 2. Request morning plan with an explicit high energy to avoid the unknown energy note
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={
            "plan_date": plan_date.isoformat(),
            "available_minutes": 120,
            "current_energy": 80,
            "force_regenerate": True
        },
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    
    # Filter the selected micro-actions belonging to this task
    stuck_scheduled = [a for a in plan_data["selected_micro_actions"] if a["task_id"] == task_id]
    assert len(stuck_scheduled) <= 1, f"Expected at most 1 stuck task micro-action, scheduled: {len(stuck_scheduled)}"
    
    # The message should contain advice about the stuck task
    assert "stuck task" in plan_data["message"].lower()


def test_heavy_load_scaling_and_recovery_blocks():
    """Verify that if the calendar is heavy, maximum micro-actions are scaled down and recovery blocks are added."""
    headers = {"X-User-ID": "context-user-4"}
    plan_date = date(2026, 5, 20)
    
    # 1. Set up a heavy calendar load: 4 events, 2 back-to-backs, total meeting duration > 120 minutes
    resp_cal = client.post(
        "/calendar/import/mock",
        json={
            "events": [
                {
                    "title": "Meeting 1",
                    "start_time": "2026-05-20T09:00:00",
                    "end_time": "2026-05-20T09:45:00",
                },
                {
                    "title": "Meeting 2",
                    "start_time": "2026-05-20T09:50:00", # back-to-back with 1
                    "end_time": "2026-05-20T10:30:00",
                },
                {
                    "title": "Meeting 3",
                    "start_time": "2026-05-20T11:00:00",
                    "end_time": "2026-05-20T12:00:00",
                },
                {
                    "title": "Meeting 4",
                    "start_time": "2026-05-20T14:00:00",
                    "end_time": "2026-05-20T15:00:00",
                }
            ]
        },
        headers=headers
    )
    assert resp_cal.status_code == 201
    
    # 2. Create 10 micro-actions
    resp_task = client.post("/tasks", json={"title": "Heavy Task"}, headers=headers)
    task_id = resp_task.json()["id"]
    db = TestingSessionLocal()
    try:
        for i in range(10):
            ma = MicroActionModel(
                id=f"ma-heavy-{i}",
                user_id="context-user-4",
                task_id=task_id,
                title=f"Subtask {i}",
                duration_minutes=15,
                status="open"
            )
            db.add(ma)
        db.commit()
    finally:
        db.close()
        
    # 3. Request morning plan with 240 available minutes
    # Max actions is scaled down by 1 when calendar is heavy (normal limit: min(5, 240//20 = 12) -> 5. Heavy load scales it to 4!)
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={
            "plan_date": plan_date.isoformat(),
            "available_minutes": 240,
            "force_regenerate": True
        },
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    
    # Check max actions scaled down to 4
    assert len(plan_data["selected_micro_actions"]) <= 4
    
    # Check post-meeting recovery block is added due to back-to-back meetings
    recovery_titles = [rb["title"] for rb in plan_data["recovery_blocks"]]
    assert "Post-Meeting Recovery Break" in recovery_titles


def test_fully_booked_day():
    """Verify that if the user's day has only small gaps, actions larger than the gap are left unscheduled (scheduled_time=None)."""
    headers = {"X-User-ID": "context-user-5"}
    plan_date = date(2026, 5, 20)
    
    # 1. Book the day from 09:15 to 17:00. This leaves a single 15-minute free block at 09:00 - 09:15.
    resp_cal = client.post(
        "/calendar/import/mock",
        json={
            "events": [
                {
                    "title": "Semi-All-Day Offsite Planning",
                    "start_time": "2026-05-20T09:15:00",
                    "end_time": "2026-05-20T17:00:00",
                    "attendee_count": 20
                }
            ]
        },
        headers=headers
    )
    assert resp_cal.status_code == 201
    
    # 2. Create task and a 30-minute micro-action
    resp_task = client.post("/tasks", json={"title": "Offsite Tasks"}, headers=headers)
    task_id = resp_task.json()["id"]
    db = TestingSessionLocal()
    try:
        ma = MicroActionModel(
            id="ma-offsite-1",
            user_id="context-user-5",
            task_id=task_id,
            title="Read prep materials",
            duration_minutes=30,  # 30 minutes won't fit in the 15-minute gap!
            status="open"
        )
        db.add(ma)
        db.commit()
    finally:
        db.close()
        
    # 3. Generate morning plan
    # The action has a 30-minute duration but the only free block is 15 minutes, so it should be left unscheduled (None)
    plan_resp = client.post(
        "/copilot/morning-plan",
        json={
            "plan_date": plan_date.isoformat(),
            "available_minutes": 120,
            "force_regenerate": True
        },
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    
    assert len(plan_data["selected_micro_actions"]) == 1
    assert plan_data["selected_micro_actions"][0]["scheduled_time"] is None
