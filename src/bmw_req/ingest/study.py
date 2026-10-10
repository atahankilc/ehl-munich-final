"""Ingest `F70_G60_G68_G70_customer_studies.xlsx` (data-inventory §2, D-026).

One `source_item` (kind 'study') + one `study_metric` per item × model × market column.
- `CN_EU_2025`: label row + `Mean` row per category; column headers give market (China/EU) and model.
- `US_2025`: per question `Sample total` + 7-point distribution for G60 and G70 → top2 / bottom3 / net / mean.
Scales of the two sheets are not comparable (Q-006); z-scores are only computed within one column.
Idempotent: refs already ingested are skipped.

`uv run python -m bmw_req.ingest.study`
"""

import json
import re
import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from bmw_req.ingest.common import audit_batch, existing_refs, open_batch

FILE = "F70_G60_G68_G70_customer_studies.xlsx"
WAVE = 2
STUDY_YEAR = 2025

# Config, not code paths (AGENTS rule 7). Market header labels → our market codes.
MARKET_LABELS = {"China": "CN", "EU": "EU", "Europe": "EU", "US": "US", "USA": "US"}
# Sheet → scale; `market` fixes the market for sheets without a market header row.
SHEETS = {
    "CN_EU_2025": {"scale": "mean_10", "market": None},
    "US_2025": {"scale": "dist_7", "market": "US"},
}
DIST_LABELS = ["I Hate It", "A Failure", "Unsatisfactory", "Satisfactory", "Excellent", "Delightful", "I Love It"]
TOP2 = DIST_LABELS[5:]
BOTTOM3 = DIST_LABELS[:3]
MODEL_CODE = re.compile(r"\b([A-Z]\d{2})\s*$")


@dataclass
class Item:
    sheet: str
    item: str
    model: str            # vehicle_model id
    model_label: str      # header as in the file
    market: str
    row: int              # excel row of the value (CN/EU) or of the question label (US)
    col: int              # excel column (1-based)
    scale: str
    mean: float | None = None
    top2: float | None = None
    bottom3: float | None = None
    net: float | None = None
    dist: dict = field(default_factory=dict)
    z: float | None = None
    rank: int | None = None
    n: int | None = None

    @property
    def ref(self) -> str:
        return f"{FILE}#{self.sheet}:R{self.row}:C{self.col}"

    @property
    def key_value(self) -> float:
        return self.mean if self.scale == "mean_10" else self.net


def _model_code(label: str) -> str:
    m = MODEL_CODE.search(label.strip())
    if not m:
        raise ValueError(f"No model e-code in study column header {label!r}")
    return m.group(1)


def _label(v) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def parse_cn_eu(ws, sheet: str) -> list[Item]:
    items: list[Item] = []
    columns: dict[int, tuple[str, str, str]] = {}   # col index → (model, label, market)
    markets: dict[int, str] = {}
    current = None
    for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = list(row)
        # Market header row: col A empty, other cells are market labels (forward-filled to the right).
        if not markets and any(_label(c) in MARKET_LABELS for c in cells[1:]):
            last = None
            for c_idx in range(1, len(cells)):
                lab = _label(cells[c_idx])
                if lab in MARKET_LABELS:
                    last = MARKET_LABELS[lab]
                if last:
                    markets[c_idx] = last
            continue
        if not columns and any((_label(c) or "").startswith("BMW ") for c in cells[1:]):
            for c_idx in range(1, len(cells)):
                lab = _label(cells[c_idx])
                if lab and lab.startswith("BMW "):
                    if c_idx not in markets:
                        raise ValueError(f"{sheet}: column {c_idx + 1} has a model but no market header")
                    columns[c_idx] = (_model_code(lab), lab, markets[c_idx])
        first = _label(cells[0]) if cells else None
        if first is None:
            continue
        if first == "Mean":
            if current is None:
                raise ValueError(f"{sheet}: 'Mean' row {r_idx} without a category label")
            for c_idx, (model, lab, market) in columns.items():
                v = cells[c_idx] if c_idx < len(cells) else None
                if isinstance(v, (int, float)):
                    items.append(Item(sheet, current, model, lab, market, r_idx, c_idx + 1, "mean_10", mean=float(v)))
            current = None
        else:
            current = first
    return items


