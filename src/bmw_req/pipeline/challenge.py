"""PM challenge (brief: "review, challenge, modify"): the PM questions a requirement, its rationale or evidence;
sol answers from the stored evidence plus a semantic search over all signals (sqlite-vec), and may PROPOSE
content changes or evidence links — which become change proposals the PM accepts or rejects (AGENTS rule 5).
"""

import json
import sqlite3

import numpy as np
from pydantic import BaseModel, Field

from bmw_req.llm import LLM
from bmw_req.pipeline.requirements import audit
from bmw_req.service import EDITABLE, _need

PROMPT_VERSION = "challenge-v1"


class ProposedEdit(BaseModel):
    field: str = Field(description=f"one of {EDITABLE}")
    new_value: str
    reason: str


class ChallengeAnswer(BaseModel):
    verdict: str = Field(description="upheld | partially_upheld | not_upheld — is the PM's challenge right?")
    answer: str = Field(description="Plain-language answer for the PM, 3–8 sentences; cite finding IDs [F123] and verbatim IDs")
    evidence_for: list[str] = Field(description="Short bullets with IDs that support the requirement")
    evidence_against: list[str] = Field(description="Short bullets with IDs that weaken it or conflict; may be empty")
    proposed_edits: list[ProposedEdit] = Field(description="Only if the challenge shows the requirement should change")
    link_finding_ids: list[int] = Field(description="Finding IDs from the search results that should be linked as evidence")


INSTRUCTIONS = """You are the AI analyst in a BMW product-requirements tool. A product manager (PM) challenges a
proposed customer requirement. Answer honestly and specifically from the evidence given (the requirement, its
score breakdown and linked findings with quotes, plus semantically similar customer signals found by search).
- If the PM is right, say so (verdict upheld) and propose concrete edits; if partly right, partially_upheld.
- Separate evidence from assumption. Cite IDs. Never invent quotes, numbers or sources.
- Remember: markets are different customer groups; China has no verbatims (study + web only); the sales file
  is BMW-internal relative data; support-call questions are weak usability evidence.
- You never decide: edits you propose go to the PM for approval."""


def similar_signals(conn: sqlite3.Connection, llm: LLM, text: str, k: int = 25) -> list[dict]:
    vec = np.asarray(llm.embed([text], job="challenge:embed")[0], dtype=np.float32)
    rows = conn.execute(
        """SELECT e.rowid sid, e.distance, g.feedback_type, g.need_statement, g.quote, g.support_question,
                  s.external_id, s.vehicle_model_id, s.market_code,
                  (SELECT fs.finding_id FROM finding_signal fs WHERE fs.signal_id = g.id LIMIT 1) finding_id
           FROM signal_embedding e JOIN signal g ON g.id = e.rowid JOIN source_item s ON s.id = g.source_item_id
           WHERE e.embedding MATCH ? AND k = ? ORDER BY e.distance""", (vec.tobytes(), k)).fetchall()
    return [dict(r) for r in rows]


def build_context(conn: sqlite3.Connection, req_id: str) -> dict:
    req = dict(conn.execute("SELECT * FROM requirement WHERE id = ?", (req_id,)).fetchone())
    req.pop("derivation_json", None)
    targets = []
    for t in conn.execute("SELECT * FROM requirement_target WHERE requirement_id = ?", (req_id,)):
        b = json.loads(t["score_breakdown_json"]) if t["score_breakdown_json"] else {}
        targets.append({"target": f"{t['vehicle_model_id']}×{t['market_code']}", "score": t["score"],
                        "ai_priority": t["proposed_priority"], "pm_priority": t["priority"],
                        "evidence_level": t["evidence_level"], "factors": b.get("factors"), "gaps": b.get("gaps")})
    findings = []
    for f in conn.execute("""SELECT f.*, rf.relation FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
                             WHERE rf.requirement_id = ?""", (req_id,)):
        quotes = [f"{q['external_id'] or q['ref']}: {q['quote']}" for q in conn.execute(
            """SELECT s.external_id, s.ref, fs.quote FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id
               WHERE fs.finding_id = ? LIMIT 6""", (f["id"],))]
        m = json.loads(f["metrics_json"] or "{}")
        findings.append({"id": f["id"], "relation": f["relation"], "kind": f["source_kind"], "type": f["type"],
                         "title": f["title"], "summary": f["summary"], "derivative": f["vehicle_model_id"],
                         "market": f["market_code"],
                         "markets": {k: v.get("verbatims") for k, v in m.get("by_wave", {}).get("2", {}).get("markets", {}).items()} or None,
                         "quotes": quotes})
    fits = [dict(r) for r in conn.execute(
        "SELECT vehicle_model_id, market_code, check_type, result, rationale FROM fit_check WHERE requirement_id = ?", (req_id,))]
    return {"requirement": req, "targets": targets, "linked_findings": findings, "fit_checks": fits}


def challenge(conn: sqlite3.Connection, llm: LLM, req_id: str, question: str, actor: str) -> dict:
    _need(actor, question)
    ctx = build_context(conn, req_id)
    ctx["similar_signals"] = similar_signals(conn, llm, f"{ctx['requirement']['title']}. {question}")
    conn.execute("BEGIN IMMEDIATE")
    old_status = ctx["requirement"]["status"]
    conn.execute("UPDATE requirement SET status = 'challenged' WHERE id = ?", (req_id,))
    audit(conn, actor_type="human", actor_id=actor, action="challenge", entity_type="requirement", entity_id=req_id,
          field="status", old=old_status, new="challenged", rationale=question)
    conn.execute("COMMIT")
    res = llm.generate(job="challenge", tier="smart", instructions=INSTRUCTIONS,
                       input=json.dumps({"pm_challenge": question, **ctx}, ensure_ascii=False, default=str),
                       schema=ChallengeAnswer, reasoning_effort="medium", max_output_tokens=12_000, demo=True)
    ans: ChallengeAnswer = res.parsed
    model = llm.model_for("smart")
    known = {r[0] for r in conn.execute("SELECT id FROM finding")}
    linked = {f["id"] for f in ctx["linked_findings"]}
    conn.execute("BEGIN IMMEDIATE")
    try:
        audit(conn, actor_type="ai", actor_id="pipeline.challenge", action="challenge_response", entity_type="requirement",
              entity_id=req_id, new=ans.model_dump(), rationale=ans.answer, model=model, prompt_ref=PROMPT_VERSION)
        for e in ans.proposed_edits:
            if e.field not in EDITABLE:
                continue
            cur = conn.execute(f"SELECT {e.field} FROM requirement WHERE id = ?", (req_id,)).fetchone()[0]
            conn.execute(
                """INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                   VALUES (?, ?, ?, ?, ?, 'content')""", (req_id, e.field, cur, e.new_value, f"PM challenge: {e.reason}"))
        for fid in ans.link_finding_ids:
            if fid in known and fid not in linked:
                conn.execute(
                    """INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                       VALUES (?, ?, NULL, 'supports', ?, 'link_finding')""",
                    (req_id, f"finding:{fid}", "Found by semantic search while answering a PM challenge"))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"answer": ans.model_dump(), "cost": res.cost_usd, "cached": res.cached}
