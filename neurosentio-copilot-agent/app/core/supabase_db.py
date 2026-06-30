"""
Direct Supabase connection for the AI Proxy Backend.
Uses SQLAlchemy Core to execute raw SQL against the Supabase Postgres instance.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

engine = None
SessionLocal = None

def _init_supabase_engine():
    global engine, SessionLocal
    if engine is None:
        settings = get_settings()
        
        # Use SUPABASE_DATABASE_URL if available, fallback to DATABASE_URL
        db_url = getattr(settings, "supabase_database_url", settings.database_url)
        
        engine = create_engine(
            db_url,
            # Connection pooling optimized for Supabase Pooler (port 6543)
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=settings.debug,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_supabase_db():
    """FastAPI dependency: yields a Supabase database session."""
    _init_supabase_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
