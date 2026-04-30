"""HTTP middlewares: request ID + structured access log, security headers.

Both middlewares are plain ASGI (not BaseHTTPMiddleware) because
BaseHTTPMiddleware wraps the inner ASGI app in an anyio TaskGroup which
intercepts exceptions before Starlette's exception-handler chain has a
chance to map them to the response envelope.
"""

from __future__ import annotations

import time

import structlog
import uuid6
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import AppEnv, Settings
from app.core.logging import get_logger

REQUEST_ID_HEADER = "x-request-id"
_MAX_INBOUND_RID_LEN = 64


class RequestContextMiddleware:
    """Bind request_id, emit one structured access log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = _read_inbound_request_id(scope)
        request_id = (
            inbound if inbound and len(inbound) <= _MAX_INBOUND_RID_LEN else str(uuid6.uuid6())
        )

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=scope.get("method", ""),
            route=scope.get("path", ""),
        )
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        log = get_logger("api.access")
        start = time.perf_counter()
        status_code: int = 500

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers = [(k, v) for (k, v) in headers if k.lower() != REQUEST_ID_HEADER.encode()]
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            log.exception("request_failed")
            raise
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            log.info("request", status=status_code, latency_ms=latency_ms)


class SecurityHeadersMiddleware:
    """Inject security-related response headers on every HTTP response.

    HSTS only ships in non-local environments — local development runs over
    HTTP and HSTS would brick the host's localhost for a year.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self._settings = settings
        self._extra_headers: list[tuple[bytes, bytes]] = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
        ]
        if settings.app_env is not AppEnv.LOCAL:
            self._extra_headers.append(
                (
                    b"strict-transport-security",
                    b"max-age=31536000; includeSubDomains; preload",
                )
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for (k, _v) in headers}
                for k, v in self._extra_headers:
                    if k not in existing:
                        headers.append((k, v))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send)


def _read_inbound_request_id(scope: Scope) -> str | None:
    target = REQUEST_ID_HEADER.encode()
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for k, v in headers:
        if k.lower() == target:
            try:
                decoded = v.decode("ascii")
            except UnicodeDecodeError:
                return None
            return decoded
    return None
