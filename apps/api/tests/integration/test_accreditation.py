"""End-to-end accreditation flow.

Submit → 202 PENDING. Then we directly invoke the worker's resolve_check
function (the same code the ARQ job runs) to drive the pending row to a
terminal state. This avoids needing a real ARQ worker process during
pytest while still exercising the production resolve path.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.accreditation import MockAccreditationAdapter
from app.models.accreditation import AccreditationCheck, AccreditationStatus
from app.models.audit_log import AuditAction, AuditLog
from app.services.accreditation import resolve_check

PASSWORD = "an-unusually-long-passphrase-1"
EMAIL_OK = "ada@example.com"
EMAIL_FAIL = "ada+acc_fail@example.com"


@pytest.fixture
async def db_session(_migrated_db_url: str) -> AsyncSession:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(async_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def adapter() -> MockAccreditationAdapter:
    instance = MockAccreditationAdapter()
    yield instance
    await instance.aclose()


async def _signup(client: AsyncClient, email: str) -> None:
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text


# Default income-path body that satisfies SEC criteria. Tests that need
# a failure outcome should pass an explicit body to _post_accreditation.
_INCOME_PATH_OK: dict[str, object] = {
    "path": "income",
    "annual_income_usd": "300000.00",
    "joint_with_spouse": False,
    "years_at_or_above": 3,
    "expects_same_current_year": True,
}


async def _post_accreditation(
    client: AsyncClient, body: dict[str, object] | None = None
) -> object:  # type: ignore[name-defined]
    return await client.post("/api/v1/accreditation", json=body or _INCOME_PATH_OK)


async def _audit_actions(session: AsyncSession) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(AuditLog.action, AuditLog.status).order_by(AuditLog.timestamp)
    )
    return list(rows.all())


# ---- GET /accreditation initially -------------------------------------


async def test_status_is_not_started_initially(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    r = await client.get("/api/v1/accreditation")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == AccreditationStatus.NOT_STARTED.value
    assert body["latest"] is None


# ---- POST /accreditation -> 202 PENDING + audit ----------------------


async def test_submit_returns_pending_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _signup(client, EMAIL_OK)
    r = await _post_accreditation(client)
    assert r.status_code == 202, r.text
    data = r.json()["data"]
    assert data["status"] == AccreditationStatus.PENDING.value
    assert data["resolved_at"] is None
    assert data["provider_reference"].startswith("mock-acc-")

    rows = (await db_session.execute(select(AccreditationCheck))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == AccreditationStatus.PENDING.value

    actions = await _audit_actions(db_session)
    assert (AuditAction.ACCREDITATION_SUBMITTED, "pending") in actions


async def test_double_submit_is_409(client: AsyncClient) -> None:
    await _signup(client, EMAIL_OK)
    await _post_accreditation(client)
    r = await _post_accreditation(client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


# ---- worker-driven resolution (success) -------------------------------


async def test_resolve_check_flips_pending_to_success(
    client: AsyncClient, db_session: AsyncSession, adapter: MockAccreditationAdapter
) -> None:
    await _signup(client, EMAIL_OK)
    submit = await _post_accreditation(client)
    check_id = submit.json()["data"]["id"]
    provider_ref = submit.json()["data"]["provider_reference"]

    # Force the mock to a terminal state and run the worker resolver.
    await adapter.force_resolve(provider_ref, status=AccreditationStatus.SUCCESS)
    status, terminal = await resolve_check(
        check_id=__import__("uuid").UUID(check_id), provider=adapter
    )
    assert terminal is True
    assert status is AccreditationStatus.SUCCESS

    r = await client.get("/api/v1/accreditation")
    body = r.json()["data"]
    assert body["status"] == AccreditationStatus.SUCCESS.value
    assert body["latest"]["resolved_at"] is not None

    actions = await _audit_actions(db_session)
    assert (AuditAction.ACCREDITATION_RESOLVED, "success") in actions


async def test_resolve_check_flips_pending_to_failed(
    client: AsyncClient, db_session: AsyncSession, adapter: MockAccreditationAdapter
) -> None:
    await _signup(client, EMAIL_FAIL)
    submit = await _post_accreditation(client)
    provider_ref = submit.json()["data"]["provider_reference"]
    check_id = submit.json()["data"]["id"]

    await adapter.force_resolve(
        provider_ref,
        status=AccreditationStatus.FAILED,
        failure_reason="income_documentation_insufficient",
    )
    status, terminal = await resolve_check(
        check_id=__import__("uuid").UUID(check_id), provider=adapter
    )
    assert terminal is True
    assert status is AccreditationStatus.FAILED

    r = await client.get("/api/v1/accreditation")
    body = r.json()["data"]
    assert body["status"] == AccreditationStatus.FAILED.value
    assert body["latest"]["failure_reason"] == "income_documentation_insufficient"


# ---- resolve_check is a no-op on a terminal row ------------------------


async def test_resolve_check_on_terminal_returns_terminal(
    client: AsyncClient, adapter: MockAccreditationAdapter
) -> None:
    await _signup(client, EMAIL_OK)
    submit = await _post_accreditation(client)
    check_id = submit.json()["data"]["id"]
    ref = submit.json()["data"]["provider_reference"]

    await adapter.force_resolve(ref, status=AccreditationStatus.SUCCESS)
    await resolve_check(check_id=__import__("uuid").UUID(check_id), provider=adapter)

    # Second call should still return terminal=True with the same status.
    status, terminal = await resolve_check(
        check_id=__import__("uuid").UUID(check_id), provider=adapter
    )
    assert terminal is True
    assert status is AccreditationStatus.SUCCESS


# ---- still-pending path: worker would re-enqueue itself ---------------


async def test_resolve_check_still_pending_returns_terminal_false(
    client: AsyncClient, adapter: MockAccreditationAdapter
) -> None:
    await _signup(client, EMAIL_OK)
    submit = await _post_accreditation(client)
    check_id = submit.json()["data"]["id"]

    # Don't force-resolve — adapter still says PENDING (resolves_at is in
    # the future given the test's tiny default delay).
    status, terminal = await resolve_check(
        check_id=__import__("uuid").UUID(check_id), provider=adapter
    )
    assert terminal is False
    assert status is AccreditationStatus.PENDING


# ---- auth ------------------------------------------------------------


async def test_endpoints_require_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/accreditation")
    assert r.status_code == 401
    r = await _post_accreditation(client)
    assert r.status_code == 401
