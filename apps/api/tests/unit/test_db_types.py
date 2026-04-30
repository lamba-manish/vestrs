"""UUIDType + new_uuid() behaviour."""

from __future__ import annotations

from uuid import UUID

from app.db.types import UUIDType, new_uuid


def test_new_uuid_returns_v6() -> None:
    value = new_uuid()
    assert isinstance(value, UUID)
    assert value.version == 6


def test_uuid_type_bind_accepts_uuid_and_string() -> None:
    t = UUIDType()
    val = new_uuid()
    assert t.process_bind_param(val, dialect=None) == val  # type: ignore[arg-type]
    assert t.process_bind_param(str(val), dialect=None) == val  # type: ignore[arg-type]
    assert t.process_bind_param(None, dialect=None) is None  # type: ignore[arg-type]


def test_uuid_type_result_normalizes() -> None:
    t = UUIDType()
    val = new_uuid()
    assert t.process_result_value(val, dialect=None) == val  # type: ignore[arg-type]
    assert t.process_result_value(str(val), dialect=None) == val  # type: ignore[arg-type]
    assert t.process_result_value(None, dialect=None) is None  # type: ignore[arg-type]
