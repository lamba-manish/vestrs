"""Accreditation check model.

Distinct from KYC: KYC is typically synchronous (or near-real-time), while
accreditation reviews can take 12-48 hours. The state machine is:

    not_started -> pending -> success | failed

The mock vendor returns ``pending`` from ``submit`` and resolves later when
``fetch_status`` is called. The ARQ worker schedules that resolution.
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


class AccreditationStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class AccreditationCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accreditation_checks"
    __table_args__ = (
        Index("ix_accreditation_user_id_attempt", "user_id", "attempt_number"),
        Index("ix_accreditation_user_id_created_at", "user_id", "created_at"),
        Index("ix_accreditation_status", "status"),
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
        return self.status in {AccreditationStatus.SUCCESS.value, AccreditationStatus.FAILED.value}
