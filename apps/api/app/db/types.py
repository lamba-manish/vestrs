"""Custom SQLAlchemy column types.

UUIDv6 is the project standard for primary keys: time-ordered (good index
locality, predictable cursor pagination), opaque, and not enumerable.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import uuid6
from sqlalchemy import Dialect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


def new_uuid() -> UUID:
    """Generate a fresh UUIDv6 (sortable, no enumeration)."""
    return uuid6.uuid6()


class UUIDType(TypeDecorator[UUID]):
    """Postgres UUID column that defaults to UUIDv6 in Python.

    We bind v6 in the application, not the database, so dev/test fixtures
    behave the same way as production and so test seeds stay deterministic.
    """

    impl = PG_UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    def process_result_value(self, value: Any, dialect: Dialect) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
