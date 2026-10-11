"""Simulated ingest waves (Q-012, D-027). The feedback has no dates, so time is simulated: each source item
gets the wave in which it becomes visible to the pipeline. Clearly labelled as a simulation in the UI.

Feedback is split per (derivative × channel × market) stratum, so a wave never looks different only
because it holds another channel (Q-012: channels differ systematically, Q-005).
"""

import json
import random
import sqlite3
from collections import defaultdict

SEED = 2026

WAVES = {
    1: {
        "label": "Wave 1 · Concept kick-off",
        "simulated_date": "2026-11",
        "description": "First half of the verbatims (stratified), 2024 sales, option lists, reference data, "
                       "baseline web research.",
    },
    2: {
        "label": "Wave 2 · +6 months",
        "simulated_date": "2027-05",
        "description": "Second half of the verbatims, customer study 2025, sales 2025 and 2030 forecast.",
    },
    3: {
        "label": "Wave 3 · +12 months, market event",
        "simulated_date": "2027-11",
        "description": "New web research on recent competitor launches and market shifts.",
    },
}


def assign_feedback_waves(conn: sqlite3.Connection, seed: int = SEED) -> dict:
    """Assign wave 1 or 2 to every feedback source item. Deterministic; re-running gives the same split."""
    strata = defaultdict(list)
    for r in conn.execute("SELECT id, external_id, vehicle_model_id, market_code, meta_json FROM source_item"
                          " WHERE kind = 'feedback' ORDER BY external_id"):
        channel = json.loads(r["meta_json"]).get("channel")
        strata[(r["vehicle_model_id"], channel, r["market_code"])].append(r["id"])
    rng = random.Random(seed)
    updates, counts = [], defaultdict(int)
    for key in sorted(strata, key=str):
        ids = strata[key][:]
        rng.shuffle(ids)
        half = (len(ids) + 1) // 2
        for i, sid in enumerate(ids):
            wave = 1 if i < half else 2
            updates.append((wave, sid))
            counts[(key[0], wave)] += 1
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("UPDATE source_item SET wave = ? WHERE id = ?", updates)
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, rationale)
               VALUES ('system', 'pipeline.waves', 'assign_waves', 'source_item', 'feedback', ?, ?)""",
            (json.dumps({f"{k[0]}:w{k[1]}": v for k, v in sorted(counts.items())}),
             f"Simulated ingest waves (Q-012), stratified by derivative × channel × market, seed {seed}"),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return dict(counts)


if __name__ == "__main__":
    from bmw_req.db import connect

    print(assign_feedback_waves(connect()))
