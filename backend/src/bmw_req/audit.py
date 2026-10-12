"""The append-only audit trail writer (AGENTS rule 6). Every change to requirement content, score, priority, evidence,
status or a setting is one `audit_event` row; the table refuses UPDATE and DELETE (triggers in `db.py`)."""

import json

from bmw_req.db import Connection


def audit(conn, *, actor_type, actor_id, action, entity_type, entity_id, field=None, old=None, new=None,
          rationale=None, model=None, prompt_ref=None, run_id=None):
    conn.execute(
        """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, field, old_value, new_value,
                                    rationale, model, prompt_ref, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (actor_type, actor_id, action, entity_type, entity_id, field,
         None if old is None else (old if isinstance(old, str) else json.dumps(old, ensure_ascii=False)),
         None if new is None else (new if isinstance(new, str) else json.dumps(new, ensure_ascii=False)),
         rationale, model, prompt_ref, run_id),
    )


def log_access(conn: Connection, actor: str, action: str, entity_type: str, entity_id: str, detail=None):
    """Access events (view/export) are part of the audit trail (brief: 'all actions, changes, access events')."""
    audit(conn, actor_type="human", actor_id=actor or "anonymous", action=action, entity_type=entity_type,
          entity_id=entity_id, new=detail)
