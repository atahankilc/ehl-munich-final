"""Prioritization (D-050, page 4): prio-v1 scores per requirement × car line × market at a checkpoint, bundles,
choose-jointly flags, proposals; PM confirms priorities and decides proposals — append-only (`prio_decision`) and
audited as human events (rule 5, 6). The AI never sets a confirmed priority.

GET  /api/prioritize?cp=                              targets, bundles, proposals, summary
GET  /api/prioritize/target/{key}?line=&market=&cp=   one target + history across checkpoints + evidence summary
GET  /api/prioritize/what-if?key=&line=&market=&level=&cp=   recompute for another rung, nothing stored
POST /api/prioritize/decision                         {key, line, market, priority, rationale, actor?, cp?, override_brand?}
POST /api/prioritize/proposal/{id}                    {verdict: accept|reject, rationale, actor?}
POST /api/prioritize/weights                          {factors, bands, rationale, actor?} → new prio-v1 weights version + re-score
GET  /api/prioritize/weights/history                  prio-v1 weights versions (revert = save an earlier one again)
POST /api/prioritize/preview                          {factors, bands, cp, line?, market?} → in-memory re-score, nothing stored

Decision, proposal verdict and weights queue an automatic re-score (`api/rescore.py`) after their commit and return
`rescore: queued`; GET /api/prioritize carries its `rescore` status.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api import rescore as R
from api.deps import conflict, db, get_actor, need_rationale, not_found
from bmw_req.checkpoints import BY_ID, CHECKPOINTS, CheckpointError, latest_run, visible_ids
from bmw_req.audit import audit
from bmw_req.prioritize import ensure
from bmw_req.prioritize import score as P

router = APIRouter(prefix="/api/prioritize", tags=["prioritize"])
DIM_ORDER = ("customer", "business", "future")


def _loads(s, default=None):
    return json.loads(s) if s else default


def _runs(conn, cp: str) -> dict:
    if cp not in BY_ID:
        raise not_found(f"No checkpoint {cp!r}")
    ensure(conn)
    return {s: latest_run(conn, cp, s) for s in ("prioritize", "gate")}


def _run_view(r) -> dict | None:
    return {"id": r["id"], "finished_at": r["finished_at"], "stats": _loads(r["stats_json"], {})} if r else None


def _reqs(conn, run_id: int | None) -> dict[str, dict]:
    if not run_id:
        return {}
    return {r["key"]: dict(r) for r in conn.execute("SELECT key, title, domain, zones_json, area_key FROM def_requirement WHERE run_id = ?", (run_id,))}


def _target(row, req: dict | None, decided: dict | None, state: str | None, prev: dict | None) -> dict:
    b = _loads(row["breakdown_json"], {})
    conf = _loads(row["confidence_json"], {})
    factors = sorted(({"key": k, "dimension": f.get("dimension"), "label": f.get("label"), "value": f.get("value"), "weight": f.get("weight"),
                       "points": f.get("points") or 0, "explanation": f.get("explanation"), "available": f.get("available"),
                       **({"method": f["method"]} if "method" in f else {})} for k, f in b.get("factors", {}).items()),
                     key=lambda f: DIM_ORDER.index(f["dimension"]) if f["dimension"] in DIM_ORDER else 9)
    return {"key": row["req_key"], "version": row["req_version"], "title": (req or {}).get("title"), "domain": (req or {}).get("domain"),
            "zones": _loads((req or {}).get("zones_json"), []), "area_key": (req or {}).get("area_key"),
            "line": row["line"], "market": row["market"], "score": row["score"], "base": row["base"], "band": row["band"],
            "own_band": b.get("own_priority"),
            "confirmed": {"priority": decided["priority"], "actor": decided["actor"], "at": decided["created_at"],
                          "rationale": decided["rationale"]} if decided else None,
            "rank": row["rank"], "state": state,
            "confidence": {"level": conf.get("level"), "mult": conf.get("mult"), "basis_mix": conf.get("basis_mix"),
                           "basis_score": conf.get("basis_score"), "comments": conf.get("comments"), "study": conf.get("study")},
            "factors": factors, "modifiers": _loads(row["modifiers_json"], []), "gates": b.get("gate_detail") or {},
            "bundle_id": row["bundle_id"], "flags": _loads(row["flags_json"], []),
            "rung": {"chosen": (b.get("rung") or {}).get("chosen"), "recommended": (b.get("rung") or {}).get("recommended"),
                     "by": (b.get("rung") or {}).get("by")},
            "effort": b.get("effort"), "gaps": b.get("gaps", []), "rationale": row["rationale"],
            "prev": {"score": prev["score"], "band": prev["band"], "checkpoint": prev.get("checkpoint")} if prev else None}


def _prev_band(conn, run) -> dict[tuple, dict]:
    if not run or not run["parent_run_id"]:
        return {}
    cp = conn.execute("SELECT checkpoint_id FROM checkpoint_run WHERE id = ?", (run["parent_run_id"],)).fetchone()[0]
    return {(r["req_key"], r["line"], r["market"]): {"score": r["score"], "band": r["band"], "checkpoint": cp}
            for r in conn.execute("SELECT req_key, line, market, score, band FROM prio_score WHERE run_id = ?", (run["parent_run_id"],))}


def _states(conn, run_id: int) -> dict[tuple, str]:
    out = {}
    for r in conn.execute("SELECT entity_key, state FROM track WHERE run_id = ? AND entity_key LIKE 'prio:%'", (run_id,)):
        k, line, m = r["entity_key"][5:].split("|")
        out[(k, line, m)] = r["state"]
    return out


def _proposal(r) -> dict:
    fd = _loads(r["factor_delta_json"], {})
    return {"id": r["id"], "run_id": r["run_id"], "key": r["req_key"], "line": r["line"], "market": r["market"], "old_band": r["old_band"],
            "proposed_band": r["proposed_band"], "cause": r["cause"], "factor_delta": fd.get("points", {}),
            "explain": fd.get("explain"), "against": fd.get("against"), "score": fd.get("score"), "prev_score": fd.get("prev_score"),
            "status": r["status"], "decided_by": r["decided_by"], "decided_at": r["decided_at"],
            "decision_rationale": r["decision_rationale"], "created_at": r["created_at"]}


def _visible_proposals(conn, cp: str, run_id: int) -> list[dict]:
    """Proposals a PM at `cp` may see: those of the current run, plus still-open ones from earlier runs at checkpoints
    visible at `cp` (cp1 sees cp1 only; cp2 sees cp1 + cp2) — never a later checkpoint's. One open proposal per target:
    the newest wins."""
    vis = visible_ids(cp)
    rows = conn.execute(f"""SELECT p.* FROM prio_proposal p JOIN checkpoint_run r ON r.id = p.run_id
                            WHERE r.checkpoint_id IN ({','.join('?' * len(vis))}) AND (p.run_id = ? OR p.status = 'open')
                            ORDER BY p.id""", (*vis, run_id)).fetchall()
    newest_open = {}
    for r in rows:
        if r["status"] == "open":
            newest_open[(r["req_key"], r["line"], r["market"])] = r["id"]
    return [_proposal(r) for r in rows if r["status"] != "open" or newest_open[(r["req_key"], r["line"], r["market"])] == r["id"]]


@router.get("")
def prioritize(cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        wid, weights, bands = P.stored_config(conn)
        meta = P.current_meta(conn)
        base = {"checkpoint": cp, "runs": {s: _run_view(r) for s, r in runs.items()},
                "weights": {"scheme": P.SCHEME, "version": meta["version"], "id": wid, "factors": weights, "bands": bands,
                            "actor": meta["actor"], "at": meta["at"], "rationale": meta["rationale"], "default": meta["default"],
                            "defaults": {"factors": P.DEFAULT_WEIGHTS, "bands": P.DEFAULT_BANDS}},
                "rescore": R.status(),
                "dimensions": P.DIMENSION,
                "labels": {"market_weight": "stylized (Q-015)", "market_weight_note": P.MARKET_LABEL}}
        run = runs["prioritize"]
        if not run:
            return {**base, "ready": False, "lines": [], "markets": [], "targets": [], "bundles": [], "proposals": [], "summary": {}}
        stats = _loads(run["stats_json"], {})
        reqs = _reqs(conn, (stats.get("upstream") or {}).get("define"))
        decided, prev, states = P.decisions_at(conn, cp), _prev_band(conn, run), _states(conn, run["id"])
        targets = [_target(r, reqs.get(r["req_key"]), decided.get((r["req_key"], r["line"], r["market"])),
                           states.get((r["req_key"], r["line"], r["market"])), prev.get((r["req_key"], r["line"], r["market"])))
                   for r in conn.execute("SELECT * FROM prio_score WHERE run_id = ? ORDER BY line, market, rank", (run["id"],))]
        bundles = [{"id": r["bundle_id"], "keys": _loads(r["keys_json"], []), **(_loads(r["relations_json"], {}) or {}),
                    "band_by_target": _loads(r["band_by_target_json"], {})}
                   for r in conn.execute("SELECT * FROM prio_bundle WHERE run_id = ? ORDER BY id", (run["id"],))]
        keys = {t["key"] for t in targets}
        proposals = [p for p in _visible_proposals(conn, cp, run["id"]) if p["key"] in keys]
        lines = sorted({t["line"] for t in targets})
        markets = sorted({t["market"] for t in targets})
        return {**base, "ready": True, "lines": lines, "markets": markets, "targets": targets, "bundles": bundles,
                "proposals": proposals, "summary": {"by_band": stats.get("by_band"), "by_market": stats.get("by_market"),
                                                    "flags": stats.get("flags"), "competitive_method": stats.get("competitive_method")}}


@router.get("/target/{key:path}")
def target(key: str, line: str = Query(...), market: str = Query(...), cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        run = runs["prioritize"]
        if not run:
            raise not_found("No prioritize run at this checkpoint")
        row = conn.execute("SELECT * FROM prio_score WHERE run_id = ? AND req_key = ? AND line = ? AND market = ?",
                           (run["id"], key, line, market)).fetchone()
        if row is None:
            raise not_found(f"No target {key} × {line} × {market} at {cp}")
        stats = _loads(run["stats_json"], {})
        reqs = _reqs(conn, (stats.get("upstream") or {}).get("define"))
        decided = P.decisions_at(conn, cp)
        out = _target(row, reqs.get(key), decided.get((key, line, market)), _states(conn, run["id"]).get((key, line, market)),
                      _prev_band(conn, run).get((key, line, market)))
        history = []
        for c in CHECKPOINTS:
            if c.position > BY_ID[cp].position:
                continue
            r = latest_run(conn, c.id, "prioritize")
            h = conn.execute("SELECT score, band, rank, rung, rationale FROM prio_score WHERE run_id = ? AND req_key = ? AND line = ? AND market = ?",
                             (r["id"], key, line, market)).fetchone() if r else None
            if h:
                dc = P.decisions_at(conn, c.id).get((key, line, market))
                history.append({"checkpoint": c.id, "label": c.label, "run_id": r["id"], **dict(h),
                                "confirmed": dc["priority"] if dc else None})
        req = conn.execute("SELECT evidence_ids_json, trend_ids_json, statement FROM def_requirement WHERE run_id = ? AND key = ?",
                           ((stats.get("upstream") or {}).get("define"), key)).fetchone()
        ev = _loads(req["evidence_ids_json"], []) if req else []
        kinds = defaultdict(int)
        for i in ev:
            kinds[i.split(":")[0]] += 1
        vis = visible_ids(cp)
        decisions = [dict(x) for x in conn.execute(
            f"SELECT * FROM prio_decision WHERE req_key = ? AND line = ? AND market = ? AND (checkpoint_id IS NULL OR checkpoint_id IN "
            f"({','.join('?' * len(vis))})) ORDER BY id", (key, line, market, *vis))]
        proposals = [_proposal(x) for x in conn.execute(
            f"SELECT p.* FROM prio_proposal p JOIN checkpoint_run r ON r.id = p.run_id WHERE p.req_key = ? AND p.line = ? AND p.market = ? "
            f"AND r.checkpoint_id IN ({','.join('?' * len(vis))}) ORDER BY p.id", (key, line, market, *vis))]
        return {**out, "statement": req["statement"] if req else None, "history": history, "decisions": decisions, "proposals": proposals,
                "evidence": {"comments": out["confidence"]["comments"], "study": kinds.get("study", 0), "research": kinds.get("research", 0),
                             "options": kinds.get("option", 0), "insights": kinds.get("insight", 0),
                             "own_market": "borrowed_voice" not in out["flags"], "count": len(ev), "by_kind": dict(kinds), "trend_ids": _loads(req["trend_ids_json"], []) if req else [],
                             "factors": {f["key"]: f["explanation"] for f in out["factors"]}}}


@router.get("/what-if")
def what_if(key: str = Query(...), line: str = Query(...), market: str = Query(...),
            level: Literal["baseline", "threshold", "target", "stretch"] = Query(...), cp: str = Query("cp2")) -> dict:
    with db() as conn:
        _runs(conn, cp)
        try:
            return P.what_if(conn, cp, key, line, market, level)
        except CheckpointError as e:
            raise conflict(str(e)) from e
        except KeyError as e:
            raise not_found(str(e)) from e


class DecisionBody(BaseModel):
    key: str
    line: str
    market: str
    priority: Literal["Must", "Should", "Could"]
    rationale: str
    actor: str | None = None
    cp: str | None = None
    override_brand: bool = False


class ProposalBody(BaseModel):
    verdict: Literal["accept", "reject"]
    rationale: str
    actor: str | None = None


class WeightsBody(BaseModel):
    factors: dict[str, float] | None = None
    weights: dict[str, float] | None = None     # legacy name of `factors`
    bands: dict[str, float] | None = None       # {Must, Should}; omitted = keep the current thresholds
    rationale: str
    actor: str | None = None


class PreviewBody(BaseModel):
    factors: dict[str, float]
    bands: dict[str, float]
    cp: str = "cp2"
    line: str | None = None
    market: str | None = None


def _gate_brand(conn, key: str, line: str, market: str, cp: str | None) -> str | None:
    for c in ([cp] if cp in BY_ID else []) + [c.id for c in reversed(CHECKPOINTS)]:
        r = latest_run(conn, c, "gate")
        if r:
            g = conn.execute("SELECT result FROM prio_fit WHERE run_id = ? AND req_key = ? AND line = ? AND market = ? AND check_type = 'brand' "
                             "ORDER BY id DESC LIMIT 1", (r["id"], key, line, market)).fetchone()
            return g["result"] if g else None
    return None


def _decide(conn, key: str, line: str, market: str, priority: str, why: str, actor: str, cp: str | None, extra: dict) -> tuple[int, dict | None]:
    """Insert a prio_decision + human audit_event (caller holds the transaction)."""
    before = conn.execute("SELECT priority, rationale, actor, checkpoint_id FROM prio_decision WHERE req_key = ? AND line = ? AND market = ? "
                          "ORDER BY id DESC LIMIT 1", (key, line, market)).fetchone()
    cur = conn.execute("INSERT INTO prio_decision (req_key, line, market, priority, rationale, actor, checkpoint_id) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
                       (key, line, market, priority, why, actor, cp))
    audit(conn, actor_type="human", actor_id=actor, action="confirm_priority", entity_type="prio_target", entity_id=f"{key}|{line}|{market}",
          field="priority", old=dict(before) if before else None, new={"priority": priority, "checkpoint": cp, **extra}, rationale=why)
    return cur.fetchone()[0], dict(before) if before else None


@router.post("/decision")
def decision(body: DecisionBody, header_actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    actor = (body.actor or "").strip() or header_actor
    with db() as conn:
        ensure(conn)
        cp = body.cp if body.cp in BY_ID else None
        ai = conn.execute("SELECT band, score FROM prio_score WHERE req_key = ? AND line = ? AND market = ? ORDER BY run_id DESC LIMIT 1",
                          (body.key, body.line, body.market)).fetchone()
        if ai is None:
            raise not_found(f"No scored target {body.key} × {body.line} × {body.market}")
        brand = _gate_brand(conn, body.key, body.line, body.market, cp)
        if brand == "fail" and body.priority in ("Must", "Should") and not body.override_brand:
            raise conflict("Brand-fit FAIL: confirming this priority needs override_brand with a rationale (D-008).")
        conn.execute("BEGIN IMMEDIATE")
        try:
            did, before = _decide(conn, body.key, body.line, body.market, body.priority, why, actor, cp,
                                  {"ai_band": ai["band"], "ai_score": ai["score"], "brand_gate": brand, "override_brand": body.override_brand})
            seen_at = [c.id for c in CHECKPOINTS if cp is None or cp in visible_ids(c.id)]   # the decision applies here
            conn.execute(f"UPDATE prio_proposal SET status = 'superseded' WHERE req_key = ? AND line = ? AND market = ? AND status = 'open' "
                         f"AND run_id IN (SELECT id FROM checkpoint_run WHERE checkpoint_id IN ({','.join('?' * len(seen_at))}))",
                         (body.key, body.line, body.market, *seen_at))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    # inputs at the decision's checkpoint are unchanged: re-score the LATER checkpoints against the PM's band
    rs = R.queue(cp or CHECKPOINTS[0].id, "decision", include_self=False)
    return {"ok": True, "id": did, "decision": {"key": body.key, "line": body.line, "market": body.market, "priority": body.priority,
                                                "rationale": why, "actor": actor}, "before": before, "rescore": rs}


@router.post("/proposal/{pid}")
def proposal(pid: int, body: ProposalBody, header_actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    actor = (body.actor or "").strip() or header_actor
    with db() as conn:
        ensure(conn)
        p = conn.execute("SELECT * FROM prio_proposal WHERE id = ?", (pid,)).fetchone()
        if p is None:
            raise not_found(f"No proposal {pid}")
        if p["status"] != "open":
            raise conflict(f"Proposal {pid} is {p['status']}, not open")
        cp = conn.execute("SELECT checkpoint_id FROM checkpoint_run WHERE id = ?", (p["run_id"],)).fetchone()[0]
        if body.verdict == "accept" and p["proposed_band"] in ("Must", "Should") and \
                _gate_brand(conn, p["req_key"], p["line"], p["market"], cp) == "fail":
            raise conflict("Brand-fit FAIL: accept via POST /decision with override_brand and a rationale (D-008).")
        conn.execute("BEGIN IMMEDIATE")
        try:
            status = "accepted" if body.verdict == "accept" else "rejected"
            conn.execute("UPDATE prio_proposal SET status = ?, decided_by = ?, decided_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
                         "decision_rationale = ? WHERE id = ?", (status, actor, why, pid))
            audit(conn, actor_type="human", actor_id=actor, action=f"proposal_{status}", entity_type="prio_proposal", entity_id=str(pid),
                  field="status", old={"status": "open", "band": p["old_band"]},
                  new={"status": status, "proposed_band": p["proposed_band"], "cause": p["cause"]}, rationale=why)
            did = None
            if status == "accepted":
                did, _ = _decide(conn, p["req_key"], p["line"], p["market"], p["proposed_band"], why, actor, cp,
                                 {"via_proposal": pid, "cause": p["cause"]})
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    rs = R.queue(cp, f"proposal_{status}", include_self=False)
    return {"ok": True, "proposal": pid, "status": status, "decision_id": did, "rescore": rs}


@router.post("/weights")
def weights(body: WeightsBody, header_actor: str = Depends(get_actor)) -> dict:
    """New prio-v1 weights version (factors + band thresholds) + human audit_event, then an automatic re-score of every
    checkpoint (cp1 → cp2); PM-confirmed bands that now differ get a `weights_changed` proposal, never a silent change."""
    why = need_rationale(body.rationale)
    actor = (body.actor or "").strip() or header_actor
    factors = body.factors if body.factors is not None else body.weights
    if factors is None:
        raise conflict("factors are required")
    with db() as conn:
        ensure(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            wid = P.set_weights(conn, factors, actor, why, body.bands)
            conn.execute("COMMIT")
        except ValueError as e:
            conn.execute("ROLLBACK")
            raise conflict(str(e)) from e
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        _, f, b = P.stored_config(conn)
        meta = P.current_meta(conn)
    rs = R.queue(None, "weights_changed")
    return {"ok": True, "weights_version": meta["version"], "id": wid, "factors": f, "weights": f, "bands": b, "rescore": rs}


@router.get("/weights/history")
def weights_history(limit: int = Query(20, ge=1, le=100)) -> dict:
    with db() as conn:
        ensure(conn)
        wid, f, b = P.stored_config(conn)
        return {"current": {**P.current_meta(conn), "factors": f, "bands": b},
                "defaults": {"factors": P.DEFAULT_WEIGHTS, "bands": P.DEFAULT_BANDS},
                "history": P.weights_history(conn, limit)}


@router.post("/preview")
def preview(body: PreviewBody) -> dict:
    """Re-score every target at `cp` with the proposed weights + bands in memory (no writes)."""
    with db() as conn:
        _runs(conn, body.cp)
        try:
            return P.preview(conn, body.cp, body.factors, body.bands, body.line, body.market)
        except ValueError as e:
            raise conflict(str(e)) from e
        except CheckpointError as e:
            raise conflict(str(e)) from e


@router.get("/rescore")
def rescore_status() -> dict:
    return R.status()
