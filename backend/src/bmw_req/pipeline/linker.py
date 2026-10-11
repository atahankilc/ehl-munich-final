"""Evidence linker (D-028): after derivation, attach the relevant customer-study items and web findings to each
requirement for its target markets, so every target's score uses the evidence that exists for it — and a
strong study result where the requirement claims a weakness shows up as conflicting evidence.

luna picks relevance; the relation is decided deterministically:
- study item: pain/want requirement → z ≤ −0.3 supports, z ≥ +0.5 contradicts, else context;
  must-not-lose requirement → z ≥ +0.3 supports, z ≤ −0.5 contradicts, else context.
- web finding: `supports` (luna only links findings that back the need) or `contradicts` if luna says so.

`uv run python -m bmw_req.pipeline.linker [REQ-0001 ...]`
"""

import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline.requirements import audit

PROMPT_VERSION = "link-v1"


class Link(BaseModel):
    finding_id: int
    contradicts: bool = Field(description="True only if this evidence argues AGAINST the requirement")
    why: str


class LinkResult(BaseModel):
    links: list[Link]


INSTRUCTIONS = """You link evidence to a customer requirement for a BMW successor vehicle.
Candidates are customer-study items (satisfaction scores per model × market) and web findings (cited competitor
advantages, reviews, trends) for the requirement's target markets. Return ONLY candidates that are directly
about the same customer need as the requirement (be selective: typically 1–3 study items per target
market and 0–4 web findings). Same need, not same theme (D-038): a review about seat comfort does not support a
requirement about controls; a rival's rear-seat entertainment does not support a phone-connectivity requirement.
When unsure, leave it out — every web link raises the requirement's score. Set contradicts=true only if the candidate argues against the requirement.
Use only candidate IDs from the input."""


def candidates(conn: sqlite3.Connection, req_id: str, wave: int) -> tuple[list[dict], set[int]]:
    targets = [(t["vehicle_model_id"], t["market_code"]) for t in conn.execute(
        "SELECT vehicle_model_id, market_code FROM requirement_target WHERE requirement_id = ?", (req_id,))]
    linked = {r[0] for r in conn.execute("SELECT finding_id FROM requirement_finding WHERE requirement_id = ?", (req_id,))}
    out = []
    for d, m in targets:
        for f in conn.execute(
            """SELECT id, source_kind, type, title, summary, vehicle_model_id, market_code, category FROM finding
               WHERE source_kind IN ('study', 'web') AND COALESCE(first_wave, 1) <= ?
                 AND (vehicle_model_id = ? OR vehicle_model_id IS NULL) AND (market_code = ? OR market_code IS NULL)""",
            (wave, d, m)):
            if f["id"] not in linked:
                out.append(dict(f))
    uniq = {f["id"]: f for f in out}
    return list(uniq.values()), set(uniq)


def relation_for(conn, fid: int, must_not_lose: bool, contradicts: bool) -> str:
    f = conn.execute("SELECT source_kind, metrics_json FROM finding WHERE id = ?", (fid,)).fetchone()
    if f["source_kind"] != "study":
        return "contradicts" if contradicts else "supports"
    z = json.loads(f["metrics_json"] or "{}").get("z")
    if z is None:
        return "context"
    if must_not_lose:
        return "supports" if z >= 0.3 else ("contradicts" if z <= -0.5 else "context")
    return "supports" if z <= -0.3 else ("contradicts" if z >= 0.5 else "context")


def link(llm: LLM, conn: sqlite3.Connection, req_id: str, wave: int) -> int:
    req = dict(conn.execute("SELECT id, title, description, category, must_not_lose FROM requirement WHERE id = ?",
                            (req_id,)).fetchone())
    cands, ids = candidates(conn, req_id, wave)
    if not cands:
        return 0
    payload = {"requirement": req, "candidates": [
        {k: c[k] for k in ("id", "source_kind", "type", "title", "summary", "vehicle_model_id", "market_code")} for c in cands]}
    res = llm.generate(job="link", tier="fast", instructions=INSTRUCTIONS, input=json.dumps(payload, ensure_ascii=False),
                       schema=LinkResult, reasoning_effort="medium", max_output_tokens=6000, flex=True)
    links = [l for l in res.parsed.links if l.finding_id in ids]
    model = llm.model_for("fast")
    conn.execute("BEGIN IMMEDIATE")
    try:
        added = {}
        for l in links:
            rel = relation_for(conn, l.finding_id, bool(req["must_not_lose"]), l.contradicts)
            conn.execute("INSERT OR IGNORE INTO requirement_finding (requirement_id, finding_id, relation) VALUES (?, ?, ?)",
                         (req_id, l.finding_id, rel))
            added[l.finding_id] = {"relation": rel, "why": l.why}
        if added:
            audit(conn, actor_type="ai", actor_id="pipeline.linker", action="link_findings", entity_type="requirement",
                  entity_id=req_id, field="evidence", new=added, rationale="evidence linker: study items and web findings for target markets",
                  model=model, prompt_ref=PROMPT_VERSION)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(added)


def run(conn: sqlite3.Connection, req_ids: list[str], wave: int, workers: int = 8) -> int:
    def work(rid):
        c = connect()
        return link(LLM(conn=c), c, rid, wave)

    with ThreadPoolExecutor(workers) as pool:
        return sum(pool.map(work, req_ids))


if __name__ == "__main__":
    from bmw_req.pipeline.graph import get_wave

    c = connect()
    ids = sys.argv[1:] or [r[0] for r in c.execute("SELECT id FROM requirement ORDER BY id")]
    print("links added:", run(c, ids, max(get_wave(c), 1)))
