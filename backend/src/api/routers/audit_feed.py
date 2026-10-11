"""GET /api/audit/feed — the audit trail scoped to what the PM is looking at.

scope=evidence   what entered the data and when: data loads (ingest batches), research agents, checkpoint research
                 imports, the checkpoint sweeps (acquire runs), snapshot restores
scope=structure  the agent's structure & context runs (classify, cluster, contextualize, areas) and every AI step,
                 for the selected checkpoint
scope=definition the requirement-definition stages (benchmarks, define, specify, couple) and every AI step, plus the
                 PM's target choices and link reviews (D-048), for the selected checkpoint
scope=all        everything in the audit trail (page views excluded) plus data loads and checkpoint runs
Every row carries `area` (evidence / structure / definition / prioritize / settings / other) for the Audit page's filter.
Every row says who acted (ai / system / human, model for AI), when, a one-line summary and its checkpoint if known.

Separation by checkpoint: with `cp`, the evidence and structure scopes show only that checkpoint's rows; "all" shows
both, each tagged — unless `only_cp=true` (the Audit page, D-055): then only that checkpoint's rows, and `cp=none` gives
the rows tied to no checkpoint (settings, exports, …). The classifier's A/B test ran on neither checkpoint and is tagged "ab" (shown in "all" only).
History before the checkpoint rebuild (the old wave-based app) stays in the append-only table but is left out unless
`history=true`; the cutoff is the first checkpoint run.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from api.deps import db
from bmw_req.checkpoints import BY_ID

router = APIRouter(prefix="/api/audit", tags=["audit"])

EVIDENCE_ACTORS = ("ingest.", "agent:", "research.", "pipeline.waves", "demo_state", "checkpoint")
STRUCTURE_STAGES = ("classify", "cluster", "contextualize", "areas")
DEFINITION_STAGES = ("benchmarks", "define", "specify", "couple")
DEFINITION_ACTIONS = ("def_choice", "def_link_review")
PRIO_ACTIONS = ("confirm_priority", "proposal_accepted", "proposal_rejected")
PRIO_STAGES = ("gate", "prioritize")
STAGE_NAME = {"acquire": "Sweep", "classify": "Classify", "cluster": "Cluster", "contextualize": "Contextualize", "areas": "Requirement areas",
              "benchmarks": "Benchmarks", "define": "Define requirements", "specify": "Specify targets", "couple": "Couple requirements"}


def _target_name(conn, titles: dict, key: str, line: str | None, market: str | None) -> str:
    """'<requirement title> (5 Series · CN)' for a prioritization target; the key if the title is unknown."""
    if key not in titles:
        r = conn.execute("SELECT title FROM def_requirement WHERE key = ? ORDER BY run_id DESC LIMIT 1", (key,)).fetchone()
        titles[key] = r["title"] if r and r["title"] else key
    where = " · ".join(x for x in (line, market) if x)
    return f"{titles[key]}{f' ({where})' if where else ''}"


def _prio_summary(conn, titles: dict, action: str, entity_id: str | None, payload: dict, rationale: str | None) -> str | None:
    """Page-4 rows name what was decided: the requirement, its car line × market, the band, and the PM's reason."""
    why = f" — “{rationale.strip()}”" if rationale and rationale.strip() else ""
    if action == "confirm_priority" and entity_id and entity_id.count("|") == 2:
        key, line, market = entity_id.split("|")
        ai = payload.get("ai_band")
        was = f", AI had {ai}" if ai and ai != payload.get("priority") else ", same as the AI" if ai else ""
        how = " (accepted an AI proposal)" if payload.get("via_proposal") else " (brand-fit override)" if payload.get("override_brand") else ""
        return f"PM set {payload.get('priority', '?')} for {_target_name(conn, titles, key, line, market)}{was}{how}{why}"
    if action in ("proposal_accepted", "proposal_rejected") and entity_id:
        p = conn.execute("SELECT req_key, line, market, old_band, proposed_band FROM prio_proposal WHERE id = ?", (entity_id,)).fetchone()
        if p:
            verb = "accepted" if action == "proposal_accepted" else "rejected"
            move = f"{p['old_band'] or '–'} → {p['proposed_band']}"
            return f"PM {verb} the AI proposal {move} for {_target_name(conn, titles, p['req_key'], p['line'], p['market'])}{why}"
    if action == "change_weights":
        return f"PM changed the prioritization weights (version {entity_id}){why}"
    return None


