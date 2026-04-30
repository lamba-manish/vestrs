"""Bank linking API schemas — never echo raw account/routing numbers."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pycountry
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.models.bank import BankAccountType


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


_DIGITS = re.compile(r"^\d+$")


def _validate_iso_currency(raw: str) -> str:
    code = raw.strip().upper()
    if len(code) != 3 or pycountry.currencies.get(alpha_3=code) is None:
        raise ValueError("must be a valid ISO-4217 currency code")
    return code


class BankLinkRequest(_Strict):
    bank_name: str = Field(min_length=1, max_length=80)
    account_holder_name: str = Field(min_length=1, max_length=120)
    account_type: BankAccountType
    account_number: SecretStr = Field(min_length=4, max_length=34)
    routing_number: SecretStr = Field(min_length=8, max_length=12)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("bank_name", "account_holder_name", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("currency", mode="before")
    @classmethod
    def _check_currency(cls, v: Any) -> Any:
        return _validate_iso_currency(v) if isinstance(v, str) else v

    @field_validator("account_number", "routing_number", mode="after")
    @classmethod
    def _digits_only(cls, v: SecretStr) -> SecretStr:
        if not _DIGITS.match(v.get_secret_value()):
            raise ValueError("must contain only digits")
        return v


class BankAccountPublic(BaseModel):
    """Public view — masked. Plaintext numbers are never returned."""

    id: UUID
    bank_name: str
    account_holder_name: str
    account_type: str
    last_four: str
    currency: str
    mock_balance: Decimal
    status: str
    linked_at: datetime
    unlinked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BankSummary(BaseModel):
    """GET /bank — single active account or null."""

    linked: bool
    account: BankAccountPublic | None = None
