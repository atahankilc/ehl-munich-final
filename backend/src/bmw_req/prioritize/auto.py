"""Automatic re-score after PM actions (D-050 "As built"): re-run the deterministic `prioritize` stage at a checkpoint
and every later one, in checkpoint order, so a band that now differs from the PM's confirmed band becomes a proposal
right away. Free (no LLM) and ~0.1 s per checkpoint. The API runs it in a background worker (`api/rescore.py`);
tests call `rescore` synchronously.

Only checkpoints that already have a prioritize run are re-run — an auto re-score never starts a stage the PM hasn't.
"""

from __future__ import annotations

from bmw_req import checkpoints as C
from bmw_req.prioritize import ensure
from bmw_req.prioritize import score as P
from bmw_req.structure.events import log

ACTOR = "structure.prioritize"


def checkpoints_from(cp: str | None) -> list[str]:
    """`cp` and every later checkpoint (all of them when `cp` is None / unknown)."""
    start = C.BY_ID[cp].position if cp in C.BY_ID else 0
    return [c.id for c in sorted(C.CHECKPOINTS, key=lambda c: c.position) if c.position >= start]


def rescore(conn, cp: str | None, trigger: str, include_self: bool = True) -> list[dict]:
    """Re-run prioritize at `cp` (unless `include_self` is False — the input there didn't change) and every later
    checkpoint. Returns one entry per checkpoint: {checkpoint, run_id, proposals} or {checkpoint, skipped}."""
    ensure(conn)
    cps = checkpoints_from(cp)
    if cp in C.BY_ID and not include_self:
        cps = cps[1:]
    out = []
    for c in cps:
        if not C.latest_run(conn, c, "prioritize"):
            out.append({"checkpoint": c, "skipped": "no prioritize run yet"})
            continue
        try:
            r = P.run(conn, c, actor=ACTOR, trigger=f"auto:{trigger}")
        except C.CheckpointError as e:
            out.append({"checkpoint": c, "skipped": str(e)})
            continue
        out.append({"checkpoint": c, "run_id": r["run_id"], "proposals": r["proposals"]})
    log(conn, "prioritize", "auto_rescore", {"trigger": trigger, "from": cp, "include_self": include_self, "runs": out},
        next((x["run_id"] for x in reversed(out) if "run_id" in x), None), P.SCHEME)
    return out
