"""PM-facing actions (the only write path the UI uses). Every action is a human action with a rationale and
an append-only audit event (AGENTS rules 5, 6, 8; D-003, D-013).

Status machine: proposed → approved | rejected | deferred | challenged; challenged → (AI answers) → PM decides.
Only humans change status. Brand-fit `fail` blocks approval unless the PM overrides with a rationale.
"""

import json
import sqlite3

from bmw_req.pipeline.requirements import audit

HUMAN_STATUSES = {"approved", "rejected", "deferred", "challenged", "proposed"}
EDITABLE = ["title", "description", "category", "target_metric", "acceptance_criteria", "horizon", "kano_class",
            "kano_drift", "assumptions", "uncertainties", "conflicting_evidence", "effort"]
PRIORITIES = ["Must", "Should", "Could"]


class ActionError(ValueError):
    pass


def _need(actor: str, rationale: str):
    if not actor or not actor.strip():
        raise ActionError("A named human actor is required.")
    if not rationale or len(rationale.strip()) < 5:
        raise ActionError("A rationale is required for every PM decision.")


def _tx(conn):
    conn.execute("BEGIN IMMEDIATE")


def log_access(conn: sqlite3.Connection, actor: str, action: str, entity_type: str, entity_id: str, detail=None):
    """Access events (view/export) are part of the audit trail (brief: 'all actions, changes, access events')."""
    audit(conn, actor_type="human", actor_id=actor or "anonymous", action=action, entity_type=entity_type,
          entity_id=entity_id, new=detail)


def brand_blocked(conn, req_id: str) -> list[str]:
    """Targets whose brand check failed and have no PM override."""
    fails = [f"{r['vehicle_model_id']}×{r['market_code']}" for r in conn.execute(
        """SELECT DISTINCT vehicle_model_id, market_code FROM fit_check f WHERE requirement_id = ? AND check_type = 'brand'
           AND result = 'fail' AND id = (SELECT MAX(id) FROM fit_check g WHERE g.requirement_id = f.requirement_id
           AND g.vehicle_model_id = f.vehicle_model_id AND g.market_code = f.market_code AND g.check_type = 'brand')""",
        (req_id,))]
    overridden = {r["entity_id"].split(":", 1)[1] for r in conn.execute(
        "SELECT entity_id FROM audit_event WHERE action = 'override_gate' AND entity_id LIKE ?", (f"{req_id}:%",))}
    return [t for t in fails if t not in overridden]


def set_status(conn, req_id: str, status: str, actor: str, rationale: str) -> None:
    _need(actor, rationale)
    if status not in HUMAN_STATUSES:
        raise ActionError(f"Unknown status {status}")
    req = conn.execute("SELECT status FROM requirement WHERE id = ?", (req_id,)).fetchone()
    if req is None:
        raise ActionError(f"No requirement {req_id}")
    if status == "approved":
        blocked = brand_blocked(conn, req_id)
        if blocked:
            raise ActionError(f"Brand-fit FAIL on {', '.join(blocked)} — override the gate with a rationale first.")
    _tx(conn)
    try:
        conn.execute("UPDATE requirement SET status = ? WHERE id = ?", (status, req_id))
        audit(conn, actor_type="human", actor_id=actor, action="set_status", entity_type="requirement",
              entity_id=req_id, field="status", old=req["status"], new=status, rationale=rationale)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def override_gate(conn, req_id: str, target: str, actor: str, rationale: str) -> None:
    _need(actor, rationale)
    _tx(conn)
    try:
        audit(conn, actor_type="human", actor_id=actor, action="override_gate", entity_type="requirement_target",
              entity_id=f"{req_id}:{target}", field="brand_fit", old="fail", new="overridden", rationale=rationale)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def set_priority(conn, req_id: str, vehicle: str, market: str, priority: str | None, actor: str, rationale: str) -> None:
    """PM confirms (or changes) the priority of one target."""
    _need(actor, rationale)
    if priority is not None and priority not in PRIORITIES:
        raise ActionError(f"Priority must be one of {PRIORITIES}")
    row = conn.execute("SELECT priority FROM requirement_target WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?",
                       (req_id, vehicle, market)).fetchone()
    if row is None:
        raise ActionError(f"{req_id} has no target {vehicle}×{market}")
    _tx(conn)
    try:
        conn.execute("UPDATE requirement_target SET priority = ? WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?",
                     (priority, req_id, vehicle, market))
        audit(conn, actor_type="human", actor_id=actor, action="set_priority", entity_type="requirement_target",
              entity_id=f"{req_id}:{vehicle}×{market}", field="priority", old=row["priority"] if row else None,
              new=priority, rationale=rationale)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def edit_requirement(conn, req_id: str, changes: dict, actor: str, rationale: str, *, actor_type: str = "human",
                     model: str | None = None) -> int:
    """Edit content fields; bumps version; one audit event per changed field. Returns the new version."""
    _need(actor, rationale)
    cur = dict(conn.execute("SELECT * FROM requirement WHERE id = ?", (req_id,)).fetchone())
    diff = {k: v for k, v in changes.items() if k in EDITABLE and v != cur.get(k)}
    if not diff:
        return cur["version"]
    _tx(conn)
    try:
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE requirement SET {sets}, version = version + 1 WHERE id = ?", (*diff.values(), req_id))
        for k, v in diff.items():
            audit(conn, actor_type=actor_type, actor_id=actor, action="edit", entity_type="requirement", entity_id=req_id,
                  field=k, old=cur.get(k), new=v, rationale=rationale, model=model)
        if cur["status"] == "approved" and actor_type == "human":
            pass   # an approved requirement stays approved after a PM edit; the edit is in the trail
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return cur["version"] + 1


