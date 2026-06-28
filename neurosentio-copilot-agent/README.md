# NeuroSentio Copilot Agent 🧠

A standalone, local-first backend — the brain of **NeuroSentio Daily Copilot**.  
Designed for neurodivergent-friendly executive function support.

**Current version: 0.6.0 (Execution Automation Pack)**  
**Status: 188 tests passing | 44 business endpoints**

---

## 1. What this service does

| Feature | Day | Description |
|---|---|---|
| **User Profiles** | 1–2 | Sensory preferences, tone, energy windows |
| **Task Management** | 1–2 | Full CRUD with energy/sensory cost tagging |
| **Energy Logging** | 1–2 | Battery level, sensory state, mood tracking |
| **Copilot Dashboard** | 1–2 | Aggregated view with smart next-action priority chain |
| **Quick Plan** | 1–2 | Rule-based daily plan with recovery mode |
| **Overload Detection** | 1–2 | Risk scoring engine (0–100) |
| **Task Decomposition** | 3–4 | LLM-powered micro-action generation (mock by default) |
| **Make Smaller** | 3–4 | Split any micro-action into 1–3 child actions |
| **Morning Plan** | 5 | Full daily plan: scheduled micro-actions + recovery blocks + transitions |
| **Transition Scripts** | 6 | Gentle step-by-step scripts for 7 transition types |
| **Reply Drafter** | 7–8 | Paste any message → get short/warm/detailed reply options. Never sends. |
| **Alembic Migrations** | 5 | Schema versioning with SQLite batch support |
| **Prompt Versioning** | 9 | All prompts in `app/prompts/` with version strings (e.g. `task_decomposition_v1`) |
| **LLM Usage Logging** | 9 | Metadata-only log per call (no prompt text). Cost estimation, latency tracking. |
| **Rate Limiting** | 9 | Daily (50) + monthly (1000) per-user limits. Graceful fallback on limit. |
| **Prompt Safety** | 10 | 16-pattern injection detector. Prepends safety note. Never blocks response. |
| **Usage API** | 10 | `GET /llm/usage` + `GET /llm/usage/summary` — user-scoped metadata only. |
| **Supabase JWT Auth** | 11 | HS256 JWT verification via `SUPABASE_JWT_SECRET`. Modular for future JWKS. |
| **Postgres Support** | 11 | `DATABASE_URL` supports both SQLite (local) and PostgreSQL (production). |
| **Auth Middleware** | 11 | `get_current_user_id` dependency with dev/production mode switching. |

All responses use **neurodivergent-friendly language** — no shame, no pressure, no "just focus".

---

## 1b. Authentication

### Development Mode (default)

```env
APP_ENV=development
ALLOW_DEV_USER_HEADER=true
AUTH_REQUIRED=false
```

In development mode, any request can include `X-User-ID: your-test-id` as a header.
If no header is present, requests default to `demo-user`.  
This is convenient for local testing with curl, Postman, or the test client.

> ⚠️ **Never enable `ALLOW_DEV_USER_HEADER=true` in production.** It allows anyone to impersonate any user.

### Production Mode

```env
APP_ENV=production
ALLOW_DEV_USER_HEADER=false
AUTH_REQUIRED=true
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
SUPABASE_JWT_AUDIENCE=authenticated
```

In production mode:
- `X-User-ID` header is **rejected** — it cannot be used to identify users.
- All user-data endpoints require `Authorization: Bearer <jwt>`.
- The JWT is verified using `SUPABASE_JWT_SECRET` (HS256).
- The `sub` claim in the JWT payload becomes the `user_id`.
- Missing, invalid, or expired tokens return `401 Unauthorized`.
- `GET /health` remains public (no auth required).

### JWT Verification Strategy

| Method | Config | Status |
|---|---|---|
| **HS256** (symmetric) | `SUPABASE_JWT_SECRET` | ✅ Implemented |
| **RS256/ES256** (asymmetric) | `SUPABASE_JWKS_URL` | 🔜 Placeholder (not yet implemented) |

