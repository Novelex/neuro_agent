"""
Database engine, session factory, and base model setup.
Uses SQLite for local development; swap DATABASE_URL for Postgres/Supabase later.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

# connect_args only needed for SQLite (thread-safety)
connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}

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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup (dev convenience)."""
    # Import all models so their tables are registered on Base.metadata
    from app.models import user_profile, task, energy_log, copilot_plan, micro_action  # noqa: F401
    Base.metadata.create_all(bind=engine)
