"""
Utility: extract user_id from request header.

For local development, every request can pass:
  X-User-ID: demo-user

If no header is present, defaults to "demo-user".
This will be replaced with real JWT-based auth when connecting to Supabase.
"""

from fastapi import Header
from typing import Optional
from app.core.config import get_settings

settings = get_settings()


def get_user_id(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
) -> str:
    """
    FastAPI dependency: returns user_id from X-User-ID header.
    Falls back to the configured default (demo-user) if not provided.
    """
    return x_user_id or settings.default_user_id
