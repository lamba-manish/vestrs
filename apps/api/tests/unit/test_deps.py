"""DI helpers — RoleRequired, TokenSubject extraction."""

from __future__ import annotations

import pytest

from app.api.deps import RoleRequired, TokenSubject
from app.core.errors import DomainError, ErrorCode, ForbiddenError
from app.core.security import Role, new_jti


def _subject(role: Role) -> TokenSubject:
    return TokenSubject(id=new_jti(), email="caller@example.com", role=role)


async def test_role_required_passes_matching_role() -> None:
    gate = RoleRequired(Role.USER)
    out = await gate(_subject(Role.USER))
    assert out.role is Role.USER


async def test_role_required_rejects_other_role() -> None:
    gate = RoleRequired(Role.ADMIN)
    with pytest.raises(ForbiddenError) as exc:
        await gate(_subject(Role.USER))
    assert isinstance(exc.value, DomainError)
    assert exc.value.code is ErrorCode.FORBIDDEN
    assert exc.value.http_status == 403


async def test_role_required_accepts_any_listed_role() -> None:
    gate = RoleRequired(Role.USER, Role.ADMIN)
    assert (await gate(_subject(Role.USER))).role is Role.USER
    assert (await gate(_subject(Role.ADMIN))).role is Role.ADMIN


def test_role_required_needs_at_least_one_role() -> None:
    with pytest.raises(ValueError, match="at least one role"):
        RoleRequired()