**HS256** using `SUPABASE_JWT_SECRET` is acceptable for initial Supabase integration, especially for legacy projects.  
**JWKS** (asymmetric keys) is the recommended longer-term production path for newer Supabase projects.  
JWKS support should be added before public production launch if the Supabase project uses asymmetric signing keys.

Find your JWT secret in: **Supabase Dashboard → Settings → API → JWT Secret**

### How to Test Auth

```bash
# Run auth unit tests
python -m pytest tests/test_auth.py -v

# Run E2E auth verification (start server first)
python -m scripts.e2e_auth_verify
```

---

## 1c. Database Configuration

### SQLite (Local Development)

```env
DATABASE_URL=sqlite:///./neurosentio.db
```

SQLite is the default. No external database needed. Perfect for local dev and testing.

### PostgreSQL / Supabase (Production)

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
```

Use the **direct connection** URL from Supabase (not the pooler URL) for server-side applications.  
Find it in: **Supabase Dashboard → Settings → Database → Connection String → URI**

### Running Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Check current migration status
alembic current
```

Migrations use `render_as_batch=True`, which is compatible with both SQLite and PostgreSQL.

### Current Limitations

- SQLite remains fully supported for local development.
- PostgreSQL/Supabase is recommended for production.
- Real Supabase Postgres has not been tested in this step (no credentials connected).
- JWKS verification is documented but not yet implemented.

---

## 2. Install locally (without Docker)

### Prerequisites
- Python 3.12+
- pip

### Steps

```bash
# 1. Navigate into the project
cd neurosentio-copilot-agent

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy environment file
cp .env.example .env

# 6. Run migrations (first time setup)
alembic upgrade head

# 7. Start the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open: http://127.0.0.1:8000/docs

---

## 3. Database Migrations (Alembic)

Day 5 introduces Alembic for schema versioning.

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after editing models
alembic revision --autogenerate -m "describe_your_change"

# Roll back one step
alembic downgrade -1

# View current migration state
alembic current

# View migration history
alembic history
```

> **SQLite limitation**: SQLite does not natively support `ALTER COLUMN` or `DROP COLUMN`.
> Alembic uses `render_as_batch=True` (copy strategy) to work around this.
> This is safe for local development. When switching to PostgreSQL, remove the batch flag.

---

## 4. Run with Docker

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d

# Stop
docker compose down
```

---

## 5. Run tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run only Day 5–6 tests
python -m pytest tests/test_day56.py -v

# Run with short traceback
python -m pytest tests/ -v --tb=short
```

---

## 6. Environment Variables

