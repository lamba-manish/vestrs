"""End-to-end audit-log read flow."""

from __future__ import annotations

import base64
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.user import User

PASSWORD = "an-unusually-long-passphrase-1"


@pytest.fixture
async def db_session(_migrated_db_url: str) -> AsyncSession:
    async_url = _migrated_db_url.replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(async_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _signup(client: AsyncClient, email: str = "ada@example.com") -> dict[str, object]:
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()["data"]["user"]


async def _make_admin(db_session: AsyncSession, user_id: UUID, client: AsyncClient) -> None:
    """Promote a user to admin and refresh their access token so the new
    role is in the JWT claim."""
    await db_session.execute(update(User).where(User.id == user_id).values(is_admin=True))
    await db_session.commit()
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200, r.text


# ---- self-only -----------------------------------------------------


async def test_user_sees_only_their_own_audit_log(
    client: AsyncClient,
) -> None:
    await _signup(client)
    r = await client.get("/api/v1/audit")
    assert r.status_code == 200
    body = r.json()["data"]
    assert all(item["action"] == "AUTH_SIGNUP" for item in body["items"])
    assert all(item["status"] == "success" for item in body["items"])
    assert body["next_cursor"] is None


async def test_filters_by_action(client: AsyncClient) -> None:
    await _signup(client)
    await client.post("/api/v1/kyc")  # adds KYC_SUBMITTED
    r = await client.get("/api/v1/audit", params={"action": "KYC_SUBMITTED"})
    body = r.json()["data"]
    assert all(item["action"] == "KYC_SUBMITTED" for item in body["items"])


async def test_default_returns_newest_first(client: AsyncClient) -> None:
    await _signup(client)
    await client.post("/api/v1/kyc")
    r = await client.get("/api/v1/audit")
    actions = [item["action"] for item in r.json()["data"]["items"]]
    # KYC_SUBMITTED happened after AUTH_SIGNUP → must come first.
    assert actions[0] == "KYC_SUBMITTED"
    assert actions[-1] == "AUTH_SIGNUP"


# ---- pagination ----------------------------------------------------


async def test_cursor_pagination_walks_full_log(client: AsyncClient) -> None:
    await _signup(client)
    # Add a few more events.
    await client.post("/api/v1/kyc")
    await client.post("/api/v1/accreditation")
    await client.post("/api/v1/auth/refresh")
    await client.post("/api/v1/auth/refresh")

    r = await client.get("/api/v1/audit", params={"limit": 2})
    body = r.json()["data"]
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    first_page_ids = {item["id"] for item in body["items"]}

    r = await client.get("/api/v1/audit", params={"limit": 2, "cursor": body["next_cursor"]})
    page2 = r.json()["data"]
    assert len(page2["items"]) == 2
    second_page_ids = {item["id"] for item in page2["items"]}
    assert first_page_ids.isdisjoint(second_page_ids)


async def test_invalid_cursor_returns_422(client: AsyncClient) -> None:
    await _signup(client)
    r = await client.get("/api/v1/audit", params={"cursor": "not-base64"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- authorization -------------------------------------------------


async def test_non_admin_cannot_read_other_users_log(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user_a = await _signup(client, "alice@example.com")
    # Sign up bob in another client/cookie jar so we know his id.
    await client.post(
        "/api/v1/auth/logout",
    )
    client.cookies.clear()
    user_b = await _signup(client, "bob@example.com")

    r = await client.get("/api/v1/audit", params={"user_id": user_a["id"]})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"

    # ?all=true is also forbidden for non-admins
    r = await client.get("/api/v1/audit", params={"all": "true"})
    assert r.status_code == 403
    assert user_b is not None  # silence ruff: variable used


async def test_admin_can_read_other_users_log(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Alice will be the admin; Bob is the target.
    bob = await _signup(client, "bob@example.com")
    await client.post("/api/v1/auth/logout")
    client.cookies.clear()

    alice = await _signup(client, "alice@example.com")
    await _make_admin(db_session, UUID(alice["id"]), client)

    r = await client.get("/api/v1/audit", params={"user_id": bob["id"]})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert items, "expected at least bob's signup audit"
    assert all(item["user_id"] == bob["id"] for item in items)


async def test_admin_can_view_all_users_with_all_flag(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    bob = await _signup(client, "bob@example.com")
    await client.post("/api/v1/auth/logout")
    client.cookies.clear()
    alice = await _signup(client, "alice@example.com")
    await _make_admin(db_session, UUID(alice["id"]), client)

    r = await client.get("/api/v1/audit", params={"all": "true", "limit": 200})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    user_ids = {item["user_id"] for item in items}
    assert UUID(bob["id"]) in {UUID(u) for u in user_ids if u}
    assert UUID(alice["id"]) in {UUID(u) for u in user_ids if u}


# ---- response shape ------------------------------------------------


async def test_response_shape_uses_metadata_key_not_audit_metadata(
    client: AsyncClient,
) -> None:
    await _signup(client)
    r = await client.get("/api/v1/audit")
    item = r.json()["data"]["items"][0]
    assert "metadata" in item
    assert "audit_metadata" not in item


async def test_cursor_is_base64_uuid(client: AsyncClient) -> None:
    await _signup(client)
    await client.post("/api/v1/kyc")
    await client.post("/api/v1/accreditation")
    r = await client.get("/api/v1/audit", params={"limit": 1})
    cursor = r.json()["data"]["next_cursor"]
    decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    UUID(decoded)  # raises if not a valid UUID


async def test_endpoint_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/audit")
    assert r.status_code == 401
