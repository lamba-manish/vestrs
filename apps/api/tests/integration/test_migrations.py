"""End-to-end migration test: upgrade head -> downgrade base -> upgrade head.

Requires Postgres reachable at TEST_DATABASE_URL (defaults to the local
compose stack on localhost:5432). Skipped if the DB is unreachable so the
unit suite still runs in environments without docker.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_URL = "postgresql+psycopg2://vestrs:change_me_in_local@localhost:5432/vestrs_test"


def _alembic_config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _ensure_db_or_skip(admin_url: str, db_name: str) -> str:
    try:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        engine.dispose()
    except Exception as exc:
        pytest.skip(f"postgres unreachable: {type(exc).__name__}")
    return f"postgresql+psycopg2://vestrs:change_me_in_local@localhost:5432/{db_name}"


def test_alembic_round_trip() -> None:
    test_db = "vestrs_test"
    url = _ensure_db_or_skip(
        os.getenv(
            "TEST_DATABASE_ADMIN_URL",
            "postgresql+psycopg2://vestrs:change_me_in_local@localhost:5432/postgres",
        ),
        test_db,
    )

    # env.py uses cfg.sqlalchemy.url when set, so this is fully isolated from
    # the project Settings cache.
    cfg = _alembic_config(url)

    # Clean slate.
    downgrade(cfg, "base")

    upgrade(cfg, "head")
    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"users", "refresh_tokens", "audit_logs", "alembic_version"}.issubset(tables)

    # users.email is unique-indexed
    user_indexes = {ix["name"] for ix in insp.get_indexes("users")}
    assert "ix_users_email" in user_indexes

    # audit_logs has the analytical indexes per CLAUDE.md sec. 9
    audit_indexes = {ix["name"] for ix in insp.get_indexes("audit_logs")}
    assert {
        "ix_audit_logs_user_id_timestamp",
        "ix_audit_logs_action_timestamp",
        "ix_audit_logs_request_id",
    }.issubset(audit_indexes)

    downgrade(cfg, "base")
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "users" not in tables
    assert "refresh_tokens" not in tables
    assert "audit_logs" not in tables

    engine.dispose()
