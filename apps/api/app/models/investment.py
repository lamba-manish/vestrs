"""Investment model — one row per executed investment.

Money lives here as ``NUMERIC(20, 4)`` (CLAUDE.md sec. 5: Decimal end-to-end,
never float). The mock flow always settles synchronously — the model has a
``status`` column so a future async-escrow vendor can plug in without a
migration.
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
    from app.models.bank import BankAccount
    from app.models.user import User


class InvestmentStatus(StrEnum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


class Investment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investments"
    __table_args__ = (
        Index("ix_investments_user_id_created_at", "user_id", "created_at"),
        Index("ix_investments_status", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    bank_account_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=InvestmentStatus.SETTLED.value, nullable=False
    )

    escrow_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped[User] = relationship()
    bank_account: Mapped[BankAccount] = relationship()
