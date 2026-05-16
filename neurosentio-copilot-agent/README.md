# NeuroSentio Copilot Agent 🧠

A standalone, local-first backend — the brain of **NeuroSentio Daily Copilot**.  
Designed for neurodivergent-friendly executive function support.

**Current version: 0.2.0 (Day 5–6)**  
**Status: 54 tests passing | 26 business endpoints**

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
| **Alembic Migrations** | 5 | Schema versioning with SQLite batch support |

All responses use **neurodivergent-friendly language** — no shame, no pressure, no "just focus".

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
