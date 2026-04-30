"""Envelope-shape tests — these are the contract every consumer relies on."""

from __future__ import annotations

from app.core.envelope import (
    envelope_from_domain_error,
    error_envelope,
    success_envelope,
)
from app.core.errors import ErrorCode, ValidationError


def test_success_envelope_has_required_keys() -> None:
    out = success_envelope({"x": 1}, request_id="rid-1")
    assert out == {"success": True, "data": {"x": 1}, "request_id": "rid-1"}


def test_error_envelope_minimal() -> None:
    out = error_envelope(ErrorCode.NOT_FOUND, "Missing.", request_id="rid-2")
    assert out == {
        "success": False,
        "error": {"code": "NOT_FOUND", "message": "Missing."},
        "request_id": "rid-2",
    }


def test_error_envelope_with_details() -> None:
    out = error_envelope(
        ErrorCode.VALIDATION_ERROR,
        "Bad input.",
        request_id="rid-3",
        details={"email": ["Required."], "password": ["Too short."]},
    )
    assert out["success"] is False
    assert out["error"]["code"] == "VALIDATION_ERROR"
    assert out["details"] == {"email": ["Required."], "password": ["Too short."]}
    # request_id is the LAST key per the public contract
    assert list(out)[-1] == "request_id"


def test_envelope_from_domain_error_uses_subclass_code() -> None:
    err = ValidationError(details={"email": ["required"]})
    out = envelope_from_domain_error(err, request_id="rid-4")
    assert out["error"]["code"] == "VALIDATION_ERROR"
    assert out["details"] == {"email": ["required"]}
