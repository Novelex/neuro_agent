"""Script to generate curl examples for the NeuroSentio Copilot Agent developer guide."""

import os

def generate_examples():
    os.makedirs("reports", exist_ok=True)
    
    curl_md = """# NeuroSentio Copilot Agent — Developer Curl Examples

This guide provides comprehensive curl examples for interacting with the backend API.
For development and local testing, you can bypass live Supabase JWT verification by providing the developer bypass header:
- `X-User-ID`: The target UUID of the mock user (e.g. `mock-user-123`).

If you are testing JWT authentication, pass the bearer token:
- `Authorization`: `Bearer <jwt_token>`

---

## 🔒 Privacy & Granular Data Controls

### 1. Retrieve Privacy Preferences
Gets or automatically initializes default privacy preferences for the user.
```bash
curl -X GET http://127.0.0.1:8000/privacy/preferences \\
  -H "X-User-ID: mock-user-123"
```

### 2. Update Privacy Preferences
Enables granular storage toggles and data retention policies (in days, between 1 and 3650, or null).
```bash
curl -X PATCH http://127.0.0.1:8000/privacy/preferences \\
  -H "X-User-ID: mock-user-123" \\
  -H "Content-Type: application/json" \\
  -d '{
    "store_reply_original_messages": false,
    "store_message_snippets": false,
    "store_calendar_titles": false,
    "store_task_descriptions": false,
    "retention_days_reply_drafts": 30,
    "retention_days_messages": 90,
    "retention_days_calendar_events": 180,
    "retention_days_llm_usage_logs": 365
  }'
```

### 3. View Privacy Audit Logs
Retrieves the reverse-chronological, non-sensitive audit history of privacy actions.
```bash
curl -X GET http://127.0.0.1:8000/privacy/audit-log \\
  -H "X-User-ID: mock-user-123"
```

---

## 📦 Data Portability & Erasure

### 1. Full Data Export (Raw)
Exports all owned data across all 14 database models.
```bash
curl -X GET http://127.0.0.1:8000/user/export-data \\
  -H "X-User-ID: mock-user-123"
```

### 2. Redacted Data Export (In-Memory Masking)
Exports all owned data but masks sensitive text columns strictly in-memory (does not mutate SQLite DB rows).
```bash
curl -X GET "http://127.0.0.1:8000/user/export-data?redacted=true" \\
  -H "X-User-ID: mock-user-123"
```

### 3. Complete Data Purge (Erasure)
Permanently wipes all user data in a single transactional sequence, leaving no trace.
```bash
curl -X DELETE "http://127.0.0.1:8000/user/delete-data?confirm=true" \\
  -H "X-User-ID: mock-user-123"
```

### 4. Manually Apply Data Retention
Trigger a manual execution of data retention pruning to delete expired messages, calendar events, reply drafts, and LLM logs.
```bash
curl -X POST http://127.0.0.1:8000/privacy/apply-retention \\
  -H "X-User-ID: mock-user-123"
```

---

## ✂️ Targeted Redactions (In-Place Purges)

### 1. Redact Reply Draft Original Message
```bash
curl -X DELETE http://127.0.0.1:8000/reply/drafts/{draft_id}/original-message \\
  -H "X-User-ID: mock-user-123"
```

### 2. Redact Message Snippet
```bash
curl -X DELETE http://127.0.0.1:8000/messages/{message_id}/snippet \\
  -H "X-User-ID: mock-user-123"
```

### 3. Redact Calendar Event Title
```bash
curl -X DELETE http://127.0.0.1:8000/calendar/events/{event_id}/title \\
  -H "X-User-ID: mock-user-123"
```

### 4. Redact Task Description
```bash
curl -X DELETE http://127.0.0.1:8000/tasks/{task_id}/description \\
  -H "X-User-ID: mock-user-123"
```

---

## 🏃 Transitions & Core Features

### 1. Generate a Transition Script
Unified script generator for neurodivergent recovery. Supported types include `leaving_house`, `starting_work`, `making_call`, `ending_day`, `context_switch`, `recovery_break`, and `custom`.
```bash
curl -X POST http://127.0.0.1:8000/transitions/generate \\
  -H "X-User-ID: mock-user-123" \\
  -H "Content-Type: application/json" \\
  -d '{
    "transition_type": "starting_work",
    "current_energy": 55,
    "context_note": "Transitioning into writing code for the privacy pack"
  }'
```

### 2. Rate a Transition Script
```bash
curl -X PATCH http://127.0.0.1:8000/transitions/{script_id}/rating \\
  -H "X-User-ID: mock-user-123" \\
  -H "Content-Type: application/json" \\
  -d '{
    "success_rating": 5
  }'
```

### 3. Create a Task
```bash
curl -X POST http://127.0.0.1:8000/tasks \\
  -H "X-User-ID: mock-user-123" \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "Build Privacy Test Suite",
    "description": "Create 25 exhaustive tests verifying granular privacy preferences and targeted redaction",
    "priority": "high",
    "estimated_energy": 45
  }'
```
"""
    
    examples_path = os.path.join("reports", "curl_examples.md")
    with open(examples_path, "w", encoding="utf-8") as f:
        f.write(curl_md.strip())
    print(f"Curl developer guide successfully generated at: {examples_path}")

if __name__ == "__main__":
    generate_examples()