def set_finding_link(conn, req_id: str, finding_id: int, relation: str | None, actor: str, rationale: str) -> None:
    """PM adds/removes/changes an evidence link (relation None = remove)."""
    _need(actor, rationale)
    old = conn.execute("SELECT relation FROM requirement_finding WHERE requirement_id = ? AND finding_id = ?",
                       (req_id, finding_id)).fetchone()
    _tx(conn)
    try:
        if relation is None:
            conn.execute("DELETE FROM requirement_finding WHERE requirement_id = ? AND finding_id = ?", (req_id, finding_id))
        else:
            conn.execute("INSERT OR REPLACE INTO requirement_finding (requirement_id, finding_id, relation) VALUES (?, ?, ?)",
                         (req_id, finding_id, relation))
        audit(conn, actor_type="human", actor_id=actor, action="edit_evidence", entity_type="requirement",
              entity_id=req_id, field=f"finding:{finding_id}", old=old["relation"] if old else None, new=relation,
              rationale=rationale)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def decide_proposal(conn, proposal_id: int, accept: bool, actor: str, rationale: str) -> None:
    """Accept or reject an AI change proposal. Accepting applies it (priority / content / link / new requirement)."""
    _need(actor, rationale)
    row = conn.execute("SELECT * FROM change_proposal WHERE id = ?", (proposal_id,)).fetchone()
    if row is None:
        raise ActionError(f"No change proposal {proposal_id}")
    p = dict(row)
    if p["status"] != "open":
        raise ActionError(f"Proposal {proposal_id} is {p['status']}")
    if accept:
        kind = p["kind"] or "priority"
        if kind == "priority":
            set_priority(conn, p["requirement_id"], p["vehicle_model_id"], p["market_code"], p["proposed_value"], actor,
                         f"Accepted AI proposal #{proposal_id}: {rationale}")
        elif kind == "content":
            edit_requirement(conn, p["requirement_id"], {p["field"]: p["proposed_value"]}, actor,
                             f"Accepted AI proposal #{proposal_id}: {rationale}")
        elif kind == "link_finding":
            set_finding_link(conn, p["requirement_id"], int(p["field"].split(":")[1]), p["proposed_value"], actor,
                             f"Accepted AI proposal #{proposal_id}: {rationale}")
        elif kind == "new_requirement":
            set_status(conn, p["requirement_id"], "proposed", actor, f"Accepted new AI requirement #{proposal_id}: {rationale}")
    _tx(conn)
    try:
        conn.execute("""UPDATE change_proposal SET status = ?, decided_by = ?, decided_at = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                        decision_rationale = ? WHERE id = ?""", ("accepted" if accept else "rejected", actor, rationale, proposal_id))
        audit(conn, actor_type="human", actor_id=actor, action="accept_proposal" if accept else "reject_proposal",
              entity_type="change_proposal", entity_id=str(proposal_id), field=p["field"], old=p["old_value"],
              new=p["proposed_value"], rationale=rationale)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def requirement_trail(conn, req_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT * FROM audit_event WHERE (entity_type = 'requirement' AND entity_id = ?)
           OR (entity_type = 'requirement_target' AND entity_id LIKE ?)
           OR (entity_type = 'change_proposal' AND entity_id IN (SELECT CAST(id AS TEXT) FROM change_proposal WHERE requirement_id = ?))
           ORDER BY id""", (req_id, f"{req_id}:%", req_id))]


def export_requirements(conn) -> list[dict]:
    """Structured requirement list = the BMW deliverable (ID, description, findings+sources, score, rationale,
    evidence level, assumptions/uncertainties, status)."""
    out = []
    for r in conn.execute("SELECT * FROM requirement ORDER BY id"):
        r = dict(r)
        targets = [dict(t) for t in conn.execute("SELECT * FROM requirement_target WHERE requirement_id = ?", (r["id"],))]
        findings = []
        for f in conn.execute("""SELECT f.id, f.title, f.type, f.source_kind, f.vehicle_model_id, f.market_code, rf.relation
                                 FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ?""",
                              (r["id"],)):
            srcs = [dict(s) for s in conn.execute(
                """SELECT s.kind, s.ref, s.external_id, s.url, s.trust_tier, fs.quote FROM finding_source fs
                   JOIN source_item s ON s.id = fs.source_item_id WHERE fs.finding_id = ? LIMIT 25""", (f["id"],))]
            n_src = conn.execute("SELECT COUNT(*) FROM finding_source WHERE finding_id = ?", (f["id"],)).fetchone()[0]
            findings.append({**dict(f), "n_sources": n_src, "sources_sample": srcs})
        out.append({
            "id": r["id"], "title": r["title"], "description": r["description"], "category": r["category"],
            "target_metric": r["target_metric"], "acceptance_criteria": r["acceptance_criteria"],
            "horizon": r["horizon"], "kano_class": r["kano_class"], "kano_drift": r["kano_drift"],
            "must_not_lose": bool(r["must_not_lose"]), "effort": r["effort"],
            "evidence_level": r["evidence_level"], "status": r["status"], "version": r["version"],
            "assumptions": r["assumptions"], "uncertainties": r["uncertainties"],
            "conflicting_evidence": r["conflicting_evidence"],
            "targets": [{"target": f"{t['vehicle_model_id']}×{t['market_code']}", "realization": t["realization"],
                         "score": t["score"], "ai_proposed_priority": t["proposed_priority"],
                         "pm_priority": t["priority"], "evidence_level": t["evidence_level"],
                         "rationale": (json.loads(t["score_breakdown_json"]) or {}).get("rationale") if t["score_breakdown_json"] else None,
                         "score_breakdown": json.loads(t["score_breakdown_json"]) if t["score_breakdown_json"] else None,
                         "market_note": t["rationale"]}
                        for t in targets],
            "findings": findings,
        })
    return out
