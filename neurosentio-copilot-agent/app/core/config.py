"""
Core configuration for NeuroSentio Copilot Agent.

Environment variables are loaded from .env file.
Supports development (SQLite + X-User-ID) and production (Postgres + JWT) modes.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "neurosentio-copilot-agent"
    app_version: str = "0.5.0"
    debug: bool = False

    # ── Environment ────────────────────────────────────────────────────
    app_env: str = "development"  # "development" | "production" | "testing"

    # ── CORS ───────────────────────────────────────────────────────────
    # In production, set CORS_ORIGINS to a comma-separated list of allowed origins.
    # In development, CORS is wide open regardless of this setting.
    cors_origins: List[str] = ["http://localhost:3000"]

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "sqlite:///./neurosentio.db"
    postgres_test_database_url: Optional[str] = None
    
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_database_url: str = ""

    def __init__(self, **values):
        super().__init__(**values)
        try:
            import psycopg  # type: ignore
        except ImportError:
            try:
                import psycopg2  # type: ignore
                if self.postgres_database_url.startswith("postgresql+psycopg://"):
                    self.postgres_database_url = self.postgres_database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")
                if self.database_url.startswith("postgresql+psycopg://"):
                    self.database_url = self.database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")
            except ImportError:
                pass

    # ── Auth: Development fallback ─────────────────────────────────────
    allow_dev_user_header: bool = True
    default_user_id: str = "demo-user"
    user_id_header: str = "X-User-ID"

    # ── Auth: Supabase JWT ─────────────────────────────────────────────
    auth_required: bool = False
    supabase_url: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_jwks_url: Optional[str] = None
    supabase_jwt_audience: str = "authenticated"
    supabase_database_url: Optional[str] = None

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
