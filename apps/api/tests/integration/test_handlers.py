"""Integration tests for global exception handlers + middleware via the real app.

We mount throwaway routes onto the real FastAPI app to verify that:
- domain errors round-trip into the envelope with the right code/status
- validation errors produce a populated ``details`` map
- request-ID middleware sets ``X-Request-ID`` and echoes the inbound header
- security headers are present
- unhandled exceptions never leak internals
"""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel

from app.core.errors import ConflictError, NotFoundError, ValidationError


class _Echo(BaseModel):
    email: str
    password: str


def _wire_test_routes(app: FastAPI) -> None:
    if getattr(app.state, "_test_routes_wired", False):
        return

    @app.get("/__test__/conflict")
    async def _conflict() -> None:
        raise ConflictError("Already exists.")

    @app.get("/__test__/not-found")
    async def _missing() -> None:
        raise NotFoundError()

    @app.get("/__test__/boom")
    async def _boom() -> None:
        raise RuntimeError("internal sentinel — must not leak")

    @app.get("/__test__/domain-validation")
    async def _domain_validation() -> None:
        raise ValidationError(details={"amount": ["Must be positive."]})

    @app.post("/__test__/echo")
    async def _echo(body: _Echo) -> dict[str, str]:
        return {"email": body.email}

    app.state._test_routes_wired = True


async def test_domain_error_produces_envelope(app: FastAPI, client: AsyncClient) -> None:
    _wire_test_routes(app)
    r = await client.get("/__test__/conflict")
    assert r.status_code == 409
    body = r.json()
    assert body["success"] is False
    assert body["error"] == {"code": "CONFLICT", "message": "Already exists."}
    assert body["request_id"]


async def test_not_found_uses_default_message(app: FastAPI, client: AsyncClient) -> None:
    _wire_test_routes(app)
    r = await client.get("/__test__/not-found")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"


async def test_pydantic_validation_returns_details_map(app: FastAPI, client: AsyncClient) -> None:
    _wire_test_routes(app)
    r = await client.post("/__test__/echo", json={"email": "a@b.com"})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in body["details"]
    assert isinstance(body["details"]["password"], list)


async def test_domain_validation_carries_details(app: FastAPI, client: AsyncClient) -> None:
    _wire_test_routes(app)
    r = await client.get("/__test__/domain-validation")
    assert r.status_code == 422
    body = r.json()
    assert body["details"] == {"amount": ["Must be positive."]}


async def test_unhandled_exception_does_not_leak(app: FastAPI, client: AsyncClient) -> None:
    _wire_test_routes(app)
    r = await client.get("/__test__/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "sentinel" not in body["error"]["message"]


async def test_request_id_is_generated_and_echoed(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    rid = r.headers.get("X-Request-ID")
    assert rid
    assert r.json()["request_id"] == rid


async def test_inbound_request_id_is_honored(client: AsyncClient) -> None:
    r = await client.get("/healthz", headers={"X-Request-ID": "rid-abc-123"})
    assert r.headers.get("X-Request-ID") == "rid-abc-123"
    assert r.json()["request_id"] == "rid-abc-123"


async def test_security_headers_set_in_local(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    # HSTS is intentionally absent in local
    assert "Strict-Transport-Security" not in r.headers
