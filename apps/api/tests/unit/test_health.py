"""Health endpoint smoke test — verifies the response envelope shape."""

from __future__ import annotations

from httpx import AsyncClient


async def test_healthz_returns_success_envelope(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["env"] in {"local", "staging", "production"}
    assert "version" in body["data"]
    assert "request_id" in body