def _summary(action: str, entity_type: str, entity_id: str | None, payload: dict, rationale: str | None) -> str:
    if action == "web_research":
        return f"Web research agent collected {payload.get('items', payload.get('kept', ''))} cited items".strip()
    if action == "ingest":
        return f"Loaded {entity_id or entity_type}"
    if action == "def_choice" and payload.get("level"):
        where = " · ".join(str(payload[k]) for k in ("line", "market") if payload.get(k))
        return f"PM chose the {payload['level']} rung for {payload.get('key') or entity_id}{f' ({where})' if where else ''}"[:160]
    if action == "def_link_review" and payload.get("verdict"):
        return f"PM {payload['verdict']} the link {payload.get('a', '')} ↔ {payload.get('b', '')}".strip()[:160]
    if action == "restore_snapshot":
        return f"Restored snapshot {entity_id}"
    if action == "extract_signals":
        return f"Old extraction (v3): {payload.get('verbatims', '')} comments → {payload.get('signals', '')} signals"
    return (rationale or action.replace("_", " "))[:160]


def _area(actor: str, action: str, entity_type: str | None, evidence: bool, structure: bool, definition: bool) -> str:
    if entity_type == "setting":
        return "settings"
    if actor.startswith(tuple(f"structure.{s}" for s in PRIO_STAGES)) or actor == "prioritize" or action in PRIO_ACTIONS \
            or action == "change_weights" or (entity_type or "").startswith(("prio_", "weights")):
        return "prioritize"
    if definition:
        return "definition"
    if structure:
        return "structure"
    return "evidence" if evidence else "other"


def _run_area(stage: str) -> str:
    return ("evidence" if stage == "acquire" else "definition" if stage in DEFINITION_STAGES
            else "prioritize" if stage in PRIO_STAGES else "structure")


