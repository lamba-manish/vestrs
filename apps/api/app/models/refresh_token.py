"""Refresh-token storage — supports rotation + reuse detection.

Tokens are stored hashed (sha256). On every refresh we rotate (issue a new
one and mark the old one as ``replaced_by``). If a previously-rotated
token is presented, the entire family (linked by ``family_id``) is revoked.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UUIDType

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # sha256 of the opaque refresh token string. The plaintext token is only
    # ever seen by the client and during issuance; we never store it.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # All rotations descending from a single login share a family_id. Reuse
    # detection revokes the whole family in one update.
    family_id: Mapped[UUID] = mapped_column(UUIDType(), nullable=False)

    # If non-null, this token was rotated; the new token's id is here.
    replaced_by_id: Mapped[UUID | None] = mapped_column(UUIDType())

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 max length

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.replaced_by_id is None