Copy `.env.example` to `.env` before running.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `neurosentio-copilot-agent` | Service name |
| `APP_VERSION` | `0.2.0` | Version string |
| `DATABASE_URL` | `sqlite:///./neurosentio.db` | SQLite path |
| `DEFAULT_USER_ID` | `demo-user` | Fallback user ID for dev |
| `USER_ID_HEADER` | `X-User-ID` | Header name for user identity |
| `LLM_PROVIDER` | `mock` | `mock`, `anthropic`, or `openai` |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required if `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | _(empty)_ | Required if `LLM_PROVIDER=openai` |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM request timeout |

---

## 7. API Endpoints (32 total)

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health check |

### Profile
| Method | Path | Description |
|---|---|---|
| GET | `/profile` | Get or auto-create user profile |
| PUT | `/profile` | Update profile |

### Tasks
| Method | Path | Description |
|---|---|---|
| GET | `/tasks` | List tasks (`?status=open\|done\|active`) |
| POST | `/tasks` | Create task |
| PATCH | `/tasks/{id}` | Update task fields |
| PATCH | `/tasks/{id}/status` | Update task status |
| DELETE | `/tasks/{id}` | Delete task |

### Energy
| Method | Path | Description |
|---|---|---|
| POST | `/energy/log` | Log energy reading |
| GET | `/energy/latest` | Get latest energy |
| GET | `/energy/history` | Get energy history |

### Task Decomposition
| Method | Path | Description |
|---|---|---|
| POST | `/tasks/{id}/decompose` | Decompose task into micro-actions |
| GET | `/tasks/{id}/micro-actions` | List micro-actions for task |

### Micro-Actions
| Method | Path | Description |
|---|---|---|
| PATCH | `/micro-actions/{id}/status` | Update status (done/snoozed/deferred/skipped) |
| POST | `/micro-actions/{id}/make-smaller` | Split into smaller child actions |

### Copilot
| Method | Path | Description |
|---|---|---|
| GET | `/copilot/dashboard` | Dashboard with smart next-action |
| GET | `/copilot/context` | Raw context (profile + tasks + energy) |
| POST | `/copilot/quick-plan` | Rule-based quick plan |
| POST | `/copilot/morning-plan` | Generate full morning plan |
| GET | `/copilot/morning-plan/today` | Get today's plan |

### Transitions
| Method | Path | Description |
|---|---|---|
| POST | `/transitions/generate` | Generate a transition script |
| GET | `/transitions` | List all user's scripts |
| GET | `/transitions/{type}/latest` | Get latest script for a type |
| PATCH | `/transitions/{id}/rating` | Rate a script (1–5) |
| POST | `/transitions/{id}/used` | Mark script as used |
| DELETE | `/transitions/{id}` | Delete script |

---

## 8. Example curl Commands

### Create a task
```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "title": "Prepare quarterly review slides",
    "description": "Build the first version of the slides",
    "priority": "high",
    "estimated_energy": "medium"
  }'
```

### Log energy
```bash
curl -X POST http://127.0.0.1:8000/energy/log \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "battery_level": 38,
    "sensory_state": "overstimulated",
    "note": "Feeling tired after meetings",
    "mood": "drained"
  }'
```

### Decompose a task into micro-actions
```bash
curl -X POST http://127.0.0.1:8000/tasks/{task_id}/decompose \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "current_energy": 38,
    "max_actions": 3,
    "force_regenerate": false
  }'
```

### Generate a morning plan
```bash
curl -X POST http://127.0.0.1:8000/copilot/morning-plan \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "current_energy": 38,
    "sensory_state": "overstimulated",
    "available_minutes": 90,
    "start_time": "09:00",
    "auto_decompose": true,
    "include_transition_scripts": true,
    "force_regenerate": false
  }'
```

### Generate a starting_work transition script
```bash
curl -X POST http://127.0.0.1:8000/transitions/generate \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "transition_type": "starting_work",
    "current_energy": 38,
    "sensory_state": "overstimulated",
    "next_task_title": "Prepare quarterly review slides",
    "context_note": "I am avoiding starting",
    "max_steps": 5
  }'
```

### Generate a making_call transition script
```bash
curl -X POST http://127.0.0.1:8000/transitions/generate \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "transition_type": "making_call",
    "current_energy": 45,
    "next_task_title": "Call supplier about invoice",
    "context_note": "I keep avoiding the call",
    "max_steps": 4
  }'
