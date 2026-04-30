"""Canonical response envelope.

Every JSON response — success or failure — is wrapped here. Routes return the
unwrapped payload; FastAPI dependencies + exception handlers wrap them.

Shape (success):
    { "success": true, "data": <payload>, "request_id": "<uuidv6>" }

Shape (failure):
    { "success": false,
      "error": { "code": "<STABLE_CODE>", "message": "<human>" },
      "details": { "<field>": ["<msg>", ...] }   # optional
      "request_id": "<uuidv6>" }
"""

from __future__ import annotations

from typing import Any

from app.core.errors import DomainError, ErrorCode


def success_envelope(data: Any, request_id: str | None) -> dict[str, Any]:
    return {"success": True, "data": data, "request_id": request_id}


def error_envelope(
    code: ErrorCode | str,
    message: str,
    *,
    request_id: str | None,
    details: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code.value if isinstance(code, ErrorCode) else code,
            "message": message,
        },
    }
    if details is not None:
        payload["details"] = details
    payload["request_id"] = request_id
    return payload


def envelope_from_domain_error(err: DomainError, request_id: str | None) -> dict[str, Any]:
    return error_envelope(err.code, err.message, request_id=request_id, details=err.details)
