"""SQLite store (D-016) with sqlite-vec loaded (D-018).

Only the LLM usage log exists so far; the demo data model is open (Q-017).
"""

import sqlite3
from pathlib import Path

import sqlite_vec

from bmw_req.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id                 INTEGER PRIMARY KEY,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    settled_at         TEXT,
    job                TEXT NOT NULL,
    demo               INTEGER NOT NULL DEFAULT 0,
    kind               TEXT NOT NULL,            -- responses | embeddings
    model              TEXT NOT NULL,
    service_tier       TEXT,
    status             TEXT NOT NULL,            -- reserved | completed | failed
    reserved_usd       REAL NOT NULL,
    cost_usd           REAL,
    input_tokens       INTEGER,
    cached_tokens      INTEGER,
    cache_write_tokens INTEGER,
    output_tokens      INTEGER,
    reasoning_tokens   INTEGER,
    search_calls       INTEGER,
    response_id        TEXT,
    error              TEXT
);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the app DB (default `data/app.db`), load sqlite-vec and ensure the schema.

    Autocommit mode: callers open transactions explicitly (`BEGIN IMMEDIATE`).
    """
    if path is None:
        path = get_settings().db_path
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript(SCHEMA)
    return conn
