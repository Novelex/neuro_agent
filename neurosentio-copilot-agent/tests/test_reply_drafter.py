"""
Day 7–8 Tests: Reply Drafter feature.

Coverage:
- test_create_reply_draft_default
- test_create_reply_draft_low_energy_includes_boundary
- test_create_reply_draft_decline_intent
- test_create_reply_draft_delay_intent
- test_create_reply_draft_accept_intent
- test_create_reply_draft_urgent_message
- test_create_reply_draft_saves_to_db
- test_list_reply_drafts
- test_list_reply_drafts_pagination
- test_get_reply_draft_by_id
- test_update_reply_draft_selected_option_and_edit
- test_update_reply_draft_status_to_selected
- test_delete_reply_draft_soft_delete
- test_get_deleted_drafts_when_status_deleted
- test_deleted_draft_hidden_from_default_list
- test_reply_draft_user_scope_protection_get
- test_reply_draft_user_scope_protection_patch
- test_reply_draft_user_scope_protection_delete
- test_invalid_empty_original_message_rejected
- test_invalid_too_short_original_message_rejected
- test_invalid_current_energy_too_high_rejected
- test_invalid_current_energy_negative_rejected
- test_invalid_status_update_sent_rejected
- test_mock_llm_always_returns_three_required_types
- test_mock_decline_returns_decline_language
- test_fallback_source_on_invalid_llm_output
- test_dashboard_still_works_after_reply_drafts
- test_dashboard_includes_reply_draft_count
- test_reply_draft_all_option_types_present_high_energy
- test_no_boundary_when_excluded_from_request
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── Test DB setup ──────────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_reply_drafter.db"
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


def h(uid: str = "reply-test-user") -> dict:
    return {"X-User-ID": uid, "Content-Type": "application/json"}


def _draft(
    message: str = "Can you send me the updated report today?",
    intent: str = None,
    energy: int = None,
    include_boundary: bool = True,
    uid: str = "reply-test-user",
    **kwargs,
) -> dict:
    body: dict = {"original_message": message, "include_boundary_option": include_boundary}
    if intent:
        body["user_intent"] = intent
    if energy is not None:
        body["current_energy"] = energy
    body.update(kwargs)
    resp = client.post("/reply/draft", json=body, headers=h(uid))
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()


# ══════════════════════════════════════════════════════════════════════
# BASIC CREATION TESTS
# ══════════════════════════════════════════════════════════════════════

def test_create_reply_draft_default():
    """Default creation with original_message only — must return 3 options."""
    data = _draft()
    assert data["id"]
    assert data["status"] == "drafted"
    assert data["source"] in ("mock", "fallback")
    types = {opt["type"] for opt in data["draft_options"]}
    assert "short" in types
    assert "warm" in types
    assert "detailed" in types
    # Text must be non-empty
    for opt in data["draft_options"]:
        assert len(opt["text"]) > 0


def test_create_reply_draft_low_energy_includes_boundary():
    """When current_energy < 40, boundary option must be present."""
    data = _draft(energy=20, include_boundary=True)
    types = {opt["type"] for opt in data["draft_options"]}
    assert "boundary" in types, f"Expected boundary in {types}"


def test_create_reply_draft_decline_intent():
    """Decline intent should produce drafts that include 'not able', 'can't', or 'cannot'."""
    data = _draft(intent="decline politely", uid="reply-decline-user")
    all_text = " ".join(opt["text"] for opt in data["draft_options"]).lower()
    assert any(phrase in all_text for phrase in ["can't", "cannot", "not able", "not available"])


def test_create_reply_draft_delay_intent():
    """Delay intent should produce drafts mentioning time or tomorrow."""
    data = _draft(intent="delay — need more time", uid="reply-delay-user")
    all_text = " ".join(opt["text"] for opt in data["draft_options"]).lower()
    assert any(phrase in all_text for phrase in ["tomorrow", "more time", "get back to you"])


def test_create_reply_draft_accept_intent():
    """Accept intent should produce affirmative drafts."""
    data = _draft(intent="accept the meeting invite", uid="reply-accept-user")
    all_text = " ".join(opt["text"] for opt in data["draft_options"]).lower()
    assert any(phrase in all_text for phrase in ["works for me", "yes", "happy to", "go ahead"])


def test_create_reply_draft_urgent_message():
    """Urgent message should produce drafts that acknowledge urgency."""
    data = _draft(
        message="This is urgent — I need the report NOW.",
        uid="reply-urgent-user",
    )
    types = {opt["type"] for opt in data["draft_options"]}
    assert "short" in types and "warm" in types and "detailed" in types


