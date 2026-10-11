"""Structure & context (D-043): what the AI made of the raw evidence at a checkpoint.

GET /api/structure?cp=            clusters (positioned in the comment galaxy), themes, evidence edges, requirement areas,
                                  comment → cluster map for the morph, per-stage funnel and track states
GET /api/structure/cluster/{key}?cp=   members (signals with quotes), insight, theme
GET /api/structure/theme/{key}?cp=     insights, evidence with sources, the area it belongs to
GET /api/structure/signals/{source_id} what the classifier extracted from one source item
"""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, Query

from api.deps import db, not_found
from bmw_req.checkpoints import BY_ID, latest_run

router = APIRouter(prefix="/api/structure", tags=["structure"])
STAGES = ["classify", "cluster", "contextualize", "areas"]


def _runs(conn, cp: str) -> dict:
    if cp not in BY_ID:
        raise not_found(f"No checkpoint {cp!r}")
    return {s: latest_run(conn, cp, s) for s in STAGES}


def _states(conn, run_id: int | None, prefix: str) -> dict[str, dict]:
    if not run_id:
        return {}
    return {r["entity_key"][len(prefix):]: {"state": r["state"], "weight": r["weight"], "prev": r["prev_weight"],
                                            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None}
            for r in db_rows(conn, "SELECT * FROM track WHERE run_id = ? AND entity_key LIKE ?", (run_id, prefix + "%"))}


def db_rows(conn, q, args=()):
    return conn.execute(q, args).fetchall()


