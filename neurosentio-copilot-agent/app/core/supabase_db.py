"""
Direct Supabase connection for the AI Proxy Backend.
Uses psycopg2 connection pooling directly to interact with Supabase Postgres.
"""

from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

_pool = None

def _init_supabase_pool():
    global _pool
    if _pool is None:
        settings = get_settings()
        db_url = getattr(settings, "supabase_database_url", settings.database_url)
        
        if db_url is None:
            raise ValueError("Database URL is missing. Please set DATABASE_URL or SUPABASE_DATABASE_URL environment variable.")

        # If the local sqlite fallback is present, raise an error 
        # (psycopg2 does not support sqlite).
        if "sqlite" in db_url:
            raise ValueError("SQLite is not supported. Please configure SUPABASE_DATABASE_URL with a PostgreSQL connection string.")
            
        logger.info("Initializing ThreadedConnectionPool for PostgreSQL...")
        
        # Connection pooling optimized for Supabase Pooler
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=db_url,
        )

@contextmanager
def get_db_connection():
    """Yields a psycopg2 database connection from the pool."""
    _init_supabase_pool()
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)

def get_supabase_db():
    """FastAPI dependency: yields a psycopg2 database connection."""
    with get_db_connection() as conn:
        yield conn