@router.get("/feed")
def feed(scope: str = Query("all", pattern="^(evidence|structure|definition|all)$"), cp: str | None = Query(None),
         limit: int = Query(80, ge=1, le=500), before: str | None = Query(None), history: bool = Query(False),
         only_cp: bool = Query(False)) -> dict:
    with db() as conn:
        run_cp = {r[0]: r[1] for r in conn.execute("SELECT id, checkpoint_id FROM checkpoint_run")}
        since = None if history else conn.execute("SELECT MIN(started_at) FROM checkpoint_run").fetchone()[0]
        usage_cp = {}
        for r in conn.execute("SELECT id, job FROM llm_usage WHERE job LIKE 'classify:%' OR job LIKE 'areas:%'"):
            usage_cp[str(r[0])] = ("cp2" if r[1].endswith("cp2") else "cp1" if r[1].endswith("cp1")
                                   else "ab" if r[1].endswith(":ab") else None)
        items: list[dict] = []
        titles: dict[str, str] = {}

        # audit events
        q = "SELECT id, ts, actor_type, actor_id, action, entity_type, entity_id, new_value, rationale, model, run_id FROM audit_event WHERE action != 'view'"
        args: list = []
        if since:
            q += " AND ts >= ?"
            args.append(since)
        if before:
            q += " AND ts < ?"
            args.append(before)
        for r in conn.execute(q + " ORDER BY ts DESC LIMIT 4000", args):
            actor = r["actor_id"] or ""
            is_structure = actor.startswith("structure.")
            is_evidence = actor.startswith(EVIDENCE_ACTORS) or r["action"] in ("restore_snapshot", "ingest", "web_research")
            is_definition = (actor.startswith(tuple(f"structure.{s}" for s in DEFINITION_STAGES))
                             or r["action"] in DEFINITION_ACTIONS or (r["entity_type"] or "").startswith("def_"))
            if scope == "structure" and (not is_structure or is_definition):
                continue
            if scope == "definition" and not is_definition:
                continue
            if scope == "evidence" and not is_evidence:
                continue
            try:
                payload = json.loads(r["new_value"]) if r["new_value"] and r["new_value"].startswith("{") else {}
            except ValueError:
                payload = {}
            ecp = run_cp.get(r["run_id"]) or (usage_cp.get(r["entity_id"]) if r["entity_type"] == "llm_usage" else None)
            if is_definition and not ecp:   # PM choices / link reviews carry their checkpoint in the payload, not a run
                ecp = payload.get("checkpoint_id") or payload.get("checkpoint") or payload.get("cp")
            if r["action"] in PRIO_ACTIONS and not ecp:   # PM priority decisions carry their checkpoint in the payload
                ecp = payload.get("checkpoint")
            summary = None if is_structure else (_prio_summary(conn, titles, r["action"], r["entity_id"], payload, r["rationale"])
                                                 or _summary(r["action"], r["entity_type"], r["entity_id"], payload, r["rationale"]))
            items.append({"id": f"a{r['id']}", "ts": r["ts"], "actor_type": r["actor_type"], "actor": actor, "model": r["model"],
                          "kind": "structure" if is_structure else "event", "stage": actor.split(".", 1)[1] if is_structure else None,
                          "action": r["action"], "payload": payload, "checkpoint": ecp, "summary": summary,
                          "area": _area(actor, r["action"], r["entity_type"], is_evidence, is_structure, is_definition)})

        # checkpoint runs: one row when a stage started and one when it finished
        for r in conn.execute("SELECT id, checkpoint_id, stage, parent_run_id, status, actor, started_at, finished_at, stats_json FROM checkpoint_run"):
            evidence_run = r["stage"] == "acquire"
            if (scope == "structure" and (evidence_run or r["stage"] not in STRUCTURE_STAGES)) or (scope == "evidence" and not evidence_run) \
                    or (scope == "definition" and r["stage"] not in DEFINITION_STAGES):
                continue
            label = f"{STAGE_NAME.get(r['stage'], r['stage'])} · {BY_ID[r['checkpoint_id']].label}"
            base = {"actor_type": "system" if r["actor"] == "system" else "human", "actor": r["actor"], "model": None,
                    "kind": "run", "stage": r["stage"], "checkpoint": r["checkpoint_id"], "payload": {}, "area": _run_area(r["stage"])}
            parent = f", building on run {r['parent_run_id']}" if r["parent_run_id"] else ""
            items.append({**base, "id": f"r{r['id']}s", "ts": r["started_at"], "action": "run_start",
                          "summary": f"{label} started (run {r['id']}{parent})"})
            if r["finished_at"]:
                st = json.loads(r["stats_json"] or "{}")
                tr = st.get("tracks") if isinstance(st.get("tracks"), dict) else None
                extra = f" — {', '.join(f'{v} {k}' for k, v in tr.items() if isinstance(v, int) and v)}" if tr and all(isinstance(v, int) for v in tr.values()) else ""
                items.append({**base, "id": f"r{r['id']}f", "ts": r["finished_at"], "action": f"run_{r['status']}",
                              "summary": f"{label} {r['status']}{extra}"})

        # data loads: a batch that fed both checkpoints becomes one row per checkpoint with its own item count
        if scope in ("evidence", "all"):
            split: dict[int, list] = {}
            for r in conn.execute("""SELECT ingest_batch_id b, checkpoint, COUNT(*) n FROM source_item
                                     WHERE ingest_batch_id IS NOT NULL AND checkpoint IS NOT NULL GROUP BY 1, 2"""):
                split.setdefault(r["b"], []).append((r["checkpoint"], r["n"]))
            for r in conn.execute("SELECT id, ts, kind, description, file FROM ingest_batch" + (" WHERE ts >= ?" if since else ""),
                                  (since,) if since else ()):
                what = f"{r['kind'].replace('_', ' ')}: {r['description'] or r['file'] or ''}".strip()
                for c, n in split.get(r["id"]) or [(None, None)]:
                    items.append({"id": f"b{r['id']}{c or ''}", "ts": r["ts"], "actor_type": "system", "actor": "ingest",
                                  "model": None, "kind": "load", "stage": None, "action": "load", "payload": {}, "checkpoint": c,
                                  "area": "evidence",
                                  "summary": (f"Loaded {n:,} items for {BY_ID[c].label} · {what}" if c in BY_ID
                                              else f"Loaded {what}")[:160]})

        if since:
            items = [i for i in items if (i["ts"] or "") >= since]
        if cp and (scope != "all" or only_cp):
            want = None if cp == "none" else cp
            items = [i for i in items if i["checkpoint"] == want]
        if before:
            items = [i for i in items if i["ts"] < before]
        items.sort(key=lambda i: i["ts"] or "", reverse=True)
        return {"scope": scope, "items": items[:limit], "more": len(items) > limit}
