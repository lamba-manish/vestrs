"""Domain error codes and exception hierarchy.

Services raise ``DomainError`` (or a subclass). The global exception handler
maps the error to the canonical response envelope and HTTP status. Routes
never construct error responses by hand.

The error code is the stable contract: frontends switch on the code, not the
HTTP status.
"""

from __future__ import annotations

from enum import StrEnum
from http import HTTPStatus
from typing import Any


class ErrorCode(StrEnum):
    # generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"

    # auth
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_EMAIL_NOT_FOUND = "AUTH_EMAIL_NOT_FOUND"
    AUTH_PASSWORD_INCORRECT = "AUTH_PASSWORD_INCORRECT"  # noqa: S105
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"  # noqa: S105 — error code, not a credential
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"  # noqa: S105 — error code, not a credential
    AUTH_REFRESH_REQUIRED = "AUTH_REFRESH_REQUIRED"

    # KYC
    KYC_NOT_STARTED = "KYC_NOT_STARTED"
    KYC_PENDING = "KYC_PENDING"
    KYC_FAILED = "KYC_FAILED"
    KYC_RETRY_EXHAUSTED = "KYC_RETRY_EXHAUSTED"

    # accreditation
    ACCREDITATION_PENDING = "ACCREDITATION_PENDING"
    ACCREDITATION_FAILED = "ACCREDITATION_FAILED"

    # bank
    BANK_LINK_FAILED = "BANK_LINK_FAILED"
    BANK_NOT_LINKED = "BANK_NOT_LINKED"

    # investment
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVESTMENT_FAILED = "INVESTMENT_FAILED"


_DEFAULT_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.CONFLICT: HTTPStatus.CONFLICT,
    ErrorCode.FORBIDDEN: HTTPStatus.FORBIDDEN,
    ErrorCode.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorCode.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
    ErrorCode.IDEMPOTENCY_KEY_REUSED: HTTPStatus.CONFLICT,
    ErrorCode.AUTH_INVALID_CREDENTIALS: HTTPStatus.UNAUTHORIZED,
    ErrorCode.AUTH_EMAIL_NOT_FOUND: HTTPStatus.UNAUTHORIZED,
    ErrorCode.AUTH_PASSWORD_INCORRECT: HTTPStatus.UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_EXPIRED: HTTPStatus.UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_INVALID: HTTPStatus.UNAUTHORIZED,
    ErrorCode.AUTH_REFRESH_REQUIRED: HTTPStatus.UNAUTHORIZED,
    ErrorCode.KYC_NOT_STARTED: HTTPStatus.CONFLICT,
    ErrorCode.KYC_PENDING: HTTPStatus.ACCEPTED,
    ErrorCode.KYC_FAILED: HTTPStatus.BAD_REQUEST,
    ErrorCode.KYC_RETRY_EXHAUSTED: HTTPStatus.CONFLICT,
    ErrorCode.ACCREDITATION_PENDING: HTTPStatus.ACCEPTED,
    ErrorCode.ACCREDITATION_FAILED: HTTPStatus.BAD_REQUEST,
    ErrorCode.BANK_LINK_FAILED: HTTPStatus.BAD_REQUEST,
    ErrorCode.BANK_NOT_LINKED: HTTPStatus.CONFLICT,
    ErrorCode.INSUFFICIENT_BALANCE: HTTPStatus.BAD_REQUEST,
    ErrorCode.INVESTMENT_FAILED: HTTPStatus.BAD_REQUEST,
}


def default_status_for(code: ErrorCode) -> int:
    return _DEFAULT_HTTP_STATUS[code]


class DomainError(Exception):
    """Base for all errors that map to the response envelope.

    Carry an ``ErrorCode`` plus a user-safe message. Optionally attach
    structured ``details`` (per-field messages, etc.). Never embed PII.
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, list[str]] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.details = details
        self.http_status = http_status or default_status_for(self.code)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        return payload


class ValidationError(DomainError):
    code = ErrorCode.VALIDATION_ERROR
    default_message = "The provided input data is invalid."


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND
    default_message = "The requested resource was not found."


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT
    default_message = "The request conflicts with the current state."


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN
    default_message = "You do not have permission to perform this action."


class RateLimitedError(DomainError):
    code = ErrorCode.RATE_LIMITED
    default_message = "Too many requests. Please try again later."


class AuthError(DomainError):
    code = ErrorCode.AUTH_INVALID_CREDENTIALS
    default_message = "Authentication failed."
