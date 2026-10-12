"""Shared bits of the deterministic ingests: batch + audit rows, existing-ref lookup."""

import json

from bmw_req.db import Connection


def existing_refs(conn: Connection, kind: str, file_name: str) -> set[str]:
    return {
        r[0] for r in conn.execute(
            "SELECT ref FROM source_item WHERE kind = ? AND ref LIKE ?", (kind, f"{file_name}#%")
        )
    }


def open_batch(conn: Connection, kind: str, description: str, file_name: str) -> int:
    """Insert an `ingest_batch` row; call inside the caller's transaction."""
    return conn.execute(
        "INSERT INTO ingest_batch (kind, description, file) VALUES (?, ?, ?) RETURNING id", (kind, description, file_name)
    ).fetchone()[0]


def audit_batch(conn: Connection, actor_id: str, batch_id: int, payload: dict) -> None:
    conn.execute(
        """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value)
           VALUES ('system', ?, 'ingest', 'ingest_batch', ?, ?)""",
        (actor_id, str(batch_id), json.dumps(payload)),
    )
