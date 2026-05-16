"""
NeuroSentio Copilot Agent — FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.api.routes import health, profile, tasks, energy, copilot, decompose, micro_actions, morning_plan, transitions

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

# ── CORS (wide open for local dev) ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
