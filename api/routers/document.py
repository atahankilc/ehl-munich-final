"""Document (page 5): the deliverable — the final, traceable requirement list per car line × market at a checkpoint
(challenge brief, BMW process step 5 "Documentation / tracking"). Read-only over the definition (D-048) and
prioritization (D-050) layers; every export is an access event in the audit trail (rule 6).

GET /api/document?cp=&line=&market=                     header + every target of the latest prioritize run at cp
GET /api/document/changes?line=&market=                 JAN → JUL diff for that line × market
GET /api/document/export?cp=&line=&market=&format=md|csv   downloadable deliverable (logged as `export`)

Checkpoint visibility: everything is read "as of" cp — PM choices, decisions, link reviews and proposals made at a
later checkpoint never show (cp1 shows nothing from cp2).
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from api.deps import db, get_actor, not_found
from api.routers import definition as D
from api.routers import prioritize as PR
from bmw_req import service
from bmw_req.checkpoints import BY_ID, CHECKPOINTS, latest_run, visible_ids
from bmw_req.prioritize import score as P

router = APIRouter(prefix="/api/document", tags=["document"])
BAND_ORDER = {"Must": 0, "Should": 1, "Could": 2}
FLAG_TEXT = {
    "volume_conflict": "BMW sales file conflicts with public figures (Q-015) — market weight is stylized and relative only",
    "competitive_none": "no cited competitor number — competitive gap not scored",
    "competitive_fallback": "competitive gap from a source-count fallback, not a cited BMW-vs-rival number",
    "borrowed_voice": "too few own-market comments — customer voice borrowed from other markets at half weight",
    "basic_aligned": "Kano basic: expected by customers, its absence hurts more than its presence helps",
    "bundle_band": "band lifted to match a linked bundle member",
    "brand_warn": "brand-fit check raised a warning",
}


def _loads(s, default=None):
    return json.loads(s) if s else default


def _in(vis) -> str:
    return ",".join("?" * len(vis))


def _numbers(conn) -> dict[str, int]:
    """Stable requirement numbers: order of first appearance across all definition runs (cp1 keys first)."""
    rows = conn.execute("SELECT key, MIN(run_id) first FROM def_requirement GROUP BY key ORDER BY first, key").fetchall()
    return {r["key"]: i + 1 for i, r in enumerate(rows)}


def human_id(line: str, market: str, n: int) -> str:
    return f"REQ-{(line or '?').split()[0]}{market}-{n:03d}"


def _choices_at(conn, cp: str) -> dict[tuple, dict]:
    vis = visible_ids(cp)
    out = {}
    for r in conn.execute(f"SELECT * FROM def_choice WHERE checkpoint_id IS NULL OR checkpoint_id IN ({_in(vis)}) ORDER BY id", vis):
        out[(r["req_key"], r["line"], r["market"])] = {"level": r["level"], "rationale": r["rationale"], "actor": r["actor"],
                                                       "at": r["created_at"], "checkpoint": r["checkpoint_id"]}
    return out


def _links_at(conn, cp: str, couple_run: int | None, keys: set[str], titles: dict[str, str]) -> dict[str, list[dict]]:
    """Links per requirement with only the PM reviews visible at cp (latest wins); PM-removed links are kept, marked."""
    vis = visible_ids(cp)
    reviews = {}
    for r in conn.execute(f"SELECT * FROM def_link_review WHERE checkpoint_id IS NULL OR checkpoint_id IN ({_in(vis)}) ORDER BY id", vis):
        reviews[(r["a_key"], r["b_key"], r["relation"])] = {"verdict": r["verdict"], "actor": r["actor"], "rationale": r["rationale"],
                                                            "via": r["via"], "strength": r["strength"]}
    raw, seen = [], set()
    for l in (conn.execute("SELECT * FROM def_link WHERE run_id = ? ORDER BY id", (couple_run,)) if couple_run else []):
        k = (l["a_key"], l["b_key"], l["relation"])
        seen.add(k)
        raw.append({"a": k[0], "b": k[1], "relation": k[2], "via": l["via"], "strength": l["strength"], "rationale": l["rationale"],
                    "source": "ai", "review": reviews.get(k)})
    for k, rv in reviews.items():
        if k not in seen and rv["verdict"] == "added":
            raw.append({"a": k[0], "b": k[1], "relation": k[2], "via": rv["via"], "strength": rv["strength"] or 2,
                        "rationale": rv["rationale"], "source": "pm", "review": rv})
    out: dict[str, list[dict]] = defaultdict(list)
    for l in raw:
        for me, other in ((l["a"], l["b"]), (l["b"], l["a"])):
            if me in keys:
                out[me].append({"key": other, "title": titles.get(other), "relation": l["relation"], "via": l["via"],
                                "strength": l["strength"], "rationale": l["rationale"], "source": l["source"],
                                "status": (l["review"] or {}).get("verdict") or "proposed"})
    return out


def _quotes(conn, cluster_run: int | None, cluster_key: str, line: str, market: str, n: int = 2) -> list[dict]:
    if not cluster_run:
        return []
    rows = conn.execute("""SELECT g.quote, s.id sid, s.external_id, s.market_code, v.line FROM cluster_member m
                           JOIN signal g ON g.id = m.signal_id JOIN source_item s ON s.id = g.source_item_id
                           LEFT JOIN vehicle_model v ON v.id = s.vehicle_model_id
                           WHERE m.run_id = ? AND m.cluster_key = ? AND g.quote IS NOT NULL AND g.quote != ''
                           ORDER BY (v.line = ?) + (s.market_code = ?) DESC, COALESCE(g.intensity, 0) DESC, g.id LIMIT ?""",
                        (cluster_run, cluster_key, line, market, n)).fetchall()
    return [{"quote": r["quote"], "source_id": r["sid"], "external_id": r["external_id"], "market": r["market_code"], "line": r["line"]}
            for r in rows]


def _proposals_at(conn, cp: str, line: str, market: str) -> dict[str, list[dict]]:
    vis = visible_ids(cp)
    out: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(f"""SELECT p.*, r.checkpoint_id cp FROM prio_proposal p JOIN checkpoint_run r ON r.id = p.run_id
                              WHERE r.checkpoint_id IN ({_in(vis)}) AND p.line = ? AND p.market = ? ORDER BY p.id""", (*vis, line, market)):
        out[r["req_key"]].append({**PR._proposal(r), "checkpoint": r["cp"]})
    return out


def _decisions_at(conn, cp: str, line: str, market: str) -> dict[str, list[dict]]:
    vis = visible_ids(cp)
    out: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(f"""SELECT * FROM prio_decision WHERE line = ? AND market = ? AND (checkpoint_id IS NULL OR checkpoint_id IN ({_in(vis)}))
                              ORDER BY id""", (line, market, *vis)):
        out[r["req_key"]].append({"priority": r["priority"], "rationale": r["rationale"], "actor": r["actor"], "at": r["created_at"],
                                  "checkpoint": r["checkpoint_id"]})
    return out


def _history(conn, cp: str, line: str, market: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for c in CHECKPOINTS:
        if c.position > BY_ID[cp].position:
            continue
        r = latest_run(conn, c.id, "prioritize")
        if not r:
            continue
        dec = P.decisions_at(conn, c.id)
        for h in conn.execute("SELECT req_key, score, band, rank FROM prio_score WHERE run_id = ? AND line = ? AND market = ?", (r["id"], line, market)):
            d = dec.get((h["req_key"], line, market))
            out[h["req_key"]].append({"checkpoint": c.id, "label": c.label, "score": h["score"], "band": h["band"], "rank": h["rank"],
                                      "confirmed": d["priority"] if d else None})
    return out


def _rung_value(level: dict | None) -> dict | None:
    if not level:
        return None
    return {"value": level.get("value"), "text": level.get("text"), "basis": level.get("basis"), "note": level.get("note"),
            "source_ids": level.get("source_ids") or []}


def build(conn, cp: str, line: str, market: str) -> dict:
    """The deliverable for one car line × market at cp (also used by the export and the JAN → JUL diff)."""
    if cp not in BY_ID:
        raise not_found(f"No checkpoint {cp!r}")
    runs = PR._runs(conn, cp)
    run = runs["prioritize"]
    c = BY_ID[cp]
    wid, _, bands = P.stored_config(conn)
    pairs = []
    if run:
        pairs = [(r["line"], r["market"]) for r in conn.execute(
            "SELECT DISTINCT line, market FROM prio_score WHERE run_id = ? ORDER BY line, market", (run["id"],))]
    stats = _loads(run["stats_json"], {}) if run else {}
    header = {"checkpoint": cp, "label": c.label, "cutoff": c.cutoff.isoformat(), "line": line, "market": market,
              "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "run": {"id": run["id"], "finished_at": run["finished_at"]} if run else None,
              "weights_version": stats.get("weights_version", wid), "scheme": stats.get("scheme", P.SCHEME), "band_thresholds": bands,
              "lines": sorted({l for l, _ in pairs}), "markets_by_line": {l: [m for ll, m in pairs if ll == l] for l in sorted({l for l, _ in pairs})}}
    if not run:
        return {"ready": False, "header": {**header, "by_band": {}, "ai_by_band": {}, "confirmed": 0, "open_proposals": 0, "count": 0}, "items": []}
    up = stats.get("upstream") or {}
    drun = up.get("define")
    srun = up.get("specify")
    reqs = {r["key"]: dict(r) for r in conn.execute("SELECT * FROM def_requirement WHERE run_id = ?", (drun,))} if drun else {}
    specs = {r["req_key"]: dict(r) for r in conn.execute("SELECT * FROM def_spec WHERE run_id = ?", (srun,))} if srun else {}
    areas = D._area_titles(conn, cp)
    choices = _choices_at(conn, cp)
    decided = P.decisions_at(conn, cp)
    prev, states = PR._prev_band(conn, run), PR._states(conn, run["id"])
    nums = _numbers(conn)
    titles = {k: r["title"] for k, r in reqs.items()}
    rows = conn.execute("SELECT * FROM prio_score WHERE run_id = ? AND line = ? AND market = ?", (run["id"], line, market)).fetchall()
    links = _links_at(conn, cp, up.get("couple"), {r["req_key"] for r in rows}, titles)
    proposals, decisions, history = _proposals_at(conn, cp, line, market), _decisions_at(conn, cp, line, market), _history(conn, cp, line, market)
    crun = latest_run(conn, cp, "cluster")
    items = []
    for row in rows:
        key = row["req_key"]
        req, spec = reqs.get(key) or {}, specs.get(key)
        t = PR._target(row, req, decided.get((key, line, market)), states.get((key, line, market)), prev.get((key, line, market)))
        ladder_row = next((x for x in (_loads(spec["ladder_json"], []) if spec else []) if x.get("line") == line and x.get("market") == market), None)
        ch = choices.get((key, line, market))
        level = (ch or {}).get("level") or (ladder_row or {}).get("recommended")
        rung = {"level": level, "by": "pm" if ch else "ai", "recommended": (ladder_row or {}).get("recommended"),
                **(_rung_value((ladder_row or {}).get(level)) or {}), "choice": ch}
        ev = D._evidence(conn, _loads(req.get("evidence_ids_json"), []), req.get("area_key") or "", cp) if req else []
        for e in ev:
            if e["kind"] == "comments" and e["id"].startswith("insight:"):
                e["quotes"] = _quotes(conn, crun["id"] if crun else None, e["id"].split(":", 1)[1], line, market)
        props = proposals.get(key, [])
        open_p = next((p for p in reversed(props) if p["status"] == "open"), None)
        effective = t["confirmed"]["priority"] if t["confirmed"] else t["band"]
        status = "confirmed" if t["confirmed"] else "ai_proposal"
        if open_p:
            status = "open_proposal_against_pm" if t["confirmed"] else "open_proposal"
        gaps = list(dict.fromkeys((_loads(spec["gaps_json"], []) if spec else []) + (t["gaps"] or [])))
        uncertainties = [FLAG_TEXT.get(f, f.replace("_", " ")) for f in t["flags"]]
        uncertainties += [f"{g}: {v.get('rationale') or v.get('result')}" for g, v in (t["gates"] or {}).items()
                          if isinstance(v, dict) and v.get("result") in ("warn", "fail")]
        metric = _loads(spec["metric_json"]) if spec else None
        items.append({
            "key": key, "id": human_id(line, market, nums.get(key, 0)), "number": nums.get(key, 0), "version": req.get("version"),
            "title": req.get("title"), "statement": req.get("statement"), "domain": req.get("domain"),
            "area": areas.get(req.get("area_key")) or ({"key": req.get("area_key")} if req.get("area_key") else None),
            "horizon": req.get("horizon"), "horizon_year": req.get("horizon_year"), "kano": req.get("kano"),
            "decision_type": req.get("decision_type"), "today_status": req.get("today_status"), "req_status": req.get("status"),
            "metric": metric, "acceptance": _loads(spec["acceptance_json"], []) if spec else [],
            "rung": rung, "ladder": ladder_row,
            "priority": {"band": effective, "ai_band": t["band"], "ai_score": t["score"], "base": t["base"], "rank": t["rank"],
                         "confirmed": t["confirmed"], "own_band": t["own_band"]},
            "status": status, "open_proposal": open_p, "rationale": t["rationale"],
            "factors": [{k: f.get(k) for k in ("key", "label", "dimension", "weight", "points", "value", "available", "explanation")} for f in t["factors"]],
            "modifiers": t["modifiers"], "effort": t["effort"],
            "evidence": {"level": t["confidence"]["level"], "confidence": t["confidence"], "comments": t["confidence"]["comments"],
                         "count": len(ev), "items": ev, "trend_ids": _loads(req.get("trend_ids_json"), [])},
            "assumptions": _loads(req.get("assumptions_json"), []) + (_loads(spec["assumptions_json"], []) if spec else []),
            "gaps": gaps, "uncertainties": uncertainties, "flags": t["flags"],
            "links": links.get(key, []), "gates": t["gates"], "track": t["state"], "prev": t["prev"],
            "history": history.get(key, []), "proposals": props, "decisions": decisions.get(key, []),
        })
    items.sort(key=lambda i: (BAND_ORDER.get(i["priority"]["band"], 9), -(i["priority"]["ai_score"] or 0), i["number"]))
    by_band, ai_by_band = defaultdict(int), defaultdict(int)
    for i in items:
        by_band[i["priority"]["band"]] += 1
        ai_by_band[i["priority"]["ai_band"]] += 1
    header |= {"by_band": dict(by_band), "ai_by_band": dict(ai_by_band), "count": len(items),
               "confirmed": sum(1 for i in items if i["priority"]["confirmed"]),
               "open_proposals": sum(1 for i in items if i["open_proposal"])}
    return {"ready": True, "header": header, "items": items}


@router.get("")
def document(cp: str = Query("cp2"), line: str = Query("5 Series"), market: str = Query("US")) -> dict:
    with db() as conn:
        return build(conn, cp, line, market)


def changes_between(conn, line: str, market: str, a: str = "cp1", b: str = "cp2") -> dict:
    da, dbb = build(conn, a, line, market), build(conn, b, line, market)
    ia, ib = {i["key"]: i for i in da["items"]}, {i["key"]: i for i in dbb["items"]}

    def brief(i):
        return {"key": i["key"], "id": i["id"], "title": i["title"], "domain": i["domain"], "band": i["priority"]["band"],
                "ai_band": i["priority"]["ai_band"], "score": i["priority"]["ai_score"]}

    moved = []
    for k in ia.keys() & ib.keys():
        x, y = ia[k]["priority"], ib[k]["priority"]
        xc, yc = (x["confirmed"] or {}).get("priority"), (y["confirmed"] or {}).get("priority")
        if x["ai_band"] != y["ai_band"] or xc != yc or abs((y["ai_score"] or 0) - (x["ai_score"] or 0)) >= 3:
            dir_ = BAND_ORDER.get(x["band"], 9) - BAND_ORDER.get(y["band"], 9)
            moved.append({**brief(ib[k]), "from": {"ai_band": x["ai_band"], "score": x["ai_score"], "confirmed": xc},
                          "to": {"ai_band": y["ai_band"], "score": y["ai_score"], "confirmed": yc},
                          "direction": "up" if dir_ > 0 else "down" if dir_ < 0 else "same",
                          "ai_band_changed": x["ai_band"] != y["ai_band"], "pm_band_changed": xc != yc})
    moved.sort(key=lambda m: (m["direction"] == "same", BAND_ORDER.get(m["band"], 9), -(m["score"] or 0)))
    decisions = [{**d, "key": k, "id": ib.get(k, ia.get(k, {})).get("id"), "title": ib.get(k, ia.get(k, {})).get("title")}
                 for k, ds in _decisions_at(conn, b, line, market).items() for d in ds if d["checkpoint"] == b]
    props = [{**p, "id_human": ib.get(k, ia.get(k, {})).get("id"), "title": ib.get(k, ia.get(k, {})).get("title")}
             for k, ps in _proposals_at(conn, b, line, market).items() for p in ps if p["checkpoint"] == b]
    return {"from": {"checkpoint": a, "label": BY_ID[a].label}, "to": {"checkpoint": b, "label": BY_ID[b].label},
            "line": line, "market": market,
            "new": [brief(ib[k]) for k in ib.keys() - ia.keys()], "removed": [brief(ia[k]) for k in ia.keys() - ib.keys()],
            "moved": moved, "band_up": sum(1 for m in moved if m["direction"] == "up"),
            "band_down": sum(1 for m in moved if m["direction"] == "down"),
            "decisions": decisions,
            "proposals": {"accepted": [p for p in props if p["status"] == "accepted"], "rejected": [p for p in props if p["status"] == "rejected"],
                          "open": [p for p in props if p["status"] == "open"], "superseded": [p for p in props if p["status"] == "superseded"]}}


@router.get("/changes")
def changes(line: str = Query("5 Series"), market: str = Query("US")) -> dict:
    with db() as conn:
        return changes_between(conn, line, market)


# ------------------------------------------------------------------------------------------------ export
STATUS_TEXT = {"confirmed": "PM-confirmed", "ai_proposal": "AI proposal (not yet confirmed)",
               "open_proposal": "AI proposal with an open band change", "open_proposal_against_pm": "PM-confirmed; open AI proposal against it"}


def _target_text(i: dict, unit: str | None = None) -> str:
    r = i["rung"]
    v = r.get("text") or (f"{r['value']} {unit or ''}".strip() if r.get("value") is not None else "open gap")
    return f"{v} ({r.get('level') or '–'}, {r.get('basis') or '–'}, {'PM choice' if r.get('by') == 'pm' else 'AI recommended'})"


def _src(e: dict) -> str:
    bits = [e["id"]]
    if e.get("tier"):
        bits.append(e["tier"])
    if e.get("published"):
        bits.append(str(e["published"]))
    return " · ".join(bits)


def markdown(doc: dict) -> str:
    h = doc["header"]
    out = [f"# Customer requirements — {h['line']} · {h['market']} · {h['label']}", "",
           f"Checkpoint {h['label']} (evidence known up to {h['cutoff']}) · generated {h['generated_at']} · "
           f"scoring {h['scheme']} weights v{h['weights_version']} · prioritize run {(h['run'] or {}).get('id', '–')}", "",
           f"**{h['count']} requirements** — Must {h['by_band'].get('Must', 0)} · Should {h['by_band'].get('Should', 0)} · "
           f"Could {h['by_band'].get('Could', 0)} · {h['confirmed']} confirmed by the PM · {h['open_proposals']} open AI proposals", "",
           "Bands shown are the PM's confirmed band where one exists, otherwise the AI's proposed band. Evidence and "
           "forward-looking assumptions are listed separately; every requirement links to its sources.", ""]
    for band in ("Must", "Should", "Could"):
        group = [i for i in doc["items"] if i["priority"]["band"] == band]
        if not group:
            continue
        out += [f"## {band} ({len(group)})", ""]
        for i in group:
            p, m = i["priority"], i["metric"] or {}
            conf = p["confirmed"]
            out += [f"### {i['id']} · {i['title']}", "",
                    f"- **Decision status:** {STATUS_TEXT.get(i['status'], i['status'])}"
                    + (f" — {conf['priority']} by {conf['actor']} ({conf['at'][:10]}): {conf['rationale']}" if conf else ""),
                    f"- **Priority:** {p['band']} · AI score {p['ai_score']:.1f} → AI band {p['ai_band']} · rank {p['rank']}",
                    f"- **Evidence level:** {i['evidence']['level'] or '–'} · {i['evidence']['comments'] or 0} customer comments · {i['evidence']['count']} linked sources",
                    f"- **Domain / area:** {i['domain'] or '–'} / {(i['area'] or {}).get('title') or '–'}"
                    f" · horizon {i['horizon'] or '–'}{(' ' + str(i['horizon_year'])) if i['horizon_year'] else ''} · Kano {i['kano'] or '–'}",
                    f"- **Key:** `{i['key']}` v{i['version']}", "", i["statement"] or "", ""]
            if m:
                out += [f"**Metric:** {m.get('name')} [{m.get('unit') or '–'}], {m.get('direction') or ''} is better  ",
                        f"**Target:** {_target_text(i, m.get('unit'))}  "]
                if m.get("conditions"):
                    out.append(f"**Conditions:** {m['conditions']}  ")
                out.append("")
            if i["ladder"]:
                out += ["| Rung | Value | Basis | Note |", "|---|---|---|---|"]
                for lv in ("baseline", "threshold", "target", "stretch"):
                    x = i["ladder"].get(lv)
                    if x:
                        tag = " (AI rec.)" if i["ladder"].get("recommended") == lv else ""
                        out.append(f"| {lv}{tag} | {x.get('text') or x.get('value') or '–'} | {x.get('basis') or '–'} | {(x.get('note') or '').replace('|', '/')} |")
                out.append("")
            if i["acceptance"]:
                out += ["**Acceptance criteria**", ""]
                out += [f"- {a.get('criterion')}: {a.get('pass')} — *{a.get('condition')}*" for a in i["acceptance"]]
                out.append("")
            out += ["**Prioritization rationale**", "", i["rationale"] or "–", ""]
            out += ["| Factor | Points | Why |", "|---|---|---|"]
            out += [f"| {f['label']} | {f['points']:.1f} | {(f['explanation'] or '').replace('|', '/')} |" for f in i["factors"]]
            out += [f"| {mo['key']} (modifier) | {mo['points']:+.1f} | {mo.get('why') or ''} |" for mo in i["modifiers"]]
            out += ["", "**Evidence**", ""]
            for e in i["evidence"]["items"]:
                line = f"- [{e['kind']}] {e.get('text') or e['id']} — {_src(e)}"
                if e.get("url"):
                    line += f" — <{e['url']}>"
                out.append(line)
                for q in e.get("quotes") or []:
                    out.append(f"  - “{q['quote']}” (comment {q['external_id']}, {q['line'] or ''} {q['market'] or ''})")
            out += ["", "**Assumptions (forward-looking)**", ""] + ([f"- {a}" for a in i["assumptions"]] or ["- –"])
            out += ["", "**Gaps and uncertainties**", ""] + ([f"- {g}" for g in i["gaps"] + i["uncertainties"]] or ["- –"])
            if i["links"]:
                out += ["", "**Linked requirements**", ""]
                out += [f"- {l['relation']} {l['title'] or l['key']} via {l['via'] or '–'} (strength {l['strength']}, {l['status']})" for l in i["links"]]
            if i["gates"]:
                out += ["", "**Gates**", ""]
                out += [f"- {g}: {v.get('result') if isinstance(v, dict) else v}" + (f" — {v.get('rationale')}" if isinstance(v, dict) and v.get("rationale") else "")
                        for g, v in i["gates"].items()]
            if i["history"]:
                out += ["", "**History**", ""]
                out += [f"- {x['label']}: score {x['score']:.1f}, AI {x['band']}" + (f", PM {x['confirmed']}" if x["confirmed"] else "") for x in i["history"]]
            for pr in i["proposals"]:
                out.append(f"- Proposal {pr['old_band']} → {pr['proposed_band']} ({pr['cause']}): {pr['status']}"
                           + (f" by {pr['decided_by']} — {pr['decision_rationale']}" if pr.get("decided_by") else ""))
            out += ["", "---", ""]
    return "\n".join(out)


CSV_FIELDS = ["id", "key", "title", "domain", "area", "statement", "band", "ai_band", "ai_score", "rank", "decision_status",
              "pm_band", "pm_actor", "pm_date", "pm_rationale", "metric", "unit", "direction", "target", "target_level", "target_basis",
              "target_by", "acceptance_criteria", "evidence_level", "comments", "n_sources", "sources", "rationale", "factors",
              "assumptions", "gaps_uncertainties", "links", "gates", "horizon", "kano", "history", "open_proposal"]


def csv_rows(doc: dict) -> list[dict]:
    rows = []
    for i in doc["items"]:
        p, m, c = i["priority"], i["metric"] or {}, i["priority"]["confirmed"] or {}
        rows.append({
            "id": i["id"], "key": i["key"], "title": i["title"], "domain": i["domain"], "area": (i["area"] or {}).get("title"),
            "statement": i["statement"], "band": p["band"], "ai_band": p["ai_band"], "ai_score": p["ai_score"], "rank": p["rank"],
            "decision_status": i["status"], "pm_band": c.get("priority"), "pm_actor": c.get("actor"), "pm_date": c.get("at"),
            "pm_rationale": c.get("rationale"), "metric": m.get("name"), "unit": m.get("unit"), "direction": m.get("direction"),
            "target": i["rung"].get("text") or i["rung"].get("value"), "target_level": i["rung"].get("level"),
            "target_basis": i["rung"].get("basis"), "target_by": i["rung"].get("by"),
            "acceptance_criteria": " | ".join(f"{a.get('criterion')}: {a.get('pass')}" for a in i["acceptance"]),
            "evidence_level": i["evidence"]["level"], "comments": i["evidence"]["comments"], "n_sources": i["evidence"]["count"],
            "sources": "; ".join(_src(e) + (f" {e['url']}" if e.get("url") else "") for e in i["evidence"]["items"]),
            "rationale": i["rationale"], "factors": "; ".join(f"{f['label']} {f['points']:.1f}" for f in i["factors"]),
            "assumptions": " | ".join(i["assumptions"]), "gaps_uncertainties": " | ".join(i["gaps"] + i["uncertainties"]),
            "links": "; ".join(f"{l['relation']} {l['key']} via {l['via']}" for l in i["links"]),
            "gates": "; ".join(f"{g}={v.get('result') if isinstance(v, dict) else v}" for g, v in i["gates"].items()),
            "horizon": i["horizon"], "kano": i["kano"],
            "history": "; ".join(f"{x['label']} {x['score']:.1f} {x['band']}" + (f" PM {x['confirmed']}" if x["confirmed"] else "") for x in i["history"]),
            "open_proposal": f"{i['open_proposal']['old_band']}→{i['open_proposal']['proposed_band']} ({i['open_proposal']['cause']})" if i["open_proposal"] else "",
        })
    return rows


@router.get("/export")
def export(cp: str = Query("cp2"), line: str = Query("5 Series"), market: str = Query("US"),
           format: Literal["md", "csv"] = "md", actor: str = Depends(get_actor)) -> Response:
    with db() as conn:
        doc = build(conn, cp, line, market)
        slug = f"requirements_{line.split()[0]}-series_{market}_{BY_ID[cp].label.replace(' ', '')}"
        if format == "csv":
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(csv_rows(doc))
            body, mime, name = buf.getvalue(), "text/csv; charset=utf-8", f"{slug}.csv"
        else:
            body, mime, name = markdown(doc), "text/markdown; charset=utf-8", f"{slug}.md"
        service.log_access(conn, actor, "export", "export", name,
                           f"document page: {doc['header']['count']} requirements; {line} × {market} at {cp}; format {format}")
    return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
