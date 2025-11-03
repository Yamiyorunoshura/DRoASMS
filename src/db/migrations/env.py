from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Engine
import structlog

# Alembic Config object, provides access to `.ini` values.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

LOGGER = structlog.get_logger(__name__)


def _database_url() -> str:
    load_dotenv(override=False)
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set to run database migrations.")
    return url


def run_migrations_offline() -> None:
    """Run migrations without creating a SQLAlchemy engine."""
    context.configure(
        url=_database_url(),
        target_metadata=None,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()
        LOGGER.info("alembic.migrations.run", mode="offline")


def run_migrations_online() -> None:
    """Run migrations using a SQLAlchemy engine."""
    configuration: dict[str, Any] = dict(config.get_section(config.config_ini_section) or {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable: Engine = create_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()
            LOGGER.info("alembic.migrations.run", mode="online")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
