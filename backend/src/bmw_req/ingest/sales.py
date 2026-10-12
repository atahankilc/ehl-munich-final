"""Ingest `sales_volumes.xlsx` (data-inventory §3).

Per sheet row two `source_item`s (kind 'sales'): the 2024 actual (wave 1) and 2025 actual + 2030 forecast
(wave 2), each referenced by its `sales` rows. Values look stylized and conflict with public data (Q-015):
BMW-internal relative weights only, never blended with public figures.
Idempotent: refs already ingested are skipped.

`uv run python -m bmw_req.ingest.sales`
"""

import json
import sqlite3
from pathlib import Path

import openpyxl

from bmw_req.ingest.common import audit_batch, existing_refs, open_batch

FILE = "sales_volumes.xlsx"

# Config, not code paths (AGENTS rule 7).
# Sheet → vehicle model per file market code ('*' = all other markets). G60_G68 is one combined sheet;
# China is the long-wheelbase G68 (data-inventory §3).
SHEET_MODELS = {
    "F70": {"*": "F70"},
    "G60_G68": {"CN": "G68", "*": "G60"},
    "G70": {"*": "G70"},
}
# File market code → our market code.
MARKET_CODES = {"EU": "EU", "US": "US", "CN": "CN", "RoW": "RoW", "ROW": "RoW"}
# Year column → (wave, is_forecast). Source items group years by wave.
YEARS = {"volume_2024": (2024, 1, 0), "volume_2025": (2025, 2, 0), "volume_2030": (2030, 2, 1)}
NOTE = ("Values look stylized and conflict with public data (Q-015) — use as BMW-internal relative weights; "
        "never blend with public sales figures.")


def read_sales(path: Path) -> list[dict]:
    """One dict per sheet row with cached values; formulas are kept in `formulas` for provenance."""
    wb_val = openpyxl.load_workbook(path, data_only=True)
    wb_raw = openpyxl.load_workbook(path, data_only=False)
    rows = []
    try:
        for sheet, models in SHEET_MODELS.items():
            ws, ws_raw = wb_val[sheet], wb_raw[sheet]
            header = [c.value for c in ws[1]]
            col = {name: i for i, name in enumerate(header) if name}
            for r_idx in range(2, ws.max_row + 1):
                cells = [c.value for c in ws[r_idx]]
                code = cells[col["market_code"]]
                if code is None:
                    continue
                if code not in MARKET_CODES:
                    raise ValueError(f"{sheet} row {r_idx}: unknown market code {code!r}")
                market = MARKET_CODES[code]
                formulas = {}
                volumes = {}
                for ycol in YEARS:
                    raw = ws_raw.cell(row=r_idx, column=col[ycol] + 1).value
                    if isinstance(raw, str) and raw.startswith("="):
                        formulas[ycol] = raw
                    v = cells[col[ycol]]
                    volumes[ycol] = int(v) if isinstance(v, (int, float)) else None
                rows.append({
                    "sheet": sheet, "row": r_idx, "market_label": cells[col["market"]], "file_code": code,
                    "market": market, "model": models.get(code, models["*"]), "volumes": volumes,
                    "formulas": formulas,
                })
    finally:
        wb_val.close()
        wb_raw.close()
    return rows


def _items(path_name: str, row: dict) -> list[dict]:
    """Split a row into one source item per wave."""
    by_wave: dict[int, list[str]] = {}
    for ycol, (_, wave, _) in YEARS.items():
        by_wave.setdefault(wave, []).append(ycol)
    out = []
    for wave, ycols in sorted(by_wave.items()):
        years = [YEARS[c][0] for c in ycols]
        suffix = "+".join(str(y) for y in years)
        parts = [f"{y}{' (forecast)' if YEARS[c][2] else ''}: {row['volumes'][c]:,} units"
                 if row["volumes"][c] is not None else f"{y}: n/a" for c, y in zip(ycols, years)]
        out.append({
            "ref": f"{path_name}#{row['sheet']}:R{row['row']}:{suffix}",
            "wave": wave,
            "ycols": ycols,
            "text": f"BMW sales volumes, {row['model']} {row['market']} ({row['market_label']}) — " + "; ".join(parts)
                    + " (BMW-internal, stylized; Q-015)",
            "meta": {
                "sheet": row["sheet"], "excel_row": row["row"], "market_label": row["market_label"],
                "file_market_code": row["file_code"], "years": years,
                "volumes": {str(YEARS[c][0]): row["volumes"][c] for c in ycols},
                "formulas": {c: f for c, f in row["formulas"].items() if c in ycols},
                "combined_sheet": row["sheet"] if len(SHEET_MODELS[row["sheet"]]) > 1 else None,
                "notes": NOTE,
            },
        })
    return out


def ingest_sales(conn: sqlite3.Connection, path: Path) -> int:
    """Returns the number of newly ingested source items."""
    path = Path(path)
    rows = read_sales(path)
    seen = existing_refs(conn, "sales", path.name)
    todo = [(row, it) for row in rows for it in _items(path.name, row) if it["ref"] not in seen]
    if not todo:
        return 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        batch_id = open_batch(conn, "sales", f"{len(todo)} sales items from {path.name}", path.name)
        n_sales = 0
        for row, it in todo:
            sid = conn.execute(
                """INSERT INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code,
                                            text, meta_json, ingest_batch_id, wave)
                   VALUES ('sales', ?, ?, 'T1', ?, ?, ?, ?, ?, ?) RETURNING id""",
                (it["ref"], f"{row['sheet']}:{row['file_code']}", row["model"], row["market"], it["text"],
                 json.dumps(it["meta"]), batch_id, it["wave"]),
            ).fetchone()[0]
            for ycol in it["ycols"]:
                year, _, forecast = YEARS[ycol]
                conn.execute(
                    """INSERT INTO sales (vehicle_model_id, market_code, year, units, is_forecast, source_item_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (row["model"], row["market"], year, row["volumes"][ycol], forecast, sid),
                )
                n_sales += 1
        audit_batch(conn, "ingest.sales", batch_id,
                    {"file": path.name, "source_items": len(todo), "sales_rows": n_sales, "note": NOTE})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(todo)


def main() -> None:
    from bmw_req.config import get_settings
    from bmw_req.db import connect
    from bmw_req.ingest import reference

    conn = connect()
    reference.seed(conn)
    path = get_settings().raw_data_dir / FILE
    rows = read_sales(path)
    print("market codes in file:", sorted({r["file_code"] for r in rows}))
    for r in rows:
        if r["formulas"]:
            print(f"  formula cells {r['sheet']} R{r['row']}: {r['formulas']} → cached {r['volumes']}")
    print(f"sales: {ingest_sales(conn, path)} new source items")


if __name__ == "__main__":
    main()
