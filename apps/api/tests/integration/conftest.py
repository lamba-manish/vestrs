"""Integration-test fixtures — real Postgres, in-process app.

A throwaway database is created at session start; migrations applied. Each
test gets a fresh AsyncClient pointed at the app, with the app's settings +
DB engine reset to point at the test DB. Skips cleanly when Postgres is
unreachable so the unit suite still runs offline.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic.command import upgrade
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

API_ROOT = Path(__file__).resolve().parent.parent.parent

ADMIN_URL = os.getenv(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+psycopg2://vestrs:change_me_in_local@localhost:5432/postgres",
)
TEST_DB_NAME = f"vestrs_it_{uuid.uuid4().hex[:8]}"


def _ensure_or_skip() -> str:
    try:
        engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        engine.dispose()
    except Exception as exc:
        pytest.skip(f"postgres unreachable: {type(exc).__name__}")
    return f"postgresql+psycopg2://vestrs:change_me_in_local@localhost:5432/{TEST_DB_NAME}"


def _drop_db() -> None:
    try:
        engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            # Test-only path; TEST_DB_NAME is a uuid hex we control. Bind it as
            # a parameter to keep ruff/bandit happy.
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": TEST_DB_NAME},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        engine.dispose()
    except Exception:  # noqa: S110 — best-effort cleanup
        pass


@pytest.fixture(scope="session")
def _migrated_db_url() -> str:
    sync_url = _ensure_or_skip()
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    upgrade(cfg, "head")
    yield sync_url
    _drop_db()


@pytest.fixture
async def app(monkeypatch: pytest.MonkeyPatch, _migrated_db_url: str) -> FastAPI:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("JWT_SECRET", "test-secret-must-be-long-enough-for-hs256-32+chars")

    # Reset module-level caches so the app picks up the new env. The
    # MockAccreditationAdapter singleton holds an aioredis client bound to
    # the loop it was first used on; pytest spins up a new loop per test, so
    # we recreate the singleton here to stay loop-safe.
    from app.adapters.accreditation import MockAccreditationAdapter
    from app.api import deps as deps_mod
    from app.core import config as cfg_mod
    from app.db import session as db_mod

    cfg_mod.get_settings.cache_clear()
    db_mod._engine = None
    db_mod._session_factory = None
    deps_mod._accreditation_provider = MockAccreditationAdapter()

    # The IdempotencyStore singleton holds a Redis client bound to the
    # import-time loop; recreate per test for the same loop-safety reason as
    # the accreditation adapter.
    from app.core.idempotency import IdempotencyStore

    deps_mod._idempotency_store = IdempotencyStore()

    # Wipe data + Redis between tests (schema stays; just truncate the rows).
    sync_engine = create_engine(_migrated_db_url, isolation_level="AUTOCOMMIT")
    with sync_engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE refresh_tokens, audit_logs, kyc_checks, "
                "accreditation_checks, bank_accounts, investments, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    sync_engine.dispose()

    import redis

    redis.Redis.from_url("redis://localhost:6379/15").flushdb()

    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
