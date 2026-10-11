"""Build the demo states end to end (simulated ~2-year process, Q-012 / D-027).

`uv run python scripts/demo_build.py`  (needs snapshot 'evidence' = all evidence ingested, no requirements)

Saves snapshots:
- wave1 : wave 1 done, no PM decisions → for a LIVE demo where the PM reviews from scratch
- demo  : wave 1 → scripted PM review → wave 2 → PM decides proposals → wave 3 → the full history to explore

The scripted PM decisions are clearly attributed to the demo PM persona with rationales; they stand in for
a human and are labelled as scripted in their rationale.
"""

import json
import subprocess
import sys
from pathlib import Path

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline import challenge, graph
from bmw_req import service

PM = "Atahan (PM)"
TAG = "[scripted demo decision] "


def sh(*args):
    subprocess.run([sys.executable, str(Path(__file__).with_name("demo_state.py")), *args], check=True)


def pick(conn, sql, *params):
    r = conn.execute(sql, params).fetchone()
    return r[0] if r else None


def pm_review_wave1(conn):
    """Confirm AI priorities on the 5 Series core targets, approve strong ones, reject one, challenge one."""
    log = []
    for d, m in [("G60", "US"), ("G68", "CN"), ("G60", "EU")]:
        for r in conn.execute("""SELECT requirement_id, proposed_priority FROM requirement_target
                                 WHERE vehicle_model_id = ? AND market_code = ? AND priority IS NULL""", (d, m)).fetchall():
            service.set_priority(conn, r[0], d, m, r[1], PM, TAG + "Reviewed the score breakdown; AI proposal confirmed.")
    log.append("confirmed AI priorities on G60×US, G68×CN, G60×EU")
    # approve the three best-evidenced requirements on G60×US (E1/E2 and Must)
    best = [r[0] for r in conn.execute(
        """SELECT requirement_id FROM requirement_target WHERE vehicle_model_id = 'G60' AND market_code = 'US'
           AND evidence_level IN ('E1', 'E2') ORDER BY score DESC LIMIT 3""")]
    for rid in best:
        try:
            service.set_status(conn, rid, "approved", PM, TAG + "Strong multi-channel US evidence; fits brand; approve for concept phase.")
            log.append(f"approved {rid}")
        except service.ActionError as e:
            log.append(f"could not approve {rid}: {e}")
    # defer the weakest RoW-only-ish requirement
    weakest = pick(conn, """SELECT requirement_id FROM requirement_target GROUP BY requirement_id ORDER BY MAX(score) ASC LIMIT 1""")
    if weakest:
        service.set_status(conn, weakest, "deferred", PM, TAG + "Evidence too thin across all targets; revisit after the next feedback wave.")
        log.append(f"deferred {weakest}")
    # challenge the China requirement with web-only evidence
    cn = pick(conn, """SELECT t.requirement_id FROM requirement_target t JOIN requirement r ON r.id = t.requirement_id
                       WHERE t.market_code = 'CN' AND r.status = 'proposed' ORDER BY t.score DESC LIMIT 1""")
    if cn:
        out = challenge.challenge(conn, LLM(conn=conn), cn,
                                  "China has no verbatims here — how do we know G68 customers really want this, and "
                                  "would it still fit BMW if we copy local competitors?", PM)
        log.append(f"challenged {cn}: verdict {out['answer']['verdict']}, ${out['cost']:.3f}")
        props = conn.execute("SELECT id, kind FROM change_proposal WHERE requirement_id = ? AND status = 'open'", (cn,)).fetchall()
        for p in props[:1]:
            service.decide_proposal(conn, p[0], True, PM, TAG + "The AI's revision makes the China evidence gap explicit; accepted.")
            log.append(f"accepted challenge proposal {p[0]} ({p[1]})")
        service.set_status(conn, cn, "proposed", PM, TAG + "Challenge answered; keep as proposed until the customer study arrives.")
    return log


def pm_decide_inbox(conn):
    log = []
    for p in conn.execute("SELECT id, kind, requirement_id, proposed_value FROM change_proposal WHERE status = 'open' ORDER BY id").fetchall():
        if p["kind"] == "priority":
            accept = p["proposed_value"] != "Could"   # PM keeps downgrades to Could under review
            service.decide_proposal(conn, p["id"], accept, PM, TAG + (
                "New study/feedback evidence justifies the move." if accept else
                "Not downgrading to Could on one wave of data; keep and watch."))
        elif p["kind"] == "new_requirement":
            service.decide_proposal(conn, p["id"], True, PM, TAG + "New evidence-backed need; add to the backlog as proposed.")
        elif p["kind"] == "extend":
            service.decide_proposal(conn, p["id"], True, PM, TAG + "Same need as the existing requirement; extend it rather than keep a duplicate.")
        else:
            continue
        log.append(f"decided proposal {p['id']} ({p['kind']})")
    return log


def main():
    sh("restore", "evidence")
    print("\n".join(graph.advance(1, initiated_by=PM)["log"]))
    sh("save", "wave1")
    conn = connect()
    print("\n".join(pm_review_wave1(conn)))
    print("\n".join(graph.advance(2, initiated_by=PM)["log"]))
    print("\n".join(pm_decide_inbox(connect())))
    print("\n".join(graph.advance(3, initiated_by=PM)["log"]))
    sh("save", "demo")


if __name__ == "__main__":
    main()
