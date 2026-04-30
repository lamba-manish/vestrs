"""End-to-end profile flow against real Postgres."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.audit_log import AuditAction, AuditLog, AuditStatus
from app.models.user import User

EMAIL = "client@example.com"
PASSWORD = "an-unusually-long-passphrase-1"
VALID = {
    "full_name": "Ada Lovelace",
    "nationality": "GB",
    "domicile": "US",
    "phone": "+14155551234",
}


@pytest.fixture
async def db_session(_migrated_db_url: str) -> AsyncSession:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(async_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _signup(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201, r.text


async def test_get_me_returns_empty_profile_after_signup(client: AsyncClient) -> None:
    await _signup(client)
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["email"] == EMAIL
    assert body["full_name"] is None
    assert body["nationality"] is None
    assert body["domicile"] is None
    assert body["phone"] is None


async def test_put_me_persists_and_normalises(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client)
    r = await client.put("/api/v1/users/me", json={**VALID, "nationality": "gb"})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["full_name"] == "Ada Lovelace"
    assert body["nationality"] == "GB"  # normalized to upper
    assert body["domicile"] == "US"
    assert body["phone"] == "+14155551234"

    # DB row carries the normalized values.
    row = (await db_session.execute(select(User).where(User.email == EMAIL))).scalar_one()
    assert row.full_name == "Ada Lovelace"
    assert row.nationality == "GB"


async def test_put_me_writes_audit_log_in_same_tx(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client)
    r = await client.put("/api/v1/users/me", json=VALID)
    assert r.status_code == 200

    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == AuditAction.PROFILE_UPDATED)
    )
    entries = list(rows.scalars())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.status == AuditStatus.SUCCESS
    assert entry.resource_type == "user"
    assert entry.user_id is not None
    assert entry.audit_metadata == {
        "full_name_was_set": False,
        "nationality_was_set": False,
        "domicile_was_set": False,
        "phone_was_set": False,
    }


async def test_put_me_requires_auth(client: AsyncClient) -> None:
    r = await client.put("/api/v1/users/me", json=VALID)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


async def test_put_me_validation_returns_details(client: AsyncClient) -> None:
    await _signup(client)
    r = await client.put(
        "/api/v1/users/me",
        json={**VALID, "nationality": "ZZ", "phone": "not-a-phone"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "nationality" in body["details"]
    assert "phone" in body["details"]


async def test_put_me_rejects_unknown_fields(client: AsyncClient) -> None:
    await _signup(client)
    r = await client.put("/api/v1/users/me", json={**VALID, "ssn": "123-45-6789"})
    assert r.status_code == 422


async def test_put_me_overwrite_metadata_marks_previous_set(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client)
    await client.put("/api/v1/users/me", json=VALID)
    second = {**VALID, "full_name": "Grace Hopper", "nationality": "US"}
    r = await client.put("/api/v1/users/me", json=second)
    assert r.status_code == 200

    rows = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.PROFILE_UPDATED)
        .order_by(AuditLog.timestamp)
    )
    entries = list(rows.scalars())
    assert len(entries) == 2
    assert all(v is False for v in entries[0].audit_metadata.values())
    assert all(v is True for v in entries[1].audit_metadata.values())
