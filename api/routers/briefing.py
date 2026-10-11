"""GET /api/briefing — the home screen: what changed since the last run, what's new, what waits for the PM, and a
pulse per car × market. A composition of existing tables; no writes."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from api import labels as L
from api.deps import db
from api.queries import (PRIORITY_RANK, best_first, conflict_info, current_wave, effective, evidence_gaps, loads,
                         parse_key, proposals, requirement_summaries, target_obj, target_rows, verbatim_base)
from bmw_req.pipeline.waves import WAVES
from bmw_req.portfolio import all_targets

router = APIRouter(prefix="/api", tags=["briefing"])

FEED_MAX = 25
# Nested actions written by accept/reject_proposal or by "also accept the AI priorities" — the parent event stands for them.
NESTED_PREFIXES = ("Accepted AI proposal #", "Accepted new AI requirement #", "Rejected new AI requirement #",
                   "Accepted the AI suggestion with the decision")
DECISION_ACTIONS = ("set_status", "set_priority", "accept_proposal", "reject_proposal", "override_gate", "challenge")


def _tone_priority(old: str | None, new: str | None) -> str:
    if old in PRIORITY_RANK and new in PRIORITY_RANK:
        return "up" if PRIORITY_RANK[new] < PRIORITY_RANK[old] else ("down" if PRIORITY_RANK[new] > PRIORITY_RANK[old] else "neutral")
    return "neutral"


def _target_from_entity(entity_id: str):
    if ":" not in entity_id:
        return None
    try:
        return target_obj(*parse_key(entity_id.split(":", 1)[1]))
    except Exception:
        return None


def _movers(conn, run_id: int | None, prev_id: int | None, titles: dict) -> tuple[list, dict]:
    stats = {"priority_changes": 0, "risers": 0, "fallers": 0}
    if not run_id or not prev_id:
        return [], stats
    snaps = defaultdict(dict)
    for r in conn.execute("""SELECT run_id, requirement_id, vehicle_model_id, market_code, score, priority
                             FROM score_snapshot WHERE run_id IN (?, ?)""", (prev_id, run_id)):
        snaps[(r["requirement_id"], r["vehicle_model_id"], r["market_code"])][r["run_id"]] = r
    causes = {r[0]: r[1] for r in conn.execute(
        "SELECT entity_id, rationale FROM audit_event WHERE action = 'rescore' AND run_id = ?", (run_id,))}
    movers = []
    for (rid, v, m), by_run in snaps.items():
        old, new = by_run.get(prev_id), by_run.get(run_id)
        if not old or not new or old["score"] is None or new["score"] is None:
            continue
        delta = new["score"] - old["score"]
        if old["priority"] != new["priority"]:
            stats["priority_changes"] += 1
        if delta >= 0.5:
            stats["risers"] += 1
        elif delta <= -0.5:
            stats["fallers"] += 1
        if abs(delta) >= 0.05 or old["priority"] != new["priority"]:
            movers.append({"req_id": rid, "title": titles.get(rid, {}).get("title"), "target": target_obj(v, m),
                           "score_old": round(old["score"], 1), "score_new": round(new["score"], 1),
                           "delta": round(delta, 1), "priority_old": old["priority"], "priority_new": new["priority"],
                           "cause": causes.get(f"{rid}:{v}×{m}")})
    movers.sort(key=lambda x: (-abs(x["delta"]), x["req_id"]))
    return movers[:8], stats


def _feed(conn, props: list[dict], titles: dict) -> list[dict]:
    items = []
    for p in props:
        if p["status"] == "superseded":
            continue
        kind, title_req = p["kind"], p["requirement_title"]
        chip = None
        if kind == "priority":
            title = f"AI suggests {p['proposed_value']} for {p['target']['label'] if p['target'] else p['requirement_id']}"
            chip = {"text": f"{p['old_value'] or 'not set'} → {p['proposed_value']}",
                    "tone": _tone_priority(p["old_value"], p["proposed_value"])}
            actor = "pipeline.scoring"
        elif kind == "new_requirement":
            title, chip, actor = f"New requirement drafted: {title_req}", {"text": "new", "tone": "up"}, "pipeline.derive"
        elif kind == "extend":
            title = f"Merge suggested into {p['requirement_id']}: {title_req}"
            chip, actor = {"text": "merge", "tone": "neutral"}, "pipeline.derive"
        elif kind == "link_finding":
            title = f"Evidence link suggested ({p['field'].replace('finding:', 'F')}) for {p['requirement_id']}"
            chip, actor = {"text": "evidence", "tone": "neutral"}, "pipeline.challenge"
        else:
            title = f"Content edit suggested ({p['field']}) for {p['requirement_id']}"
            chip, actor = {"text": "edit", "tone": "neutral"}, "pipeline.challenge"
        if p["status"] != "open":
            chip = {"text": p["status"], "tone": "up" if p["status"] == "accepted" else "down"}
        items.append({"id": f"prop:{p['id']}", "ts": p["created_at"], "kind": "proposal", "title": title,
                      "detail": p["reason"], "req_id": p["requirement_id"], "target": p["target"],
                      "actor_type": "ai", "actor": actor, "chip": chip})

    prop_req = {str(r[0]): r[1] for r in conn.execute("SELECT id, requirement_id FROM change_proposal")}
    ph = ",".join("?" * len(DECISION_ACTIONS))
    for e in conn.execute(
            f"""SELECT id, ts, actor_type, actor_id, action, entity_type, entity_id, field, old_value, new_value, rationale
                FROM audit_event WHERE actor_type = 'human' AND action IN ({ph}) ORDER BY id DESC LIMIT 300""",
            DECISION_ACTIONS):
        why = e["rationale"] or ""
        if why.startswith(NESTED_PREFIXES):
            continue
        a, eid = e["action"], e["entity_id"]
        rid = prop_req.get(eid) if e["entity_type"] == "change_proposal" else eid.split(":", 1)[0]
        req_title = titles.get(rid, {}).get("title") or rid
        tgt = _target_from_entity(eid) if e["entity_type"] == "requirement_target" else None
        kind = "decision"
        if a == "set_status":
            new = e["new_value"]
            title = f"{L.STATUS_LABELS.get(new, new)}: {req_title}"
            chip = {"text": L.STATUS_LABELS.get(new, new),
                    "tone": {"approved": "up", "rejected": "down", "deferred": "warn"}.get(new, "neutral")}
        elif a == "set_priority":
            title = f"Priority {e['new_value'] or 'cleared'} for {tgt['label'] if tgt else eid}: {req_title}"
            chip = {"text": e["new_value"] or "cleared", "tone": _tone_priority(e["old_value"], e["new_value"])}
        elif a in ("accept_proposal", "reject_proposal"):
            acc = a == "accept_proposal"
            title = f"{'Accepted' if acc else 'Rejected'} AI suggestion #{eid}: {req_title}"
            chip = {"text": "accepted" if acc else "rejected", "tone": "up" if acc else "down"}
        elif a == "override_gate":
            title, chip = f"Brand gate overridden for {tgt['label'] if tgt else eid}: {req_title}", {"text": "override", "tone": "warn"}
        else:   # challenge
            kind, title, chip = "challenge", f"Challenged: {req_title}", {"text": "challenged", "tone": "warn"}
        items.append({"id": f"audit:{e['id']}", "ts": e["ts"], "kind": kind, "title": title, "detail": why or None,
                      "req_id": rid, "target": tgt, "actor_type": "human", "actor": e["actor_id"], "chip": chip})

    for e in conn.execute("""SELECT id, ts, actor_id, entity_id, new_value, rationale FROM audit_event
                             WHERE action = 'challenge_response' ORDER BY id DESC LIMIT 50"""):
        verdict = (loads(e["new_value"], {}) or {}).get("verdict")
        items.append({"id": f"audit:{e['id']}", "ts": e["ts"], "kind": "challenge",
                      "title": f"AI answered the challenge on {e['entity_id']}: {titles.get(e['entity_id'], {}).get('title') or ''}".rstrip(": "),
                      "detail": e["rationale"], "req_id": e["entity_id"], "target": None, "actor_type": "ai",
                      "actor": e["actor_id"], "chip": {"text": L.VERDICTS.get(verdict, verdict or "answer"),
                                                       "tone": "warn" if verdict in ("upheld", "partially_upheld") else "neutral"}})

    n_props = dict(conn.execute("SELECT run_id, COUNT(*) FROM change_proposal WHERE run_id IS NOT NULL GROUP BY 1").fetchall())
    for e in conn.execute("""SELECT id, ts, actor_type, actor_id, entity_id, new_value, rationale FROM audit_event
                             WHERE action = 'start_run' AND entity_type = 'prioritization_run' ORDER BY id DESC LIMIT 50"""):
        start = loads(e["new_value"], {}) or {}
        rid_ = int(e["entity_id"]) if str(e["entity_id"]).isdigit() else None
        n = n_props.get(rid_, 0)
        items.append({"id": f"audit:{e['id']}", "ts": e["ts"], "kind": "run",
                      "title": f"Prioritization run {e['entity_id']} ({str(start.get('trigger') or '').replace('_', ' ')}"
                               + (f", wave {start.get('wave')})" if start.get("wave") else ")"),
                      "detail": e["rationale"], "req_id": None, "target": None, "actor_type": e["actor_type"],
                      "actor": e["actor_id"], "chip": {"text": f"{n} priority suggestion{'s' if n != 1 else ''}", "tone": "neutral"}})
    for e in conn.execute("""SELECT id, ts, actor_type, actor_id, entity_id, rationale FROM audit_event
                             WHERE action = 'open_wave' ORDER BY id DESC LIMIT 20"""):
        w = int(e["entity_id"]) if str(e["entity_id"]).isdigit() else None
        items.append({"id": f"audit:{e['id']}", "ts": e["ts"], "kind": "wave",
                      "title": f"Opened {WAVES[w]['label'] if w in WAVES else 'wave ' + str(e['entity_id'])}",
                      "detail": e["rationale"], "req_id": None, "target": None, "actor_type": e["actor_type"],
                      "actor": e["actor_id"], "chip": {"text": "SIMULATION", "tone": "neutral"}})
    items.sort(key=lambda x: (x["ts"] or "", x["id"]), reverse=True)
    return items[:FEED_MAX]


def queue_size(conn, rows: list[dict] | None = None) -> int:
    """Items in the unfiltered decision queue (requirements to review + open proposals not folded into them)."""
    review = {r[0] for r in conn.execute("SELECT id FROM requirement WHERE status IN ('proposed', 'challenged')")}
    n = len(review)
    for rid, kind in conn.execute("SELECT requirement_id, COALESCE(kind, 'priority') FROM change_proposal WHERE status = 'open'"):
        if kind == "new_requirement" and rid in review:
            continue
        n += 1
    return n


@router.get("/briefing")
def briefing() -> dict:
    with db() as conn:
        w = current_wave(conn)
        runs = conn.execute("SELECT id, ts, trigger, initiated_by FROM prioritization_run ORDER BY id DESC LIMIT 2").fetchall()
        run = dict(runs[0]) if runs else None
        prev_id = runs[1]["id"] if len(runs) > 1 else None
        rows = target_rows(conn)
        titles = {r["id"]: dict(r) for r in conn.execute(
            "SELECT id, title, category, status, created_at, json_extract(derivation_json, '$.wave') wave FROM requirement")}
        movers, mstats = _movers(conn, run["id"] if run else None, prev_id, titles)
        props = proposals(conn)

        # new requirements drafted in the current wave (with their new_requirement proposal, if any)
        new_ids = [rid for rid, t in titles.items() if w and t["wave"] == w]
        summaries = {s["id"]: s for s in requirement_summaries(conn, new_ids)} if new_ids else {}
        nr_prop = {p["requirement_id"]: p for p in props if p["kind"] == "new_requirement"}
        new_list = []
        for rid in sorted(new_ids, key=lambda r: (titles[r]["created_at"] or "", r), reverse=True):
            s = summaries[rid]
            p = nr_prop.get(rid)
            new_list.append({"req_id": rid, "title": s["title"], "category": s["category"], "status": s["status"],
                             "max_score": s["max_score"], "best_target": s["best_target"],
                             "proposal_id": p["id"] if p else None, "proposal_status": p["status"] if p else None,
                             "reason": p["reason"] if p else f"Drafted when {WAVES.get(w, {}).get('label', 'the wave')} opened"})

        base = verbatim_base(conn, w)
        gaps = evidence_gaps(conn, w, base)
        by_t = defaultdict(list)
        for r in rows:
            if r["status"] != "rejected":
                by_t[(r["vehicle_model_id"], r["market_code"])].append(r)
        pulse = []
        for d, m in all_targets():
            ts = by_t.get((d, m), [])
            pc = {"Must": 0, "Should": 0, "Could": 0}
            for r in ts:
                p = effective(r["pm_priority"], r["proposed_priority"])
                if p in pc:
                    pc[p] += 1
            top = best_first(ts)[0] if ts else None
            pulse.append({
                "target": target_obj(d, m), "n": len(ts), "must": pc["Must"], "should": pc["Should"], "could": pc["Could"],
                "approved": sum(r["status"] == "approved" for r in ts), "pm_confirmed": sum(r["pm_priority"] is not None for r in ts),
                "voice_base": base.get((d, m), {}).get("in_scope", 0), "gaps": gaps.get((d, m), []),
                "top": {"req_id": top["requirement_id"], "title": titles[top["requirement_id"]]["title"],
                        "score": None if top["score"] is None else round(top["score"], 1),
                        "priority": effective(top["pm_priority"], top["proposed_priority"]),
                        "ai_only": top["pm_priority"] is None} if top else None,
            })
        feed = _feed(conn, props, titles)
        waiting = queue_size(conn)
        merges_open = sum(p["kind"] == "extend" and p["status"] == "open" for p in props)
        n_conf = len(conflict_info(rows))
    wave = WAVES.get(w)
    return {
        "wave": {"n": w, "label": wave["label"] if wave else None, "simulated_date": wave["simulated_date"] if wave else None},
        "run": run, "previous_run_id": prev_id,
        "headline": {"new_requirements": len(new_ids), "priority_changes": mstats["priority_changes"],
                     "risers": mstats["risers"], "fallers": mstats["fallers"], "merges_open": merges_open,
                     "conflicts": n_conf},
        "movers": movers, "new_requirements": new_list[:6], "feed": feed, "pulse": pulse,
        "decisions_waiting": waiting,
    }
