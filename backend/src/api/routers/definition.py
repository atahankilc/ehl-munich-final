"""Requirement definition (D-048): requirements with metric, acceptance criteria and target ladders, and the links
between them, at a checkpoint. The AI proposes; the PM chooses ladder levels and confirms / removes / adds links —
both append-only (`def_choice`, `def_link_review`) and audited as human events (rule 5, 6).

GET  /api/definition?cp=                     requirements, links, bundles, domains, resources, zones, 3D models
GET  /api/definition/requirement/{key}?cp=   one requirement + evidence, facts, area, history across checkpoints
POST /api/definition/choice                  {key, line, market, level, rationale, actor?, cp?}
POST /api/definition/link-review             {a, b, relation, verdict, via?, strength?, rationale, actor?, cp?}
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.deps import conflict, db, get_actor, need_rationale, not_found
from bmw_req.car_zones import MODELS_GLTF, ZONES, model_url
from bmw_req.checkpoints import BY_ID, CHECKPOINTS, latest_run
from bmw_req.definition import benchmarks as B
from bmw_req.definition.define import ensure
from bmw_req.definition.domains import DOMAINS, RESOURCES
from bmw_req.audit import audit

router = APIRouter(prefix="/api/definition", tags=["definition"])
STAGES = ("define", "specify", "couple")
LINE_MODEL = {"1 Series": "F70", "5 Series": "G60", "7 Series": "G70"}
RUNGS = ("baseline", "threshold", "target", "stretch")


def _loads(s, default=None):
    return json.loads(s) if s else default


def _runs(conn, cp: str) -> dict:
    if cp not in BY_ID:
        raise not_found(f"No checkpoint {cp!r}")
    ensure(conn)
    return {s: latest_run(conn, cp, s) for s in STAGES}


def _run_view(r) -> dict | None:
    return {"id": r["id"], "finished_at": r["finished_at"], "stats": _loads(r["stats_json"], {})} if r else None


def _model(v: str) -> dict:
    m = MODELS_GLTF.get(v) or {}
    return {"vehicle": v, "url": model_url(v), "orientation": m.get("orientation"), "stand_in": m.get("stand_in"),
            "attribution": {k: m.get(k) for k in ("name", "author", "license", "source_url")} if m else None}


def _states(conn, run_id: int | None, prefix: str) -> dict[str, dict]:
    if not run_id:
        return {}
    return {r["entity_key"][len(prefix):]: {"state": r["state"], "payload": _loads(r["payload_json"])}
            for r in conn.execute("SELECT entity_key, state, payload_json FROM track WHERE run_id = ? AND entity_key LIKE ?",
                                  (run_id, prefix + "%"))}


def _choices(conn) -> dict[tuple, dict]:
    out = {}
    for r in conn.execute("SELECT * FROM def_choice ORDER BY id"):   # latest wins
        out[(r["req_key"], r["line"], r["market"])] = {"level": r["level"], "rationale": r["rationale"], "actor": r["actor"],
                                                       "at": r["created_at"], "checkpoint": r["checkpoint_id"]}
    return out


def _reviews(conn) -> dict[tuple, dict]:
    out = {}
    for r in conn.execute("SELECT * FROM def_link_review ORDER BY id"):
        out[(r["a_key"], r["b_key"], r["relation"])] = {"verdict": r["verdict"], "actor": r["actor"], "rationale": r["rationale"],
                                                        "at": r["created_at"], "via": r["via"], "strength": r["strength"]}
    return out


def _area_titles(conn, cp: str) -> dict[str, dict]:
    out = {}
    for c in CHECKPOINTS:   # latest areas run per checkpoint; the requested checkpoint wins
        r = latest_run(conn, c.id, "areas")
        if r and (c.id == cp or c.position < BY_ID[cp].position):
            out |= {a["key"]: {"key": a["key"], "title": a["title"], "need": a["need"], "kind": a["kind"]}
                    for a in conn.execute("SELECT key, title, need, kind FROM req_area WHERE run_id = ?", (r["id"],))}
    return out


def _requirement(r, spec, area: dict | None, state: dict | None, spec_state: dict | None, choices: dict) -> dict:
    ladder = _loads(spec["ladder_json"], []) if spec else []
    for rung in ladder:
        rung["choice"] = choices.get((r["key"], rung["line"], rung["market"]))
    return {"key": r["key"], "version": r["version"], "area_key": r["area_key"], "area_title": (area or {}).get("title"),
            "title": r["title"], "statement": r["statement"], "domain": r["domain"], "aspects": _loads(r["aspects_json"], []),
            "zones": _loads(r["zones_json"], []), "lines": _loads(r["lines_json"], []), "markets": _loads(r["markets_json"], []),
            "targets": _loads(r["targets_json"], []), "decision_type": r["decision_type"], "today_status": r["today_status"],
            "horizon": r["horizon"], "horizon_year": r["horizon_year"], "kano": r["kano"], "status": r["status"],
            "state": (state or {}).get("state"), "spec_state": (spec_state or {}).get("state"),
            "spec_moved": ((spec_state or {}).get("payload") or {}).get("moved"),
            "change_note": r["change_note"], "spec_change_note": spec["change_note"] if spec else None,
            "metric": _loads(spec["metric_json"]) if spec else None, "acceptance": _loads(spec["acceptance_json"], []) if spec else [],
            "ladder": ladder, "gaps": _loads(spec["gaps_json"], []) if spec else [],
            "assumptions": _loads(r["assumptions_json"], []) + (_loads(spec["assumptions_json"], []) if spec else []),
            "evidence_count": len(_loads(r["evidence_ids_json"], [])), "trend_ids": _loads(r["trend_ids_json"], [])}


def bundles(links: list[dict], keys: set[str] | None = None) -> list[dict]:
    """Connected components over links with strength ≥ 2 that the PM has not removed (union-find)."""
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    use = [l for l in links if (l.get("strength") or 0) >= 2 and (l.get("review") or {}).get("verdict") != "removed"
           and (keys is None or (l["a"] in keys and l["b"] in keys))]
    for l in use:
        parent[find(l["a"])] = find(l["b"])
    comp = defaultdict(set)
    for l in use:
        comp[find(l["a"])].update((l["a"], l["b"]))
    out = []
    for i, ks in enumerate(sorted(comp.values(), key=lambda s: (-len(s), sorted(s)[0]))):
        inner = [l for l in use if l["a"] in ks]
        rel = defaultdict(int)
        for l in inner:
            rel[f"{l['relation']} via {l['via']}"] += 1
        out.append({"id": f"bundle:{i + 1}", "keys": sorted(ks), "conflict": any(l["relation"] == "conflicts" for l in inner),
                    "reason": ", ".join(f"{k} ×{n}" if n > 1 else k for k, n in sorted(rel.items(), key=lambda kv: -kv[1]))})
    return out


def _links(conn, run_id: int | None, keys: set[str]) -> list[dict]:
    reviews = _reviews(conn)
    states = _states(conn, run_id, "link:")
    out, seen = [], set()
    for l in (conn.execute("SELECT * FROM def_link WHERE run_id = ? ORDER BY id", (run_id,)) if run_id else []):
        k = (l["a_key"], l["b_key"], l["relation"])
        seen.add(k)
        out.append({"id": "|".join(k), "a": l["a_key"], "b": l["b_key"], "relation": l["relation"], "via": l["via"],
                    "strength": l["strength"], "direction": l["direction"], "rationale": l["rationale"], "method": l["method"],
                    "state": (states.get("|".join(k)) or {}).get("state"), "review": reviews.get(k), "source": "ai"})
    for k, rv in reviews.items():   # links the PM added
        if k not in seen and rv["verdict"] == "added" and k[0] in keys and k[1] in keys:
            out.append({"id": "|".join(k), "a": k[0], "b": k[1], "relation": k[2], "via": rv["via"], "strength": rv["strength"] or 2,
                        "direction": "mutual", "rationale": rv["rationale"], "method": "pm", "state": "added", "review": rv,
                        "source": "pm"})
    return out


@router.get("")
def definition(cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        base = {"checkpoint": cp, "runs": {s: _run_view(r) for s, r in runs.items()},
                "domains": [{"key": d["key"], "label": d["label"], "aspects": d["aspects"]} for d in DOMAINS],
                "resources": RESOURCES, "zones": ZONES, "models": {line: _model(v) for line, v in LINE_MODEL.items()}}
        if not runs["define"]:
            return {**base, "ready": False, "requirements": [], "links": [], "bundles": []}
        drun = runs["define"]["id"]
        srun = runs["specify"]["id"] if runs["specify"] else None
        specs = {s["req_key"]: s for s in conn.execute("SELECT * FROM def_spec WHERE run_id = ?", (srun,))} if srun else {}
        areas, choices = _area_titles(conn, cp), _choices(conn)
        rstate, sstate = _states(conn, drun, "rq:"), _states(conn, srun, "spec:")
        reqs = [_requirement(r, specs.get(r["key"]), areas.get(r["area_key"]), rstate.get(r["key"]), sstate.get(r["key"]), choices)
                for r in conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY domain, key", (drun,))]
        keys = {r["key"] for r in reqs}
        links = _links(conn, runs["couple"]["id"] if runs["couple"] else None, keys)
        lost = [k for k, s in rstate.items() if s["state"] == "lost"]
        return {**base, "ready": bool(srun), "requirements": reqs, "links": links, "bundles": bundles(links, keys),
                "lost": lost}


def _evidence(conn, ids: list[str], area_key: str, cp: str) -> list[dict]:
    xrun, arun = latest_run(conn, cp, "contextualize"), latest_run(conn, cp, "areas")
    themes = []
    if arun:
        a = conn.execute("SELECT theme_keys_json FROM req_area WHERE run_id = ? AND key = ?", (arun["id"], area_key)).fetchone()
        themes = _loads(a["theme_keys_json"], []) if a else []
    rel = {}
    if xrun and themes:
        for e in conn.execute(f"""SELECT src_type, src_id, relation FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme'
                                  AND dst_id IN ({','.join('?' * len(themes))})""", (xrun["id"], *themes)):
            rel.setdefault(f"{e['src_type']}:{e['src_id']}", e["relation"])
    out = []
    for i in ids:
        typ, nid = i.split(":", 1)
        row = {"id": i, "kind": typ, "text": None, "url": None, "tier": None, "published": None, "relation": rel.get(i), "quote": None}
        if typ in ("research", "option"):
            s = conn.execute("SELECT kind, text, url, trust_tier, published_at, quote, vehicle_model_id, meta_json FROM source_item WHERE id = ?",
                             (int(nid),)).fetchone()
            if s:
                m = _loads(s["meta_json"], {})
                text = f"{s['vehicle_model_id']}: {m.get('name_en')} ({m.get('availability')}, German price list)" if typ == "option" else s["text"]
                row |= {"kind": s["kind"] if typ == "research" else "option", "text": text, "url": s["url"], "tier": s["trust_tier"],
                        "published": s["published_at"], "quote": s["quote"]}
        elif typ == "study":
            s = conn.execute("SELECT item, vehicle_model_id, market_code, scale, mean, top2, z_within_column FROM study_metric WHERE id = ?",
                             (int(nid),)).fetchone()
            if s:
                val = f"mean {s['mean']:.2f}/10" if s["scale"] == "mean_10" and s["mean"] is not None else \
                    f"top-2 {s['top2'] * 100:.1f} % (7-point)" if s["top2"] is not None else ""
                row |= {"text": f"Customer study — {s['item']} ({s['vehicle_model_id']} {s['market_code']}): {val}"}
        elif typ == "insight" and xrun:
            s = conn.execute("SELECT title, statement, payload_json FROM insight WHERE run_id = ? AND cluster_key = ?", (xrun["id"], nid)).fetchone()
            if s:
                row |= {"kind": "comments", "text": f"{s['title']} — {s['statement']} ({_loads(s['payload_json'], {}).get('comments')} comments)"}
        out.append(row)
    return out


@router.get("/requirement/{key:path}")
def requirement(key: str, cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        if not runs["define"]:
            raise not_found("No definition run at this checkpoint")
        r = conn.execute("SELECT * FROM def_requirement WHERE run_id = ? AND key = ?", (runs["define"]["id"], key)).fetchone()
        if r is None:
            raise not_found(f"No requirement {key!r} at {cp}")
        srun = runs["specify"]["id"] if runs["specify"] else None
        spec = conn.execute("SELECT * FROM def_spec WHERE run_id = ? AND req_key = ?", (srun, key)).fetchone() if srun else None
        areas = _area_titles(conn, cp)
        out = _requirement(r, spec, areas.get(r["area_key"]), _states(conn, runs["define"]["id"], "rq:").get(key),
                           _states(conn, srun, "spec:").get(key), _choices(conn))
        fact_ids = [int(f.split(":")[1]) for f in _loads(spec["fact_ids_json"], [])] if spec else []
        B.ensure(conn)
        facts = B._fact_rows(conn, f"f.id IN ({','.join('?' * len(fact_ids))})", fact_ids, None) if fact_ids else []
        history = []
        for c in CHECKPOINTS:
            if c.position > BY_ID[cp].position:
                continue
            d, s = latest_run(conn, c.id, "define"), latest_run(conn, c.id, "specify")
            h = conn.execute("SELECT version, title, statement, change_note FROM def_requirement WHERE run_id = ? AND key = ?",
                             (d["id"], key)).fetchone() if d else None
            hs = conn.execute("SELECT version, ladder_json, change_note FROM def_spec WHERE run_id = ? AND req_key = ?",
                              (s["id"], key)).fetchone() if s else None
            if h:
                rec = {}
                for rung in _loads(hs["ladder_json"], []) if hs else []:
                    lv = rung.get(rung["recommended"]) or {}
                    rec[f"{rung['line']}:{rung['market']}"] = {"level": rung["recommended"], "value": lv.get("value"), "text": lv.get("text")}
                history.append({"checkpoint": c.id, "label": c.label, "version": h["version"], "title": h["title"],
                                "statement": h["statement"], "change_note": h["change_note"], "spec_version": hs["version"] if hs else None,
                                "spec_change_note": hs["change_note"] if hs else None, "recommended": rec})
        decisions = [dict(x) for x in conn.execute("SELECT * FROM def_choice WHERE req_key = ? ORDER BY id", (key,))]
        return {**out, "evidence": _evidence(conn, _loads(r["evidence_ids_json"], []), r["area_key"], cp), "facts": facts,
                "area": areas.get(r["area_key"]), "history": history, "choices": decisions}


class ChoiceBody(BaseModel):
    key: str
    line: str
    market: str
    level: Literal["baseline", "threshold", "target", "stretch"]
    rationale: str
    actor: str | None = None
    cp: str | None = None


class LinkReviewBody(BaseModel):
    a: str
    b: str
    relation: Literal["conflicts", "competes_for", "enables", "synergy"]
    verdict: Literal["confirmed", "removed", "added"]
    via: str | None = None
    strength: int | None = Field(default=None, ge=1, le=3)
    rationale: str
    actor: str | None = None
    cp: str | None = None


def _rescore(cp: str | None, trigger: str) -> str:
    """Queue the automatic prioritize re-score (page 4) after a PM action that changes its inputs (`api/rescore.py`)."""
    from api import rescore

    return rescore.queue(cp if cp in BY_ID else None, trigger)


@router.post("/choice")
def choose(body: ChoiceBody, header_actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    actor = (body.actor or "").strip() or header_actor
    with db() as conn:
        ensure(conn)
        if not conn.execute("SELECT 1 FROM def_requirement WHERE key = ? LIMIT 1", (body.key,)).fetchone():
            raise not_found(f"No requirement {body.key!r}")
        before = conn.execute("SELECT level, rationale, actor FROM def_choice WHERE req_key = ? AND line = ? AND market = ? ORDER BY id DESC LIMIT 1",
                              (body.key, body.line, body.market)).fetchone()
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute("INSERT INTO def_choice (req_key, line, market, level, rationale, actor, checkpoint_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (body.key, body.line, body.market, body.level, why, actor, body.cp))
            audit(conn, actor_type="human", actor_id=actor, action="choose_level", entity_type="def_requirement", entity_id=body.key,
                  field=f"ladder:{body.line}:{body.market}", old=dict(before) if before else None,
                  new={"level": body.level, "checkpoint": body.cp}, rationale=why)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        out = {"ok": True, "id": cur.lastrowid, "choice": {"key": body.key, "line": body.line, "market": body.market, "level": body.level,
                                                           "rationale": why, "actor": actor}, "before": dict(before) if before else None}
    out["rescore"] = _rescore(body.cp, "pm_rung")   # the rung changes effort / confidence: re-score from its checkpoint on
    return out


@router.post("/link-review")
def link_review(body: LinkReviewBody, header_actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    actor = (body.actor or "").strip() or header_actor
    if body.via is not None and body.via not in RESOURCES:
        raise conflict(f"Unknown resource {body.via!r}")
    a, b = sorted((body.a, body.b))
    with db() as conn:
        ensure(conn)
        for k in (a, b):
            if not conn.execute("SELECT 1 FROM def_requirement WHERE key = ? LIMIT 1", (k,)).fetchone():
                raise not_found(f"No requirement {k!r}")
        before = conn.execute("SELECT verdict, via, strength, rationale, actor FROM def_link_review WHERE a_key = ? AND b_key = ? AND relation = ? "
                              "ORDER BY id DESC LIMIT 1", (a, b, body.relation)).fetchone()
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute("""INSERT INTO def_link_review (a_key, b_key, relation, verdict, via, strength, rationale, actor, checkpoint_id)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (a, b, body.relation, body.verdict, body.via, body.strength, why, actor, body.cp))
            audit(conn, actor_type="human", actor_id=actor, action=f"link_{body.verdict}", entity_type="def_link",
                  entity_id=f"{a}|{b}|{body.relation}", old=dict(before) if before else None,
                  new={"verdict": body.verdict, "via": body.via, "strength": body.strength, "checkpoint": body.cp}, rationale=why)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        out = {"ok": True, "id": cur.lastrowid, "review": {"a": a, "b": b, "relation": body.relation, "verdict": body.verdict,
                                                           "via": body.via, "strength": body.strength, "rationale": why, "actor": actor},
               "before": dict(before) if before else None}
    out["rescore"] = _rescore(None, "link_review")   # link reviews apply at every checkpoint
    return out
