"""End-to-end bank linking flow against real Postgres."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.audit_log import AuditAction, AuditLog
from app.models.bank import BankAccount, BankAccountStatus

PASSWORD = "an-unusually-long-passphrase-1"
EMAIL_OK = "ada@example.com"
EMAIL_FAIL = "ada+bank_fail@example.com"
PAYLOAD = {
    "bank_name": "Chase",
    "account_holder_name": "Ada Lovelace",
    "account_type": "checking",
    "account_number": "000123456789",
    "routing_number": "021000021",
    "currency": "USD",
}


@pytest.fixture
async def db_session(_migrated_db_url: str) -> AsyncSession:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(async_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _signup(client: AsyncClient, email: str) -> None:
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text


async def _audit_actions(session: AsyncSession) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.status).order_by(AuditLog.timestamp)
    )
    return list(rows.all())


# ---- GET /bank initially ----------------------------------------------


async def test_status_is_unlinked_initially(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.get("/api/v1/bank")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["linked"] is False
    assert body["account"] is None


# ---- happy path -------------------------------------------------------


async def test_link_succeeds_and_persists_only_masked_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.post("/api/v1/bank/link", json=PAYLOAD)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["bank_name"] == "Chase"
    assert data["last_four"] == "6789"
    assert data["currency"] == "USD"
    assert data["status"] == BankAccountStatus.ACTIVE.value
    # Critical: plaintext numbers are never echoed back.
    assert "account_number" not in data
    assert "routing_number" not in data

    # DB row carries last_four only.
    row = (
        await db_session.execute(select(BankAccount).where(BankAccount.last_four == "6789"))
    ).scalar_one()
    assert row.bank_name == "Chase"
    # Verify no column on the model holds the plaintext.
    for column in row.__mapper__.columns:
        if column.key != "raw_response":
            value = getattr(row, column.key)
            if isinstance(value, str):
                assert "000123456789" not in value
                assert "021000021" not in value
    # Even raw_response (mock-vendor metadata) must not leak the plaintext.
    assert "000123456789" not in str(row.raw_response)
    assert "021000021" not in str(row.raw_response)

    actions = await _audit_actions(db_session)
    assert (AuditAction.BANK_LINKED, "success") in actions


async def test_get_bank_returns_active_account(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/bank/link", json=PAYLOAD)
    r = await client.get("/api/v1/bank")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["linked"] is True
    assert body["account"]["last_four"] == "6789"


# ---- failure paths ----------------------------------------------------


async def test_link_fails_for_bank_fail_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_FAIL)
    r = await client.post("/api/v1/bank/link", json=PAYLOAD)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "BANK_LINK_FAILED"

    actions = await _audit_actions(db_session)
    assert (AuditAction.BANK_LINK_FAILED, "failure") in actions


async def test_double_link_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/bank/link", json=PAYLOAD)
    r = await client.post(
        "/api/v1/bank/link",
        json={**PAYLOAD, "bank_name": "Wells Fargo", "account_number": "999000111"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


# ---- unlink + relink --------------------------------------------------


async def test_unlink_marks_inactive_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/bank/link", json=PAYLOAD)
    r = await client.delete("/api/v1/bank")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == BankAccountStatus.UNLINKED.value
    assert body["unlinked_at"] is not None

    summary = await client.get("/api/v1/bank")
    assert summary.json()["data"]["linked"] is False

    actions = await _audit_actions(db_session)
    assert (AuditAction.BANK_UNLINKED, "success") in actions


async def test_unlink_without_active_link_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.delete("/api/v1/bank")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "BANK_NOT_LINKED"


async def test_relink_after_unlink_is_allowed(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/bank/link", json=PAYLOAD)
    await client.delete("/api/v1/bank")
    r = await client.post(
        "/api/v1/bank/link",
        json={**PAYLOAD, "bank_name": "Wells Fargo", "account_number": "888777666555"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["bank_name"] == "Wells Fargo"
    assert data["last_four"] == "6555"


# ---- validation -------------------------------------------------------


async def test_invalid_currency_returns_per_field_details(
    client: AsyncClient,
) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.post(
        "/api/v1/bank/link", json={**PAYLOAD, "currency": "ZZZ", "account_number": "abc"}
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "currency" in body["details"]
    assert "account_number" in body["details"]


async def test_endpoints_require_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/bank")
    assert r.status_code == 401
    r = await client.post("/api/v1/bank/link", json=PAYLOAD)
    assert r.status_code == 401
    r = await client.delete("/api/v1/bank")
    assert r.status_code == 401