```

### Get the copilot dashboard
```bash
curl -H "X-User-ID: demo-user" http://127.0.0.1:8000/copilot/dashboard
```

### Mark micro-action done
```bash
curl -X PATCH http://127.0.0.1:8000/micro-actions/{id}/status \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{"status": "done"}'
```

### Rate a transition script
```bash
curl -X PATCH http://127.0.0.1:8000/transitions/{id}/rating \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{"success_rating": 4}'
```

---

## 9. Morning Plan — How It Works

1. Reads latest energy log (or uses `current_energy` from request).
2. Calculates overload risk score (0–100).
3. **Recovery mode** activates if energy < 30 or risk ≥ 60:
   - Selects 1–2 lowest-friction micro-actions.
   - Adds a recovery block ("Step away. Drink water. No tasks right now.").
4. **Normal mode**: selects 3–5 micro-actions scaled to `available_minutes`.
5. If `auto_decompose=true`: tasks with no micro-actions are automatically decomposed.
6. Assigns scheduled times starting from `start_time`.
7. Saves plan to DB and links micro-actions to `plan_id`.
8. If `include_transition_scripts=true`: adds up to 2 transition suggestions.

---

## 10. Transition Scripts — 7 Types

| Type | When to use |
|---|---|
| `leaving_house` | Before leaving — gentle object check |
| `starting_work` | Beginning a work session — reduce context switching |
| `making_call` | Before a phone call — first sentence, pause permission |
| `ending_day` | Closing the day — shutdown boundary, note tomorrow's start |
| `context_switch` | Switching between tasks — write "start here next" |
| `recovery_break` | Low energy — screen away, water, no productivity demand |
| `custom` | Any other transition |

**Recovery mode**: if `current_energy < 30`, the script is capped at 3 steps automatically.

---

## 11. Dashboard — Next-Action Priority Chain

The dashboard `suggested_next_action` follows this priority:

1. **`planned_micro_action`** — first open action from today's morning plan
2. **`existing_micro_action`** — first open action from top task (no plan)
3. **`needs_decomposition`** — top task has no micro-actions yet
4. **`add_task`** — no open tasks at all
5. **`log_energy`** — no energy reading available
6. **`recovery`** — recovery mode fallback

---

## 12. Make-Smaller Behavior (Day 5 fix)

When `POST /micro-actions/{id}/make-smaller` is called:

- The **original** action is set to `status = deferred`.
- 1–3 **child** actions are created with `status = open`.
- Each child stores `parent_micro_action_id = original.id`.
- The dashboard immediately moves to the child actions — the oversized action is gone.
- Recovery mode (energy < 30) creates only 1 child action.

---

## 13. Current Limitations

| Limitation | Notes |
|---|---|
| No real auth | `X-User-ID` header is a dev proxy — add JWT for production |
| Transition scripts are rule-based | LLM-powered generation is a Day 7 upgrade |
| Morning plan uses simple rules | No calendar awareness, no time-of-day optimization |
| No pagination | List endpoints return all rows — add before scaling |
| SQLite only | Switch `DATABASE_URL` to PostgreSQL for production |

---

## 14. Recommended Day 7–8 Work

1. **LLM-powered transition scripts** — use Anthropic/OpenAI for context-aware script generation
2. **Morning plan LLM summary** — have the LLM write the daily summary message
3. **Pagination** — add `limit` / `offset` to all list endpoints
4. **JWT auth** — replace `X-User-ID` header with Supabase JWT
5. **Supabase switch** — replace SQLite `DATABASE_URL` with Supabase PostgreSQL
6. **Weekly summary endpoint** — aggregate energy, completed tasks, and notes across 7 days

---

## 15. Reply Drafter (Day 7–8)

### What it does

Paste any message you received and get **3 neurodivergent-friendly reply options**: short, warm, and detailed. A **boundary reply** is included when appropriate.

All drafts are saved locally. **This feature never sends anything.**

### What it does NOT do

- ❌ Does not send emails
- ❌ Does not connect to Gmail, Outlook, or any email service
- ❌ Does not integrate with SMS, WhatsApp, or Slack (fields exist as placeholders only)
- ❌ Does not auto-send, schedule, or queue messages
- ❌ Does not read your inbox

### Privacy note

- Message text is pasted manually by the user
- Drafts are stored only in the local SQLite database
- No external connections are made for the drafting process
- Mock LLM is the default — no data leaves your machine

### Reply Drafter Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/reply/draft` | Generate and save reply draft options |
| `GET` | `/reply/drafts` | List all drafts (excludes deleted by default) |
| `GET` | `/reply/drafts/{id}` | Get one draft by ID |
| `PATCH` | `/reply/drafts/{id}` | Update: select option, edit reply, change status |
| `DELETE` | `/reply/drafts/{id}` | Soft delete (sets status=deleted) |

### Boundary Option Logic

