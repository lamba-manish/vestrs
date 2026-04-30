"""Investment schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestmentCreateRequest(_Strict):
    """Body for ``POST /api/v1/investments``.

    Currency is implicitly the linked bank account's currency — we don't
    accept it from the client to avoid mismatches.
    """

    amount: Decimal = Field(gt=Decimal("0"), max_digits=20, decimal_places=4)
    notes: str | None = Field(default=None, max_length=500)


class InvestmentPublic(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    status: str
    escrow_reference: str
    notes: str | None = None
    bank_account_id: UUID
    settled_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestmentList(BaseModel):
    items: list[InvestmentPublic]
    total: int
