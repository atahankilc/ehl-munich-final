"""Wave orchestration as a LangGraph graph (D-015, D-013, D-027).

    advance(wave) : open_wave → derive (per vehicle line, incremental) → link_evidence (all requirements:
                    study items + web findings now visible) → fit_checks (new requirements)
                    → prioritize (snapshot + change proposals) → close

Ingest itself happened up front; every source item carries the wave in which it becomes visible (simulation,
Q-012). "Opening" a wave makes its evidence visible to derivation and scoring. AI only proposes: new
requirements arrive as `proposed` and as `new_requirement` change proposals in the PM's inbox (waves ≥ 2).

`uv run python -m bmw_req.pipeline.graph advance 1`
"""

import sys
from typing import TypedDict

from langgraph.graph import END, StateGraph

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline import fit, linker, requirements, scoring
from bmw_req.pipeline.requirements import audit
from bmw_req.pipeline.waves import WAVES
from bmw_req.portfolio import LINES

DERIVE_N = {1: {"5 Series": 18, "7 Series": 14, "1 Series": 12}, "later": 5}


class WaveState(TypedDict, total=False):
    wave: int
    lines: list[str]
    initiated_by: str
    new_requirements: list[str]
    run_id: int
    log: list[str]


def get_wave(conn) -> int:
    r = conn.execute("SELECT value FROM app_state WHERE key = 'current_wave'").fetchone()
    return int(r["value"]) if r else 0


def set_wave(conn, wave: int, actor: str) -> None:
    old = get_wave(conn)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES ('current_wave', ?)", (str(wave),))
    audit(conn, actor_type="human" if actor != "system" else "system", actor_id=actor, action="open_wave",
          entity_type="ingest_wave", entity_id=str(wave), old=old, new=wave,
          rationale=f"{WAVES[wave]['label']} (simulated {WAVES[wave]['simulated_date']}): {WAVES[wave]['description']}")
    conn.execute("COMMIT")


def node_open(state: WaveState) -> WaveState:
    conn = connect()
    set_wave(conn, state["wave"], state.get("initiated_by", "system"))
    return {"log": state.get("log", []) + [f"opened {WAVES[state['wave']]['label']}"]}


def node_derive(state: WaveState) -> WaveState:
    """Derive per vehicle line, then consolidate same-need drafts across lines into portfolio requirements."""
    conn = connect()
    llm = LLM(conn=conn)
    wave, log, drafts = state["wave"], list(state.get("log", [])), []
    for line in state.get("lines") or list(LINES):
        ctx, allowed = requirements.build_context(conn, line, wave)
        n = DERIVE_N[1][line] if wave == 1 else DERIVE_N["later"]
        result, res = requirements.derive(llm, ctx, n=n, job=f"derive:{line}:w{wave}", effort="high", wave=wave)
        ok, problems = requirements.validate(result, allowed, LINES[line]["derivatives"])
        drafts += [(line, d) for d in ok]
        log.append(f"{line}: {len(ok)} draft(s) (${res.cost_usd:.3f}{', cached' if res.cached else ''})"
                   + (f"; {len(problems)} validation note(s)" if problems else ""))
    merged = [d for _, d in drafts]
    if len({line for line, _ in drafts}) > 1:
        # iterate: a merged portfolio requirement can still match a draft the first pass left alone
        items = drafts
        for p in range(3):
            merged, notes = requirements.consolidate(llm, items, job=f"consolidate:w{wave}:p{p}")
            log += [f"  {n}" for n in notes]
            if not notes:
                break
            items = [(requirements.lines_of(d), d) for d in merged]
        log.append(f"portfolio consolidation: {len(drafts)} drafts → {len(merged)} requirements")
    if wave > 1 and merged:
        # Q-022: a later wave must not re-create a need the backlog (any line) already holds
        matches = requirements.match_existing(llm, merged, requirements.existing_for_match(conn), job=f"match_existing:w{wave}")
        dup = [(merged[m.draft_index], m) for m in matches if m.existing_id]
        if dup:
            log += requirements.propose_extensions(conn, dup, wave=wave, model=llm.model_for("smart"))
        merged = [merged[m.draft_index] for m in matches if not m.existing_id]
        log.append(f"dedup vs existing backlog: {len(dup)} draft(s) → extend proposals, {len(merged)} new")
    ids = requirements.store(conn, merged, model=llm.model_for("smart"), usage_id=None, wave=wave)
    if wave > 1 and ids:
        conn.execute("BEGIN IMMEDIATE")
        for rid in ids:
            # say honestly whether the draft rests on evidence that arrived in this wave
            new = conn.execute(
                """SELECT COUNT(*) FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
                   WHERE rf.requirement_id = ? AND rf.relation = 'supports' AND f.first_wave = ?""", (rid, wave)).fetchone()[0]
            reason = (f"New evidence in {WAVES[wave]['label']} ({new} new finding(s)) supports a need the existing "
                      "requirements don't cover" if new else
                      f"Raised in {WAVES[wave]['label']} from earlier evidence that no existing requirement cites "
                      "(no new finding in this wave)")
            conn.execute(
                """INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                   VALUES (?, 'status', NULL, 'proposed', ?, 'new_requirement')""", (rid, reason))
        conn.execute("COMMIT")
    log.append(f"stored {len(ids)} new requirement(s): {', '.join(ids)}")
    return {"new_requirements": ids, "log": log}


def node_link(state: WaveState) -> WaveState:
    conn = connect()
    ids = [r[0] for r in conn.execute("SELECT id FROM requirement WHERE status != 'rejected' ORDER BY id")]
    n = linker.run(conn, ids, state["wave"])
    return {"log": state.get("log", []) + [f"evidence linker: {n} study/web link(s) added"]}


def node_fit(state: WaveState) -> WaveState:
    conn = connect()
    ids = sorted(set(state.get("new_requirements") or []) | set(fit.unchecked_requirements(conn)))
    n = fit.run(conn, ids)
    return {"log": state.get("log", []) + [f"fit checks for {n} requirement(s)"]}


def node_prioritize(state: WaveState) -> WaveState:
    conn = connect()
    run_id = scoring.run_prioritization(conn, wave=state["wave"], trigger="new_evidence",
                                        initiated_by=state.get("initiated_by", "system"),
                                        note=f"{WAVES[state['wave']]['label']}")
    props = conn.execute("SELECT COUNT(*) FROM change_proposal WHERE run_id = ?", (run_id,)).fetchone()[0]
    return {"run_id": run_id, "log": state.get("log", []) + [f"prioritization run {run_id}: {props} priority change proposal(s)"]}


def build_graph():
    g = StateGraph(WaveState)
    g.add_node("open_wave", node_open)
    g.add_node("derive", node_derive)
    g.add_node("link_evidence", node_link)
    g.add_node("fit_checks", node_fit)
    g.add_node("prioritize", node_prioritize)
    g.set_entry_point("open_wave")
    g.add_edge("open_wave", "derive")
    g.add_edge("derive", "link_evidence")
    g.add_edge("link_evidence", "fit_checks")
    g.add_edge("fit_checks", "prioritize")
    g.add_edge("prioritize", END)
    return g.compile()


def advance(wave: int, initiated_by: str = "system", lines: list[str] | None = None) -> WaveState:
    return build_graph().invoke({"wave": wave, "initiated_by": initiated_by, "lines": lines or list(LINES), "log": []})


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "advance":
        out = advance(int(sys.argv[2]), lines=sys.argv[3:] or None)
        print("\n".join(out["log"]))
