"""PostgreSQL test helpers (D-059): throwaway databases on the local server (TEST_DATABASE_URL, `make db`).

`template_url()` builds one migrated template database per test session; `fresh_db()` clones it in milliseconds
(CREATE DATABASE … TEMPLATE) and drops it afterwards. Tests skip when no server is reachable.
"""

from __future__ import annotations

import argparse
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

import bmw_req.config  # noqa: F401  (loads .env)

BACKEND = Path(__file__).resolve().parents[1]
_template: str | None = None


def server_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set (see .env.example)")
    try:
        psycopg.connect(url, connect_timeout=2).close()
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not reachable — start it with `make db`")
    return url


def with_db(url: str, name: str) -> str:
    p = urlsplit(url)
    return urlunsplit(p._replace(path=f"/{name}"))


def _admin(sql: str) -> None:
    with psycopg.connect(server_url(), autocommit=True) as c:
        c.execute(sql)


def template_url() -> str:
    """A database with every migration applied, created once per session (dropped at exit by `drop_all`)."""
    global _template
    if _template is None:
        from alembic import command
        from alembic.config import Config

        name = f"t_template_{uuid.uuid4().hex[:8]}"
        _admin(f'CREATE DATABASE "{name}"')
        url = with_db(server_url(), name)
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        cfg.cmd_opts = argparse.Namespace(x=[f"url={url}"])
        command.upgrade(cfg, "head")
        _template = name
    return with_db(server_url(), _template)


REAL_DATA = "sharksight_testdata"   # a copy of the real data for the API tests (`make testdata`)


def has_db(name: str) -> bool:
    with psycopg.connect(server_url(), autocommit=True) as c:
        return c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None


@contextmanager
def fresh_db(template: str | None = None):
    """URL of a new database cloned from `template` (default: the empty migrated template); dropped on exit."""
    tpl = template or urlsplit(template_url()).path.lstrip("/")
    name = f"t_{uuid.uuid4().hex[:12]}"
    _admin(f'CREATE DATABASE "{name}" TEMPLATE "{tpl}"')
    try:
        yield with_db(server_url(), name)
    finally:
        _admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def drop_template() -> None:
    global _template
    if _template is not None:
        _admin(f'DROP DATABASE IF EXISTS "{_template}" WITH (FORCE)')
        _template = None
