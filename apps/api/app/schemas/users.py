"""User profile request + response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import phonenumbers
import pycountry
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_iso_country(raw: str) -> str:
    code = raw.strip().upper()
    if len(code) != 2 or pycountry.countries.get(alpha_2=code) is None:
        raise ValueError("must be a valid ISO-3166-1 alpha-2 country code")
    return code


def _validate_e164(raw: str) -> str:
    raw = raw.strip()
    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("must be a valid E.164 phone number (e.g. +14155551234)") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("phone number is not a valid number")
    formatted: str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return formatted


class ProfileUpdateRequest(_Strict):
    """Onboarding profile fields. All required at this step.

    Country fields use ISO-3166-1 alpha-2 (e.g. "US", "IN"). Phone is E.164.
    """

    full_name: str = Field(min_length=1, max_length=120)
    nationality: str = Field(min_length=2, max_length=2)
    domicile: str = Field(min_length=2, max_length=2)
    phone: str = Field(min_length=8, max_length=20)

    @field_validator("full_name", mode="before")
    @classmethod
    def _strip_full_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("nationality", "domicile", mode="before")
    @classmethod
    def _check_country(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _validate_iso_country(value)
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def _check_phone(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _validate_e164(value)
        return value


class UserProfile(BaseModel):
    """The user's profile — what GET /users/me returns."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    nationality: str | None = None
    domicile: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)
