"""
NeuroSentio Copilot Agent — FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.api.routes import health, profile, tasks, energy, copilot, decompose, micro_actions, morning_plan, transitions, reply, llm_usage, calendar, overload, messages, next_action, replan, privacy


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="NeuroSentio Copilot Agent",
    description=(
        "The standalone backend brain of NeuroSentio Daily Copilot. "
        "Manages user profiles, tasks, energy logs, and generates "
        "rule-based and LLM-powered daily plans. "
        "Designed for neurodivergent-friendly pacing."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────
# In production, lock origins to configured CORS_ORIGINS allowlist.
# In development, allow all origins for convenience.
_cors_origins = settings.cors_origins if settings.is_production else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ───────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(profile.router)
app.include_router(tasks.router)
app.include_router(energy.router)
app.include_router(copilot.router)
app.include_router(decompose.router)       # POST /tasks/{id}/decompose, GET /tasks/{id}/micro-actions
app.include_router(micro_actions.router)   # PATCH /micro-actions/{id}/status, POST /micro-actions/{id}/make-smaller
app.include_router(morning_plan.router)    # POST /copilot/morning-plan, GET /copilot/morning-plan/today
app.include_router(transitions.router)     # POST /transitions/generate, GET /transitions, etc.
app.include_router(reply.router)           # POST /reply/draft, GET|PATCH|DELETE /reply/drafts
app.include_router(llm_usage.router)       # GET /llm/usage, GET /llm/usage/summary
app.include_router(calendar.router)
app.include_router(overload.router)
app.include_router(messages.router)        # POST /messages/import/mock, GET /messages, etc.
app.include_router(next_action.router)     # GET /copilot/next-action, POST /{id}/done|snooze|skip|defer
app.include_router(replan.router)          # POST /copilot/replan, GET /copilot/replan/events
app.include_router(privacy.router)


