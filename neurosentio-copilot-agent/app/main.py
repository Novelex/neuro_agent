"""
NeuroSentio Copilot Agent — FastAPI application entry point.
"""

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import (
    health,
    decompose,
    micro_actions,
    morning_plan,
    transitions,
    reply,
    replan
)

settings = get_settings()

app = FastAPI(
    title="NeuroSentio Copilot Agent (AI Proxy)",
    description=(
        "The standalone backend brain of NeuroSentio Daily Copilot. "
        "Acts as a proxy for OpenRouter LLM requests."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────
_cors_origins = settings.cors_origins if settings.is_production else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routes ───────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(decompose.router)       # POST /tasks/{id}/decompose
app.include_router(micro_actions.router)   # PATCH /micro-actions/{id}/status, POST /micro-actions/{id}/make-smaller
app.include_router(morning_plan.router)    # POST /copilot/morning-plan
app.include_router(transitions.router)     # POST /transitions/generate
app.include_router(reply.router)           # POST /reply/draft
app.include_router(replan.router)          # POST /copilot/replan
