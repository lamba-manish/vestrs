"""Global exception handlers — they own envelope construction for errors.

Routes never build error responses by hand. They raise:
- a ``DomainError`` (or subclass) for known business outcomes, or
- nothing (for success); FastAPI wraps the return value via the response
  model.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.envelope import envelope_from_domain_error, error_envelope
from app.core.errors import DomainError, ErrorCode, default_status_for
from app.core.logging import get_logger

log = get_logger("api.errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _format_pydantic_errors(
    errors: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Group pydantic/validation errors by field path (dot-joined)."""
    out: dict[str, list[str]] = {}
    for err in errors:
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        field = ".".join(loc) if loc else "_root"
        msg = err.get("msg", "Invalid value.")
        out.setdefault(field, []).append(msg)
    return out


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    payload = envelope_from_domain_error(exc, _request_id(request))
    log.warning(
        "domain_error",
        code=exc.code.value,
        http_status=exc.http_status,
    )
    return JSONResponse(payload, status_code=exc.http_status)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = _format_pydantic_errors(list(exc.errors()))
    payload = error_envelope(
        ErrorCode.VALIDATION_ERROR,
        "The provided input data is invalid.",
        request_id=_request_id(request),
        details=details,
    )
    return JSONResponse(payload, status_code=default_status_for(ErrorCode.VALIDATION_ERROR))


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _http_status_to_code(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    payload = error_envelope(code, message, request_id=_request_id(request))
    return JSONResponse(payload, status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals: log with full context, return a generic envelope.
    log.exception("unhandled_exception", exc_type=type(exc).__name__)
    payload = error_envelope(
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred.",
        request_id=_request_id(request),
    )
    return JSONResponse(payload, status_code=500)


def _http_status_to_code(status: int) -> ErrorCode:
    if status == 404:
        return ErrorCode.NOT_FOUND
    if status == 401:
        return ErrorCode.AUTH_INVALID_CREDENTIALS
    if status == 403:
        return ErrorCode.FORBIDDEN
    if status == 409:
        return ErrorCode.CONFLICT
    if status == 422:
        return ErrorCode.VALIDATION_ERROR
    if status == 429:
        return ErrorCode.RATE_LIMITED
    return ErrorCode.INTERNAL_ERROR


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
