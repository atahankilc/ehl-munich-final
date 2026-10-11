"""Agent activity events (D-043): one audit row per AI step, so the PM can watch the agent work (page 2 feed) and
every AI change stays in the append-only audit trail (rule 6)."""

import json


def log(conn, stage: str, action: str, payload: dict, run_id: int | None = None, model: str | None = None) -> None:
    conn.execute("""INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, model, run_id)
                    VALUES ('ai', ?, ?, 'checkpoint_run', ?, ?, ?, ?)""",
                 (f"structure.{stage}", action, str(run_id) if run_id else None, json.dumps(payload, ensure_ascii=False), model, run_id))
