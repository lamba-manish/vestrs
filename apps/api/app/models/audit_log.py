"""Audit log — every state-changing event in the platform.

Per CLAUDE.md sec. 9, audit log writes happen in the same DB transaction as
the action they describe. Never best-effort, never fire-and-forget.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.types import UUIDType

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction:
    """Stable string constants for the ``action`` column.

    Not a StrEnum because we expect to grow this set across slices and a
    plain string column accepts new values without a migration.
    """

    # auth
    AUTH_SIGNUP = "AUTH_SIGNUP"
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_REFRESH = "AUTH_REFRESH"
    AUTH_REFRESH_REUSE_DETECTED = "AUTH_REFRESH_REUSE_DETECTED"
    AUTH_LOGOUT = "AUTH_LOGOUT"

    # profile
    PROFILE_UPDATED = "PROFILE_UPDATED"

    # KYC
    KYC_SUBMITTED = "KYC_SUBMITTED"
    KYC_RETRY_BLOCKED = "KYC_RETRY_BLOCKED"
    KYC_RETRY_EXHAUSTED = "KYC_RETRY_EXHAUSTED"

    # accreditation
    ACCREDITATION_SUBMITTED = "ACCREDITATION_SUBMITTED"
    ACCREDITATION_RESOLVED = "ACCREDITATION_RESOLVED"
    ACCREDITATION_RETRY_BLOCKED = "ACCREDITATION_RETRY_BLOCKED"

    # bank linking
    BANK_LINKED = "BANK_LINKED"
    BANK_LINK_FAILED = "BANK_LINK_FAILED"
    BANK_UNLINKED = "BANK_UNLINKED"
    BANK_LINK_BLOCKED = "BANK_LINK_BLOCKED"


class AuditStatus:
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
        Index("ix_audit_logs_request_id", "request_id"),
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(UUIDType())
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    request_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    user: Mapped[User | None] = relationship(back_populates="audit_logs")
