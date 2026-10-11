"""Shared read models (SQL from the Streamlit app, inventory §3) — bulk queries, no per-target N+1 loops.

All functions take the shared connection; callers hold `deps.LOCK`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from typing import Any

from fastapi import HTTPException

from api.labels import PRIORITY_RANK, car, mkt, plain_target
from bmw_req.car_zones import requirement_zone
from bmw_req.portfolio import MIN_MARKET_VERBATIMS, TARGETS, all_targets

SEP = "×"   # U+00D7 — entity-id convention "REQ-0001:G60×US"


# ------------------------------------------------------------------------------------------------ small helpers
def loads(s: Any, default: Any = None) -> Any:
    if s is None or s == "":
        return default
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


def scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    r = conn.execute(sql, params).fetchone()
    return None if r is None else r[0]


def current_wave(conn: sqlite3.Connection) -> int:
    v = scalar(conn, "SELECT value FROM app_state WHERE key = 'current_wave'")
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def metrics_wave(wave: int) -> str:
    """Key into finding.metrics_json['by_wave'] (waves 1–2 carry verbatims; wave 3 adds web only)."""
    return str(min(max(wave, 1), 2))


def tkey(v: str, m: str) -> str:
    return f"{v}{SEP}{m}"


def target_obj(v: str | None, m: str | None) -> dict | None:
    if not v or not m:
        return None
    return {"vehicle": v, "market": m, "key": tkey(v, m), "label": plain_target(v, m), "car": car(v),
            "market_label": mkt(m)}


def parse_key(key: str) -> tuple[str, str]:
    """'G60×US' (also 'G60 × US', 'G60|US', 'G60xUS' for convenience) → ('G60', 'US'); 422 when malformed."""
    k = (key or "").replace(" ", "")
    for sep in (SEP, "|", ":"):
        if sep in k:
            v, m = k.split(sep, 1)
            break
    else:
        if "x" in k:
            v, m = k.split("x", 1)
        else:
            raise HTTPException(422, f"Malformed target key {key!r}; expected e.g. 'G60{SEP}US'")
    if not v or not m:
        raise HTTPException(422, f"Malformed target key {key!r}; expected e.g. 'G60{SEP}US'")
    return v, m


def effective(pm: str | None, ai: str | None) -> str | None:
    return pm or ai


def split_bullets(text: str | None) -> list[str]:
    """Markdown bullet string → list of items (plain text → one item)."""
    if not text or not str(text).strip():
        return []
    items, cur = [], None
    for line in str(text).splitlines():
        s = line.strip()
        m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", s)
        if m:
            if cur is not None:
                items.append(cur)
            cur = m.group(1).strip()
        elif s:
            cur = s if cur is None else f"{cur} {s}"
    if cur is not None:
        items.append(cur)
    return [i for i in items if i]


def latest_extractor(conn: sqlite3.Connection) -> str | None:
    return scalar(conn, "SELECT MAX(extractor_version) FROM verbatim_extraction")


def spend_by_prefix(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["p"]: {"calls": int(r["calls"]), "usd": round(float(r["usd"] or 0), 4)} for r in conn.execute(
        """SELECT substr(job, 1, instr(job || ':', ':') - 1) p, COUNT(*) calls, SUM(cost_usd) usd FROM llm_usage
           WHERE status != 'reserved' GROUP BY 1""")}


def run_waves(conn: sqlite3.Connection) -> dict[int, int | None]:
    """run_id → wave (from the start_run audit event)."""
    out = {}
    for r in conn.execute("""SELECT entity_id, new_value FROM audit_event WHERE action = 'start_run'
                             AND entity_type = 'prioritization_run'"""):
        try:
            out[int(r["entity_id"])] = (loads(r["new_value"], {}) or {}).get("wave")
        except (TypeError, ValueError):
            pass
    return out


# ------------------------------------------------------------------------------------------------ breakdown & voice
_BASE_RE = re.compile(r"(?:of|only) (\d[\d,]*) in-scope")


def voice_base(b: dict | None) -> int | None:
    """In-scope verbatim base of the target, parsed once from the customer-voice explanation (score-v2 and v3)."""
    if not b:
        return None
    cv = (b.get("factors") or {}).get("customer_voice") or {}
    m = _BASE_RE.search(cv.get("explanation") or "")
    return int(m.group(1).replace(",", "")) if m else None


def enrich_breakdown(b: dict | None) -> dict | None:
    if not b:
        return None
    return {**b, "voice_base": voice_base(b)}


def voice_of(b: dict | None) -> dict:
    """This market's own customer voice: verbatims of base (share); own = false when absent or borrowed (score-v3)."""
    if not b:
        return {"verbatims": 0, "base": None, "share": None, "own": False}
    cv = (b.get("factors") or {}).get("customer_voice") or {}
    own = bool(cv.get("available")) and b.get("voice_observed") is not False
    n = int(((b.get("verbatims") or {}).get("verbatims")) or 0)
    base = voice_base(b)
    return {"verbatims": n if own else 0, "base": base,
            "share": round(n / base, 4) if own and base else None, "own": own}


