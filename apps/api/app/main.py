"""FastAPI application entrypoint.

Slice 2: response envelope helpers, request-ID + security middleware,
structured JSON logging, global exception handlers, Redis-backed rate
limiter. ``/healthz`` now returns the canonical envelope with a real
request_id and uses ``ORJSONResponse`` everywhere.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.envelope import success_envelope
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import get_redis, rate_limiter_lifespan
from app.db.session import get_engine

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("api")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("api_starting", env=settings.app_env.value, version=app.version)
    async with rate_limiter_lifespan(app, settings):
        yield
    log.info("api_stopped")


app = FastAPI(
    title="Vestrs API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=_lifespan,
)

# Order matters: outermost first. Security headers wrap everything; request
# context must run before route logic so handlers can read request_id.
app.add_middleware(SecurityHeadersMiddleware, settings=settings)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)
app.include_router(api_router)

# Prometheus /metrics — exposed on the same port. Excludes the metrics
# endpoint itself from the scrape histogram and ignores /healthz so
# the per-route latency panels reflect real user traffic only. The
# kill switch is `settings.enable_metrics` — defaults on; flip via the
# ENABLE_METRICS env var in any deployment that wants /metrics hidden.
if settings.enable_metrics:
    Instrumentator(
        excluded_handlers=["/metrics", "/healthz"],
        should_group_status_codes=True,
        should_ignore_untemplated=True,
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/healthz", tags=["meta"])
async def healthz(request: Request) -> Any:
    """Liveness + readiness in one endpoint.

    Probes Postgres (`SELECT 1`) and Redis (`PING`) on every call. Caddy
    smoke tests + Prometheus blackbox-exporter + the deploy.sh smoke
    test all hit this — if any dependency is wedged we want the
    healthcheck to fail loudly, not silently return 200 while the API
    is actually 500-ing.

    Why on every call (no caching): the load on / from healthchecks is
    a `SELECT 1` and a Redis PING — sub-millisecond on the localhost
    socket. Caching would mask brief outages exactly when we need the
    signal.
    """
    db_ok = False
    db_error: str | None = None
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # surface the dependency error in the body
        db_error = type(exc).__name__

    redis_ok = False
    redis_error: str | None = None
    redis_client = get_redis()
    if redis_client is None:
        redis_error = "rate_limiter_redis_not_initialised"
    else:
        try:
            await redis_client.ping()
            redis_ok = True
        except Exception as exc:
            redis_error = type(exc).__name__

    healthy = db_ok and redis_ok
    checks: dict[str, dict[str, Any]] = {
        "database": {"ok": db_ok, **({"error": db_error} if db_error else {})},
        "redis": {"ok": redis_ok, **({"error": redis_error} if redis_error else {})},
    }
    body: dict[str, Any] = {
        "status": "ok" if healthy else "degraded",
        "env": settings.app_env.value,
        "version": app.version,
        "checks": checks,
    }
    if healthy:
        return success_envelope(body, request_id=request.state.request_id)
    # 503 with a hand-built envelope so the operator sees which check
    # failed without having to grep logs. Caddy / Prom blackbox / the
    # deploy.sh smoke test all treat 503 as a failure.
    failed = [name for name, c in checks.items() if not c["ok"]]
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Dependencies unhealthy: {', '.join(failed)}.",
            },
            "data": body,
            "request_id": request.state.request_id,
        },
    )