A boundary reply is included when ANY of these are true:
- `current_energy < 40`
- `user_intent` contains: decline / delay / boundary / not available
- (regardless of `include_boundary_option` flag for the above)

When `include_boundary_option=False` and energy is high and intent is neutral, boundary is excluded.

### Fallback Behaviour

If the LLM fails or returns invalid output, rule-based drafts are generated automatically.
`source="fallback"` indicates this happened. The response shape is identical — no crash, no empty result.

### Valid Statuses (PATCH)

| Status | Meaning |
|---|---|
| `drafted` | Initial state after creation |
| `edited` | User has edited the reply text |
| `selected` | User has selected an option to send manually |
| `archived` | Kept but not active |
| `deleted` | Soft deleted — hidden from default list |

`sent` is **intentionally not a valid status** — this service never sends messages.

### Reply Drafter curl Examples

**Create a basic reply draft:**
```bash
curl -X POST http://127.0.0.1:8000/reply/draft \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "original_message": "Can you send me the updated report today?",
    "message_sender": "Sarah",
    "message_subject": "Updated report",
    "message_channel": "manual",
    "user_intent": "delay politely",
    "preferred_tone": "gentle_direct",
    "context_note": "I am low energy today",
    "include_boundary_option": true,
    "current_energy": 28
  }'
```

**List all drafts:**
```bash
curl http://127.0.0.1:8000/reply/drafts \
  -H "X-User-ID: demo-user"
```

**List deleted drafts:**
```bash
curl "http://127.0.0.1:8000/reply/drafts?status=deleted" \
  -H "X-User-ID: demo-user"
```

**Get one draft:**
```bash
curl http://127.0.0.1:8000/reply/drafts/{draft_id} \
  -H "X-User-ID: demo-user"
```

**Select an option and save edited reply:**
```bash
curl -X PATCH http://127.0.0.1:8000/reply/drafts/{draft_id} \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "selected_option_type": "short",
    "edited_reply": "Thanks — I will send it tomorrow morning.",
    "status": "edited"
  }'
```

**Soft delete a draft:**
```bash
curl -X DELETE http://127.0.0.1:8000/reply/drafts/{draft_id} \
  -H "X-User-ID: demo-user"
```

### Dashboard Integration

The `/copilot/dashboard` response now includes:
- `reply_drafts_count` — number of active (non-deleted) drafts
- `latest_reply_draft_id` — ID of the most recent draft (nullable)
- `latest_reply_draft_subject` — subject of the most recent draft (nullable)

Dashboard never fails if reply drafter is unavailable — defaults to 0 / null.

---

## 16. Execution Automation Pack (v0.6.0)

The **Execution Automation Pack** enables safe, distraction-free execution support for neurodivergent individuals by bridging incoming communications, immediate prioritization, and plan flexibility.

### 🛡️ Privacy Architecture (Metadata-Only)
To eliminate executive friction without sacrificing personal data privacy, this agent implements a **strict metadata-only ingestion architecture**:
1. **No Content Storage**: Full message or email bodies are **never** accepted, stored, or parsed.
2. **Strict Ingestion Limits**:
   - Only basic communication metadata is allowed (sender, channel, subject, datetime).
   - The message body/content is strictly truncated to a **maximum 500-character snippet** before database save.
   - Any sensitive fields such as *attachments*, *recipient lists*, *invitees*, or *meeting descriptions* are stripped out entirely during intake.
3. **No Background Sync Connections**: The service does not connect to live mailboxes (Gmail, Outlook) or SMS gateways. All metadata imports are user-initiated via mock import endpoints.

---

### 16a. Message Monitor
A manual/mock metadata-only message intake that respects privacy, flags urgency, and facilitates quick reply drafting.

#### Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/messages/import/mock` | Bulk import mock communication metadata (Email/SMS) |
| `GET` | `/messages` | List imported messages (filterable by `is_read`, `needs_reply`) |
| `GET` | `/messages/{id}` | Retrieve a single message detail |
| `PATCH` | `/messages/{id}/read` | Mark a message as read |
| `GET` | `/messages/analytics/urgency` | Retrieve real-time communication urgency analytics |