# ------------------------------------------------------------------------------------------------ targets
def brand_state(conn: sqlite3.Connection) -> tuple[dict, set]:
    """Latest brand fit result per (req, vehicle, market), and the set of overridden 'REQ:V×M' entity ids."""
    latest = {}
    for r in conn.execute("""SELECT requirement_id, vehicle_model_id, market_code, result FROM fit_check
                             WHERE check_type = 'brand' ORDER BY id"""):
        latest[(r[0], r[1], r[2])] = r[3]
    overrides = {r[0] for r in conn.execute("SELECT DISTINCT entity_id FROM audit_event WHERE action = 'override_gate'")}
    return latest, overrides


def gate_for(latest: dict, overrides: set, rid: str, v: str, m: str) -> str | None:
    res = latest.get((rid, v, m))
    if res == "fail" and f"{rid}:{tkey(v, m)}" in overrides:
        return "overridden"
    return res


def target_rows(conn: sqlite3.Connection) -> list[dict]:
    """Every requirement_target with its requirement's status (the `targets_df` workhorse, without pandas)."""
    return [dict(r) for r in conn.execute(
        """SELECT t.requirement_id, t.vehicle_model_id, t.market_code, t.realization, t.score, t.proposed_priority,
                  t.priority AS pm_priority, t.evidence_level AS target_evidence, t.rationale AS market_note,
                  t.score_breakdown_json, t.run_id, r.status
           FROM requirement_target t JOIN requirement r ON r.id = t.requirement_id
           ORDER BY t.requirement_id, t.vehicle_model_id, t.market_code""")]


def ranks(rows: list[dict]) -> dict[tuple, int]:
    """Rank within each target over non-rejected, scored requirements (descending score, ties share the min rank)."""
    by_t = defaultdict(list)
    for r in rows:
        if r["status"] != "rejected" and r["score"] is not None:
            by_t[(r["vehicle_model_id"], r["market_code"])].append(r)
    out = {}
    for items in by_t.values():
        scores = sorted((x["score"] for x in items), reverse=True)
        for x in items:
            out[(x["requirement_id"], x["vehicle_model_id"], x["market_code"])] = scores.index(x["score"]) + 1
    return out


def target_row(r: dict, rank: int | None, gate: str | None) -> dict:
    pm, ai = r["pm_priority"], r["proposed_priority"]
    return {"target": target_obj(r["vehicle_model_id"], r["market_code"]), "realization": r["realization"],
            "score": None if r["score"] is None else round(float(r["score"]), 1),
            "ai_priority": ai, "pm_priority": pm, "priority": effective(pm, ai), "ai_only": pm is None,
            "evidence_level": r["target_evidence"], "market_note": r["market_note"] or None,
            "brand_gate": gate, "rank": rank}


REQ_COLS = """id, title, description, category, status, version, horizon, kano_class, kano_drift, must_not_lose, effort,
              evidence_level, created_by, created_at"""


def summarize(req: dict, trows: list[dict], rk: dict, latest: dict, overrides: set) -> dict:
    rid = req["id"]
    targets = [target_row(t, rk.get((rid, t["vehicle_model_id"], t["market_code"])),
                          gate_for(latest, overrides, rid, t["vehicle_model_id"], t["market_code"])) for t in trows]
    scored = [t for t in targets if t["score"] is not None]
    best = max(scored, key=lambda t: t["score"]) if scored else None
    return {
        "id": rid, "title": req["title"], "category": req["category"], "status": req["status"],
        "version": req["version"], "horizon": req["horizon"], "kano_class": req["kano_class"],
        "kano_drift": req["kano_drift"], "must_not_lose": bool(req["must_not_lose"]), "effort": req["effort"],
        "evidence_level": req["evidence_level"], "created_by": req.get("created_by"), "created_at": req.get("created_at"),
        "max_score": best["score"] if best else None, "best_target": best["target"] if best else None,
        "zone": requirement_zone(req["title"], req["category"], req.get("description")),
        "brand_blocked": [t["target"]["key"] for t in targets if t["brand_gate"] == "fail"],
        "targets": targets,
    }


