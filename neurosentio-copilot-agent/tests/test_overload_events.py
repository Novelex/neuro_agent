"""
Tests for overload scoring, database logging, and deduplication rules.
"""

import pytest
from datetime import datetime, date, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.services.overload_service import calculate_overload_risk
from app.models.overload_event import OverloadEvent as OverloadEventModel

TEST_DATABASE_URL = "sqlite:///./test_neurosentio_overload.db"
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


def test_calculate_overload_risk_no_calendar():
    """Verify that when no calendar parameters are provided, overload calculation behaves as before."""
    # Battery under 30 (+50), overstimulated (+25) -> risk_score 75
    mock_energy = type("Energy", (), {"battery_level": 15, "sensory_state": "overstimulated"})()
    res = calculate_overload_risk(
        latest_energy=mock_energy,
        open_tasks_count=2,
        high_priority_count=0
    )
    assert res["risk_score"] == 75
    assert res["mode"] == "recovery"
    assert "Energy is very low" in "".join(res["reasons"])


def test_calculate_overload_risk_with_calendar():
    """Verify calendar-aware multipliers: 4+ events (+20), 2+ back-to-backs (+25), high-load event (+20), minutes > 240 (+20)."""
    mock_energy = type("Energy", (), {"battery_level": 60, "sensory_state": "calm"})()
    
    # 1. 4+ events today (+20)
    res = calculate_overload_risk(mock_energy, 0, 0, event_count=4)
    assert res["risk_score"] == 20
    
    # 2. 2+ back-to-back events today (+25)
    res = calculate_overload_risk(mock_energy, 0, 0, back_to_back_count=2)
    assert res["risk_score"] == 25
    
    # 3. High-load event exists (+20)
    res = calculate_overload_risk(mock_energy, 0, 0, high_load_event_exists=True)
    assert res["risk_score"] == 20
    
    # 4. Total meeting minutes > 240 (+20)
    res = calculate_overload_risk(mock_energy, 0, 0, total_meeting_minutes=250)
    assert res["risk_score"] == 20
    
    # 5. Combined calendar factors: 4 events (+20), 2 back-to-back (+25), high-load exists (+20), 300 minutes (+20) -> 85 score
    res = calculate_overload_risk(
        mock_energy, 
        0, 
        0, 
        event_count=4, 
        back_to_back_count=2, 
        high_load_event_exists=True, 
        total_meeting_minutes=300
    )
    assert res["risk_score"] == 85
    assert res["mode"] == "recovery"


def test_overload_logging_and_deduplication():
    """Verify overload event logging during morning plan generation and the 30-minute deduplication threshold of >= 15 points."""
    headers = {"X-User-ID": "overload-logging-user"}
    
    # Setup 2 tasks
    client.post("/tasks", json={"title": "Task 1", "priority": "high"}, headers=headers)
    client.post("/tasks", json={"title": "Task 2", "priority": "high"}, headers=headers)
    
    # 1. Generate morning plan with low energy/sensory to trigger overload event logging
    # Battery 10 (+50), overstimulated (+25) -> risk score is 75 (>= 60)
    plan_resp = client.post(
        "/copilot/morning-plan", 
        json={
            "available_minutes": 120,
            "current_energy": 10,
            "sensory_state": "overstimulated",
        }, 
        headers=headers
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["overload_risk_score"] == 75
    
    # Verify exactly 1 event is in the log database
    resp = client.get("/overload/events", headers=headers)
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    
    # 2. Trigger morning plan again within 30 minutes with identical score parameters
    # The new plan generation should run, but the overload logger should deduplicate (no new log entry)
    plan_resp2 = client.post(
        "/copilot/morning-plan", 
        json={
            "available_minutes": 120,
            "current_energy": 10,
            "sensory_state": "overstimulated",
            "force_regenerate": True,
        }, 
        headers=headers
    )
    assert plan_resp2.status_code == 200
    
    resp2 = client.get("/overload/events", headers=headers)
    assert len(resp2.json()) == 1, "Should deduplicate similar score events within 30 minutes"
    
    # 3. Modify task parameters to trigger a high overload difference (>= 15 points)
    # Let's add 5 more high priority tasks (total 7 tasks, 7 high priority)
    # open_tasks > 5 adds +15
    # high priority > 2 adds +15
    # Risk score will become 75 + 15 + 15 = 105 (change is 30 points, which is >= 15)
    for i in range(5):
        client.post("/tasks", json={"title": f"Extra Task {i}", "priority": "high"}, headers=headers)
        
    plan_resp3 = client.post(
        "/copilot/morning-plan", 
        json={
            "available_minutes": 120,
            "current_energy": 10,
            "sensory_state": "overstimulated",
            "force_regenerate": True,
        }, 
        headers=headers
    )
    assert plan_resp3.status_code == 200
    assert plan_resp3.json()["overload_risk_score"] == 105
    
    resp3 = client.get("/overload/events", headers=headers)
    assert len(resp3.json()) == 2, "Should log a new event when score change is >= 15 points"
