"""Baseline: today's schema on PostgreSQL + pgvector (D-059 P0), see sql/0001_baseline.sql.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from migrations.helpers import run_sql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0001_baseline.sql")


def downgrade() -> None:
    raise NotImplementedError("The baseline is not reversible; restore a backup instead.")
