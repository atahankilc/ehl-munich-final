"""Run a migration's SQL file through the raw psycopg connection: no parameter parsing, so `%` and `:name` in the SQL
(format strings, comments, PL/pgSQL) are taken literally."""

from pathlib import Path

from alembic import op

SQL_DIR = Path(__file__).parent / "sql"


def run_sql(name: str) -> None:
    op.get_bind().connection.driver_connection.execute((SQL_DIR / name).read_text())
