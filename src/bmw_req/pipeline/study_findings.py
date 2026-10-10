"""Customer-study findings (D-026): one finding per study item × model × market, carrying its z-score
against the other items of the same column. Deterministic, no LLM.

`uv run python -m bmw_req.pipeline.study_findings`

Notable items (|z| ≥ NOTABLE_Z) are shown to derivation; all items can be linked later by the evidence linker,
so an average study result is visible as "no gap" instead of "no data".
"""

import json
import sqlite3

from bmw_req.db import connect
from bmw_req.pipeline.requirements import audit

METHOD = "study-v1"
NOTABLE_Z = 0.8


def describe(r) -> tuple[str, str, str]:
    z = r["z_within_column"]
    if r["scale"] == "dist_7":
        num = f"top-2-box {100 * (r['top2'] or 0):.0f}%, bottom-3-box {100 * (r['bottom3'] or 0):.0f}%, net {100 * (r['net'] or 0):+.0f}"
    else:
        num = f"mean {r['mean']:.2f} (scale unconfirmed, Q-006)"
    kind = "satisfaction_gap" if z is not None and z <= -NOTABLE_Z else (
        "satisfaction_strength" if z is not None and z >= NOTABLE_Z else "satisfaction_level")
    word = {"satisfaction_gap": "weak", "satisfaction_strength": "strong", "satisfaction_level": "average"}[kind]
    title = f"{r['item']}: {word} in {r['vehicle_model_id']} {r['market_code']} study"
    summary = (f"Customer study 2025, {r['vehicle_model_id']} × {r['market_code']}: {r['item']} — {num}; "
               f"z = {z:+.2f} vs the other {r['n_items_in_column'] - 1} items of this column "
               f"(rank {r['rank_within_column']} of {r['n_items_in_column']}, 1 = worst). No sample size given.")
    return kind, title, summary


def build(conn: sqlite3.Connection) -> int:
    done = {r[0] for r in conn.execute(
        "SELECT fs.source_item_id FROM finding f JOIN finding_source fs ON fs.finding_id = f.id WHERE f.source_kind = 'study'")}
    rows = conn.execute(
        """SELECT m.*, s.wave FROM study_metric m JOIN source_item s ON s.id = m.source_item_id ORDER BY m.id""").fetchall()
    n = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in rows:
            if r["source_item_id"] in done:
                continue
            kind, title, summary = describe(r)
            metrics = {"method": METHOD, "z": r["z_within_column"], "scale": r["scale"], "mean": r["mean"],
                       "top2": r["top2"], "bottom3": r["bottom3"], "net": r["net"], "rank": r["rank_within_column"],
                       "n_items": r["n_items_in_column"], "notable": abs(r["z_within_column"] or 0) >= NOTABLE_Z}
            fid = conn.execute(
                """INSERT INTO finding (type, title, summary, scope_level, vehicle_model_id, market_code, metrics_json,
                                        created_by, source_kind, polarity, category, first_wave)
                   VALUES (?, ?, ?, 'market', ?, ?, ?, 'system:study-v1', 'study', ?, NULL, ?)""",
                (kind, title, summary, r["vehicle_model_id"], r["market_code"], json.dumps(metrics),
                 "like" if kind == "satisfaction_strength" else ("pain_or_want" if kind == "satisfaction_gap" else "context"),
                 r["wave"]),
            ).lastrowid
            conn.execute("INSERT INTO finding_source (finding_id, source_item_id, quote, relation) VALUES (?, ?, ?, 'supports')",
                         (fid, r["source_item_id"], summary))
            n += 1
        audit(conn, actor_type="system", actor_id="pipeline.study_findings", action="build_findings",
              entity_type="study", entity_id="customer_study_2025", new={"findings": n}, prompt_ref=METHOD)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return n


if __name__ == "__main__":
    print("study findings:", build(connect()))
