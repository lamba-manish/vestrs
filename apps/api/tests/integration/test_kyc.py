"""End-to-end KYC flow against real Postgres + the in-process mock adapter."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.audit_log import AuditAction, AuditLog
from app.models.kyc import KYC_MAX_ATTEMPTS, KycCheck, KycStatus

PASSWORD = "an-unusually-long-passphrase-1"
EMAIL_OK = "ada@example.com"
EMAIL_FAIL = "ada+kyc_fail@example.com"
EMAIL_PENDING = "ada+kyc_pending@example.com"


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


# ---- GET /kyc on a fresh user ------------------------------------------


async def test_status_is_not_started_initially(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.get("/api/v1/kyc")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == KycStatus.NOT_STARTED.value
    assert body["attempts_used"] == 0
    assert body["attempts_remaining"] == KYC_MAX_ATTEMPTS
    assert body["latest"] is None


# ---- POST /kyc happy paths --------------------------------------------


async def test_submit_succeeds_for_clean_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.post("/api/v1/kyc")
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == KycStatus.SUCCESS.value
    assert data["attempt_number"] == 1
    assert data["provider_name"] == "mock"
    assert data["resolved_at"] is not None

    # One attempt row, one audit success.
    rows = (await db_session.execute(select(KycCheck))).scalars().all()
    assert len(rows) == 1
    actions = await _audit_actions(db_session)
    assert (AuditAction.KYC_SUBMITTED, "success") in actions


async def test_submit_records_failure_for_kyc_fail_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_FAIL)
    r = await client.post("/api/v1/kyc")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["status"] == KycStatus.FAILED.value
    assert data["failure_reason"] == "document_quality_insufficient"
    actions = await _audit_actions(db_session)
    assert (AuditAction.KYC_SUBMITTED, "failure") in actions


async def test_submit_records_pending_for_kyc_pending_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_PENDING)
    r = await client.post("/api/v1/kyc")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["status"] == KycStatus.PENDING.value
    assert data["resolved_at"] is None
    actions = await _audit_actions(db_session)
    assert (AuditAction.KYC_SUBMITTED, "pending") in actions


# ---- conflict guards ---------------------------------------------------


async def test_submit_twice_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/kyc")
    r = await client.post("/api/v1/kyc")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


async def test_retry_without_prior_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 409


async def test_retry_after_success_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await client.post("/api/v1/kyc")
    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 409


async def test_retry_after_pending_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_PENDING)
    await client.post("/api/v1/kyc")
    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 409


# ---- retry flow + cap --------------------------------------------------


async def test_retry_succeeds_after_failure(client: AsyncClient, db_session: AsyncSession) -> None:
    # Sign up with the failing tag and let attempt #1 fail.
    await _signup(client, EMAIL_FAIL)
    await client.post("/api/v1/kyc")

    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["attempt_number"] == 2
    assert data["status"] == KycStatus.FAILED.value  # tag still says fail


async def test_retry_cap_returns_kyc_retry_exhausted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_FAIL)
    # Fill the cap: initial submit (1) + (KYC_MAX_ATTEMPTS - 1) retries.
    await client.post("/api/v1/kyc")
    for _ in range(KYC_MAX_ATTEMPTS - 1):
        await client.post("/api/v1/kyc/retry")

    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "KYC_RETRY_EXHAUSTED"
    actions = await _audit_actions(db_session)
    assert (AuditAction.KYC_RETRY_EXHAUSTED, "failure") in actions


# ---- summary endpoint after activity ----------------------------------


async def test_summary_reflects_attempts(client: AsyncClient, db_session: AsyncSession) -> None:
    await _signup(client, EMAIL_FAIL)
    await client.post("/api/v1/kyc")
    await client.post("/api/v1/kyc/retry")

    r = await client.get("/api/v1/kyc")
    body = r.json()["data"]
    assert body["status"] == KycStatus.FAILED.value
    assert body["attempts_used"] == 2
    assert body["attempts_remaining"] == KYC_MAX_ATTEMPTS - 2
    assert body["latest"]["attempt_number"] == 2


# ---- auth required ----------------------------------------------------


async def test_kyc_endpoints_require_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/kyc")
    assert r.status_code == 401
    r = await client.post("/api/v1/kyc")
    assert r.status_code == 401
    r = await client.post("/api/v1/kyc/retry")
    assert r.status_code == 401
