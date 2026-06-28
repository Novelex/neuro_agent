"""
E2E PostgreSQL Live-Server Verification.
Executes a real HTTP-only multi-step workflow against a running Uvicorn server in Postgres mode.
DOES NOT import or use TestClient.
"""

import sys
import io
import time
import requests
import jwt as pyjwt
import os
import argparse
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000"
USER_ID = "e2e-postgres-hardened-user"


def _create_test_jwt(sub, secret, exp_offset=3600):
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "role": "authenticated",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _check(step_name, condition, details=""):
    if condition:
        print(f"  [PASS] {step_name} {details}")
        return True
    else:
        print(f"  [FAIL] {step_name} {details}")
        sys.exit(1)


def main():
    # 1. Parse CLI arguments for safety guard and database URL check
    parser = argparse.ArgumentParser(description="Run E2E Postgres Live Server validation.")
    parser.add_argument("--allow-non-test-db", action="store_true", help="Allow destructive cleanup on databases not containing 'test' in the name")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL database URL to verify")
    args = parser.parse_args()

    # Determine database URL from argument, environment, or settings default
    postgres_url = args.db_url or os.environ.get("POSTGRES_DATABASE_URL")
    if not postgres_url:
        from app.core.config import get_settings
        settings = get_settings()
        postgres_url = settings.postgres_database_url

    print("=" * 80)
    print("NeuroSentio Copilot Agent — Real HTTP E2E PostgreSQL Compatibility Verification")
    print(f"Target Base URL: {BASE_URL}")
    print(f"PostgreSQL URL:  {postgres_url}")
    print("=" * 80)

    # Safety Guard Check
    parsed = urlparse(postgres_url)
    db_name = parsed.path.lstrip('/')
    if "test" not in db_name.lower() and not args.allow_non_test_db:
        print(f"ERROR: Destructive database operations refused. Database name '{db_name}' does not contain 'test' and --allow-non-test-db was not supplied.")
        sys.exit(1)

    print(f"Safety guard passed. Database '{db_name}' contains 'test'. Proceeding with HTTP E2E check...")

    # 2. Health check & Reachability
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        _check("Health Check", r.status_code == 200, "Server is reachable.")
    except requests.ConnectionError:
        print("\n[FAIL] Server not reachable. Please start uvicorn in PostgreSQL mode:")
        print(f"   DATABASE_URL={postgres_url} uvicorn app.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    # 3. Determine auth mode and prepare headers
    r = requests.get(f"{BASE_URL}/profile")
    if r.status_code == 401:
        print("Production Auth Mode Detected (Supabase JWT Hardening Active)")
        secret = os.environ.get("SUPABASE_JWT_SECRET", "test-jwt-secret-for-e2e")
        token = _create_test_jwt(USER_ID, secret)
        headers = {"Authorization": f"Bearer {token}"}
    else:
        print("Development Auth Mode Detected (X-User-ID Header Bypass Active)")
        headers = {"X-User-ID": USER_ID}

    # Initialize/Reset: ensure clean slate for test user
    print("\n[Step 0] Cleaning up any existing data for the user...")
    r = requests.delete(f"{BASE_URL}/user/delete-data?confirm=true", headers=headers)
    _check("Initial Cleanup", r.status_code in (200, 400, 404), f"Status: {r.status_code}")

    # Step 1: Check Profile & Default Privacy Preferences initialization
    print("\n[Step 1] Initializing profile and default privacy preferences...")
    r = requests.put(f"{BASE_URL}/profile", json={"preferred_name": "Postgres User", "preferred_tone": "warm"}, headers=headers)
    _check("Create Profile", r.status_code == 200, r.text[:100])

    r = requests.get(f"{BASE_URL}/privacy/preferences", headers=headers)
    _check("Get Preferences", r.status_code == 200)
    prefs = r.json()
    _check("Verify Default Preference Values", 
           prefs["store_reply_original_messages"] is True and
           prefs["store_message_snippets"] is True and
           prefs["store_calendar_titles"] is True and
           prefs["store_task_descriptions"] is True and
           prefs["retention_days_reply_drafts"] is None,
           f"Values: {prefs}"
    )

    # Step 2: Seed data (Message, Calendar, Task, Reply Draft)
    print("\n[Step 2] Seeding initial sensitive data...")
    
    # Task
    r = requests.post(f"{BASE_URL}/tasks", json={"title": "Strategy Draft", "description": "Highly sensitive strategic document."}, headers=headers)
    _check("Seed Task", r.status_code == 201)
    task_id = r.json()["id"]

    # Message
    r = requests.post(f"{BASE_URL}/messages/import/mock", json={
        "messages": [{
            "source": "mock",
            "external_message_id": "e2e-msg-1",
            "channel": "email",
            "sender": "investor@venture.com",
            "subject": "Investment Offer",
            "snippet": "Here is our secret valuation numbers snippet.",
            "received_at": "2026-05-21T12:00:00Z"
        }]
    }, headers=headers)
    _check("Seed Message", r.status_code == 200)
    message_id = r.json()["messages"][0]["id"]

    # Calendar Event
    r = requests.post(f"{BASE_URL}/calendar/import/mock", json={
        "events": [{
            "provider": "mock",
            "external_event_id": "e2e-cal-1",
            "title": "Secret Restructuring Plan Meeting",
            "start_time": "2026-05-22T10:00:00Z",
            "end_time": "2026-05-22T11:00:00Z"
        }]
    }, headers=headers)
    _check("Seed Calendar Event", r.status_code == 201)
    calendar_id = r.json()["events"][0]["id"]

    # Reply Draft
    r = requests.post(f"{BASE_URL}/reply/draft", json={
        "original_message": "Can we acquire the competitor company next week?",
        "message_sender": "ceo@corp.com",
        "message_channel": "email",
        "user_intent": "Accept the challenge"
    }, headers=headers)
    _check("Seed Reply Draft", r.status_code == 201)
    draft_id = r.json()["id"]

    # Step 3: Toggle Privacy Preferences to False
    print("\n[Step 3] Toggling all storage preferences to False...")
    r = requests.patch(f"{BASE_URL}/privacy/preferences", json={
        "store_reply_original_messages": False,
        "store_message_snippets": False,
        "store_calendar_titles": False,
        "store_task_descriptions": False
    }, headers=headers)
    _check("Toggle Preferences", r.status_code == 200)
    
    # Verify Audit Log
    r = requests.get(f"{BASE_URL}/privacy/audit-log", headers=headers)
    _check("Get Privacy Audit Log", r.status_code == 200)
    logs = r.json()
    _check("Verify update_preferences action logged", 
           any(l["action_type"] == "update_preferences" for l in logs),
           f"Logs count: {len(logs)}"
    )

    # Step 4: Seed data again and prove privacy enforcement
    print("\n[Step 4] Importing/Creating data again and proving privacy preferences are strictly enforced...")
    
    # Task with description disabled
    r = requests.post(f"{BASE_URL}/tasks", json={"title": "Private Task", "description": "This text must not be stored."}, headers=headers)
    _check("Create Task under Restriction", r.status_code == 201)
    _check("Task Description Enforced Null", r.json()["description"] is None)

    # Message snippet disabled
    r = requests.post(f"{BASE_URL}/messages/import/mock", json={
        "messages": [{
            "source": "mock",
            "external_message_id": "e2e-msg-restricted",
            "channel": "email",
            "sender": "friend@email.com",
            "subject": "Lunch",
            "snippet": "Lunch details snippet.",
            "received_at": "2026-05-21T13:00:00Z"
        }]
    }, headers=headers)
    _check("Import Message under Restriction", r.status_code == 200)
    _check("Message Snippet Enforced Null", r.json()["messages"][0]["snippet"] is None)

    # Calendar title placeholder replacement
    r = requests.post(f"{BASE_URL}/calendar/import/mock", json={
        "events": [{
            "provider": "mock",
            "external_event_id": "e2e-cal-restricted",
            "title": "Private Restructuring Plan",
            "start_time": "2026-05-22T13:00:00Z",
            "end_time": "2026-05-22T14:00:00Z"
        }]
    }, headers=headers)
    _check("Import Calendar under Restriction", r.status_code == 201)
    _check("Calendar Title Redacted to Placeholder", r.json()["events"][0]["title"] == "[redacted]")

    # Reply draft original message redacted
    r = requests.post(f"{BASE_URL}/reply/draft", json={
        "original_message": "Do not store this original message.",
        "message_sender": "boss@work.com",
        "message_channel": "email",
        "user_intent": "Decline"
    }, headers=headers)
    _check("Create Reply Draft under Restriction", r.status_code == 201)
    _check("Reply Original Message Redacted to Placeholder", r.json()["original_message"] == "[redacted]")

    # Step 5: Perform in-place targeted redactions
    print("\n[Step 5] Performing targeted in-place redactions on the step-2 seeded records...")
    
    # Task description redaction
    r = requests.delete(f"{BASE_URL}/tasks/{task_id}/description", headers=headers)
    _check("Redact Task Description", r.status_code == 200)
    _check("Verify Task Description in response is None", r.json()["description"] is None)

    # Message snippet redaction
    r = requests.delete(f"{BASE_URL}/messages/{message_id}/snippet", headers=headers)
    _check("Redact Message Snippet", r.status_code == 200)
    _check("Verify Message Snippet in response is None", r.json()["snippet"] is None)

    # Calendar title redaction
    r = requests.delete(f"{BASE_URL}/calendar/events/{calendar_id}/title", headers=headers)
    _check("Redact Calendar Title", r.status_code == 200)
    _check("Verify Calendar Title in response is [redacted]", r.json()["title"] == "[redacted]")

    # Reply Draft original message redaction
    r = requests.delete(f"{BASE_URL}/reply/drafts/{draft_id}/original-message", headers=headers)
    _check("Redact Reply Original Message", r.status_code == 200)
    _check("Verify Original Message in response is [redacted]", r.json()["original_message"] == "[redacted]")

    # Verify audit logs track all 4 targeted redactions
    r = requests.get(f"{BASE_URL}/privacy/audit-log", headers=headers)
    _check("Get Privacy Audit Log for Redactions", r.status_code == 200)
    redact_logs = [l for l in r.json() if l["action_type"] == "redact_field"]
    _check("Verify 4 redact_field logs exist", len(redact_logs) == 4, f"Found: {len(redact_logs)}")

    # Step 6: Data Retention Policy Execution
    print("\n[Step 6] Verifying Data Retention policy execution...")
    r = requests.patch(f"{BASE_URL}/privacy/preferences", json={
        "retention_days_messages": 30,
        "retention_days_reply_drafts": 30
    }, headers=headers)
    _check("Set Retention Days", r.status_code == 200)

    r = requests.post(f"{BASE_URL}/privacy/apply-retention", headers=headers)
    _check("Apply Retention Policy Manually", r.status_code == 200)
    counts = r.json()["pruned_counts"]
    _check("Verify apply-retention response format", "pruned_messages" in counts)

    # Step 7: Redacted Export (Non-mutating)
    print("\n[Step 7] Checking redacted export (non-mutating)...")
    r = requests.get(f"{BASE_URL}/user/export-data?redacted=true", headers=headers)
    _check("Export Redacted Data", r.status_code == 200)
    export_payload = r.json()
    
    draft_in_export = [d for d in export_payload["reply_drafts"] if d["id"] == draft_id][0]
    _check("Exported Reply Draft Redacted", draft_in_export["original_message"] == "[redacted]")

    r = requests.get(f"{BASE_URL}/reply/drafts/{draft_id}", headers=headers)
    _check("Fetch Draft from DB", r.status_code == 200)
    _check("DB Value Persisted", r.json()["original_message"] == "[redacted]")

    # Step 8: Confirmed Complete Erasure
    print("\n[Step 8] Triggering confirmed complete erasure...")
    r = requests.delete(f"{BASE_URL}/user/delete-data?confirm=true", headers=headers)
    _check("Complete Erasure", r.status_code == 200)
    
    # Verify everything is gone
    r_tasks = requests.get(f"{BASE_URL}/tasks", headers=headers)
    _check("Tasks list is empty", len(r_tasks.json()) == 0)

    r_messages = requests.get(f"{BASE_URL}/messages", headers=headers)
    _check("Messages list is empty", len(r_messages.json()) == 0)

    r_drafts = requests.get(f"{BASE_URL}/reply/drafts", headers=headers)
    _check("Reply drafts list is empty", len(r_drafts.json()) == 0)

    r_logs = requests.get(f"{BASE_URL}/privacy/audit-log", headers=headers)
    _check("Audit log is empty", len(r_logs.json()) == 0)

    print("\n" + "=" * 80)
    print("ALL HTTP-ONLY POSTGRES COMPATIBILITY LIVE-SERVER E2E PRIVACY TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    main()
