"""Requirements: list, detail (with the review context), history, evidence chain, audit, step-by-step trace, and every
PM write (status, gate override, priorities, content edit, evidence links, challenge) plus access logging.

Writes go through `bmw_req.service` only (append-only audit inside). The API adds the validation the service leaves
to the UI: enums, existence of requirement / target / finding, no partial priority writes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import jobs, labels as L
from api.deps import action_errors, conflict, db, get_actor, need_rationale, not_found
from api.queries import (current_wave, enrich_breakdown, latest_extractor, loads, metrics_wave, parse_key, proposals,
                         require_requirement, requirement_summaries, requirement_summary, run_waves, split_bullets,
                         spend_by_prefix, target_obj, tkey, voice_of)
from bmw_req import service
from bmw_req.car_zones import requirement_zone
from bmw_req.pipeline.scoring import CONFIDENCE, EFFORT_MOD, MARKET_FIT_MOD, PRIORITY_BANDS

router = APIRouter(prefix="/api", tags=["requirements"])

DERIVATION_KEYS = ("product_decision", "evidence_summary", "horizon_reason", "effort_reason")


# ------------------------------------------------------------------------------------------------ reads
@router.get("/requirements")
def list_requirements(status: str | None = Query(None, description="comma-separated statuses"),
                      vehicle: str | None = None, market: str | None = None, category: str | None = None,
                      q: str | None = None, include_rejected: bool = False) -> list[dict]:
    with db() as conn:
        items = requirement_summaries(conn)
        texts = {r[0]: f"{r[0]} {r[1] or ''} {r[2] or ''}".lower() for r in
                 conn.execute("SELECT id, title, description FROM requirement")}
    statuses = {s.strip() for s in status.split(",") if s.strip()} if status else None
    out = []
    for s in items:
        if statuses is not None:
            if s["status"] not in statuses:
                continue
        elif not include_rejected and s["status"] == "rejected":
            continue
        if category and s["category"] != category:
            continue
        if vehicle or market:
            if not any((not vehicle or t["target"]["vehicle"] == vehicle) and (not market or t["target"]["market"] == market)
                       for t in s["targets"]):
                continue
        if q and q.lower() not in texts.get(s["id"], ""):
            continue
        out.append(s)
    return out


def _quotes(conn, rid: str, wave: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT s.external_id, s.market_code AS market, s.country, fs.quote, f.id AS finding_id
           FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
           JOIN finding_source fs ON fs.finding_id = f.id JOIN source_item s ON s.id = fs.source_item_id
           WHERE rf.requirement_id = ? AND rf.relation = 'supports' AND fs.quote IS NOT NULL AND s.wave <= ?
           ORDER BY (SELECT COUNT(*) FROM finding_source x WHERE x.finding_id = f.id) DESC, s.id LIMIT 8""",
        (rid, wave or 99))]