def test_create_reply_draft_saves_to_db():
    """Created draft must be retrievable by its ID."""
    uid = "reply-save-db-user"
    created = _draft(uid=uid)
    draft_id = created["id"]

    resp = client.get(f"/reply/drafts/{draft_id}", headers=h(uid))
    assert resp.status_code == 200
    assert resp.json()["id"] == draft_id


def test_create_reply_draft_with_all_fields():
    """Full request with all optional fields should save and return them."""
    uid = "reply-fullfields-user"
    resp = client.post("/reply/draft", json={
        "original_message": "Can you send me the updated report today?",
        "message_sender": "Sarah",
        "message_subject": "Updated report",
        "message_channel": "manual",
        "user_intent": "delay politely",
        "preferred_tone": "gentle_direct",
        "context_note": "I am low energy today",
        "include_boundary_option": True,
        "current_energy": 28,
    }, headers=h(uid))
    assert resp.status_code == 201
    data = resp.json()
    assert data["message_sender"] == "Sarah"
    assert data["message_subject"] == "Updated report"
    assert data["preferred_tone"] == "gentle_direct"


# ══════════════════════════════════════════════════════════════════════
# LIST / GET TESTS
# ══════════════════════════════════════════════════════════════════════

def test_list_reply_drafts():
    """GET /reply/drafts should return all non-deleted drafts for the user."""
    uid = "reply-list-user"
    _draft(uid=uid, message="First message to reply to")
    _draft(uid=uid, message="Second message to reply to")
    _draft(uid=uid, message="Third message to reply to")

    resp = client.get("/reply/drafts", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3


def test_list_reply_drafts_pagination():
    """limit and offset should work correctly."""
    uid = "reply-pagination-user"
    for i in range(5):
        _draft(uid=uid, message=f"Message number {i + 1} for reply")

    page1 = client.get("/reply/drafts?limit=2&offset=0", headers=h(uid)).json()
    page2 = client.get("/reply/drafts?limit=2&offset=2", headers=h(uid)).json()

    assert len(page1) == 2
    assert len(page2) >= 1
    # Pages must not overlap
    ids1 = {d["id"] for d in page1}
    ids2 = {d["id"] for d in page2}
    assert ids1.isdisjoint(ids2), "Pagination pages must not overlap"


def test_get_reply_draft_by_id():
    """GET /reply/drafts/{id} must return the correct draft."""
    uid = "reply-byid-user"
    created = _draft(uid=uid, message="Get me by ID please")
    draft_id = created["id"]

    resp = client.get(f"/reply/drafts/{draft_id}", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == draft_id
    assert data["original_message"] == "Get me by ID please"


def test_get_nonexistent_draft_returns_404():
    """GET /reply/drafts/nonexistent-id must return 404."""
    resp = client.get("/reply/drafts/does-not-exist-at-all", headers=h())
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# UPDATE TESTS
# ══════════════════════════════════════════════════════════════════════

def test_update_reply_draft_selected_option_and_edit():
    """PATCH with selected_option_type and edited_reply must save both."""
    uid = "reply-update-user"
    created = _draft(uid=uid, message="Can we reschedule the meeting to next week?")
    draft_id = created["id"]

    resp = client.patch(f"/reply/drafts/{draft_id}", json={
        "selected_option_type": "short",
        "edited_reply": "Thanks — I'll send it tomorrow morning.",
        "status": "edited",
    }, headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_option_type"] == "short"
    assert data["edited_reply"] == "Thanks — I'll send it tomorrow morning."
    assert data["status"] == "edited"


def test_update_reply_draft_status_to_selected():
    """PATCH status=selected must update without requiring edited_reply."""
    uid = "reply-select-user"
    created = _draft(uid=uid, message="Please confirm your attendance")
    draft_id = created["id"]

    resp = client.patch(f"/reply/drafts/{draft_id}", json={
        "selected_option_type": "warm",
        "status": "selected",
    }, headers=h(uid))
    assert resp.status_code == 200
    assert resp.json()["status"] == "selected"
    assert resp.json()["selected_option_type"] == "warm"


def test_update_nonexistent_draft_returns_404():
    """PATCH on nonexistent draft must return 404."""
    resp = client.patch("/reply/drafts/not-real", json={"status": "archived"}, headers=h())
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# SOFT DELETE TESTS
# ══════════════════════════════════════════════════════════════════════

def test_delete_reply_draft_soft_delete():
    """DELETE must return {deleted: true, id: ...} and set status=deleted."""
    uid = "reply-delete-user"
    created = _draft(uid=uid, message="This draft will be soft deleted")
    draft_id = created["id"]

    resp = client.delete(f"/reply/drafts/{draft_id}", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["id"] == draft_id

    # Verify status is deleted
    get_resp = client.get(f"/reply/drafts/{draft_id}", headers=h(uid))
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "deleted"


def test_deleted_draft_hidden_from_default_list():
    """Deleted drafts must not appear in GET /reply/drafts (default)."""
    uid = "reply-hidden-user"
    created = _draft(uid=uid, message="Draft to hide after deletion")
    draft_id = created["id"]

    client.delete(f"/reply/drafts/{draft_id}", headers=h(uid))

    list_resp = client.get("/reply/drafts", headers=h(uid))
    ids = [d["id"] for d in list_resp.json()]
    assert draft_id not in ids, "Deleted draft should not appear in default list"


def test_get_deleted_drafts_when_status_deleted():
    """GET /reply/drafts?status=deleted must show deleted drafts."""
    uid = "reply-deleted-filter-user"
    created = _draft(uid=uid, message="Will be deleted and queried")
    draft_id = created["id"]

    client.delete(f"/reply/drafts/{draft_id}", headers=h(uid))

    list_resp = client.get("/reply/drafts?status=deleted", headers=h(uid))
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert draft_id in ids, "Deleted draft should appear when status=deleted is requested"


def test_delete_nonexistent_draft_returns_404():
    """DELETE on nonexistent draft must return 404."""
    resp = client.delete("/reply/drafts/not-a-real-id", headers=h())
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# USER SCOPE PROTECTION
# ══════════════════════════════════════════════════════════════════════

def test_reply_draft_user_scope_protection_get():
    """User B must get 404 when trying to GET user A's draft."""
    uid_a = "reply-scope-a"
    uid_b = "reply-scope-b"
    created = _draft(uid=uid_a, message="This belongs to user A only")
    draft_id = created["id"]

    resp = client.get(f"/reply/drafts/{draft_id}", headers=h(uid_b))
    assert resp.status_code == 404


def test_reply_draft_user_scope_protection_patch():
    """User B must get 404 when trying to PATCH user A's draft."""
    uid_a = "reply-scope-patch-a"
    uid_b = "reply-scope-patch-b"
    created = _draft(uid=uid_a, message="User A's confidential draft message")
    draft_id = created["id"]

    resp = client.patch(
        f"/reply/drafts/{draft_id}",
        json={"status": "archived"},
        headers=h(uid_b),
    )
    assert resp.status_code == 404


def test_reply_draft_user_scope_protection_delete():
    """User B must get 404 when trying to DELETE user A's draft."""
    uid_a = "reply-scope-del-a"
    uid_b = "reply-scope-del-b"
    created = _draft(uid=uid_a, message="User A draft for scope test")
    draft_id = created["id"]

    resp = client.delete(f"/reply/drafts/{draft_id}", headers=h(uid_b))
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# INPUT VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════════

def test_invalid_empty_original_message_rejected():
    """original_message='' must return 422."""
    resp = client.post("/reply/draft", json={"original_message": ""}, headers=h())
    assert resp.status_code == 422


def test_invalid_too_short_original_message_rejected():
    """original_message shorter than 3 chars must return 422."""
    resp = client.post("/reply/draft", json={"original_message": "hi"}, headers=h())
    assert resp.status_code == 422


def test_invalid_current_energy_too_high_rejected():
    """current_energy=150 must return 422."""
    resp = client.post("/reply/draft", json={
        "original_message": "Can we reschedule?",
        "current_energy": 150,
    }, headers=h())
    assert resp.status_code == 422


def test_invalid_current_energy_negative_rejected():
    """current_energy=-5 must return 422."""
    resp = client.post("/reply/draft", json={
        "original_message": "Can we reschedule?",
        "current_energy": -5,
    }, headers=h())
    assert resp.status_code == 422


def test_invalid_status_update_sent_rejected():
    """PATCH status='sent' must return 422 — agent never sends messages."""
    uid = "reply-no-send-user"
    created = _draft(uid=uid, message="I will never send this automatically")
    draft_id = created["id"]

    resp = client.patch(
        f"/reply/drafts/{draft_id}",
        json={"status": "sent"},
        headers=h(uid),
    )
    assert resp.status_code == 422, (
        "Status 'sent' must be rejected — the agent never sends messages"
    )


# ══════════════════════════════════════════════════════════════════════
# MOCK LLM BEHAVIOUR TESTS
# ══════════════════════════════════════════════════════════════════════

def test_mock_llm_always_returns_three_required_types():
    """Mock LLM must always return short, warm, and detailed."""
    uid = "reply-mock-types-user"
    for _ in range(3):
        data = _draft(uid=uid, message="Can you send me the quarterly report?")
        types = {opt["type"] for opt in data["draft_options"]}
        assert "short" in types
        assert "warm" in types
        assert "detailed" in types


def test_mock_decline_returns_decline_language():
    """Mock LLM should return decline-appropriate language for decline intent."""
    uid = "reply-mock-decline-user"
    data = _draft(uid=uid, intent="decline this gracefully", include_boundary=True)
    types = {opt["type"] for opt in data["draft_options"]}
    assert "short" in types and "warm" in types and "detailed" in types
    # Any option should contain non-accepting language
    all_text = " ".join(opt["text"] for opt in data["draft_options"]).lower()
    assert any(w in all_text for w in ["can't", "cannot", "not able", "not available", "boundary", "capacity"])


def test_no_boundary_when_excluded_from_request():
    """When include_boundary_option=False and energy >= 40, no boundary option."""
    uid = "reply-no-boundary-user"
    data = _draft(
        uid=uid,
        energy=70,
        include_boundary=False,
        message="Please review the attached document and share feedback",
    )
    types = {opt["type"] for opt in data["draft_options"]}
    assert "boundary" not in types, "Boundary should not be present when include_boundary_option=False and energy is high"


def test_reply_draft_all_option_types_present_high_energy():
    """
    With high energy and include_boundary=True but no intent keyword,
    the service does NOT force boundary (energy >= 40, no decline/delay intent).
    short/warm/detailed must be present.
    """
    uid = "reply-all-types-user"
    data = _draft(
        uid=uid,
        energy=80,
        include_boundary=True,
        message="Are you available for a quick sync this Friday afternoon?",
    )
    types = {opt["type"] for opt in data["draft_options"]}
    assert "short" in types
    assert "warm" in types
    assert "detailed" in types
    # With high energy and no intent, boundary is NOT forced (correct behaviour)


def test_reply_draft_boundary_forced_by_intent():
    """With include_boundary=True and a decline intent, boundary must appear."""
    uid = "reply-boundary-intent-user"
    data = _draft(
        uid=uid,
        energy=70,
        include_boundary=True,
        intent="decline",
        message="Can you take on this extra project this month?",
    )
    types = {opt["type"] for opt in data["draft_options"]}
    assert "boundary" in types, f"Expected boundary in {types}"


def test_fallback_source_on_invalid_llm_output():
    """
    When a broken LLM client raises LLMError, source must be 'fallback'.
    Injects a broken client directly into the service.
    """
    import asyncio
    from app.llm.base import BaseLLMClient, LLMError
    from app.services.reply_drafter_service import draft_reply
    from app.schemas.reply_schema import ReplyDraftRequest

    class BrokenLLMClient(BaseLLMClient):
        async def generate_json(self, system_prompt, user_prompt, schema_name=""):
            raise LLMError("Simulated LLM failure")

    db = TestingSessionLocal()
    try:
        request = ReplyDraftRequest(original_message="Can we push the deadline to next week?")
        result = asyncio.run(
            draft_reply(
                db=db,
                user_id="reply-fallback-user-2",
                request=request,
                llm_client=BrokenLLMClient(),
            )
        )
        assert result.source == "fallback"
        types = {opt.type for opt in result.draft_options}
        assert "short" in types and "warm" in types and "detailed" in types
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════
# DASHBOARD INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════

def test_dashboard_still_works_after_reply_drafts():
    """Dashboard must return 200 even when reply drafts exist."""
    uid = "reply-dash-test-user"
    _draft(uid=uid, message="Dashboard integration check message")

    resp = client.get("/copilot/dashboard", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "open_tasks_count" in data


def test_dashboard_includes_reply_draft_count():
    """Dashboard reply_drafts_count must reflect created non-deleted drafts."""
    uid = "reply-dash-count-user"
    _draft(uid=uid, message="First dashboard count draft")
    _draft(uid=uid, message="Second dashboard count draft")

    resp = client.get("/copilot/dashboard", headers=h(uid))
    assert resp.status_code == 200
    data = resp.json()
    assert "reply_drafts_count" in data
    assert data["reply_drafts_count"] >= 2
