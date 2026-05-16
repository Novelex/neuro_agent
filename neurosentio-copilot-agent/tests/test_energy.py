"""
Tests for energy endpoints and quick-plan recovery mode trigger.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_neurosentio_energy.db"
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
HEADERS = {"X-User-ID": "energy-test-user"}


def test_log_energy():
    """POST /energy/log — creates a new energy entry."""
    payload = {
        "battery_level": 42,
        "note": "Feeling drained after calls",
        "sensory_state": "overstimulated",
        "mood": "tired",
    }
    response = client.post("/energy/log", json=payload, headers=HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["battery_level"] == 42
    assert data["sensory_state"] == "overstimulated"


def test_get_latest_energy():
    """GET /energy/latest — returns single most recent log."""
    # Ensure there is at least one log
    client.post(
        "/energy/log",
        json={"battery_level": 55, "sensory_state": "calm"},
        headers=HEADERS,
    )
    response = client.get("/energy/latest", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "battery_level" in data


def test_get_energy_history():
    """GET /energy/history — returns list of logs, newest first."""
    response = client.get("/energy/history", headers=HEADERS)
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1


def test_battery_level_validation():
    """battery_level > 100 must fail with 422."""
    response = client.post(
        "/energy/log",
        json={"battery_level": 150, "sensory_state": "calm"},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_recovery_mode_activates_below_30():
    """Quick plan must return recovery mode when battery < 30."""
    low_energy_headers = {"X-User-ID": "recovery-mode-test"}
    client.post(
        "/energy/log",
        json={"battery_level": 15, "sensory_state": "shutdown"},
        headers=low_energy_headers,
    )
    response = client.post("/copilot/quick-plan", headers=low_energy_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "recovery"


def test_normal_mode_at_high_energy():
    """Quick plan must return normal mode when battery >= 30 with no sensory issues."""
    high_energy_headers = {"X-User-ID": "normal-mode-test"}
    client.post(
        "/energy/log",
        json={"battery_level": 80, "sensory_state": "calm"},
        headers=high_energy_headers,
    )
    response = client.post("/copilot/quick-plan", headers=high_energy_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "normal"
