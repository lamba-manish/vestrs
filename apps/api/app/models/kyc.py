"""KYC check model — one row per submission attempt.

Each row is immutable except for status / resolved_at when a pending check
flips to a terminal state. New attempts (retries) create new rows; the
``attempt_number`` column makes the chain explicit and the cap easy to
enforce in SQL.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UUIDType

if TYPE_CHECKING:
    from app.models.user import User


class KycStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# Maximum attempts (initial submit + retries). Re-attempts beyond this are
# refused with KYC_RETRY_EXHAUSTED.
KYC_MAX_ATTEMPTS = 3


class KycCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kyc_checks"
    __table_args__ = (
        Index("ix_kyc_checks_user_id_attempt_number", "user_id", "attempt_number"),
        Index("ix_kyc_checks_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped[User] = relationship()

    @property
    def is_terminal(self) -> bool:
        return self.status in {KycStatus.SUCCESS.value, KycStatus.FAILED.value}
