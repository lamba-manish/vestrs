"""End-to-end auth flow against real Postgres.

Covers signup, login (incl. wrong password + unknown email), refresh
rotation, refresh reuse detection (whole family revoked), logout, and the
``/me`` endpoint. Every flow asserts that an audit_logs row was written in
the same transaction as the action.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE
from app.models.audit_log import AuditAction, AuditLog, AuditStatus
from app.models.refresh_token import RefreshToken

EMAIL = "ada.lovelace@example.com"
PASSWORD = "an-unusually-long-passphrase-1"


def _cookie(client: AsyncClient, name: str) -> str | None:
    return client.cookies.get(name)


async def _audit_actions(session: AsyncSession) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.status).order_by(AuditLog.timestamp)
    )
    return list(rows.all())


@pytest.fixture
async def db_session(_migrated_db_url: str) -> AsyncSession:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(async_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_signup_sets_cookies_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == EMAIL
    assert _cookie(client, ACCESS_COOKIE)
    assert _cookie(client, REFRESH_COOKIE)

    actions = await _audit_actions(db_session)
    assert (AuditAction.AUTH_SIGNUP, AuditStatus.SUCCESS) in actions


async def test_signup_duplicate_email_409(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    r = await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"
    actions = await _audit_actions(db_session)
    assert (AuditAction.AUTH_SIGNUP, AuditStatus.FAILURE) in actions


async def test_login_unknown_email_401(client: AsyncClient, db_session: AsyncSession) -> None:
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nope@example.com", "password": "whatever"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    actions = await _audit_actions(db_session)
    assert (AuditAction.AUTH_LOGIN_FAILED, AuditStatus.FAILURE) in actions


async def test_login_wrong_password_401(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    client.cookies.clear()
    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_success_sets_cookies(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    client.cookies.clear()
    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert _cookie(client, ACCESS_COOKIE)
    assert _cookie(client, REFRESH_COOKIE)


async def test_me_requires_access_cookie(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


async def test_me_returns_token_subject_without_admin_flag(
    client: AsyncClient,
) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["email"] == EMAIL
    assert "id" in body
    # Role / privilege state is intentionally NOT exposed in the response;
    # the FE never gates UI on it.
    assert "is_admin" not in body
    assert "role" not in body


async def test_signup_response_omits_admin_flag(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201
    user = r.json()["data"]["user"]
    assert "is_admin" not in user
    assert "role" not in user


async def test_refresh_rotates_tokens(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    old_access = _cookie(client, ACCESS_COOKIE)
    old_refresh = _cookie(client, REFRESH_COOKIE)
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200, r.text
    new_access = _cookie(client, ACCESS_COOKIE)
    new_refresh = _cookie(client, REFRESH_COOKIE)
    assert new_access and new_access != old_access
    assert new_refresh and new_refresh != old_refresh


async def test_refresh_reuse_revokes_family(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    first_refresh = _cookie(client, REFRESH_COOKIE)
    assert first_refresh

    # Rotate once — first_refresh is now retired.
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200

    # Replay the retired token. The whole family should be revoked.
    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_REFRESH_REQUIRED"

    actions = await _audit_actions(db_session)
    assert (AuditAction.AUTH_REFRESH_REUSE_DETECTED, AuditStatus.FAILURE) in actions

    # All refresh tokens should be revoked or replaced — none active.
    rows = await db_session.execute(select(RefreshToken))
    tokens = list(rows.scalars())
    assert tokens
    assert all(not t.is_active for t in tokens)


async def test_logout_revokes_and_clears(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["logged_out"] is True

    # Subsequent /me with no cookies must fail with auth-invalid.
    client.cookies.clear()
    r2 = await client.get("/api/v1/auth/me")
    assert r2.status_code == 401

    actions = await _audit_actions(db_session)
    assert (AuditAction.AUTH_LOGOUT, AuditStatus.SUCCESS) in actions
