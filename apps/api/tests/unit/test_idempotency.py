"""hash_body — stable, order-insensitive."""

from __future__ import annotations

from app.core.idempotency import hash_body


def test_hash_is_stable() -> None:
    assert hash_body({"a": 1, "b": 2}) == hash_body({"a": 1, "b": 2})


def test_hash_is_order_insensitive() -> None:
    assert hash_body({"a": 1, "b": 2}) == hash_body({"b": 2, "a": 1})


def test_hash_changes_with_value() -> None:
    assert hash_body({"a": 1}) != hash_body({"a": 2})


def test_hash_changes_with_extra_field() -> None:
    assert hash_body({"a": 1}) != hash_body({"a": 1, "b": 2})


def test_hash_handles_decimal_via_default_str() -> None:
    from decimal import Decimal

    h1 = hash_body({"amount": Decimal("100.0000")})
    h2 = hash_body({"amount": Decimal("100.0000")})
    assert h1 == h2