def _linked(conn, rid: str, kind: str, wave: int, limit: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT f.id, f.title, f.type, f.vehicle_model_id, f.market_code, f.metrics_json FROM requirement_finding rf
           JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ? AND rf.relation = 'supports'
           AND f.source_kind = ? AND COALESCE(f.first_wave, 1) <= ? ORDER BY f.id LIMIT ?""",
        (rid, kind, wave or 99, limit))]


def latest_fit(conn, rid: str) -> list[dict]:
    rows = conn.execute(
        """SELECT f.* FROM fit_check f WHERE f.requirement_id = ? AND f.id = (
             SELECT MAX(g.id) FROM fit_check g WHERE g.requirement_id = f.requirement_id
             AND COALESCE(g.vehicle_model_id,'') = COALESCE(f.vehicle_model_id,'')
             AND COALESCE(g.market_code,'') = COALESCE(f.market_code,'') AND g.check_type = f.check_type)
           ORDER BY f.vehicle_model_id, f.market_code, f.check_type""", (rid,)).fetchall()
    return [{"target": target_obj(r["vehicle_model_id"], r["market_code"]), "check_type": r["check_type"],
             "result": r["result"], "rationale": r["rationale"], "checked_by": r["checked_by"],
             "checked_at": r["checked_at"]} for r in rows]


def challenges(conn, rid: str) -> list[dict]:
    """PM challenges paired with the AI answers by following event id order: each `challenge` opens an entry, the
    next `challenge_response` before the following `challenge` answers it (an orphan answer gets its own entry)."""
    out: list[dict] = []
    for e in conn.execute("""SELECT id, ts, actor_id, action, new_value, rationale, model FROM audit_event
                             WHERE entity_type = 'requirement' AND entity_id = ?
                             AND action IN ('challenge', 'challenge_response') ORDER BY id""", (rid,)):
        if e["action"] == "challenge":
            out.append({"asked_at": e["ts"], "actor": e["actor_id"], "question": e["rationale"],
                        "answered_at": None, "model": None, "answer": None})
        else:
            ans = loads(e["new_value"], {}) or {}
            answer = {k: ans.get(k) for k in ("verdict", "answer", "evidence_for", "evidence_against",
                                               "proposed_edits", "link_finding_ids")}
            if out and out[-1]["answer"] is None:
                out[-1].update(answered_at=e["ts"], model=e["model"], answer=answer)
            else:
                out.append({"asked_at": None, "actor": None, "question": None, "answered_at": e["ts"],
                            "model": e["model"], "answer": answer})
    return out


@router.get("/requirements/{rid}")
def requirement_detail(rid: str) -> dict:
    with db() as conn:
        req = require_requirement(conn, rid)
        w = current_wave(conn)
        s = requirement_summary(conn, rid)
        bmap = {(r[0], r[1]): loads(r[2]) for r in conn.execute(
            "SELECT vehicle_model_id, market_code, score_breakdown_json FROM requirement_target WHERE requirement_id = ?",
            (rid,))}
        quotes = _quotes(conn, rid, w)
        study = _linked(conn, rid, "study", w, 6)
        web = _linked(conn, rid, "web", w, 6)
        contra = [{"finding_id": r[0], "title": r[1], "source_kind": r[2]} for r in conn.execute(
            """SELECT f.id, f.title, f.source_kind FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
               WHERE rf.requirement_id = ? AND rf.relation = 'contradicts' ORDER BY f.id""", (rid,))]
        fit = latest_fit(conn, rid)
        open_props = proposals(conn, "p.requirement_id = ? AND p.status = 'open'", (rid,))
        chal = challenges(conn, rid)
    deriv = loads(req.pop("derivation_json", None))
    derivation = None
    if isinstance(deriv, dict):
        derivation = {k: deriv[k] for k in DERIVATION_KEYS if deriv.get(k)}
        derivation.update(supporting_finding_ids=deriv.get("supporting_finding_ids") or [],
                          conflicting_finding_ids=deriv.get("conflicting_finding_ids") or [],
                          wave=deriv.get("wave"), prompt=deriv.get("prompt"))
    targets = []
    for t in s["targets"]:
        b = bmap.get((t["target"]["vehicle"], t["target"]["market"]))
        targets.append({**t, "breakdown": enrich_breakdown(b), "voice": voice_of(b)})
    study_out = []
    for f in study:
        m = loads(f["metrics_json"], {}) or {}
        study_out.append({"finding_id": f["id"], "title": f["title"], "type": f["type"], "market": f["market_code"],
                          "vehicle": f["vehicle_model_id"], "mean": m.get("mean"), "z": m.get("z"), "scale": m.get("scale")})
    web_out = []
    for f in web:
        m = loads(f["metrics_json"], {}) or {}
        tiers = sorted((m.get("tiers") or {}).keys())
        web_out.append({"finding_id": f["id"], "title": f["title"], "type": f["type"], "market": f["market_code"],
                        "vehicle": f["vehicle_model_id"], "best_tier": tiers[0] if tiers else None,
                        "publishers": m.get("publishers") or [], "newest_date": m.get("newest_date")})
    return {
        **req, "must_not_lose": bool(req.get("must_not_lose")),
        "zone": requirement_zone(req["title"], req["category"], req.get("description")),
        "max_score": s["max_score"], "best_target": s["best_target"],
        "derivation": derivation,
        "assumptions_list": split_bullets(req.get("assumptions")),
        "uncertainties_list": split_bullets(req.get("uncertainties")),
        "targets": targets, "brand_blocked": s["brand_blocked"],
        "overridden": [t["target"]["key"] for t in s["targets"] if t["brand_gate"] == "overridden"],
        "quotes": quotes, "study": study_out, "web": web_out, "contradicting": contra,
        "fit": fit, "open_proposals": open_props, "challenges": chal,
    }


@router.get("/requirements/{rid}/history")
def history(rid: str) -> dict:
    with db() as conn:
        require_requirement(conn, rid)
        rw = run_waves(conn)
        series = defaultdict(list)
        for r in conn.execute(
                """SELECT s.run_id, s.vehicle_model_id v, s.market_code m, s.score, s.rank, s.priority, r.ts, r.trigger
                   FROM score_snapshot s JOIN prioritization_run r ON r.id = s.run_id WHERE s.requirement_id = ?
                   ORDER BY s.vehicle_model_id, s.market_code, s.run_id""", (rid,)):
            series[(r["v"], r["m"])].append({"run_id": r["run_id"], "ts": r["ts"], "trigger": r["trigger"],
                                             "wave": rw.get(r["run_id"]),
                                             "score": None if r["score"] is None else round(r["score"], 1),
                                             "rank": r["rank"], "priority": r["priority"]})
        causes = [{"run_id": r["run_id"], "target_key": r["entity_id"].split(":", 1)[1], "rationale": r["rationale"]}
                  for r in conn.execute("""SELECT run_id, entity_id, rationale FROM audit_event WHERE action = 'rescore'
                                           AND entity_id LIKE ? ORDER BY id""", (f"{rid}:%",))]
    return {"series": [{"target": target_obj(v, m), "points": pts} for (v, m), pts in series.items()], "causes": causes}


def finding_cards(conn, rows: list[dict], wave: int) -> list[dict]:
    """Linked findings with source counts, signal counts and per-market metrics (verbatim) or flat metrics."""
    if not rows:
        return []
    ids = tuple(r["id"] for r in rows)
    ph = ",".join("?" * len(ids))
    counts = defaultdict(list)
    n_src = defaultdict(int)
    for r in conn.execute(
            f"""SELECT fs.finding_id, s.kind, COALESCE(s.market_code, '–') market, COUNT(*) n, MIN(s.trust_tier) tier
                FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id WHERE fs.finding_id IN ({ph})
                GROUP BY 1, 2, 3""", ids):
        counts[r[0]].append({"kind": r[1], "market": r[2], "n": r[3], "tier": r[4]})
        n_src[r[0]] += r[3]
    n_sig = dict(conn.execute(f"SELECT finding_id, COUNT(*) FROM finding_signal WHERE finding_id IN ({ph}) GROUP BY 1",
                              ids).fetchall())
    mw = metrics_wave(wave)
    out = []
    for f in rows:
        m = loads(f.get("metrics_json"), {}) or {}
        card = {"id": f["id"], "source_kind": f["source_kind"], "type": f["type"], "title": f["title"],
                "summary": f["summary"], "category": f["category"], "vehicle": f["vehicle_model_id"],
                "market": f["market_code"], "polarity": f.get("polarity"), "first_wave": f["first_wave"],
                "relation": f.get("relation"), "n_sources": n_src.get(f["id"], 0), "n_signals": n_sig.get(f["id"], 0),
                "source_counts": counts.get(f["id"], [])}
        if f["source_kind"] == "verbatim":
            bw = (m.get("by_wave") or {}).get(mw) or {}
            card["verbatims"] = bw.get("verbatims")
            card["markets"] = bw.get("markets") or {}
            card["metrics_wave"] = mw
        else:
            card["metrics"] = m
        out.append(card)
    return out


@router.get("/requirements/{rid}/evidence")
def evidence(rid: str) -> dict:
    with db() as conn:
        require_requirement(conn, rid)
        rows = [dict(r) for r in conn.execute(
            """SELECT f.id, f.source_kind, f.type, f.title, f.summary, f.category, f.vehicle_model_id, f.market_code,
                      f.metrics_json, f.first_wave, f.polarity, rf.relation
               FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ?
               ORDER BY rf.relation DESC, f.id""", (rid,))]
        return {"findings": finding_cards(conn, rows, current_wave(conn))}


@router.get("/requirements/{rid}/audit")
def requirement_audit(rid: str, human_only: bool = False, order: Literal["asc", "desc"] = "asc") -> list[dict]:
    with db() as conn:
        require_requirement(conn, rid)
        ev = service.requirement_trail(conn, rid)
    if human_only:
        ev = [e for e in ev if e["actor_type"] == "human"]
    return ev[::-1] if order == "desc" else ev


@router.get("/requirements/{rid}/trace")
def trace(rid: str, target: str | None = None) -> dict:
    """'How it works' for one requirement × target: per step the global rule/stats and what happened here."""
    with db() as conn:
        req = require_requirement(conn, rid)
        deriv = loads(req.get("derivation_json"), {}) or {}
        s = requirement_summary(conn, rid)
        if not s["targets"]:
            raise conflict(f"{rid} has no car · market targets yet")
        if target:
            v, m = parse_key(target)
        else:
            keys = [(t["target"]["vehicle"], t["target"]["market"]) for t in s["targets"]]
            v, m = ("G60", "US") if ("G60", "US") in keys else keys[0]
        trow = next((t for t in s["targets"] if (t["target"]["vehicle"], t["target"]["market"]) == (v, m)), None)
        if trow is None:
            raise not_found(f"{rid} has no target {tkey(v, m)}")
        b = loads(conn.execute("""SELECT score_breakdown_json FROM requirement_target WHERE requirement_id = ?
                                  AND vehicle_model_id = ? AND market_code = ?""", (rid, v, m)).fetchone()[0], {}) or {}
        spend = spend_by_prefix(conn)

        def sp(*prefixes):
            return {"calls": sum(spend.get(p, {}).get("calls", 0) for p in prefixes),
                    "usd": round(sum(spend.get(p, {}).get("usd", 0) for p in prefixes), 4)}

        # 1 collect
        src = dict(conn.execute("SELECT kind, COUNT(*) FROM source_item GROUP BY kind").fetchall())
        ex_sql = """SELECT s.id sid, s.external_id, s.ref, s.text, s.country, s.market_code, s.meta_json, s.wave,
                           f.id fid, f.title ftitle FROM requirement_finding rf
                    JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
                    JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
                    JOIN source_item s ON s.id = g.source_item_id
                    WHERE rf.requirement_id = ? AND rf.relation = 'supports' {extra}
                    ORDER BY CASE g.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, g.quote_verified DESC,
                             g.support_question, length(s.text) BETWEEN 60 AND 400 DESC, s.id LIMIT 1"""
        ex = conn.execute(ex_sql.format(extra="AND s.vehicle_model_id = ? AND s.market_code = ?"), (rid, v, m)).fetchone()
        other_market = False
        if ex is None:
            ex = conn.execute(ex_sql.format(extra=""), (rid,)).fetchone()
            other_market = ex is not None
        example = None
        if ex is not None:
            meta = loads(ex["meta_json"], {}) or {}
            text = ex["text"] or ""
            example = {"source_id": ex["sid"], "external_id": ex["external_id"], "ref": ex["ref"],
                       "text": text if len(text) <= 600 else text[:599] + "…", "country": ex["country"],
                       "market": ex["market_code"], "channel": meta.get("channel"), "wave": ex["wave"]}
        # 2 read
        ver = latest_extractor(conn)
        n_ext = conn.execute("SELECT COUNT(*) FROM verbatim_extraction WHERE extractor_version = ?", (ver,)).fetchone()[0]
        n_in = conn.execute("SELECT COALESCE(SUM(in_scope), 0) FROM verbatim_extraction WHERE extractor_version = ?",
                            (ver,)).fetchone()[0]
        n_sig, n_unver = conn.execute("""SELECT COUNT(*), COALESCE(SUM(quote_verified = 0), 0) FROM signal
                                         WHERE extractor_version = ?""", (ver,)).fetchone()
        sigs = [dict(r) for r in conn.execute(
            """SELECT id AS signal_id, category, topic, feedback_type, severity, need_statement, quote, quote_verified,
                      support_question FROM signal WHERE source_item_id = ? AND extractor_version = ?""",
            (ex["sid"], ver))] if ex is not None else []
        # 3 group
        fk = dict(conn.execute("SELECT COALESCE(source_kind, 'other'), COUNT(*) FROM finding GROUP BY 1").fetchall())
        links = [{"kind": r[0], "relation": r[1], "n": r[2]} for r in conn.execute(
            """SELECT f.source_kind, rf.relation, COUNT(*) FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
               WHERE rf.requirement_id = ? GROUP BY 1, 2""", (rid,))]
        finding = None
        if ex is not None:
            f = conn.execute("SELECT id, title, summary, metrics_json FROM finding WHERE id = ?", (ex["fid"],)).fetchone()
            mk = ((((loads(f["metrics_json"], {}) or {}).get("by_wave") or {}).get("2") or {}).get("markets") or {})
            finding = {"id": f["id"], "title": f["title"], "summary": f["summary"],
                       "n_signals": conn.execute("SELECT COUNT(*) FROM finding_signal WHERE finding_id = ?", (f["id"],)).fetchone()[0],
                       "markets": [{"market": k, "verbatims": x.get("verbatims"), "share": x.get("share")} for k, x in mk.items()]}
        # 4 draft
        n_req = conn.execute("SELECT COUNT(*) FROM requirement").fetchone()[0]
        merges = conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'match_existing'").fetchone()[0]
        # 5 fit
        fit_matrix = [{"check_type": r[0], "result": r[1], "n": r[2]} for r in
                      conn.execute("SELECT check_type, result, COUNT(*) FROM fit_check GROUP BY 1, 2")]
        fit_here = [f for f in latest_fit(conn, rid) if f["target"] and (f["target"]["vehicle"], f["target"]["market"]) == (v, m)]
        # 7 decide
        ev = [dict(r) for r in conn.execute(
            """SELECT id, ts, actor_type, actor_id, action, entity_id, field, old_value, new_value, rationale
               FROM audit_event WHERE (entity_id = ? OR entity_id LIKE ?) AND action != 'view' ORDER BY id""",
            (rid, f"{rid}:%"))]
        # 8 repeat
        props = proposals(conn, "p.requirement_id = ?", (rid,))
        hist = [dict(r) for r in conn.execute(
            """SELECT s.run_id, s.score, s.priority, r.ts FROM score_snapshot s JOIN prioritization_run r ON r.id = s.run_id
               WHERE s.requirement_id = ? AND s.vehicle_model_id = ? AND s.market_code = ? ORDER BY s.run_id""", (rid, v, m))]
        causes = {r[0]: r[1] for r in conn.execute(
            "SELECT run_id, rationale FROM audit_event WHERE action = 'rescore' AND entity_id = ? ORDER BY id",
            (f"{rid}:{tkey(v, m)}",))}

    by_actor = defaultdict(int)
    for e in ev:
        by_actor[e["actor_type"]] += 1
    status_counts = defaultdict(int)
    for p in props:
        status_counts[p["status"]] += 1
    asm = req.get("assumptions") or deriv.get("assumptions")
    return {
        "requirement": {"id": rid, "title": req["title"], "status": req["status"], "evidence_level": req["evidence_level"]},
        "target": trow["target"], "target_row": trow,
        "steps": {
            "collect": {"global": {"sources_by_kind": src}, "example": example, "example_from_other_market": other_market},
            "read": {"global": {"extractor_version": ver, "extracted": n_ext, "in_scope": n_in, "signals": n_sig,
                                "unverified_quotes": n_unver, "spend": sp("extract", "recheck")},
                     "signals": sigs},
            "group": {"global": {"findings_by_kind": fk, "spend": sp("embed", "findings", "research")},
                      "finding": finding, "link_counts": links},
            "draft": {"global": {"requirements": n_req, "duplicates_caught": merges,
                                 "spend": sp("derive", "consolidate", "match_existing", "link")},
                      "title": req["title"], "description": req["description"], "horizon": req["horizon"],
                      "kano_class": req["kano_class"], "effort": req["effort"], "created_by": req.get("created_by"),
                      "n_supporting": len(deriv.get("supporting_finding_ids") or []),
                      "product_decision": deriv.get("product_decision"), "evidence_summary": deriv.get("evidence_summary"),
                      "assumptions": split_bullets(asm) if isinstance(asm, str) else (asm or []),
                      "horizon_reason": deriv.get("horizon_reason")},
            "fit": {"global": {"matrix": fit_matrix, "spend": sp("fit")}, "checks": fit_here},
            "score": {"global": {"confidence": CONFIDENCE, "effort_mod": EFFORT_MOD, "market_fit_mod": MARKET_FIT_MOD,
                                 "priority_bands": {n: lo for n, lo in PRIORITY_BANDS if lo > 0}},
                      "breakdown": enrich_breakdown(b) if b else None, "waterfall": waterfall(b),
                      "score": trow["score"], "ai_priority": trow["ai_priority"],
                      "cap_note": b.get("cap_note"), "priority_note": b.get("priority_note"),
                      "gaps": [f["label"] for f in (b.get("factors") or {}).values() if not f.get("available")]},
            "decide": {"global": {"by_actor_type": dict(by_actor)}, "status": req["status"],
                       "pm_priority": trow["pm_priority"], "ai_priority": trow["ai_priority"],
                       "human_events": [e for e in ev if e["actor_type"] == "human"][-8:]},
            "repeat": {"global": {"proposal_status_counts": dict(status_counts)},
                       "snapshots": [{**h, "score": None if h["score"] is None else round(h["score"], 1),
                                      "cause": causes.get(h["run_id"])} for h in hist],
                       "proposals": props[-3:]},
        },
    }


def waterfall(b: dict) -> list[dict]:
    """Score arithmetic as steps: factor points (without confidence), the confidence cut, modifiers, total."""
    facs = (b or {}).get("factors") or {}
    if not facs:
        return []
    conf = float(b.get("confidence") or 1.0)
    wsum = sum(f["weight"] for f in facs.values() if f.get("available")) or 1
    rows, run = [], 0.0
    for key, f in facs.items():
        if not f.get("available"):
            continue
        pts = 100 * f["weight"] * (f["value"] or 0) / wsum
        rows.append({"step": f["label"], "factor": key, "kind": "factor", "start": round(run, 2),
                     "end": round(run + pts, 2), "delta": round(pts, 2)})
        run += pts
    cut = run * (1 - conf)
    if cut >= 0.05:
        rows.append({"step": f"Evidence confidence ×{conf}", "factor": None, "kind": "minus", "start": round(run - cut, 2),
                     "end": round(run, 2), "delta": round(-cut, 2)})
        run -= cut
    for k, val in (b.get("modifiers") or {}).items():
        if val:
            rows.append({"step": k.replace("_", " ").capitalize(), "factor": None, "kind": "plus" if val > 0 else "minus",
                         "start": round(min(run, run + val), 2), "end": round(max(run, run + val), 2),
                         "delta": round(val, 2)})
            run += val
    rows.append({"step": "Score", "factor": None, "kind": "total", "start": 0, "end": float(b.get("score", run)),
                 "delta": float(b.get("score", run))})
    return rows


# ------------------------------------------------------------------------------------------------ writes
class StatusBody(BaseModel):
    status: Literal["approved", "rejected", "deferred", "challenged", "proposed"]
    rationale: str
    accept_ai_priorities: bool = False


class OverrideBody(BaseModel):
    target: str
    rationale: str


class PrioritiesBody(BaseModel):
    priorities: dict[str, Literal["Must", "Should", "Could"] | None] = Field(min_length=1)
    rationale: str


class EditBody(BaseModel):
    changes: dict[str, Any] = Field(min_length=1)
    rationale: str


class LinkBody(BaseModel):
    relation: Literal["supports", "contradicts"] | None
    rationale: str


class ChallengeBody(BaseModel):
    question: str


class AccessBody(BaseModel):
    action: Literal["view", "export"]
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=2000)


@router.post("/requirements/{rid}/status")
def set_status(rid: str, body: StatusBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    done: list[str] = []
    with db() as conn:
        require_requirement(conn, rid)
        with action_errors():
            service.set_status(conn, rid, body.status, actor, why)
        if body.accept_ai_priorities and body.status != "rejected":
            for t in conn.execute("""SELECT vehicle_model_id, market_code, proposed_priority FROM requirement_target
                                     WHERE requirement_id = ? AND priority IS NULL AND proposed_priority IS NOT NULL
                                     ORDER BY vehicle_model_id, market_code""", (rid,)).fetchall():
                try:
                    service.set_priority(conn, rid, t[0], t[1], t[2], actor,
                                         f"Accepted the AI suggestion with the decision: {why}")
                except service.ActionError:
                    break
                done.append(tkey(t[0], t[1]))
        return {"requirement": requirement_summary(conn, rid), "priorities_set": done}


@router.post("/requirements/{rid}/override")
def override(rid: str, body: OverrideBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    v, m = parse_key(body.target)
    with db() as conn:
        require_requirement(conn, rid)
        if conn.execute("SELECT 1 FROM requirement_target WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?",
                        (rid, v, m)).fetchone() is None:
            raise not_found(f"{rid} has no target {tkey(v, m)}")
        with action_errors():
            service.override_gate(conn, rid, tkey(v, m), actor, why)
        return {"overridden": tkey(v, m), "brand_blocked": service.brand_blocked(conn, rid)}


@router.put("/requirements/{rid}/priorities")
def set_priorities(rid: str, body: PrioritiesBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    wanted = {parse_key(k): p for k, p in body.priorities.items()}
    changed: list[str] = []
    with db() as conn:
        require_requirement(conn, rid)
        cur = {(r[0], r[1]): r[2] for r in conn.execute(
            "SELECT vehicle_model_id, market_code, priority FROM requirement_target WHERE requirement_id = ?", (rid,))}
        missing = [tkey(*k) for k in wanted if k not in cur]
        if missing:   # validate everything before writing anything
            raise conflict(f"{rid} has no target {', '.join(missing)}")
        with action_errors():
            for (v, m), p in wanted.items():
                if cur[(v, m)] != p:
                    service.set_priority(conn, rid, v, m, p, actor, why)
                    changed.append(tkey(v, m))
    return {"changed": changed}


@router.patch("/requirements/{rid}")
def edit(rid: str, body: EditBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    unknown = sorted(set(body.changes) - set(service.EDITABLE))
    if unknown:
        raise HTTPException(422, f"Not editable: {', '.join(unknown)} (editable: {', '.join(service.EDITABLE)})")
    for k, v in body.changes.items():
        if v is not None and not isinstance(v, str):
            raise HTTPException(422, f"{k} must be a string or null")
        if k in L.ENUMS and v not in L.ENUMS[k]:
            raise HTTPException(422, f"{k} must be one of {L.ENUMS[k]}")
        if k == "title" and not (v or "").strip():
            raise HTTPException(422, "title must not be empty")
    with db() as conn:
        cur = require_requirement(conn, rid)
        changed = [k for k, v in body.changes.items() if v != cur.get(k)]
        with action_errors():
            version = service.edit_requirement(conn, rid, body.changes, actor, why)
    return {"version": version, "changed": changed}


@router.put("/requirements/{rid}/findings/{fid}")
def set_link(rid: str, fid: int, body: LinkBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    with db() as conn:
        require_requirement(conn, rid)
        if conn.execute("SELECT 1 FROM finding WHERE id = ?", (fid,)).fetchone() is None:
            raise not_found(f"No finding F{fid}")
        old = conn.execute("SELECT relation FROM requirement_finding WHERE requirement_id = ? AND finding_id = ?",
                           (rid, fid)).fetchone()
        old_rel = old[0] if old else None
        if old_rel == body.relation:
            if old_rel is None:
                raise conflict(f"F{fid} is not linked to {rid}")
            return {"relation": old_rel, "changed": False}
        with action_errors():
            service.set_finding_link(conn, rid, fid, body.relation, actor, why)
    return {"relation": body.relation, "changed": True}


@router.post("/requirements/{rid}/challenge", status_code=202)
def challenge(rid: str, body: ChallengeBody, actor: str = Depends(get_actor)) -> JSONResponse:
    question = need_rationale(body.question, "A question")
    with db() as conn:
        require_requirement(conn, rid)
    jid = jobs.start("challenge", jobs.run_challenge(rid, question, actor), {"requirement_id": rid})
    if jid is None:
        raise conflict(f"Another job is running ({(jobs.running() or {}).get('id')}); try again when it has finished.")
    return JSONResponse({"job_id": jid}, status_code=202)


@router.post("/access")
def access(body: AccessBody, actor: str = Depends(get_actor)) -> dict:
    with db() as conn:
        service.log_access(conn, actor, body.action, body.entity_type, body.entity_id, body.detail)
    return {"ok": True}

