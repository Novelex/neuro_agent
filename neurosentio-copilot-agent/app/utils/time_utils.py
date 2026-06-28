"""
Utility: user identity extraction.

DEPRECATED: This module re-exports `get_current_user_id` from `app.core.auth`
for backward compatibility. New code should import directly from `app.core.auth`.

The old `get_user_id` function is preserved as an alias.
"""

from app.core.auth import get_current_user_id

# Backward-compatible alias — existing tests and internal code may reference this.
get_user_id = get_current_user_id
