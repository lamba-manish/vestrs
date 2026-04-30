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

from app.core.config import get_settings
from app.core.envelope import success_envelope
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import rate_limiter_lifespan

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


@app.get("/healthz", tags=["meta"])
async def healthz(request: Request) -> dict[str, Any]:
    return success_envelope(
        {
            "status": "ok",
            "env": settings.app_env.value,
            "version": app.version,
        },
        request_id=request.state.request_id,
    )
