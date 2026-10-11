"""Decide: one queue of everything that waits for the PM (requirements to review + open AI proposals), and the
proposal endpoints (list, decide, bulk-decide)."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import action_errors, db, get_actor, need_rationale, not_found
from api.queries import parse_key, proposals, requirement_summaries
from bmw_req import service

router = APIRouter(prefix="/api", tags=["decide"])

FIRST_KINDS = ("priority", "extend")       # change an existing decision
LAST_KINDS = ("content", "link_finding", "status")


def _subtitle(p: dict) -> str:
    k = p["kind"]
    if k == "priority":
        where = p["target"]["label"] if p["target"] else ""
        return f"{where}: {p['old_value'] or 'not set'} → {p['proposed_value']}"
    if k == "extend":
        return p["proposed_value"] or "merge a duplicate draft into this requirement"
    if k == "link_finding":
        f = p.get("finding") or {}
        return f"Link {p['field'].replace('finding:', 'F')} as {p['proposed_value']}" + (f": {f['title']}" if f.get("title") else "")
    if k == "new_requirement":
        return p["reason"] or "New requirement drafted by the AI"
    return f"Edit {p['field']}"


def _prop_item(p: dict) -> dict:
    d = p["delta"] if isinstance(p["delta"], dict) else {}
    return {"uid": f"prop:{p['id']}", "type": "proposal", "kind": p["kind"], "proposal_id": p["id"],
            "req_id": p["requirement_id"], "title": p["requirement_title"], "subtitle": _subtitle(p),
            "score": d.get("score") if p["kind"] == "priority" else None,
            "priority": p["proposed_value"] if p["kind"] == "priority" else None,
            "target": p["target"], "created_at": p["created_at"], "run_id": p["run"]["id"] if p["run"] else None,
            "status": p["status"], "reason": p["reason"]}


def _matches(p: dict, flt: tuple | None, req_targets: dict) -> bool:
    if flt is None:
        return True
    if p["target"]:
        return (p["vehicle"], p["market"]) == flt
    if flt in req_targets.get(p["requirement_id"], set()):
        return True
    d = p["delta"] if isinstance(p["delta"], dict) else {}
    return any((t.get("vehicle_model_id"), t.get("market_code")) == flt for t in d.get("targets") or [])


@router.get("/queue")
def queue(target: str | None = None, include_decided: bool = False) -> dict:
    flt = parse_key(target) if target else None
    with db() as conn:
        summaries = requirement_summaries(conn)
        props = proposals(conn, "p.status = 'open'")
    req_targets = defaultdict(set)
    for s in summaries:
        for t in s["targets"]:
            req_targets[s["id"]].add((t["target"]["vehicle"], t["target"]["market"]))
    props = [p for p in props if _matches(p, flt, req_targets)]

    reqs = [s for s in summaries if (s["status"] in ("proposed", "challenged") or
                                     (include_decided and s["status"] != "rejected"))]
    if flt is not None:
        reqs = [s for s in reqs if flt in req_targets[s["id"]]]
    new_prop = {p["requirement_id"]: p for p in props if p["kind"] == "new_requirement"}
    req_items = []
    for s in reqs:
        scope = [t for t in s["targets"] if flt is None or (t["target"]["vehicle"], t["target"]["market"]) == flt]
        scored = [t for t in scope if t["score"] is not None]
        best = max(scored, key=lambda t: t["score"]) if scored else (scope[0] if scope else None)
        np_ = new_prop.get(s["id"])
        req_items.append({
            "uid": f"req:{s['id']}", "type": "requirement",
            "kind": "challenged" if s["status"] == "challenged" else "review",
            "req_id": s["id"], "title": s["title"],
            "subtitle": " · ".join(x for x in (s["category"], best["target"]["label"] if best else None) if x),
            "score": best["score"] if best else None, "priority": best["priority"] if best else None,
            "ai_only": best["ai_only"] if best else True,
            "target": best["target"] if best else None, "created_at": s["created_at"], "run_id": None,
            "status": s["status"], "evidence_level": s["evidence_level"],
            "is_new_in_wave": np_ is not None, "proposal_id": np_["id"] if np_ else None,
        })
    req_items.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), x["req_id"]))
    listed = {x["req_id"] for x in req_items}

    order = {k: i for i, k in enumerate(FIRST_KINDS)}
    first = sorted((p for p in props if p["kind"] in FIRST_KINDS),
                   key=lambda p: (order[p["kind"]], -(p["run"]["id"] if p["run"] else 0), p["id"]))
    loose_new = [p for p in props if p["kind"] == "new_requirement" and p["requirement_id"] not in listed]
    last = [p for p in props if p["kind"] in LAST_KINDS]
    items = [_prop_item(p) for p in first] + req_items + [_prop_item(p) for p in loose_new] + [_prop_item(p) for p in last]
    counts = {"requirements": len(req_items),
              **{k: sum(p["kind"] == k for p in props) for k in ("priority", "extend", "content", "link_finding")},
              "new_requirement": sum(x.get("is_new_in_wave", False) for x in req_items) + len(loose_new)}
    return {"items": items, "counts": counts}


@router.get("/proposals")
def list_proposals(status: Literal["open", "decided", "all"] = "open", kind: str | None = None,
                   requirement_id: str | None = None) -> list[dict]:
    where, params = [], []
    if status == "open":
        where.append("p.status = 'open'")
    elif status == "decided":
        where.append("p.status != 'open'")
    if kind:
        where.append("COALESCE(p.kind, 'priority') = ?")
        params.append(kind)
    if requirement_id:
        where.append("p.requirement_id = ?")
        params.append(requirement_id)
    with db() as conn:
        return proposals(conn, " AND ".join(where) or "1 = 1", tuple(params))


class Decision(BaseModel):
    accept: bool
    rationale: str


class BulkDecision(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    accept: bool
    rationale: str


@router.post("/proposals/{pid}/decision")
def decide(pid: int, body: Decision, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    with db() as conn:
        if conn.execute("SELECT 1 FROM change_proposal WHERE id = ?", (pid,)).fetchone() is None:
            raise not_found(f"No change proposal {pid}")
        with action_errors():
            service.decide_proposal(conn, pid, body.accept, actor, why)
        return {"proposal": proposals(conn, "p.id = ?", (pid,))[0]}


@router.post("/proposals/bulk-decision")
def bulk_decide(body: BulkDecision, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    done, failed = [], []
    for pid in dict.fromkeys(body.ids):   # de-duplicate, keep order
        with db() as conn:
            try:
                if conn.execute("SELECT 1 FROM change_proposal WHERE id = ?", (pid,)).fetchone() is None:
                    raise service.ActionError(f"No change proposal {pid}")
                service.decide_proposal(conn, pid, body.accept, actor, why)
                done.append(pid)
            except service.ActionError as e:
                failed.append({"id": pid, "detail": str(e)})
    return {"done": done, "failed": failed}

