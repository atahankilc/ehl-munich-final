"""Ingest a `{derivative}_feedback_hackathon.xlsx` file: one `source_item` per verbatim ID.

The raw file has one row per (verbatim × BMW classification); the labels are kept in meta_json as hints.
Idempotent: verbatims already ingested are skipped, and no batch is created if nothing is new.
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import openpyxl

from bmw_req.ingest.reference import country_to_market

SHEET = "Feedback_Explorer"
ENGINE = {"BEVE": "BEV"}


def read_verbatims(path: Path) -> dict[str, dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = wb[SHEET].iter_rows(values_only=True)
    header = next(rows)
    col = {name: i for i, name in enumerate(header)}
    verbatims: dict[str, dict] = {}
    labels = defaultdict(list)
    for excel_row, r in enumerate(rows, start=2):
        vid = r[col["ID"]]
        if vid is None:
            continue
        verbatims.setdefault(vid, {
            "id": vid,
            "source": r[col["Source"]],
            "country": r[col["Country"]],
            "derivative": r[col["Derivate (e-code)"]],
            "engine_raw": r[col["Engine Type"]],
            "text": r[col["Customer Feedback"]],
            "rows": [],
        })["rows"].append(excel_row)
        if r[col["Feedback Type"]] or r[col["Vfc level2 Name"]]:
            labels[vid].append({
                "feedback_type": r[col["Feedback Type"]],
                "vfc_level2": r[col["Vfc level2 Name"]],
                "vfc_level3": r[col["Vfc level3 Name"]],
                "vfc_level2_3": r[col["Vfc level2 3 Name"]],
            })
    wb.close()
    for vid, v in verbatims.items():
        v["bmw_labels"] = labels[vid]
    return verbatims


def ingest_feedback(conn: sqlite3.Connection, path: Path) -> int:
    """Returns the number of newly ingested verbatims."""
    path = Path(path)
    verbatims = read_verbatims(path)
    ref = lambda vid: f"{path.name}#{SHEET}:{vid}"
    existing = {
        r[0] for r in conn.execute(
            "SELECT external_id FROM source_item WHERE kind = 'feedback' AND ref LIKE ?", (f"{path.name}#%",)
        )
    }
    new = [v for vid, v in verbatims.items() if vid not in existing]
    if not new:
        return 0
    market_of = country_to_market(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        batch_id = conn.execute(
            "INSERT INTO ingest_batch (kind, description, file) VALUES ('feedback_wave', ?, ?)",
            (f"{len(new)} verbatims from {path.name}", path.name),
        ).lastrowid
        conn.executemany(
            """INSERT INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code,
                                        country, text, meta_json, ingest_batch_id)
               VALUES ('feedback', ?, ?, 'T1', ?, ?, ?, ?, ?, ?)""",
            [
                (
                    ref(v["id"]), v["id"], v["derivative"], market_of(v["country"]), v["country"], v["text"],
                    json.dumps({
                        "channel": v["source"],
                        "engine": ENGINE.get(v["engine_raw"], v["engine_raw"]),
                        "engine_raw": v["engine_raw"],
                        "excel_rows": v["rows"],
                        "bmw_labels": v["bmw_labels"],
                    }),
                    batch_id,
                )
                for v in new
            ],
        )
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value)
               VALUES ('system', 'ingest.feedback', 'ingest', 'ingest_batch', ?, ?)""",
            (str(batch_id), json.dumps({"file": path.name, "verbatims": len(new)})),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(new)
