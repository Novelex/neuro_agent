"""
Core configuration for NeuroSentio Copilot Agent.
Environment variables are loaded from .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "neurosentio-copilot-agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./neurosentio.db"

    # Default user fallback (for local dev without auth)
    default_user_id: str = "demo-user"

    # Header name for user identification
    user_id_header: str = "X-User-ID"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
