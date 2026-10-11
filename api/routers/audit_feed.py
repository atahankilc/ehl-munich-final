"""GET /api/audit/feed — the audit trail scoped to what the PM is looking at.

scope=evidence   what entered the data and when: data loads (ingest batches), research agents, checkpoint research
                 imports, the checkpoint sweeps (acquire runs), snapshot restores
scope=structure  the agent's structure & context runs (classify, cluster, contextualize, areas) and every AI step,
                 for the selected checkpoint
scope=all        everything in the audit trail (page views excluded) plus data loads and checkpoint runs
Every row says who acted (ai / system / human, model for AI), when, a one-line summary and its checkpoint if known.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from api.deps import db
from bmw_req.checkpoints import BY_ID

router = APIRouter(prefix="/api/audit", tags=["audit"])

EVIDENCE_ACTORS = ("ingest.", "agent:", "research.", "pipeline.waves", "demo_state", "checkpoint")
STRUCTURE_STAGES = ("classify", "cluster", "contextualize", "areas")
STAGE_NAME = {"acquire": "Sweep", "classify": "Classify", "cluster": "Cluster", "contextualize": "Contextualize", "areas": "Requirement areas"}


def _summary(action: str, entity_type: str, entity_id: str | None, payload: dict, rationale: str | None) -> str:
    if action == "web_research":
        return f"Web research agent collected {payload.get('items', payload.get('kept', ''))} cited items".strip()
    if action == "ingest":
        return f"Loaded {entity_id or entity_type}"
    if action == "restore_snapshot":
        return f"Restored snapshot {entity_id}"
    if action == "extract_signals":
        return f"Old extraction (v3): {payload.get('verbatims', '')} comments → {payload.get('signals', '')} signals"
    return (rationale or action.replace("_", " "))[:160]


@router.get("/feed")
def feed(scope: str = Query("all", pattern="^(evidence|structure|all)$"), cp: str | None = Query(None),
         limit: int = Query(80, ge=1, le=500), before: str | None = Query(None)) -> dict:
    with db() as conn:
        run_cp = {r[0]: r[1] for r in conn.execute("SELECT id, checkpoint_id FROM checkpoint_run")}
        usage_cp = {}
        for r in conn.execute("SELECT id, job FROM llm_usage WHERE job LIKE 'classify:%' OR job LIKE 'areas:%'"):
            usage_cp[str(r[0])] = "cp2" if r[1].endswith("cp2") else "cp1" if r[1].endswith("cp1") else None
        items: list[dict] = []

        # audit events
        q = "SELECT id, ts, actor_type, actor_id, action, entity_type, entity_id, new_value, rationale, model, run_id FROM audit_event WHERE action != 'view'"
        args: list = []
        if before:
            q += " AND ts < ?"
            args.append(before)
        for r in conn.execute(q + " ORDER BY ts DESC LIMIT 4000", args):
            actor = r["actor_id"] or ""
            is_structure = actor.startswith("structure.")
            is_evidence = actor.startswith(EVIDENCE_ACTORS) or r["action"] in ("restore_snapshot", "ingest", "web_research")
            if scope == "structure" and not is_structure:
                continue
            if scope == "evidence" and not is_evidence:
                continue
            try:
                payload = json.loads(r["new_value"]) if r["new_value"] and r["new_value"].startswith("{") else {}
            except ValueError:
                payload = {}
            ecp = run_cp.get(r["run_id"]) or (usage_cp.get(r["entity_id"]) if r["entity_type"] == "llm_usage" else None)
            items.append({"id": f"a{r['id']}", "ts": r["ts"], "actor_type": r["actor_type"], "actor": actor, "model": r["model"],
                          "kind": "structure" if is_structure else "event", "stage": actor.split(".", 1)[1] if is_structure else None,
                          "action": r["action"], "payload": payload, "checkpoint": ecp,
                          "summary": None if is_structure else _summary(r["action"], r["entity_type"], r["entity_id"], payload, r["rationale"])})

        # checkpoint runs: one row when a stage started and one when it finished
        for r in conn.execute("SELECT id, checkpoint_id, stage, parent_run_id, status, actor, started_at, finished_at, stats_json FROM checkpoint_run"):
            evidence_run = r["stage"] == "acquire"
            if (scope == "structure" and (evidence_run or r["stage"] not in STRUCTURE_STAGES)) or (scope == "evidence" and not evidence_run):
                continue
            label = f"{STAGE_NAME.get(r['stage'], r['stage'])} · {BY_ID[r['checkpoint_id']].label}"
            base = {"actor_type": "system" if r["actor"] == "system" else "human", "actor": r["actor"], "model": None,
                    "kind": "run", "stage": r["stage"], "checkpoint": r["checkpoint_id"], "payload": {}}
            parent = f", building on run {r['parent_run_id']}" if r["parent_run_id"] else ""
            items.append({**base, "id": f"r{r['id']}s", "ts": r["started_at"], "action": "run_start",
                          "summary": f"{label} started (run {r['id']}{parent})"})
            if r["finished_at"]:
                st = json.loads(r["stats_json"] or "{}")
                tr = st.get("tracks") if isinstance(st.get("tracks"), dict) else None
                extra = f" — {', '.join(f'{v} {k}' for k, v in tr.items() if isinstance(v, int) and v)}" if tr and all(isinstance(v, int) for v in tr.values()) else ""
                items.append({**base, "id": f"r{r['id']}f", "ts": r["finished_at"], "action": f"run_{r['status']}",
                              "summary": f"{label} {r['status']}{extra}"})

        # data loads
        if scope in ("evidence", "all"):
            for r in conn.execute("SELECT id, ts, kind, description, file FROM ingest_batch"):
                items.append({"id": f"b{r['id']}", "ts": r["ts"], "actor_type": "system", "actor": "ingest", "model": None,
                              "kind": "load", "stage": None, "action": "load", "payload": {}, "checkpoint": None,
                              "summary": f"Loaded {r['kind'].replace('_', ' ')}: {r['description'] or r['file'] or ''}".strip()[:160]})

        if cp and scope == "structure":
            items = [i for i in items if i["checkpoint"] in (cp, None)]
        if before:
            items = [i for i in items if i["ts"] < before]
        items.sort(key=lambda i: i["ts"] or "", reverse=True)
        return {"scope": scope, "items": items[:limit], "more": len(items) > limit}
