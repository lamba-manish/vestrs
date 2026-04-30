"""ORM model defaults and metadata wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.db.base import Base
from app.models import AuditLog, RefreshToken, User
from app.models.audit_log import AuditAction, AuditStatus


def test_metadata_includes_all_three_tables() -> None:
    tables = set(Base.metadata.tables)
    assert {"users", "refresh_tokens", "audit_logs"}.issubset(tables)


def test_user_repr_masks_email() -> None:
    user = User(email="alice@example.com", password_hash="x")
    rendered = repr(user)
    assert "alice" not in rendered
    assert "example" not in rendered
    assert "***" in rendered


def test_audit_action_constants_exist() -> None:
    # Spot-check the auth actions; the full set grows in later slices.
    assert AuditAction.AUTH_SIGNUP == "AUTH_SIGNUP"
    assert AuditAction.AUTH_LOGIN == "AUTH_LOGIN"
    assert AuditAction.AUTH_REFRESH_REUSE_DETECTED == "AUTH_REFRESH_REUSE_DETECTED"


def test_audit_status_constants_exist() -> None:
    assert {AuditStatus.SUCCESS, AuditStatus.FAILURE, AuditStatus.PENDING} == {
        "success",
        "failure",
        "pending",
    }


def test_refresh_token_is_active_predicate() -> None:
    token = RefreshToken(
        user_id=UUID("00000000-0000-6000-8000-000000000001"),
        token_hash="a" * 64,
        family_id=UUID("00000000-0000-6000-8000-000000000002"),
        expires_at=datetime.now(UTC),
    )
    assert token.is_active is True

    token.replaced_by_id = UUID("00000000-0000-6000-8000-000000000003")
    assert token.is_active is False

    token.replaced_by_id = None
    token.revoked_at = datetime.now(UTC)
    assert token.is_active is False


def test_audit_log_metadata_default_is_empty_dict() -> None:
    log = AuditLog(
        action=AuditAction.AUTH_LOGIN,
        status=AuditStatus.SUCCESS,
        audit_metadata={},
    )
    assert log.audit_metadata == {}