---

### 16b. Next Action Prompter
A prioritized, rule-based prompter chain returning exactly **one** best action to prevent task paralysis. It incorporates smart timeouts and snooze mechanics.

#### Action Priority Chain
1. **`log_energy`** (System Priority): Triggered if no energy log is present for the user within active boundaries.
2. **`take_recovery_break`** (Overload/Recovery Priority): Triggered if user energy battery level is under 30% or overload risk score is $\ge 60$. It chooses a low-friction micro-action first, or falls back to a 15-minute screen break.
3. **`do_micro_action`** (Plan Execution): Triggered if a morning plan contains open micro-actions.
4. **`draft_reply`** (Urgent Communication): Triggered if there are urgent messages needing reply (urgency score $\ge 40$).
5. **`decompose_task`** (Stuck Tasks): Triggered if high-priority tasks have remained stuck without actionable sub-steps.
6. **`review_plan`** (Fallback): Default fallback when the day's schedule is caught up.

#### Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/copilot/next-action` | Evaluates user state and returns the single best next action |
| `POST` | `/copilot/next-action/{id}/done` | Mark the action as done (auto-completes linked task/micro-actions) |
| `POST` | `/copilot/next-action/{id}/snooze` | Temporarily snooze action (snooze range: 5 to 1440 minutes) |
| `POST` | `/copilot/next-action/{id}/skip` | Skip the action (optionally updates linked micro-action status) |
| `POST` | `/copilot/next-action/{id}/defer` | Defer the action until a specified datetime |

---

### 16c. Adaptive Re-planner
Allows dynamic, non-destructive day plan adjustments triggered by low energy, skipped steps, calendar overload, or urgent messages.

#### Key Mechanics
- **State Preservation**: Completed work is **never** deleted or overridden; completed micro-actions remain linked to the historical timeline.
- **Smart Simplification**: Skipping $\ge 3$ actions automatically scales down the remaining active plan to at most **2** high-yield, low-energy actions.
- **Automatic Energy Sync**: If the user provides a `current_energy` reading in the replan request, a new database energy log is automatically created behind the scenes, ensuring all downstream prompter chains stay contextually aligned.

#### Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/copilot/replan` | Request an adaptive plan readjustment based on a dynamic trigger |
| `GET` | `/copilot/replan/events` | List all historical replan triggers and mode transition logs |

---

### 16d. Dashboard Automation Metrics
The `/copilot/dashboard` has been safely enhanced to summarize all execution automation telemetry under a user-scoped boundary:
- `unread_messages_count`
- `urgent_messages_count`
- `next_action_prompts_count`
- `replan_events_count`

---

## 17. Supabase-First Realtime Roadmap

To support local-first synchronization and real-time execution cues, the system is designed to leverage **Supabase-first native primitives** rather than Firebase:

```mermaid
graph TD
    A[Client App] -->|FastAPI REST| B[FastAPI Server]
    B -->|Persist Metadata| C[(PostgreSQL DB)]
    C -->|CDC / Realtime Replication| D[Supabase Realtime Engine]
    D -->|Realtime WebSockets| A
    B -->|Trigger Push Events| E[Supabase Edge Functions]
    E -->|Apple APNs / Google FCM| A
```

### Real-Time & Push Notification Stack
1. **Supabase Realtime (WebSockets)**:
   - Synchronizes next-action changes directly to mobile and web dashboards instantly as database state transitions (CDC).
   - Allows users to snooze, done, or skip actions on one device and have the update render instantly across their entire active setup.
2. **Supabase Edge Functions**:
   - Instead of running complex messaging infrastructure in the core backend, lightweight TypeScript Edge Functions listen to database webhooks on the `next_action_prompts` and `replan_events` tables.
   - Converts state alerts into push notifications dispatched to user devices safely and efficiently.
