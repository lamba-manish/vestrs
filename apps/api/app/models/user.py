"""User model — the root of every onboarding flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.refresh_token import RefreshToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile fields populated after signup (slice 5).
    full_name: Mapped[str | None] = mapped_column(String(120))
    nationality: Mapped[str | None] = mapped_column(String(2))  # ISO-3166-1 alpha-2
    domicile: Mapped[str | None] = mapped_column(String(2))  # ISO-3166-1 alpha-2
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164

    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={_mask_email(self.email)}>"


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain[:1]}***"
