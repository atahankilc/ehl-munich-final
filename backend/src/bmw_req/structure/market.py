"""Market context for the structure stages (D-046): how big each car line × market is for BMW, what public figures
say is happening there, and where the two disagree. Deterministic, no LLM.

Rules (from the sales verification, `research/sales-verification.md`, and Q-015):
- BMW's sales file is used ONLY as a relative weight ("how much of BMW's volume is this line × market"), always
  labelled internal / stylized. Its growth to 2030 is never used as a trend: the market split is implausible in places
  (5 Series US ~3x public, China LWB 21–39 % low) and its growth contradicts H1 2026.
- Trends ("sales fell 18 % in China") come only from cited public research items visible at the checkpoint, with
  their source id, period, region and trust tier. Figures that cover only part of a line or more than one line are
  skipped: combined ("3 Series + 5 Series"), families ("1/2 Series") and single powertrains (i7 BEV only). Germany
  stands in for Europe and says so.
- Where BMW's file and a comparable public full-year figure differ by more than 25 %, a conflict is surfaced instead of
  either number being silently preferred.

`uv run python -m bmw_req.structure.market --checkpoint cp1`             (print the context)
`uv run python -m bmw_req.structure.market --backfill`                   (add metrics.market to existing areas, no LLM)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.structure.events import log

LINE_OF_CAR = {"F70": "1 Series", "G60": "5 Series", "G68": "5 Series", "G70": "7 Series"}
LINE_PATTERN = {"1 Series": r"\b1 Series\b|\bF70\b", "5 Series": r"\b5 Series\b|\bi5\b|\bG60\b|\bG68\b",
                "7 Series": r"\b7 Series\b|\bi7\b|\bG70\b"}
MARKET_OF_REGION = {"CN": "CN", "US": "US", "EU": "EU", "DE": "EU", "UK": "EU", "FR": "EU", "IT": "EU",
                    "KR": "RoW", "JP": "RoW", "GLOBAL": "global"}
SALES_METRICS = {"deliveries", "registrations", "retail_sales"}
TIER_RANK = {"T1": 0, "T2": 1, "T3": 2}
CONFLICT = 0.25
LABEL = "BMW volumes: internal and stylized (Q-015), used only as a relative weight, never as a trend."


def bmw_volumes(conn, cp: str) -> dict[str, dict[int, int]]:
    """'5 Series:CN' → {2024: units, 2025: units, 2030: units} (G60 + G68 summed per market)."""
    vis = C.visible_ids(cp)
    q = ",".join("?" * len(vis))
    out: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in conn.execute(f"""SELECT sa.vehicle_model_id car, sa.market_code market, sa.year, sa.units FROM sales sa
                              JOIN source_item s ON s.id = sa.source_item_id WHERE s.checkpoint IN ({q})""", vis):
        if r["car"] in LINE_OF_CAR and r["units"]:
            out[f"{LINE_OF_CAR[r['car']]}:{r['market']}"][r["year"]] += r["units"]
    return {k: dict(v) for k, v in out.items()}


def weights(vol: dict[str, dict[int, int]], year: int = 2025) -> dict[str, float]:
    """Share of BMW's (stylized) volume in the latest actual year, per line × market."""
    total = sum(v.get(year, 0) for v in vol.values()) or 1
    return {k: round(v.get(year, 0) / total, 4) for k, v in vol.items() if v.get(year)}


def public_figures(conn, cp: str) -> list[dict]:
    """Cited unit figures about one car line, visible at `cp`, de-duplicated (same line, region, period, metric, value)
    keeping the most trusted source."""
    vis = C.visible_ids(cp)
    q = ",".join("?" * len(vis))
    best: dict[tuple, dict] = {}
    for r in conn.execute(f"""SELECT id, text, trust_tier, published_at, meta_json FROM source_item
                              WHERE kind = 'research' AND checkpoint IN ({q})""", vis):
        m = json.loads(r["meta_json"] or "{}")
        ent = m.get("entity") or ""
        partial = ("+" in ent or (m.get("powertrain") or "all") != "all"
                   or re.search(r"\d/\d Series|family", f"{ent} {r['text']}", re.I))
        if m.get("unit") != "units" or m.get("metric") not in SALES_METRICS or partial or m.get("value") is None:
            continue
        lines = [ln for ln, p in LINE_PATTERN.items() if re.search(p, ent)]
        market = MARKET_OF_REGION.get(m.get("region") or "")
        if len(lines) != 1 or not market:
            continue
        f = {"line": lines[0], "market": market, "region": m.get("region"), "period": m.get("period_covered"),
             "metric": m.get("metric"), "value": m.get("value"), "yoy": m.get("yoy_pct"), "tier": r["trust_tier"],
             "source_id": r["id"], "published_at": r["published_at"], "verified": bool(m.get("verified"))}
        k = (f["line"], f["region"], f["period"], f["metric"], f["value"])
        if k not in best or (TIER_RANK.get(f["tier"], 9), not f["verified"]) < (TIER_RANK.get(best[k]["tier"], 9), not best[k]["verified"]):
            best[k] = f
    return list(best.values())


def _single_month(period: str | None) -> bool:
    return bool(re.fullmatch(r"[A-Z][a-z]{2}-\d{4}", period or ""))


def trends(figs: list[dict]) -> dict[str, dict]:
    """'5 Series:CN' → the latest public year-over-year change. Longer periods (full year, half year, quarter, Jan–x)
    beat a single month; then the most recent publication; then the most trusted source."""
    out: dict[str, dict] = {}
    rank = lambda f: (not _single_month(f["period"]), f["published_at"] or "", -TIER_RANK.get(f["tier"], 9))  # noqa: E731
    for f in figs:
        if f["yoy"] is None or f["market"] == "global":
            continue
        k = f"{f['line']}:{f['market']}"
        if k not in out or rank(f) > rank(out[k]):
            out[k] = {key: f[key] for key in ("yoy", "period", "region", "metric", "tier", "source_id", "published_at")}
    return out


