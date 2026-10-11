"""Requirement definition pipeline (D-048): define → specify → couple at one checkpoint.

`uv run python -m bmw_req.definition.run --checkpoint cp1`                    all three stages
`uv run python -m bmw_req.definition.run --checkpoint cp1 --stage specify`    one stage (needs its upstream run)
`uv run python -m bmw_req.definition.run --checkpoint cp1 --stage specify --repair`   re-ask flagged metrics only
`uv run python -m bmw_req.definition.run --checkpoint cp1 --stage define --pilot 5`
    pilot: the first N items only, printed, nothing stored (no run, no rows). LLM calls are cached, so a full run whose
    first batch is identical reuses the pilot's answer for free. Pilot first, read the output, then run fully.
"""

from __future__ import annotations

import argparse
import json

from bmw_req.db import connect

STAGES = ("define", "specify", "couple")


def run_stage(conn, cp: str, stage: str, pilot: int | None = None, repair: bool = False, redo: str | None = None,
              only: list[str] | None = None) -> dict:
    if stage == "define":
        from bmw_req.definition.define import run
    elif stage == "specify":
        from bmw_req.definition.specify import run
        return run(conn, cp, pilot=pilot, repair=repair, redo=redo, only=only)
    else:
        from bmw_req.definition.couple import run
    return run(conn, cp, pilot=pilot)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"], required=True)
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--pilot", type=int)
    ap.add_argument("--repair", action="store_true", help="specify only: re-ask requirements whose metric is flagged")
    ap.add_argument("--redo", choices=["flagged", "all"], help="specify only: new run on top of the latest one at this checkpoint")
    ap.add_argument("--only", nargs="*", help="specify only: restrict to these requirement keys (pilot)")
    a = ap.parse_args()
    conn = connect()
    spent = lambda s: conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE job LIKE ?",  # noqa: E731
                                   (f"{s}:%",)).fetchone()[0]
    for stage in [a.stage] if a.stage else STAGES:
        before = spent(stage)
        out = run_stage(conn, a.checkpoint, stage, a.pilot, a.repair, a.redo, a.only)
        out["cost_usd"] = round(spent(stage) - before, 4)
        print(json.dumps({stage: out}, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
