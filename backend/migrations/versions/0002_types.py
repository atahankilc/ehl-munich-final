"""Native types: system timestamps → timestamptz, weights_json → jsonb (D-059 P2), see sql/0002_types.sql.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""

from migrations.helpers import run_sql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0002_types.sql")


def downgrade() -> None:
    raise NotImplementedError("Restore a backup (make backup) instead.")
