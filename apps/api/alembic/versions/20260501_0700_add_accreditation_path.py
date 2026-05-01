"""add accreditation path + path_data (slice 29)

Revision ID: c4d92e75a3b1
Revises: a1a8ceea6397
Create Date: 2026-05-01 07:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d92e75a3b1"
down_revision: str | None = "a1a8ceea6397"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # path is nullable so historical rows (pre-slice-29) keep loading
    # without backfill. Service-layer code on new submissions always
    # populates it.
    op.add_column(
        "accreditation_checks",
        sa.Column("path", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "accreditation_checks",
        sa.Column(
            "path_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("accreditation_checks", "path_data")
    op.drop_column("accreditation_checks", "path")
