"""Shared plumbing: one database connection for the process, a process-wide lock, the acting PM, error mapping.

The API opens ONE PostgreSQL connection (D-059) and reuses it. One connection runs one statement or transaction at a
time, so every access — reads too — goes through `with db() as conn:`, which holds `LOCK`. Write paths open
`BEGIN IMMEDIATE` themselves; never wrap them in a transaction here.

Do not hold the lock across a dependency boundary: FastAPI may run a dependency's enter/exit in different threads, and
an RLock must be released by the thread that acquired it. Endpoints take the lock themselves.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import unquote

from fastapi import Query, Header, HTTPException

from bmw_req.config import get_settings
from bmw_req.db import Connection, connect

LOCK = threading.RLock()
DEFAULT_PM = "Atahan (PM)"


class Database:
    """Lazily opened shared connection to DATABASE_URL (the database the pipeline jobs open, D-059)."""

    def __init__(self) -> None:
        self._conn: Connection | None = None

    def conn(self) -> Connection:
        with LOCK:
            if self._conn is None:
                self._conn = connect(get_settings().database_url)
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
def db() -> Iterator[Connection]:
    """Serialized access to the shared connection."""
    with LOCK:
        yield DB.conn()


def get_actor(x_actor: str | None = Header(default=None), as_actor: str | None = Query(default=None)) -> str:
    """Named human actor for writes and access events (no auth; header may be percent-encoded for non-Latin-1 names).
    `?as_actor=` is the fallback for plain download links, which can't send headers."""
    raw = x_actor or as_actor
    name = unquote(raw).strip() if raw else ""
    return name or DEFAULT_PM


def conflict(msg: str) -> HTTPException:
    return HTTPException(status_code=409, detail=msg)


def not_found(msg: str) -> HTTPException:
    return HTTPException(status_code=404, detail=msg)


def need_rationale(rationale: str | None, what: str = "A rationale") -> str:
    """A PM decision needs a reason: ≥ 5 characters after strip (409)."""
    if not rationale or len(rationale.strip()) < 5:
        raise conflict(f"{what} is required (at least 5 characters).")
    return rationale.strip()
