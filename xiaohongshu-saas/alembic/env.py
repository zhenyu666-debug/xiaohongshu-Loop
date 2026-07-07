"""Alembic environment script for xhs-saas.

Uses the synchronous SQLAlchemy URL (sqlite:///./data/xhs_saas.db) for
migrations, since alembic's async support is still experimental. The
runtime app keeps using aiosqlite; alembic operations only need plain
sqlite to read/write schema metadata.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure app.* imports resolve when alembic is invoked from any cwd.
HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

# Inline the resolved DB URL -- +asyncpg/aiosqlite drivers don't work with
# alembic's offline/online migration story; strip them.
db_url = settings.database_url
for async_dialect in ("+aiosqlite", "+asyncpg", "+asyncmy"):
    db_url = db_url.replace(async_dialect, "")
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # sqlite ALTER support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # sqlite ALTER support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()