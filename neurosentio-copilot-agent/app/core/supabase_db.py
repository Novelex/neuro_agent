"""
Direct Supabase connection for the AI Proxy Backend.
Uses psycopg2 connection pooling directly to interact with Supabase Postgres.
"""

from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from app.core.config import get_settings
import psycopg2
import logging

logger = logging.getLogger(__name__)

_pool = None
_db_url = None


def _init_supabase_pool():
    global _pool, _db_url
    if _pool is None:
        settings = get_settings()
        _db_url = getattr(settings, "supabase_database_url", settings.database_url)

        if _db_url is None:
            raise ValueError("Database URL is missing. Please set DATABASE_URL or SUPABASE_DATABASE_URL environment variable.")

        # If the local sqlite fallback is present, raise an error
        # (psycopg2 does not support sqlite).
        if "sqlite" in _db_url:
            raise ValueError("SQLite is not supported. Please configure SUPABASE_DATABASE_URL with a PostgreSQL connection string.")

        logger.info("Initializing ThreadedConnectionPool for PostgreSQL...")

        # Connection pooling optimized for Supabase Pooler
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=_db_url,
        )


def _is_connection_alive(conn) -> bool:
    """Ping the server with a cheap query to verify the connection is still open."""
    try:
        conn.cursor().execute("SELECT 1")
        conn.rollback()  # reset any transaction state from the ping
        return True
    except Exception:
        return False


def _get_healthy_connection():
    """
    Get a connection from the pool and verify it is alive.
    If the connection is stale (closed by Supabase timeout), discard it
    and open a fresh one directly so the pool stays usable.
    """
    conn = _pool.getconn()

    if not _is_connection_alive(conn):
        logger.warning("Stale DB connection detected — replacing with a fresh connection.")
        try:
            _pool.putconn(conn, close=True)
        except Exception:
            pass
        # Open a fresh connection outside the pool for this request
        conn = psycopg2.connect(_db_url)

    return conn


@contextmanager
def get_db_connection():
    """
    Yields a healthy psycopg2 database connection.
    Detects and replaces stale connections that were closed by the server
    (e.g. after Supabase's idle-connection timeout).
    """
    _init_supabase_pool()
    conn = _get_healthy_connection()
    is_pooled = conn in [_pool._pool[k] for k in _pool._pool] if hasattr(_pool, "_pool") else False
    broken = False
    try:
        yield conn
    except psycopg2.DatabaseError:
        broken = True
        raise
    finally:
        if broken:
            # Don't return a broken connection to the pool — close it instead
            try:
                conn.close()
            except Exception:
                pass
        else:
            try:
                _pool.putconn(conn)
            except Exception:
                # Connection was opened fresh (outside pool) — just close it
                try:
                    conn.close()
                except Exception:
                    pass


def get_supabase_db():
    """FastAPI dependency: yields a psycopg2 database connection."""
    with get_db_connection() as conn:
        yield conn