3. **Zero Firebase Footprint**:
   - The roadmap relies entirely on Supabase Edge Functions and standard platform gateways (APNs / FCM directly) to minimize external vendor dependencies and maintain a tight privacy envelope.

---

## 18. Privacy + API Contract + Live-Server Hardening Pack (v0.6.0)

This pack hardens the NeuroSentio Copilot Agent with strict privacy controls, safe data export, complete sequence-based user deletion, and a verified E2E HTTP verification layer.

### 🛡️ Core Features
1. **Enforced Granular Storage Controls**:
   - `store_message_snippets=false`: Messages imported have snippets blanked out on save.
   - `store_calendar_titles=false`: Calendar imports store `[redacted]` placeholders instead of real titles.
   - `store_reply_original_messages=false`: Original messages are redacted to `[redacted]` in the reply drafter.
   - `store_task_descriptions=false`: Creating or updating a task forces its description to `null`.
2. **Targeted Redactions (In-Place Purges)**:
   - Specific endpoints to redact/purge single text fields:
     - `DELETE /reply/drafts/{id}/original-message`
     - `DELETE /messages/{id}/snippet`
     - `DELETE /calendar/events/{id}/title`
     - `DELETE /tasks/{id}/description`
   - Automatically writes a `redact_field` entry to the privacy audit log.
3. **Non-Mutating Redacted Export**:
   - `GET /user/export-data?redacted=true` performs in-memory redaction for tasks, reply drafts, messages, calendar events, and transition scripts without updating underlying SQLite rows.
4. **Data Retention Policies**:
   - Toggles under preferences: `retention_days_messages`, `retention_days_reply_drafts`, `retention_days_calendar_events`, `retention_days_llm_usage_logs`.
   - Validated: only integers between `1` and `3,650` (or `null`) are allowed.
   - `POST /privacy/apply-retention` manually executes and trims expired entries from active user tables.
5. **Complete Purge / Deletion Sequence**:
   - `DELETE /user/delete-data?confirm=true` sequential transaction-based complete deletion of all user records (15 tables, including profile, privacy preferences, and privacy audit logs).

### 📋 Route Catalog
See the complete auto-generated route inventory at [reports/routes_inventory.md](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/reports/routes_inventory.md) and developer guide at [reports/curl_examples.md](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/reports/curl_examples.md).


## 19. Real LLM Provider Validation + Local Postgres Compatibility Testing Pack (v0.7.0)

This pack adds robust, enterprise-grade capabilities to support real LLM providers (Anthropic, OpenAI) and PostgreSQL 16 database verification while maintaining complete backward compatibility with mock/SQLite defaults.

### 🧠 LLM Provider Validation & Safety
1. **Lazy Imports & Key Safety**:
   - Anthropic and OpenAI clients lazily import `anthropic`/`openai` packages.
   - Default mock mode runs out-of-the-box with zero API keys or external package requirements.
   - If a real provider (Anthropic or OpenAI) is explicitly selected but the API key is missing or blank, `get_llm_client()` raises a clean, immediate `LLMError` configuration error.
2. **Provider Smoke Test Script**:
   - [scripts/smoke_test_providers.py](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/scripts/smoke_test_providers.py) executes service-level checks (task decomposition, reply drafting, transition scripts).
   - Performs strict Pydantic/JSON shape checks on return data.
   - Automatically tracks latency, cost estimation, and verifies prompt/log privacy.
   - Exits nonzero with clear error reporting if requested provider key is missing, or skips cleanly when testing `--provider all`.
3. **12-Case Prompt Quality Evaluation Suite**:
   - [scripts/evaluate_prompt_quality.py](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/scripts/evaluate_prompt_quality.py) runs a comprehensive suite of 12 distinct user diagnostic scenarios (energy bounds, injection immunity, low sensory/battery transitions).
   - Scans generated outputs for shame-based language, medical claims, task durations exceeding 15m, complex first steps, and prompt leakage.
   - Compiles sanitized, privacy-safe reports protecting user prompts/keys to `reports/prompt_eval_report.json` and `reports/prompt_eval_report.md`.

