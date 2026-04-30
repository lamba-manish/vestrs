"""Password hashing, JWT issue/verify, and cookie helpers.

argon2id is the password hash. PyJWT (HS256) issues access + refresh tokens.
Cookie helpers centralize the per-env policy (Secure / SameSite / Domain) so
every endpoint behaves identically.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

import jwt
import uuid6
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Response

from app.core.config import AppEnv, Settings, get_settings
from app.core.errors import DomainError, ErrorCode

ACCESS_COOKIE = "vestrs_access"
REFRESH_COOKIE = "vestrs_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # refresh cookie only sent to /auth/*


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class TokenPayload:
    sub: UUID  # user id
    jti: UUID  # token id (matches refresh_tokens.id when type=refresh)
    type: TokenType
    family_id: UUID | None  # only meaningful for refresh tokens
    iat: int
    exp: int


_ph = PasswordHasher()


# ---- passwords ------------------------------------------------------------


def hash_password(plaintext: str) -> str:
    result: str = _ph.hash(plaintext)
    return result


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
    return True


def password_needs_rehash(hashed: str) -> bool:
    result: bool = _ph.check_needs_rehash(hashed)
    return result


# ---- refresh-token plaintext + storage hash ------------------------------


def new_refresh_token_value() -> str:
    """A high-entropy opaque string. We hash this for storage, never store the plaintext."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---- JWT ------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def issue_access_token(
    user_id: UUID, jti: UUID, *, settings: Settings | None = None
) -> tuple[str, datetime]:
    s = settings or get_settings()
    issued = _now()
    expires = issued + timedelta(seconds=s.access_token_ttl_seconds)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "jti": str(jti),
            "type": TokenType.ACCESS.value,
            "iat": int(issued.timestamp()),
            "exp": int(expires.timestamp()),
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    return token, expires


def issue_refresh_token(
    user_id: UUID,
    jti: UUID,
    family_id: UUID,
    *,
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    s = settings or get_settings()
    issued = _now()
    expires = issued + timedelta(seconds=s.refresh_token_ttl_seconds)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "jti": str(jti),
            "family_id": str(family_id),
            "type": TokenType.REFRESH.value,
            "iat": int(issued.timestamp()),
            "exp": int(expires.timestamp()),
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    return token, expires


def _domain_error(code: ErrorCode, message: str) -> DomainError:
    err = DomainError(message)
    err.code = code
    err.http_status = 401
    return err


def decode_token(
    token: str, *, expected: TokenType, settings: Settings | None = None
) -> TokenPayload:
    s = settings or get_settings()
    try:
        raw: dict[str, Any] = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise _domain_error(ErrorCode.AUTH_TOKEN_EXPIRED, "Token expired.") from exc
    except jwt.PyJWTError as exc:
        raise _domain_error(ErrorCode.AUTH_TOKEN_INVALID, "Invalid token.") from exc

    if raw.get("type") != expected.value:
        raise _domain_error(ErrorCode.AUTH_TOKEN_INVALID, "Wrong token type.")

    try:
        family_id = UUID(raw["family_id"]) if raw.get("family_id") else None
        return TokenPayload(
            sub=UUID(raw["sub"]),
            jti=UUID(raw["jti"]),
            type=TokenType(raw["type"]),
            family_id=family_id,
            iat=int(raw["iat"]),
            exp=int(raw["exp"]),
        )
    except (KeyError, ValueError) as exc:
        raise _domain_error(ErrorCode.AUTH_TOKEN_INVALID, "Malformed token.") from exc


# ---- cookies --------------------------------------------------------------


def _cookie_common(settings: Settings) -> dict[str, Any]:
    is_local = settings.app_env is AppEnv.LOCAL
    return {
        "httponly": True,
        "secure": not is_local,
        "samesite": "lax" if is_local else "strict",
        "domain": settings.cookie_domain if not is_local else None,
    }


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_expires: datetime,
    refresh_expires: datetime,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    common = _cookie_common(s)
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=max(0, int((access_expires - _now()).total_seconds())),
        path="/",
        **common,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=max(0, int((refresh_expires - _now()).total_seconds())),
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def clear_auth_cookies(response: Response, *, settings: Settings | None = None) -> None:
    s = settings or get_settings()
    common = _cookie_common(s)
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=common["domain"])
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, domain=common["domain"])


def new_jti() -> UUID:
    return uuid6.uuid6()