def requirement_summaries(conn: sqlite3.Connection, ids: list[str] | None = None) -> list[dict]:
    """RequirementSummary for every requirement (or the given ids), ranks computed over the whole backlog."""
    rows = target_rows(conn)
    rk = ranks(rows)
    latest, overrides = brand_state(conn)
    by_req = defaultdict(list)
    for r in rows:
        by_req[r["requirement_id"]].append(r)
    reqs = [dict(r) for r in conn.execute(f"SELECT {REQ_COLS} FROM requirement ORDER BY id")]
    if ids is not None:
        want = set(ids)
        reqs = [r for r in reqs if r["id"] in want]
    return [summarize(r, by_req.get(r["id"], []), rk, latest, overrides) for r in reqs]


def requirement_summary(conn: sqlite3.Connection, rid: str) -> dict | None:
    out = requirement_summaries(conn, [rid])
    return out[0] if out else None


# ------------------------------------------------------------------------------------------------ evidence base & gaps
def verbatim_base(conn: sqlite3.Connection, wave: int) -> dict[tuple, dict]:
    """(vehicle, market) → {total, in_scope} feedback verbatims visible up to `wave` (0 = all), latest extractor."""
    W = wave or 99
    ver = latest_extractor(conn) or ""
    return {(r["d"], r["m"]): {"total": int(r["total"]), "in_scope": int(r["inscope"] or 0)} for r in conn.execute(
        """SELECT s.vehicle_model_id d, s.market_code m, COUNT(*) total, COALESCE(SUM(e.in_scope), 0) inscope
           FROM source_item s LEFT JOIN verbatim_extraction e ON e.source_item_id = s.id AND e.extractor_version = ?
           WHERE s.kind = 'feedback' AND s.wave <= ? GROUP BY 1, 2""", (ver, W))}


def evidence_gaps(conn: sqlite3.Connection, wave: int, base: dict | None = None) -> dict[tuple, list[str]]:
    """Per target: the evidence gaps the Portfolio page lists (stated, not hidden)."""
    W = wave or 99
    base = base if base is not None else verbatim_base(conn, wave)
    extracted = {r[0] for r in conn.execute(
        "SELECT DISTINCT s.vehicle_model_id FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id")}
    study = {(r[0], r[1]) for r in conn.execute("SELECT DISTINCT vehicle_model_id, market_code FROM study_metric")}
    web = {(r[0], r[1]) for r in conn.execute(
        "SELECT DISTINCT vehicle_model_id, market_code FROM source_item WHERE kind = 'web' AND wave <= ?", (W,))}
    sales = {(r[0], r[1]) for r in conn.execute(
        "SELECT DISTINCT vehicle_model_id, market_code FROM sales WHERE year IN (2024, 2025)")}
    out = {}
    for d, m in all_targets():
        b = base.get((d, m), {"total": 0, "in_scope": 0})
        gaps = []
        if b["in_scope"] < MIN_MARKET_VERBATIMS:
            gaps.append("no verbatims" if b["total"] == 0 else
                        (f"only {b['in_scope']} in-scope verbatims" if d in extracted else "verbatims not yet extracted"))
        if (d, m) not in study:
            gaps.append("no customer study")
        if (d, m) not in web:
            gaps.append("no web research")
        if (d, m) not in sales:
            gaps.append("no sales data")
        out[(d, m)] = gaps
    return out


def priority_counts(rows: list[dict]) -> dict:
    c = {"Must": 0, "Should": 0, "Could": 0}
    for r in rows:
        p = effective(r["pm_priority"], r["proposed_priority"])
        if p in c:
            c[p] += 1
    return c


def best_first(rows: list[dict]) -> list[dict]:
    """Sort target rows Must → Should → Could, then by score descending."""
    return sorted(rows, key=lambda r: (PRIORITY_RANK.get(effective(r["pm_priority"], r["proposed_priority"]) or "", 9),
                                       -(r["score"] or 0)))


