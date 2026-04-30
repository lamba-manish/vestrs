"""Alembic env — runs the same migrations against every environment.

The DB URL comes from ``app.core.config.Settings`` so there is one source of
truth for connection details. Migrations run online (sync) with a sync URL
because Alembic's online mode expects sync; we coerce ``+asyncpg`` URLs to
``+psycopg`` (or plain) for the migration run only — the application keeps
using the async URL.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app` importable when alembic is invoked from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.types import UUIDType  # noqa: E402
from app.models import *  # noqa: F403, E402  — register all models on metadata

config = context.config


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    # Render our UUIDType as postgresql.UUID(as_uuid=True) so generated
    # migrations don't depend on the application package.
    if type_ == "type" and isinstance(obj, UUIDType):
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")  # type: ignore[attr-defined]
        return "postgresql.UUID(as_uuid=True)"
    return False  # fall through to default rendering


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url() -> str:
    # Tests + tooling can override via ``cfg.set_main_option("sqlalchemy.url", ...)``;
    # otherwise we use the project Settings (the same source the running app uses).
    override = config.get_main_option("sqlalchemy.url")
    url = override if override else get_settings().database_url
    # asyncpg cannot be used by Alembic's sync engine; swap the driver.
    return url.replace("+asyncpg", "+psycopg2").replace("postgresql://", "postgresql+psycopg2://")


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