### 🐘 PostgreSQL 16 Local Integration
1. **Local Postgres Container Setup**:
   - A PostgreSQL 16 container service with dedicated health checks is specified in the [docker-compose.yml](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/docker-compose.yml).
2. **Migration & Native Type Checking**:
   - [scripts/check_postgres_migrations.py](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/scripts/check_postgres_migrations.py) maps `POSTGRES_DATABASE_URL` to `DATABASE_URL` for Alembic, wipes the schema, programmatically migrates to head, and queries `information_schema.columns` to verify native `json` and `timestamp` column types.
   - Includes a strict safety guard refusing schema wipes unless the DB name contains `"test"` or the `--allow-non-test-db` flag is explicitly provided.
3. **PostgreSQL Reserved Keywords & CRUD Check**:
   - Verifies SQLAlchemy's ability to cleanly quote and handle metadata-like fields (such as `detected_keywords`, `extra_metadata`, `raw_metadata`, `request_metadata`) on `message_items`, `calendar_events`, `llm_usage_logs`, and `next_action_prompts` tables.
4. **Live-Server HTTP E2E on Postgres**:
   - [scripts/e2e_postgres_live_server.py](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/scripts/e2e_postgres_live_server.py) executes a real multi-step workflow via HTTP requests against a live FastAPI server running in Postgres mode.
5. **Opt-In Pytest Support**:
   - [tests/test_postgres_compatibility.py](file:///c:/Users/daniy/Downloads/neuro_agent/neurosentio-copilot-agent/tests/test_postgres_compatibility.py) provides opt-in pytest assertions which skip gracefully if the Postgres container is unreachable.

## 20. Verification Status & Gap Resolution (v0.7.1)

This section documents the explicit verification status of the NeuroSentio Copilot Agent v0.7.1 following a comprehensive test run.

### ✅ Verified
The following features have been fully run, tested, and verified programmatically in the local environment:
- **Mock LLM Provider**: Fully tested with a custom standalone service-level smoke test (`scripts/smoke_test_providers.py --provider mock`) and direct schema validation.
- **SQLite Database**: 205 baseline tests passed, validating task decomposition, morning planning, reply drafting, overload/replan events, user profile management, privacy preferences/audit logs, data retention trimming, targeted redaction, and multi-step soft-deletion.
- **12-Case Prompt Quality Evaluation (Mock)**: Passed all 12 evaluation cases with zero violations on shame-based terminology, prompt injection, medical claims, duration caps, and step constraints (`scripts/evaluate_prompt_quality.py --provider mock`).

- **Local Postgres 16 Database**: Fully verified. The Docker Desktop daemon was utilized to run the Postgres schema migration checks programmatically, handle Postgres-native `json` and `timestamp` fields, and execute the full Live-Server HTTP E2E validation against a real Uvicorn server connected natively via `psycopg2`.

### ⚠️ Skipped / Not Verified
The following integrations or infrastructure components were skipped during verification and are **NOT verified**:
- **Real LLM Providers (Anthropic/OpenAI)**: Not verified. Real API credentials (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) were not provided, so live Anthropic/OpenAI client tests were skipped.
- **Supabase Live Deployment**: No live Supabase connection or deployment was configured or run (stubbed/mocked locally).
- **JWKS Authentication**: JWT signature checks are verified using standard mocked RS256/HS256 tokens; a live external JWKS endpoint connection remains stubbed.
- **Real Google Calendar / Gmail**: Calendar and email imports are verified using mocks; direct OAuth2 connection to Google Calendar or Gmail is not implemented.
- **Flutter App Integration**: The Flutter mobile client codebase and mobile-to-backend integrations were not part of this backend validation suite.

> [!IMPORTANT]
> **Production Readiness Statement**: This release is verified for production-grade backend databases via PostgreSQL natively. However, it is **not yet certified** for real LLM integrations because live API keys were missing during this run. It remains fully verified for SQLite and Postgres offline-first operations using the mock AI provider.
