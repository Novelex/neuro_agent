"""
Alembic environment — configured for NeuroSentio Copilot Agent.

Reads DATABASE_URL from the app's config so we don't duplicate the URL.
Imports all ORM models so autogenerate detects schema changes.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Ensure project root is on sys.path ────────────────────────────────
# This allows `from app.xxx import ...` to resolve correctly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Alembic Config object ─────────────────────────────────────────────
config = context.config

# ── Set sqlalchemy.url from app config (avoids duplication) ──────────
from app.core.config import get_settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# ── Logging ───────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ALL models so autogenerate detects them ────────────────────
from app.core.database import Base  # noqa: F401 — imports Base.metadata

# Import every model module to register tables with Base.metadata
import app.models.user_profile       # noqa: F401
import app.models.task                # noqa: F401
import app.models.energy_log          # noqa: F401
import app.models.micro_action        # noqa: F401
import app.models.copilot_plan        # noqa: F401
import app.models.transition_script   # noqa: F401

target_metadata = Base.metadata


# ──────────────────────────────────────────────────────────────────────
# Migration runners
# ──────────────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Offline mode: emit SQL to stdout / a file without connecting.
    Useful for generating SQL scripts to review or apply manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite-safe — don't try to render server-side defaults
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the DB and apply migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Required for SQLite ALTER TABLE support (uses COPY strategy)
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
