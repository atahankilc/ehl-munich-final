"""Alembic environment (D-059): connects with psycopg 3 as the database owner — `-x url=…`, else MIGRATION_DATABASE_URL,
else DATABASE_URL (from .env) — and runs raw-SQL migrations. No SQLAlchemy models — the schema lives in the migration
files. The app itself connects as `sharksight_app` (DATABASE_URL), which may not change the schema."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

import bmw_req.config  # noqa: F401  (loads .env)


def database_url() -> str:
    url = (context.get_x_argument(as_dictionary=True).get("url") or os.getenv("MIGRATION_DATABASE_URL")
           or os.getenv("DATABASE_URL"))
    if not url:
        raise SystemExit("DATABASE_URL is not set (see .env.example) — start the database with `make db`")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