def parse_us(ws, sheet: str, market: str) -> list[Item]:
    items: list[Item] = []
    columns: dict[int, tuple[str, str]] = {}
    blocks: list[tuple[str, int, dict[str, list]]] = []   # (question, label row, {dist label: row})
    for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = list(row)
        if not columns and any((_label(c) or "").startswith("BMW ") for c in cells[1:]):
            columns = {i: (_model_code(c), c.strip()) for i, c in enumerate(cells) if (_label(c) or "").startswith("BMW ")}
        first = _label(cells[0]) if cells else None
        if first is None:
            continue
        if first == "Sample total":
            continue
        if first in DIST_LABELS:
            if not blocks:
                raise ValueError(f"{sheet}: distribution row {r_idx} before any question")
            blocks[-1][2][first] = cells
        else:
            blocks.append((first, r_idx, {}))
    for question, q_row, dist_rows in blocks:
        missing = [lab for lab in DIST_LABELS if lab not in dist_rows]
        if missing:
            raise ValueError(f"{sheet}: question {question!r} (row {q_row}) lacks {missing}")
        for c_idx, (model, lab) in columns.items():
            dist = {d: float(dist_rows[d][c_idx] or 0.0) for d in DIST_LABELS}
            total = sum(dist.values())
            if total <= 0:
                continue
            top2 = sum(dist[d] for d in TOP2)
            bottom3 = sum(dist[d] for d in BOTTOM3)
            mean = sum((i + 1) * dist[d] for i, d in enumerate(DIST_LABELS)) / total
            items.append(Item(sheet, question, model, lab, market, q_row, c_idx + 1, "dist_7",
                              mean=mean, top2=top2, bottom3=bottom3, net=top2 - bottom3, dist=dist))
    return items


def add_column_stats(items: list[Item]) -> None:
    """z-score and rank (1 = worst) of each item vs. the others in its sheet × model × market column."""
    cols: dict[tuple, list[Item]] = {}
    for it in items:
        cols.setdefault((it.sheet, it.model, it.market), []).append(it)
    for col in cols.values():
        vals = [it.key_value for it in col]
        mu = statistics.fmean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        for rank, it in enumerate(sorted(col, key=lambda x: x.key_value), start=1):
            it.rank, it.n = rank, len(col)
            it.z = (it.key_value - mu) / sd if sd > 0 else 0.0


def read_study(path: Path) -> list[Item]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    items: list[Item] = []
    try:
        for sheet, cfg in SHEETS.items():
            ws = wb[sheet]
            if cfg["scale"] == "mean_10":
                items += parse_cn_eu(ws, sheet)
            else:
                items += parse_us(ws, sheet, cfg["market"])
    finally:
        wb.close()
    add_column_stats(items)
    return items


def _text(it: Item) -> str:
    head = f"Customer study {STUDY_YEAR}, {it.model_label} ({it.market}) — {it.item}:"
    if it.scale == "mean_10":
        return f"{head} mean {it.mean:.2f} (scale unconfirmed, Q-006; no sample size)"
    return (f"{head} top-2 box {it.top2:.1%}, bottom-3 box {it.bottom3:.1%}, net {it.net * 100:+.1f} pts, "
            f"mean {it.mean:.2f} on 1–7 (7-point scale I Hate It…I Love It; no sample size)")


def _meta(it: Item) -> dict:
    meta = {
        "sheet": it.sheet, "raw_label": it.item, "column_header": it.model_label, "scale": it.scale,
        "cell": f"{get_column_letter(it.col)}{it.row}", "study_year": STUDY_YEAR,
        "mean": it.mean, "z_within_column": it.z, "rank_within_column": it.rank, "n_items_in_column": it.n,
        "notes": "No sample size in the file; CN/EU means and US distributions are not comparable (Q-006).",
    }
    if it.scale == "dist_7":
        meta.update(distribution=it.dist, top2=it.top2, bottom3=it.bottom3, net=it.net,
                    mean_note="mean on 1..7 computed from the distribution; ref row = question label row")
    return meta


def ingest_study(conn: sqlite3.Connection, path: Path) -> int:
    """Returns the number of newly ingested study items."""
    path = Path(path)
    items = read_study(path)
    seen = existing_refs(conn, "study", path.name)
    new = [it for it in items if it.ref not in seen]
    if not new:
        return 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        batch_id = open_batch(conn, "study", f"{len(new)} study items from {path.name}", path.name)
        for it in new:
            sid = conn.execute(
                """INSERT INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code,
                                            text, meta_json, ingest_batch_id, wave)
                   VALUES ('study', ?, ?, 'T1', ?, ?, ?, ?, ?, ?)""",
                (it.ref, it.item, it.model, it.market, _text(it), json.dumps(_meta(it)), batch_id, WAVE),
            ).lastrowid
            conn.execute(
                """INSERT INTO study_metric (source_item_id, vehicle_model_id, market_code, item, scale, mean, top2,
                                             bottom3, net, z_within_column, rank_within_column, n_items_in_column)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, it.model, it.market, it.item, it.scale, it.mean, it.top2, it.bottom3, it.net,
                 it.z, it.rank, it.n),
            )
        per_col: dict[str, int] = {}
        for it in new:
            k = f"{it.sheet}:{it.model}:{it.market}"
            per_col[k] = per_col.get(k, 0) + 1
        audit_batch(conn, "ingest.study", batch_id, {"file": path.name, "items": len(new), "columns": per_col})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(new)


def main() -> None:
    from bmw_req.config import get_settings
    from bmw_req.db import connect
    from bmw_req.ingest import reference

    conn = connect()
    reference.seed(conn)
    n = ingest_study(conn, get_settings().raw_data_dir / FILE)
    print(f"study: {n} new items")


if __name__ == "__main__":
    main()
