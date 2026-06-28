"""
Tests for user energy pattern aggregation, rolling focus window, and confidence tiers.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_neurosentio_energy_patterns.db"
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


def test_confidence_tier_low():
    """Verify confidence tier is 'low' if total logs < 5."""
    headers = {"X-User-ID": "low-user"}
    # Insert 3 logs
    now = datetime.now(timezone.utc)
    for i in range(3):
        resp = client.post(
            "/energy/log",
            json={
                "battery_level": 70,
                "sensory_state": "calm",
                "logged_at": (now - timedelta(hours=i)).isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 201

    resp = client.get("/energy/patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_tier"] == "low"
    assert "hourly_averages" in data


def test_confidence_tier_medium_and_high_energy_hours():
    """Verify confidence tier is 'medium' if logs between 5 and 15, and check high/low energy classification."""
    headers = {"X-User-ID": "medium-user"}
    # Let's add 6 logs to make it 6 (confidence_tier: medium)
    # Hour 14: let's make it 80 average (high_energy_hours should include 14 since 80 >= 65)
    # Hour 22: let's make it 20 average (low_energy_hours should include 22 since 20 <= 35)
    # Other hours: 3 logs at hour 10 with 50 battery level
    
    now = datetime.now(timezone.utc)
    dt_hour_14_1 = (now - timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    dt_hour_14_2 = (now - timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    dt_hour_22_1 = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
    dt_hour_10_1 = (now - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    dt_hour_10_2 = (now - timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    dt_hour_10_3 = (now - timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    logs = [
        {"battery_level": 80, "sensory_state": "calm", "logged_at": dt_hour_14_1.isoformat()},
        {"battery_level": 80, "sensory_state": "calm", "logged_at": dt_hour_14_2.isoformat()},
        {"battery_level": 20, "sensory_state": "shutdown", "logged_at": dt_hour_22_1.isoformat()},
        {"battery_level": 50, "sensory_state": "okay", "logged_at": dt_hour_10_1.isoformat()},
        {"battery_level": 50, "sensory_state": "okay", "logged_at": dt_hour_10_2.isoformat()},
        {"battery_level": 50, "sensory_state": "okay", "logged_at": dt_hour_10_3.isoformat()},
    ]
    
    for l in logs:
        resp = client.post("/energy/log", json=l, headers=headers)
        assert resp.status_code == 201

    resp = client.get("/energy/patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_tier"] == "medium"
    
    # 14 should be in high_energy_hours, 22 in low_energy_hours
    assert 14 in data["high_energy_hours"]
    assert 22 in data["low_energy_hours"]
    assert data["hourly_averages"]["14"] == 80.0
    assert data["hourly_averages"]["22"] == 20.0


def test_confidence_tier_high():
    """Verify confidence tier is 'high' when logs > 15."""
    headers = {"X-User-ID": "high-user"}
    # Let's add 16 logs to make confidence_tier: high
    now = datetime.now(timezone.utc)
    for i in range(16):
        resp = client.post(
            "/energy/log",
            json={
                "battery_level": 50,
                "sensory_state": "okay",
                "logged_at": (now - timedelta(days=1, hours=i)).isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 201

    resp = client.get("/energy/patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_tier"] == "high"


def test_best_focus_window():
    """Verify rolling 3-hour focus window is computed correctly."""
    headers = {"X-User-ID": "focus-window-user"}
    
    # We want a 3-hour peak at hours 10, 11, 12 (e.g. averages 90, 95, 90)
    # Other hours can be at a default/lower level
    base_time = datetime.now(timezone.utc) - timedelta(days=1)
    base_time = base_time.replace(minute=0, second=0, microsecond=0)
    
    # Let's post logs for hour 10, 11, 12
    focus_logs = [
        {"battery_level": 90, "sensory_state": "calm", "logged_at": base_time.replace(hour=10).isoformat()},
        {"battery_level": 95, "sensory_state": "calm", "logged_at": base_time.replace(hour=11).isoformat()},
        {"battery_level": 90, "sensory_state": "calm", "logged_at": base_time.replace(hour=12).isoformat()},
        # Also post some low energy logs at hour 20, 21, 22
        {"battery_level": 30, "sensory_state": "calm", "logged_at": base_time.replace(hour=20).isoformat()},
        {"battery_level": 30, "sensory_state": "calm", "logged_at": base_time.replace(hour=21).isoformat()},
        {"battery_level": 30, "sensory_state": "calm", "logged_at": base_time.replace(hour=22).isoformat()},
    ]
    
    for l in focus_logs:
        resp = client.post("/energy/log", json=l, headers=headers)
        assert resp.status_code == 201

    resp = client.get("/energy/patterns", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # The best 3-hour window should start at 10:00 (10, 11, 12 average ~ 91.7)
    # The string representation is "10:00 - 13:00"
    assert data["best_focus_window"] == "10:00 - 13:00"
