"""App role without UPDATE/DELETE on append-only tables (D-059 P2), see sql/0003_app_role.sql.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12
"""

import os

from alembic import op
from psycopg import sql

from migrations.helpers import run_sql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0003_app_role.sql")
    password = os.getenv("APP_DB_PASSWORD")
    if password:   # without it the role exists but cannot log in (and the app keeps the URL it was given)
        op.get_bind().connection.driver_connection.execute(
            sql.SQL("ALTER ROLE sharksight_app LOGIN PASSWORD {}").format(sql.Literal(password)))


def downgrade() -> None:
    raise NotImplementedError("Restore a backup (make backup) instead.")
