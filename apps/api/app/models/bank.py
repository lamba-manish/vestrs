"""Linked bank account model.

Only masked details are persisted: bank name, last 4 digits of the account
number, currency, mock balance. Raw account/routing numbers never leave the
request boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UUIDType

if TYPE_CHECKING:
    from app.models.user import User


class BankAccountStatus(StrEnum):
    ACTIVE = "active"
    UNLINKED = "unlinked"


class BankAccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    MONEY_MARKET = "money_market"


class BankAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        Index(
            "ix_bank_accounts_user_id_status",
            "user_id",
            "status",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    bank_name: Mapped[str] = mapped_column(String(80), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    mock_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0")
    )

    status: Mapped[str] = mapped_column(
        String(16), default=BankAccountStatus.ACTIVE.value, nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped[User] = relationship()

    @property
    def is_active(self) -> bool:
        return self.status == BankAccountStatus.ACTIVE.value
