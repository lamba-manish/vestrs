"""Auth request + response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupRequest(_Strict):
    email: EmailStr
    password: SecretStr = Field(
        min_length=12,
        max_length=128,
        description="Plain password — argon2id-hashed at storage.",
    )


class LoginRequest(_Strict):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    """Public user shape — what the client is allowed to render.

    Deliberately excludes the admin flag and any role/permission state. Roles
    live in the access-token JWT and are enforced server-side via
    ``RoleRequired``; the client never decides what a user can do based on
    response flags.
    """

    id: UUID
    email: EmailStr
    full_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AuthSuccess(BaseModel):
    """Returned by signup/login/refresh — tokens travel in cookies, but we
    echo the user payload so the client can render without an extra round-trip."""

    user: UserPublic
