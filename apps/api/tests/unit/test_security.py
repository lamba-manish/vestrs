"""Password + JWT helpers — pure unit tests."""

from __future__ import annotations

import pytest

from app.core.errors import DomainError, ErrorCode
from app.core.security import (
    Role,
    TokenType,
    decode_token,
    hash_password,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
    new_jti,
    new_refresh_token_value,
    verify_password,
)


def test_password_round_trip() -> None:
    h = hash_password("a-strong-passphrase-1")
    assert h.startswith("$argon2id$")
    assert verify_password("a-strong-passphrase-1", h) is True
    assert verify_password("not-it", h) is False


def test_password_two_hashes_differ() -> None:
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # salt makes them different


def test_refresh_token_value_is_random() -> None:
    a = new_refresh_token_value()
    b = new_refresh_token_value()
    assert a != b
    assert len(a) >= 40


def test_refresh_hash_is_stable() -> None:
    assert hash_refresh_token("abc") == hash_refresh_token("abc")
    assert hash_refresh_token("a") != hash_refresh_token("b")


def test_access_token_round_trip() -> None:
    user_id = new_jti()
    jti = new_jti()
    token, _exp = issue_access_token(user_id, jti, email="caller@example.com", role=Role.USER)
    payload = decode_token(token, expected=TokenType.ACCESS)
    assert payload.sub == user_id
    assert payload.jti == jti
    assert payload.type is TokenType.ACCESS
    assert payload.family_id is None
    assert payload.email == "caller@example.com"
    assert payload.role is Role.USER


def test_access_token_carries_admin_role() -> None:
    token, _ = issue_access_token(new_jti(), new_jti(), email="root@example.com", role=Role.ADMIN)
    payload = decode_token(token, expected=TokenType.ACCESS)
    assert payload.role is Role.ADMIN


def test_refresh_token_does_not_carry_role_or_email() -> None:
    token, _ = issue_refresh_token(new_jti(), new_jti(), new_jti())
    payload = decode_token(token, expected=TokenType.REFRESH)
    assert payload.email is None
    assert payload.role is Role.USER  # default fallback


def test_refresh_token_round_trip() -> None:
    user_id = new_jti()
    jti = new_jti()
    family = new_jti()
    token, _exp = issue_refresh_token(user_id, jti, family)
    payload = decode_token(token, expected=TokenType.REFRESH)
    assert payload.type is TokenType.REFRESH
    assert payload.family_id == family


def test_decode_rejects_wrong_type() -> None:
    token, _ = issue_access_token(new_jti(), new_jti(), email="x@example.com", role=Role.USER)
    with pytest.raises(DomainError) as exc:
        decode_token(token, expected=TokenType.REFRESH)
    assert exc.value.code is ErrorCode.AUTH_TOKEN_INVALID


def test_decode_rejects_garbage() -> None:
    with pytest.raises(DomainError) as exc:
        decode_token("not.a.jwt", expected=TokenType.ACCESS)
    assert exc.value.code is ErrorCode.AUTH_TOKEN_INVALID
