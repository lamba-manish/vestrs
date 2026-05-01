"""Health endpoint — verifies the envelope shape AND the dependency
probes (Postgres SELECT 1, Redis PING). Slice 27 promoted /healthz
from a static "process is up" check to a real readiness probe so
Caddy's smoke test, the deploy.sh smoke test, and the blackbox
exporter all surface dependency failures instead of silently 200-ing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.fixture
def patched_healthz(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Stub get_engine + get_redis so the unit suite doesn't need a
    live Postgres/Redis. Each test can override the side_effects on
    the returned mocks to simulate failure states."""

    fake_conn = MagicMock()
    fake_conn.execute = AsyncMock()

    @asynccontextmanager
    async def _connect():  # type: ignore[no-untyped-def]
        yield fake_conn

    fake_engine = MagicMock()
    fake_engine.connect = _connect

    fake_redis = MagicMock()
    fake_redis.ping = AsyncMock(return_value=True)

    monkeypatch.setattr("app.main.get_engine", lambda: fake_engine)
    monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)
    return {"conn": fake_conn, "engine": fake_engine, "redis": fake_redis}


async def test_healthz_returns_200_when_db_and_redis_ok(
    client: AsyncClient, patched_healthz: dict[str, MagicMock]
) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["checks"]["database"]["ok"] is True
    assert body["data"]["checks"]["redis"]["ok"] is True
    assert "request_id" in body


async def test_healthz_returns_503_when_db_down(
    client: AsyncClient, patched_healthz: dict[str, MagicMock]
) -> None:
    patched_healthz["conn"].execute.side_effect = ConnectionError("postgres unreachable")
    response = await client.get("/healthz")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "database" in body["error"]["message"]
    assert body["data"]["checks"]["database"]["ok"] is False
    assert body["data"]["checks"]["redis"]["ok"] is True


async def test_healthz_returns_503_when_redis_down(
    client: AsyncClient, patched_healthz: dict[str, MagicMock]
) -> None:
    patched_healthz["redis"].ping.side_effect = TimeoutError("redis timeout")
    response = await client.get("/healthz")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "redis" in body["error"]["message"]
    assert body["data"]["checks"]["redis"]["ok"] is False


async def test_healthz_returns_503_when_redis_not_initialised(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute = AsyncMock()

    @asynccontextmanager
    async def _connect():  # type: ignore[no-untyped-def]
        yield fake_conn

    fake_engine = MagicMock()
    fake_engine.connect = _connect

    monkeypatch.setattr("app.main.get_engine", lambda: fake_engine)
    monkeypatch.setattr("app.main.get_redis", lambda: None)

    response = await client.get("/healthz")
    assert response.status_code == 503
    body = response.json()
    assert body["data"]["checks"]["redis"]["ok"] is False
    assert "rate_limiter_redis_not_initialised" in body["data"]["checks"]["redis"]["error"]
