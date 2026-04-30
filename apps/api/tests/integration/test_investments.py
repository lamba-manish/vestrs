"""End-to-end investment flow.

Most tests need a 'fully onboarded' user — KYC SUCCESS + accreditation SUCCESS
+ active linked bank — so we provide a helper that drives the API through
those slices rather than seeding the DB directly. That keeps the tests
exercising the production paths.
"""

from __future__ import annotations

import secrets
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.accreditation import MockAccreditationAdapter
from app.models.accreditation import AccreditationStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.bank import BankAccount
from app.models.investment import Investment

PASSWORD = "an-unusually-long-passphrase-1"

BANK_PAYLOAD = {
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


async def _audit_actions(session: AsyncSession) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.status).order_by(AuditLog.timestamp)
    )
    return list(rows.all())


async def _onboard_fully(client: AsyncClient, email: str) -> None:
    """Sign up, pass KYC, get accredited, link a bank — the precondition
    set every investment test needs."""
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    # KYC default email → SUCCESS synchronously.
    r = await client.post("/api/v1/kyc")
    assert r.json()["data"]["status"] == "success"
    # Accreditation: submit, then resolve via the adapter directly so the
    # test doesn't have to wait the full delay.
    submit = await client.post("/api/v1/accreditation")
    ref = submit.json()["data"]["provider_reference"]
    check_id = submit.json()["data"]["id"]

    from app.api import deps as deps_mod
    from app.services.accreditation import resolve_check

    adapter = deps_mod._accreditation_provider
    assert isinstance(adapter, MockAccreditationAdapter)
    await adapter.force_resolve(ref, status=AccreditationStatus.SUCCESS)
    import uuid as _uuid

    await resolve_check(check_id=_uuid.UUID(check_id), provider=adapter)

    r = await client.post("/api/v1/bank/link", json=BANK_PAYLOAD)
    assert r.status_code == 201, r.text


def _idem_key() -> str:
    return f"idem-{secrets.token_hex(8)}"


# ---- happy path ------------------------------------------------------


async def test_invest_succeeds_debits_balance_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _onboard_fully(client, "ada@example.com")
    pre = (await db_session.execute(select(BankAccount))).scalar_one()
    pre_balance = pre.mock_balance

    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "1000.0000", "notes": "Q1 allocation"},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["amount"] == "1000.0000"
    assert data["currency"] == "USD"
    assert data["status"] == "settled"
    assert data["escrow_reference"].startswith("escrow-")
    assert data["notes"] == "Q1 allocation"

    # Balance debited.
    await db_session.refresh(pre)
    assert pre.mock_balance == pre_balance - Decimal("1000.0000")

    # Investment row exists.
    rows = (await db_session.execute(select(Investment))).scalars().all()
    assert len(rows) == 1

    actions = await _audit_actions(db_session)
    assert (AuditAction.INVESTMENT_CREATED, "success") in actions


# ---- idempotency ----------------------------------------------------


async def test_repeated_request_with_same_key_replays_response(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _onboard_fully(client, "ada@example.com")
    key = _idem_key()
    body = {"amount": "500.0000", "notes": "first"}

    r1 = await client.post("/api/v1/investments", headers={"Idempotency-Key": key}, json=body)
    assert r1.status_code == 201
    first_id = r1.json()["data"]["id"]

    # Same key + same body → identical response, no new investment row.
    r2 = await client.post("/api/v1/investments", headers={"Idempotency-Key": key}, json=body)
    assert r2.status_code == 201
    assert r2.json()["data"]["id"] == first_id

    rows = (await db_session.execute(select(Investment))).scalars().all()
    assert len(rows) == 1

    actions = await _audit_actions(db_session)
    assert (AuditAction.INVESTMENT_IDEMPOTENT_REPLAY, "success") in actions


async def test_same_key_different_body_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _onboard_fully(client, "ada@example.com")
    key = _idem_key()
    await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": key},
        json={"amount": "500.0000"},
    )
    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": key},
        json={"amount": "9999.0000"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    actions = await _audit_actions(db_session)
    assert (AuditAction.INVESTMENT_BLOCKED, "failure") in actions


# Note on concurrency: the current Redis-backed idempotency does
# get → process → store. Two truly-concurrent requests with the same key
# can both miss the get, both process, and both insert. Strong concurrent
# idempotency requires a DB-level unique constraint on
# (user_id, idempotency_key) with insert-or-fetch semantics. Tracked as a
# follow-up; serial replay (test above) is fully covered today.


# ---- balance --------------------------------------------------------


async def test_insufficient_balance_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _onboard_fully(client, "ada@example.com")
    pre = (await db_session.execute(select(BankAccount))).scalar_one()
    too_much = pre.mock_balance + Decimal("1.0000")
    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": str(too_much)},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INSUFFICIENT_BALANCE"

    actions = await _audit_actions(db_session)
    assert (AuditAction.INVESTMENT_FAILED, "failure") in actions


# ---- gates ----------------------------------------------------------


async def test_invest_without_kyc_is_409(client: AsyncClient, db_session: AsyncSession) -> None:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": "no-kyc@example.com", "password": PASSWORD}
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "100.0000"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "KYC_FAILED"


async def test_invest_without_accreditation_is_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": "kyc-only@example.com", "password": PASSWORD},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/kyc")
    assert r.json()["data"]["status"] == "success"

    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "100.0000"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ACCREDITATION_FAILED"


async def test_invest_without_bank_is_409(client: AsyncClient, db_session: AsyncSession) -> None:
    # Onboard everything except bank linking.
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": "no-bank@example.com", "password": PASSWORD},
    )
    assert r.status_code == 201
    await client.post("/api/v1/kyc")
    submit = await client.post("/api/v1/accreditation")
    ref = submit.json()["data"]["provider_reference"]
    check_id = submit.json()["data"]["id"]
    from app.api import deps as deps_mod
    from app.services.accreditation import resolve_check

    adapter = deps_mod._accreditation_provider
    await adapter.force_resolve(ref, status=AccreditationStatus.SUCCESS)
    import uuid as _uuid

    await resolve_check(check_id=_uuid.UUID(check_id), provider=adapter)

    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "100.0000"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "BANK_NOT_LINKED"


# ---- validation -----------------------------------------------------


async def test_missing_idempotency_key_returns_422(client: AsyncClient) -> None:
    await _onboard_fully(client, "ada@example.com")
    r = await client.post("/api/v1/investments", json={"amount": "100.0000"})
    assert r.status_code == 422


async def test_zero_amount_returns_422(client: AsyncClient) -> None:
    await _onboard_fully(client, "ada@example.com")
    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "0"},
    )
    assert r.status_code == 422


async def test_get_investments_lists_recent_first(client: AsyncClient) -> None:
    await _onboard_fully(client, "ada@example.com")
    for i in range(3):
        r = await client.post(
            "/api/v1/investments",
            headers={"Idempotency-Key": _idem_key()},
            json={"amount": f"{(i + 1) * 100}.0000"},
        )
        assert r.status_code == 201

    r = await client.get("/api/v1/investments")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 3
    # Most-recent-first: amounts go 300, 200, 100.
    amounts = [item["amount"] for item in items]
    assert amounts == ["300.0000", "200.0000", "100.0000"]


async def test_endpoints_require_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/investments")
    assert r.status_code == 401
    r = await client.post(
        "/api/v1/investments",
        headers={"Idempotency-Key": _idem_key()},
        json={"amount": "100.0000"},
    )
    assert r.status_code == 401
