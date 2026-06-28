"""
Tests for Calendar Events storage, imports, and analysis heuristics.
"""

import pytest
from datetime import datetime, date, time
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, get_db
from tests.test_tasks import engine, override_get_db

@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app)
HEADERS = {"X-User-ID": "calendar-user"}


def test_calendar_event_time_validation():
    # End time before start time should be rejected
    payload = {
        "events": [
            {
                "title": "Invalid Event",
                "start_time": "2026-05-20T12:00:00",
                "end_time": "2026-05-20T11:00:00", # end before start
                "attendee_count": 0,
            }
        ]
    }
    response = client.post("/calendar/import/mock", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_calendar_privacy_stripping():
    # Description, attendees, attendee_emails, conferenceData, hangoutLink, meeting_link, and notes must be stripped
    payload = {
        "events": [
            {
                "title": "Secret Meeting",
                "start_time": "2026-05-20T10:00:00",
                "end_time": "2026-05-20T11:00:00",
                "attendee_count": 3,
                "description": "This is a highly secret and private description that should NEVER be stored.",
                "raw_metadata": {
                    "description": "metadata description",
                    "attendees": ["attendee@example.com"],
                    "attendee_emails": ["a@b.com"],
                    "conferenceData": "conf stuff",
                    "hangoutLink": "https://hangouts.google.com/xyz",
                    "meeting_link": "https://zoom.us/xyz",
                    "notes": "some notes about secret client",
                    "safe_key": "safe value"
                }
            }
        ]
    }
    response = client.post("/calendar/import/mock", json=payload, headers=HEADERS)
    assert response.status_code == 201
    
    data = response.json()
    assert len(data["events"]) == 1
    event = data["events"][0]
    
    # Assert descriptions are stripped
    assert "description" not in event
    assert event.get("raw_metadata") is not None
    
    meta = event["raw_metadata"]
    for private_key in ["description", "attendees", "attendee_emails", "conferenceData", "hangoutLink", "meeting_link", "notes"]:
        assert private_key not in meta
        
    assert meta["safe_key"] == "safe value"


def test_calendar_upsert_rules():
    # 1. Import event with external_event_id
    payload1 = {
        "events": [
            {
                "title": "Initial Import",
                "external_event_id": "ext-1",
                "provider": "google",
                "start_time": "2026-05-20T09:00:00",
                "end_time": "2026-05-20T10:00:00",
            }
        ]
    }
    resp1 = client.post("/calendar/import/mock", json=payload1, headers=HEADERS)
    assert resp1.status_code == 201
    assert resp1.json()["imported_count"] == 1
    assert resp1.json()["updated_count"] == 0

    # 2. Re-import with same external_event_id -> should update (upsert)
    payload2 = {
        "events": [
            {
                "title": "Updated Import Title",
                "external_event_id": "ext-1",
                "provider": "google",
                "start_time": "2026-05-20T09:00:00",
                "end_time": "2026-05-20T10:00:00",
            }
        ]
    }
    resp2 = client.post("/calendar/import/mock", json=payload2, headers=HEADERS)
    assert resp2.status_code == 201
    assert resp2.json()["imported_count"] == 0
    assert resp2.json()["updated_count"] == 1
    assert resp2.json()["events"][0]["title"] == "Updated Import Title"

    # 3. Import with NULL external_event_id -> always creates new event
    payload3 = {
        "events": [
            {
                "title": "Manual Event 1",
                "external_event_id": None,
                "start_time": "2026-05-20T11:00:00",
                "end_time": "2026-05-20T12:00:00",
            },
            {
                "title": "Manual Event 2",
                "external_event_id": None,
                "start_time": "2026-05-20T13:00:00",
                "end_time": "2026-05-20T14:00:00",
            }
        ]
    }
    resp3 = client.post("/calendar/import/mock", json=payload3, headers=HEADERS)
    assert resp3.status_code == 201
    assert resp3.json()["imported_count"] == 2
    assert resp3.json()["updated_count"] == 0


def test_calendar_meeting_type_heuristics():
    # Solo block
    payload = {
        "events": [
            {
                "title": "Focus Time",
                "attendee_count": 0,
                "start_time": "2026-05-20T09:00:00",
                "end_time": "2026-05-20T10:00:00",
            },
            {
                "title": "Supplier Commute",
                "attendee_count": 0,
                "start_time": "2026-05-20T10:15:00",
                "end_time": "2026-05-20T10:45:00",
            },
            {
                "title": "Urgent Interview with Candidate",
                "attendee_count": 2,
                "start_time": "2026-05-20T11:00:00",
                "end_time": "2026-05-20T12:30:00",
            }
        ]
    }
    resp = client.post("/calendar/import/mock", json=payload, headers=HEADERS)
    assert resp.status_code == 201
    events = resp.json()["events"]
    
    # Focus Time -> solo_block, cost low (10 score)
    focus = [e for e in events if "Focus" in e["title"]][0]
    assert focus["meeting_type"] == "solo_block"
    assert focus["load_score"] == 10
    assert focus["energy_cost"] == "low"
    
    #Supplier Commute -> travel, score 40
    commute = [e for e in events if "Commute" in e["title"]][0]
    assert commute["meeting_type"] == "travel"
    assert commute["load_score"] == 40
    assert commute["energy_cost"] == "medium"
    
    # Urgent Interview -> interview, duration > 60 (+10), urgent in title (+10) -> score 100
    interview = [e for e in events if "Interview" in e["title"]][0]
    assert interview["meeting_type"] == "interview"
    assert interview["load_score"] == 100
    assert interview["energy_cost"] == "high"


def test_calendar_back_to_back_detection():
    # Clean day's events first, or use a new user/date
    # Set up events separated by <= 10 mins
    payload = {
        "events": [
            {
                "title": "Meeting A",
                "start_time": "2026-05-21T09:00:00",
                "end_time": "2026-05-21T09:45:00",
            },
            {
                "title": "Meeting B",
                "start_time": "2026-05-21T09:50:00", # 5 mins gap -> back-to-back
                "end_time": "2026-05-21T10:30:00",
            },
            {
                "title": "Meeting C",
                "start_time": "2026-05-21T11:00:00", # 30 mins gap -> not back-to-back
                "end_time": "2026-05-21T12:00:00",
            }
        ]
    }
    resp = client.post("/calendar/import/mock", json=payload, headers=HEADERS)
    assert resp.status_code == 201
    
    events = resp.json()["events"]
    m_a = [e for e in events if "Meeting A" in e["title"]][0]
    m_b = [e for e in events if "Meeting B" in e["title"]][0]
    m_c = [e for e in events if "Meeting C" in e["title"]][0]
    
    assert m_a["is_back_to_back"] is True
    assert m_b["is_back_to_back"] is True
    assert m_c["is_back_to_back"] is False


def test_calendar_free_blocks_and_day_summary():
    # GET /calendar/day-summary?date=2026-05-21
    response = client.get("/calendar/day-summary?date=2026-05-21", headers=HEADERS)
    assert response.status_code == 200
    summary = response.json()
    
    assert summary["date"] == "2026-05-21"
    assert summary["event_count"] == 3
    assert summary["back_to_back_count"] == 2
    
    # Working Day is 09:00 to 17:00
    # Busy:
    # 09:00 - 09:45 (Meeting A)
    # 09:50 - 10:30 (Meeting B)
    # 11:00 - 12:00 (Meeting C)
    # Free blocks should include:
    # 09:45 - 09:50 (5 mins -> too short < 15 minimum)
    # 10:30 - 11:00 (30 mins -> Free block!)
    # 12:00 - 17:00 (300 mins -> Free block!)
    free_blocks = summary["free_blocks"]
    assert len(free_blocks) == 2
    
    # Block 1: 10:30 - 11:00
    b1 = free_blocks[0]
    assert "10:30" in b1["start_time"]
    assert "11:00" in b1["end_time"]
    assert b1["duration_minutes"] == 30
    
    # Block 2: 12:00 - 17:00
    b2 = free_blocks[1]
    assert "12:00" in b2["start_time"]
    assert "17:00" in b2["end_time"]
    assert b2["duration_minutes"] == 300