# ------------------------------------------------------------------------------------------------ proposals
def _proposal_times(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """Proposals have no created_at column: derive it. extend → its match_existing event (same req + wave);
    content/link_finding → the latest challenge_response on the requirement."""
    match_ts = {}
    for r in conn.execute("""SELECT entity_id, ts, new_value FROM audit_event WHERE action = 'match_existing'
                             ORDER BY id"""):
        w = (loads(r["new_value"], {}) or {}).get("wave")
        match_ts.setdefault((r["entity_id"], w), r["ts"])
    chal_ts = {r[0]: r[1] for r in conn.execute(
        "SELECT entity_id, MAX(ts) FROM audit_event WHERE action = 'challenge_response' GROUP BY entity_id")}
    return match_ts, chal_ts


def proposals(conn: sqlite3.Connection, where: str = "1 = 1", params: tuple = ()) -> list[dict]:
    rows = [dict(r) for r in conn.execute(
        f"""SELECT p.*, r.title AS req_title, r.status AS req_status, r.created_at AS req_created,
                   json_extract(r.derivation_json, '$.wave') AS req_wave, pr.ts AS run_ts, pr.trigger AS run_trigger
            FROM change_proposal p JOIN requirement r ON r.id = p.requirement_id
            LEFT JOIN prioritization_run pr ON pr.id = p.run_id WHERE {where} ORDER BY p.id""", params)]
    if not rows:
        return []
    fids = set()
    deltas = {}
    for p in rows:
        kind = p["kind"] or "priority"
        p["kind"] = kind
        d = loads(p["evidence_delta_json"])
        deltas[p["id"]] = d
        if kind == "link_finding" and str(p["field"]).startswith("finding:"):
            try:
                fids.add(int(str(p["field"]).split(":", 1)[1]))
            except ValueError:
                pass
        if kind == "extend" and isinstance(d, dict):
            fids.update(int(x) for x in (d.get("supports") or []) + (d.get("contradicts") or []))
    finds = {}
    if fids:
        ph = ",".join("?" * len(fids))
        finds = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, source_kind, title, summary FROM finding WHERE id IN ({ph})", tuple(fids))}
    match_ts, chal_ts = _proposal_times(conn)
    rw = run_waves(conn)
    out = []
    for p in rows:
        kind, d = p["kind"], deltas[p["id"]]
        finding, findings = None, None
        wave = None
        if kind == "link_finding":
            try:
                finding = finds.get(int(str(p["field"]).split(":", 1)[1]))
            except ValueError:
                finding = None
        if kind == "extend" and isinstance(d, dict):
            findings = [{"id": f["id"], "source_kind": f["source_kind"], "title": f["title"],
                         "relation": rel} for rel in ("supports", "contradicts")
                        for f in (finds.get(int(x)) for x in d.get(rel) or []) if f]
            wave = d.get("wave")
        if p["run_id"]:
            created, wave = p["run_ts"], rw.get(p["run_id"])
        elif kind == "new_requirement":
            created, wave = p["req_created"], p["req_wave"]
        elif kind == "extend":
            created = match_ts.get((p["requirement_id"], wave)) or p["req_created"]
        else:
            created = chal_ts.get(p["requirement_id"]) or p["req_created"]
        out.append({
            "id": p["id"], "kind": kind, "status": p["status"], "requirement_id": p["requirement_id"],
            "requirement_title": p["req_title"], "requirement_status": p["req_status"],
            "vehicle": p["vehicle_model_id"], "market": p["market_code"],
            "target": target_obj(p["vehicle_model_id"], p["market_code"]),
            "field": p["field"], "old_value": p["old_value"], "proposed_value": p["proposed_value"], "reason": p["reason"],
            "run": {"id": p["run_id"], "ts": p["run_ts"], "trigger": p["run_trigger"]} if p["run_id"] else None,
            "delta": d, "finding": finding, "findings": findings, "created_at": created, "wave": wave,
            "decided_by": p["decided_by"], "decided_at": p["decided_at"], "decision_rationale": p["decision_rationale"],
        })
    return out


def validate_target_of(conn: sqlite3.Connection, rid: str, v: str, m: str) -> bool:
    return conn.execute("""SELECT 1 FROM requirement_target WHERE requirement_id = ? AND vehicle_model_id = ?
                           AND market_code = ?""", (rid, v, m)).fetchone() is not None


def require_requirement(conn: sqlite3.Connection, rid: str) -> dict:
    r = conn.execute("SELECT * FROM requirement WHERE id = ?", (rid,)).fetchone()
    if r is None:
        raise HTTPException(404, f"No requirement {rid}")
    return dict(r)


def known_vehicle_market(v: str, m: str | None = None) -> bool:
    return v in TARGETS and (m is None or m in TARGETS[v])


# ------------------------------------------------------------------------------------------------ conflicts
CONFLICT_SPREAD = 20.0   # points
CONFLICT_BANDS = 2       # Must vs Could


def conflict_info(rows: list[dict]) -> dict[str, dict]:
    """Requirements whose scored targets disagree: effective priorities 2 bands apart (Must vs Could) or a score
    spread ≥ 20. Non-rejected requirements with ≥ 2 scored targets only. → {req_id: {spread, bands}}."""
    by_req = defaultdict(list)
    for r in rows:
        if r["status"] != "rejected" and r["score"] is not None:
            by_req[r["requirement_id"]].append(r)
    out = {}
    for rid, ts in by_req.items():
        if len(ts) < 2:
            continue
        scores = [t["score"] for t in ts]
        spread = max(scores) - min(scores)
        bands = [PRIORITY_RANK[p] for p in (effective(t["pm_priority"], t["proposed_priority"]) for t in ts)
                 if p in PRIORITY_RANK]
        band_gap = (max(bands) - min(bands)) if bands else 0
        if band_gap >= CONFLICT_BANDS or spread >= CONFLICT_SPREAD:
            out[rid] = {"spread": round(spread, 1), "band_gap": band_gap}
    return out
