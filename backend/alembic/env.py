"""Alembic environment for the LIFE OS core store. The URL comes from the config (set by app.lifeos.db.init) or LIFEOS_DATABASE_URL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lifeos.db import Base  # noqa: E402

config = context.config
if os.environ.get("LIFEOS_DATABASE_URL") and not config.get_main_option("sqlalchemy.url", "").startswith(("sqlite:////", "postgresql")):
    config.set_main_option("sqlalchemy.url", os.environ["LIFEOS_DATABASE_URL"])
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