def conflicts(vol: dict[str, dict[int, int]], figs: list[dict]) -> list[dict]:
    """BMW file vs a comparable public full-year figure (same line, market and year; Germany is not Europe, so it is
    not compared). Global figures are compared with the line's total across markets."""
    out, seen = [], set()
    for f in figs:
        mt = re.fullmatch(r"FY(\d{4})", f["period"] or "")
        if not mt or f["region"] in ("DE", "UK", "FR", "IT", "KR", "JP"):
            continue
        year = int(mt.group(1))
        if f["market"] == "global":
            bmw = sum(v.get(year, 0) for k, v in vol.items() if k.startswith(f"{f['line']}:"))
            key = f"{f['line']}:global"
        else:
            key = f"{f['line']}:{f['market']}"
            bmw = vol.get(key, {}).get(year, 0)
        if not bmw or (key, year) in seen:
            continue
        diff = bmw / f["value"] - 1
        if abs(diff) > CONFLICT:
            seen.add((key, year))
            out.append({"key": key, "year": year, "bmw": bmw, "public": f["value"], "diff_pct": round(diff * 100),
                        "source_id": f["source_id"], "tier": f["tier"]})
    return out


def market_context(conn, cp: str) -> dict:
    vol = bmw_volumes(conn, cp)
    figs = public_figures(conn, cp)
    return {"label": LABEL, "bmw_weight": weights(vol), "public_trend": trends(figs), "conflicts": conflicts(vol, figs)}


def for_prompt(ctx: dict) -> dict:
    """The compact block the areas model sees (rounded, labelled)."""
    return {"note": LABEL + " Public trends are cited figures; any cause you infer from them is an assumption and must be "
                    "worded as one.",
            "bmw_volume_share": {k: round(v * 100) for k, v in sorted(ctx["bmw_weight"].items(), key=lambda kv: -kv[1])},
            "public_trend": {k: f"{t['yoy']:+.0f}% {t['period']} ({t['region']}, {t['tier']}, src {t['source_id']})"
                             for k, t in ctx["public_trend"].items()},
            "bmw_vs_public_conflicts": [f"{c['key']} {c['year']}: BMW file {c['diff_pct']:+d}% vs public (src {c['source_id']})"
                                        for c in ctx["conflicts"]]}


def area_market(by_line_market: dict[str, int], ctx: dict) -> dict:
    """metrics.market for one area: the line × markets its comments come from, each with BMW's volume share, the
    public trend and any BMW-vs-public conflict; plus the share of BMW's volume those markets hold together."""
    conflict_keys = {c["key"] for c in ctx["conflicts"]}
    rows = []
    for k, n in sorted(by_line_market.items(), key=lambda kv: -kv[1]):
        rows.append({"key": k, "comments": n, "bmw_share": ctx["bmw_weight"].get(k),
                     "trend": ctx["public_trend"].get(k), "conflict": k in conflict_keys})
    return {"label": LABEL, "bmw_volume_share": round(sum(ctx["bmw_weight"].get(k, 0) for k in by_line_market), 4),
            "markets": rows}


def backfill() -> dict:
    """Add metrics.market to every existing area (latest areas run per checkpoint) and recount metrics.evidence from the
    latest contextualize run of that checkpoint (a relink, D-047, may have changed the evidence). No LLM; other keys
    untouched."""
    conn = connect()
    out = {}
    for c in C.CHECKPOINTS:
        run = C.latest_run(conn, c.id, "areas")
        if not run:
            continue
        ctx = market_context(conn, c.id)
        crun = C.latest_run(conn, c.id, "contextualize")
        ev_by_theme: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        if crun:
            for e in conn.execute("""SELECT dst_id, relation FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme'
                                     AND src_type IN ('research', 'study', 'option')""", (crun["id"],)):
                ev_by_theme[e["dst_id"]][e["relation"]] += 1
        rows = conn.execute("SELECT id, theme_keys_json, metrics_json FROM req_area WHERE run_id = ?", (run["id"],)).fetchall()
        conn.execute("BEGIN IMMEDIATE")
        try:
            for r in rows:
                m = json.loads(r["metrics_json"] or "{}")
                m["market"] = area_market(m.get("by_line_market") or {}, ctx)
                if crun and r["theme_keys_json"]:
                    ev: dict[str, int] = defaultdict(int)
                    for t in json.loads(r["theme_keys_json"]):
                        for rel, n in ev_by_theme.get(t, {}).items():
                            ev[rel] += n
                    m["evidence"] = dict(ev)
                conn.execute("UPDATE req_area SET metrics_json = ? WHERE id = ?", (json.dumps(m), r["id"]))
            log(conn, "areas", "market_context", {"areas": len(rows), "conflicts": len(ctx["conflicts"]),
                                                   "trends": len(ctx["public_trend"]),
                                                   "evidence_from_run": crun["id"] if crun else None}, run["id"])
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        out[c.id] = {"run_id": run["id"], "areas": len(rows), "conflicts": len(ctx["conflicts"]), "trends": len(ctx["public_trend"])}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"])
    ap.add_argument("--backfill", action="store_true")
    a = ap.parse_args()
    if a.backfill:
        print(json.dumps(backfill(), indent=1))
    else:
        print(json.dumps(market_context(connect(), a.checkpoint or "cp2"), indent=1, default=str))
