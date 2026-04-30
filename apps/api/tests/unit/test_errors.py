"""Domain error / status mapping tests."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from app.core.errors import (
    AuthError,
    ConflictError,
    DomainError,
    ErrorCode,
    NotFoundError,
    RateLimitedError,
    ValidationError,
    default_status_for,
)


@pytest.mark.parametrize(
    ("err_cls", "expected_code", "expected_status"),
    [
        (ValidationError, ErrorCode.VALIDATION_ERROR, HTTPStatus.UNPROCESSABLE_ENTITY),
        (NotFoundError, ErrorCode.NOT_FOUND, HTTPStatus.NOT_FOUND),
        (ConflictError, ErrorCode.CONFLICT, HTTPStatus.CONFLICT),
        (RateLimitedError, ErrorCode.RATE_LIMITED, HTTPStatus.TOO_MANY_REQUESTS),
        (AuthError, ErrorCode.AUTH_INVALID_CREDENTIALS, HTTPStatus.UNAUTHORIZED),
    ],
)
def test_subclasses_carry_their_code_and_status(
    err_cls: type[DomainError], expected_code: ErrorCode, expected_status: HTTPStatus
) -> None:
    err = err_cls()
    assert err.code is expected_code
    assert err.http_status == expected_status


def test_custom_message_and_details_are_preserved() -> None:
    err = ValidationError("nope", details={"email": ["required"]})
    assert err.message == "nope"
    assert err.details == {"email": ["required"]}


def test_default_status_table_covers_every_error_code() -> None:
    # Guards against a new ErrorCode being added without a status mapping.
    for code in ErrorCode:
        assert default_status_for(code) > 0
