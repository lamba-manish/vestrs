"""/metrics endpoint smoke test — Prometheus exposition format."""

from __future__ import annotations

from httpx import AsyncClient


async def test_metrics_exposes_prometheus_format(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 200

    # prometheus_client emits a versioned text/plain content-type.
    # Different prometheus_client minor versions ship different
    # default versions (0.0.4 → 1.0.0); accept any.
    ctype = response.headers["content-type"]
    assert "text/plain" in ctype
    assert "version=" in ctype or "openmetrics-text" in ctype

    body = response.text
    # The instrumentator adds these standard series; missing any of
    # them is a strong signal that the wiring regressed.
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body

    # /healthz is excluded from the histogram on purpose; quick sanity
    # check that we don't accidentally start scraping infrastructure
    # noise into the per-route panels.
    healthz_lines = [ln for ln in body.splitlines() if "/healthz" in ln]
    assert healthz_lines == [], f"expected /healthz excluded, got {healthz_lines}"
