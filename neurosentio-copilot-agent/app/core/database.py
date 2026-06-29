"""
Database engine, session factory, and base model setup.

Supports:
  - SQLite for local development (connect_args for thread safety)
  - PostgreSQL/Supabase for production (no SQLite-specific args)

Set DATABASE_URL in .env to switch between backends.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

engine = None
SessionLocal = None

def _init_engine():
    global engine, SessionLocal
    if engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
        engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            echo=settings.debug,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass

def get_db():
    """FastAPI dependency: yields a database session and ensures it is closed."""
    _init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup (dev convenience)."""
    # Import all models so their tables are registered on Base.metadata
    from app.models import user_profile, task, energy_log, copilot_plan, micro_action  # noqa: F401
    from app.models import transition_script, reply_draft, llm_usage_log  # noqa: F401
    from app.models import calendar_event, overload_event  # noqa: F401
    from app.models import message_item, next_action_prompt, replan_event  # noqa: F401
    from app.models import privacy_preferences, privacy_audit_log  # noqa: F401
    _init_engine()
    Base.metadata.create_all(bind=engine)
