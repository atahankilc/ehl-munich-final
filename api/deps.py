"""Shared plumbing: one SQLite connection for the process, a process-wide lock, the acting PM, error mapping.

`bmw_req.db.connect()` runs the schema script, migrations and loads sqlite-vec on every call, so the API opens ONE
connection and reuses it. A sqlite3 connection is not safe for concurrent use, so every access — reads too — goes
through `with db() as conn:` which holds `LOCK`. Service write functions open `BEGIN IMMEDIATE` themselves; never wrap
them in a transaction here.

Do not hold the lock across a dependency boundary: FastAPI may run a dependency's enter/exit in different threads, and
an RLock must be released by the thread that acquired it. Endpoints take the lock themselves.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

from fastapi import Query, Header, HTTPException

from api.labels import DEFAULT_PM
from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req.service import ActionError

LOCK = threading.RLock()


class Database:
    """Lazily opened shared connection to `$DATA_DIR/app.db` (the same file the pipeline jobs open)."""

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        return get_settings().db_path

    def conn(self) -> sqlite3.Connection:
        with LOCK:
            if self._conn is None:
                self._conn = connect(self.path)
            return self._conn

    def close(self) -> None:
        with LOCK:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None


DB = Database()


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """Serialized access to the shared connection."""
    with LOCK:
        yield DB.conn()


def get_actor(x_actor: str | None = Header(default=None), as_actor: str | None = Query(default=None)) -> str:
    """Named human actor for writes and access events (no auth; header may be percent-encoded for non-Latin-1 names).
    `?as_actor=` is the fallback for plain download links, which can't send headers."""
    raw = x_actor or as_actor
    name = unquote(raw).strip() if raw else ""
    return name or DEFAULT_PM


@contextmanager
def action_errors() -> Iterator[None]:
    """Map the service layer's user-facing refusals to HTTP 409 {detail: message}."""
    try:
        yield
    except ActionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


def conflict(msg: str) -> HTTPException:
    return HTTPException(status_code=409, detail=msg)


def not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=404, detail=msg)


def need_rationale(rationale: str | None, what: str = "A rationale") -> str:
    """Same rule as `service._need`: ≥ 5 characters after strip (409, like an ActionError)."""
    if not rationale or len(rationale.strip()) < 5:
        raise conflict(f"{what} is required (at least 5 characters).")
    return rationale.strip()