@router.get("")
def structure(cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        if not runs["cluster"]:
            return {"checkpoint": cp, "ready": False, "stages": {s: bool(r) for s, r in runs.items()}}
        crun = runs["cluster"]["id"]
        xrun = runs["contextualize"]["id"] if runs["contextualize"] else None
        arun = runs["areas"]["id"] if runs["areas"] else None

        # comment → cluster (the strongest signal's cluster) and cluster centroids in the galaxy layout
        pos = {r[0]: (r[1], r[2] * 0.72, r[3]) for r in db_rows(conn, "SELECT source_item_id, x, y, z FROM source_layout")}
        best: dict[int, tuple[int, str]] = {}
        sums = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
        for r in db_rows(conn, """SELECT m.cluster_key, g.source_item_id, COALESCE(g.intensity, 1) w FROM cluster_member m
                                  JOIN signal g ON g.id = m.signal_id WHERE m.run_id = ?""", (crun,)):
            sid = r["source_item_id"]
            if sid not in best or r["w"] > best[sid][0]:
                best[sid] = (r["w"], r["cluster_key"])
        for sid, (_, k) in best.items():
            if sid in pos:
                s = sums[k]
                s[0] += pos[sid][0]; s[1] += pos[sid][1]; s[2] += pos[sid][2]; s[3] += 1
        cstate = _states(conn, crun, "")
        insights = {r["cluster_key"]: r for r in db_rows(conn, "SELECT * FROM insight WHERE run_id = ?", (xrun,))} if xrun else {}
        member_theme = {r[0]: r[1] for r in db_rows(conn, "SELECT cluster_key, theme_key FROM theme_member WHERE run_id = ?", (xrun,))} if xrun else {}
        clusters = []
        for r in db_rows(conn, "SELECT key, polarity, category FROM cluster WHERE key IN (SELECT DISTINCT cluster_key FROM cluster_member WHERE run_id = ?)", (crun,)):
            k = r["key"]
            st = cstate.get(k, {})
            p = st.get("payload") or {}
            s = sums.get(k)
            if not s or not s[3]:
                continue
            i = insights.get(k)
            clusters.append({"key": k, "polarity": r["polarity"], "category": r["category"], "state": st.get("state"),
                             "comments": p.get("comments", 0), "signals": p.get("signals", 0), "tail": p.get("tail", True),
                             "aspects": p.get("aspects"), "by_line_market": p.get("by_line_market"),
                             "x": s[0] / s[3], "y": s[1] / s[3], "z": s[2] / s[3], "theme": member_theme.get(k),
                             "insight": {"title": i["title"], "statement": i["statement"], "need_type": i["need_type"],
                                         "quality_issue": bool(i["quality_issue"])} if i else None})
        # lost clusters (cp2): keep them visible as lost marks at their cp1 position
        for k, st in cstate.items():
            if st["state"] == "lost" and not any(c["key"] == k for c in clusters):
                clusters.append({"key": k, "state": "lost", "comments": 0, "signals": 0, "tail": True, "x": 0, "y": 0, "z": 0,
                                 "polarity": None, "category": None, "theme": None, "insight": None, "aspects": None, "by_line_market": None})

        themes, edges = [], []
        if xrun:
            tstate = _states(conn, xrun, "theme:")
            by_theme = defaultdict(list)
            for c in clusters:
                if c["theme"] and c["comments"]:
                    by_theme[c["theme"]].append(c)
            for r in db_rows(conn, "SELECT key, title, statement, category FROM theme WHERE key IN (SELECT DISTINCT theme_key FROM theme_member WHERE run_id = ?)", (xrun,)):
                cs = by_theme.get(r["key"], [])
                w = sum(c["comments"] for c in cs) or 1
                themes.append({"key": r["key"], "title": r["title"], "statement": r["statement"], "category": r["category"],
                               "state": (tstate.get(r["key"]) or {}).get("state"), "comments": sum(c["comments"] for c in cs),
                               "clusters": [c["key"] for c in cs],
                               "x": sum(c["x"] * c["comments"] for c in cs) / w, "y": sum(c["y"] * c["comments"] for c in cs) / w,
                               "z": sum(c["z"] * c["comments"] for c in cs) / w})
            estate = _states(conn, xrun, "edge:")
            for e in db_rows(conn, "SELECT src_type, src_id, dst_type, dst_id, relation, rationale FROM evidence_edge WHERE run_id = ? "
                                   "AND relation NOT IN ('belongs_to')", (xrun,)):
                key = f"{e['src_type']}:{e['src_id']}>{e['relation']}>{e['dst_id']}"
                edges.append({"src_type": e["src_type"], "src_id": e["src_id"], "dst_type": e["dst_type"], "dst_id": e["dst_id"],
                              "relation": e["relation"], "why": e["rationale"], "state": (estate.get(key) or {}).get("state")})
        areas = []
        if arun:
            astate = _states(conn, arun, "area:")
            for r in db_rows(conn, "SELECT * FROM req_area WHERE run_id = ?", (arun,)):
                areas.append({"id": r["id"], "key": r["key"], "title": r["title"], "need": r["need"], "kind": r["kind"],
                              "themes": json.loads(r["theme_keys_json"]), "why_now": r["why_now"],
                              "open_questions": json.loads(r["open_questions_json"] or "[]"),
                              "metrics": json.loads(r["metrics_json"] or "{}"), "change_note": r["change_note"],
                              "state": (astate.get(r["key"]) or {}).get("state")})
        # comment → cluster index (columnar, aligned to /api/scan/points ids)
        ckeys = [c["key"] for c in clusters]
        cidx = {k: i for i, k in enumerate(ckeys)}
        member = {"ids": list(best), "cluster": [cidx.get(best[s][1], -1) for s in best]}
        funnel = {s: json.loads(r["stats_json"] or "{}") if r else None for s, r in runs.items()}
        return {"checkpoint": cp, "ready": True, "clusters": clusters, "themes": themes, "edges": edges,
                "areas": areas, "member": member, "funnel": funnel,
                "runs": {s: ({"id": r["id"], "parent": r["parent_run_id"]} if r else None) for s, r in runs.items()}}


@router.get("/cluster/{key:path}")
def cluster_detail(key: str, cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        if not runs["cluster"]:
            raise not_found("Cluster stage has not run at this checkpoint")
        rows = db_rows(conn, """SELECT g.id, g.source_item_id, g.aspect, g.nature, g.intensity, g.impact, g.need_statement, g.quote,
                                       s.external_id, s.vehicle_model_id car, s.market_code market, s.checkpoint
                                FROM cluster_member m JOIN signal g ON g.id = m.signal_id JOIN source_item s ON s.id = g.source_item_id
                                WHERE m.run_id = ? AND m.cluster_key = ? ORDER BY g.intensity DESC, g.id""", (runs["cluster"]["id"], key))
        if not rows:
            raise not_found(f"No cluster {key} at {cp}")
        ins = None
        if runs["contextualize"]:
            i = conn.execute("SELECT * FROM insight WHERE run_id = ? AND cluster_key = ?", (runs["contextualize"]["id"], key)).fetchone()
            ins = dict(i) if i else None
            if ins:
                ins.pop("embedding", None)
        return {"key": key, "insight": ins, "signals": [dict(r) for r in rows[:60]], "n": len(rows)}


@router.get("/theme/{key:path}")
def theme_detail(key: str, cp: str = Query("cp2")) -> dict:
    with db() as conn:
        runs = _runs(conn, cp)
        if not runs["contextualize"]:
            raise not_found("Contextualize stage has not run at this checkpoint")
        x = runs["contextualize"]["id"]
        t = conn.execute("SELECT key, title, statement, category FROM theme WHERE key = ?", (key,)).fetchone()
        if t is None:
            raise not_found(f"No theme {key}")
        ins = [dict(r) for r in db_rows(conn, """SELECT i.cluster_key, i.title, i.statement, i.need_type, i.quality_issue, i.payload_json
                                                 FROM insight i JOIN theme_member m ON m.cluster_key = i.cluster_key AND m.run_id = i.run_id
                                                 WHERE i.run_id = ? AND m.theme_key = ?""", (x, key))]
        ev = []
        for e in db_rows(conn, "SELECT src_type, src_id, relation, rationale FROM evidence_edge WHERE run_id = ? AND dst_id = ? "
                               "AND src_type IN ('research','study','option')", (x, key)):
            ev.append({"type": e["src_type"], "id": e["src_id"], "relation": e["relation"], "why": e["rationale"],
                       **_describe(conn, e["src_type"], int(e["src_id"]))})
        area = None
        if runs["areas"]:
            for r in db_rows(conn, "SELECT key, title, theme_keys_json FROM req_area WHERE run_id = ?", (runs["areas"]["id"],)):
                if key in json.loads(r["theme_keys_json"]):
                    area = {"key": r["key"], "title": r["title"]}
        return {"theme": dict(t), "insights": ins, "evidence": ev, "area": area}


def _describe(conn, typ: str, nid: int) -> dict:
    if typ == "research":
        r = conn.execute("SELECT text, url, published_at, trust_tier FROM source_item WHERE id = ?", (nid,)).fetchone()
        return {"text": r["text"], "url": r["url"], "published": r["published_at"], "tier": r["trust_tier"]} if r else {}
    if typ == "study":
        r = conn.execute("SELECT item, vehicle_model_id car, market_code market, z_within_column z FROM study_metric WHERE id = ?", (nid,)).fetchone()
        return {"text": f"{r['item']}", "car": r["car"], "market": r["market"], "z": r["z"]} if r else {}
    r = conn.execute("SELECT vehicle_model_id car, meta_json FROM source_item WHERE id = ?", (nid,)).fetchone()
    m = json.loads(r["meta_json"] or "{}") if r else {}
    return {"text": m.get("name_en"), "car": r["car"] if r else None, "availability": m.get("availability")}


@router.get("/signals/{source_id}")
def signals_of(source_id: int) -> dict:
    with db() as conn:
        rows = db_rows(conn, """SELECT id, aspect, category, nature, want_kind, intensity, impact, occupant, need_statement, quote,
                                       quote_verified, explicit, future_cue, benchmark, benchmark_name, source_kind
                                FROM signal WHERE source_item_id = ? AND extractor_version = 'extract-v4' ORDER BY id""", (source_id,))
        ext = conn.execute("SELECT in_scope, out_of_scope_reason FROM verbatim_extraction WHERE source_item_id = ? "
                           "AND extractor_version = 'extract-v4'", (source_id,)).fetchone()
        return {"source_id": source_id, "classified": ext is not None or bool(rows),
                "in_scope": bool(ext["in_scope"]) if ext else None, "reason": ext["out_of_scope_reason"] if ext else None,
                "signals": [dict(r) for r in rows]}


@router.get("/activity")
def activity(cp: str = Query("cp2"), since: int = Query(0, description="return events with id > since")) -> dict:
    """What the agent is doing right now: stage status + progress, the latest AI steps, and the comments classified in
    the last few seconds (the 3D view lights them up)."""
    with db() as conn:
        if cp not in BY_ID:
            raise not_found(f"No checkpoint {cp!r}")
        stages = []
        for s in STAGES:
            r = conn.execute("SELECT id, status, started_at, finished_at, stats_json FROM checkpoint_run WHERE checkpoint_id = ? "
                             "AND stage = ? AND status != 'superseded' ORDER BY id DESC LIMIT 1", (cp, s)).fetchone()
            st = {"stage": s, "status": r["status"] if r else "pending", "run_id": r["id"] if r else None,
                  "started_at": r["started_at"] if r else None, "finished_at": r["finished_at"] if r else None}
            if s == "classify":
                total = conn.execute("SELECT COUNT(*) FROM source_item WHERE kind = 'feedback' AND checkpoint = ?", (cp,)).fetchone()[0]
                done = conn.execute("""SELECT COUNT(*) FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
                                       WHERE e.extractor_version = 'extract-v4' AND s.checkpoint = ?""", (cp,)).fetchone()[0]
                st["progress"] = {"done": done, "total": total, "unit": "comments"}
            stages.append(st)
        events = [dict(r) for r in conn.execute(
            """SELECT id, ts, actor_id, action, new_value, model, run_id, entity_id FROM audit_event
               WHERE actor_id LIKE 'structure.%' AND id > ? ORDER BY id DESC LIMIT 120""", (since,))]
        run_cp = {r[0]: r[1] for r in conn.execute("SELECT id, checkpoint_id FROM checkpoint_run")}
        usage_cp = {str(r[0]): ("cp2" if r[1].endswith("cp2") else "cp1" if r[1].endswith("cp1") else None)
                    for r in conn.execute("SELECT id, job FROM llm_usage WHERE job LIKE 'classify:%'")}
        keep = []
        for e in events:   # only this checkpoint's steps (classify for both checkpoints can run in parallel)
            ecp = run_cp.get(e.pop("run_id")) or usage_cp.get(e.pop("entity_id"))
            if ecp not in (cp, None):
                continue
            e["stage"] = e.pop("actor_id").split(".", 1)[1]
            e["payload"] = json.loads(e.pop("new_value") or "{}")
            keep.append(e)
        events = keep
        # comments classified in the last ~6 s (via the audit row's llm_usage id)
        recent = [r[0] for r in conn.execute(
            """SELECT e.source_item_id FROM verbatim_extraction e WHERE e.extractor_version = 'extract-v4' AND e.llm_usage_id IN (
                 SELECT CAST(entity_id AS INTEGER) FROM audit_event WHERE actor_id = 'structure.classify'
                 AND action = 'classify_comments' AND ts >= strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-6 seconds'))""")]
        running = any(s["status"] == "running" for s in stages)
        return {"checkpoint": cp, "running": running, "stages": stages, "events": events, "recent": recent}
