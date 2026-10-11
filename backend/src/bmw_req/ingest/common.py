"""Shared bits of the deterministic ingests: batch + audit rows, existing-ref lookup."""

import json
import sqlite3


def existing_refs(conn: sqlite3.Connection, kind: str, file_name: str) -> set[str]:
    return {
        r[0] for r in conn.execute(
            "SELECT ref FROM source_item WHERE kind = ? AND ref LIKE ?", (kind, f"{file_name}#%")
        )
    }


def open_batch(conn: sqlite3.Connection, kind: str, description: str, file_name: str) -> int:
    """Insert an `ingest_batch` row; call inside the caller's transaction."""
    return conn.execute(
        "INSERT INTO ingest_batch (kind, description, file) VALUES (?, ?, ?)", (kind, description, file_name)
    ).lastrowid


def audit_batch(conn: sqlite3.Connection, actor_id: str, batch_id: int, payload: dict) -> None:
    conn.execute(
        """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value)
           VALUES ('system', ?, 'ingest', 'ingest_batch', ?, ?)""",
        (actor_id, str(batch_id), json.dumps(payload)),
    )
