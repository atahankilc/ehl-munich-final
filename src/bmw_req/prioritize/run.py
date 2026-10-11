"""Prioritization pipeline (D-050): gate → prioritize at one checkpoint.

`uv run python -m bmw_req.prioritize.run --checkpoint cp1`                       gate, then prioritize
`uv run python -m bmw_req.prioritize.run --checkpoint cp1 --stage prioritize`    re-score only (free, deterministic)
`uv run python -m bmw_req.prioritize.run --checkpoint cp1 --stage gate --pilot 5`
    pilot: the first N requirements, verdicts printed, nothing stored. LLM calls are cached, so the full run reuses them.
`--report` prints the compact distribution / top-N report of the latest prioritize run at the checkpoint.
cp2 needs a completed run of the same stage at cp1 (checkpoint lineage, D-041).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from bmw_req import checkpoints as C
from bmw_req.db import connect

STAGES = ("gate", "prioritize")
REPORT_TARGETS = ("5 Series:US", "5 Series:CN", "7 Series:US", "7 Series:CN", "1 Series:EU")


def report(conn, cp: str, top: int = 5) -> dict:
    r = C.latest_run(conn, cp, "prioritize")
    if not r:
        return {"error": f"no prioritize run at {cp}"}
    rows = [dict(x) for x in conn.execute("SELECT * FROM prio_score WHERE run_id = ? ORDER BY line, market, rank", (r["id"],))]
    by = defaultdict(list)
    for x in rows:
        by[f"{x['line']}:{x['market']}"].append(x)
    out = {"run_id": r["id"], "stats": json.loads(r["stats_json"]), "top": {}}
    for lm in REPORT_TARGETS:
        out["top"][lm] = []
        for x in by.get(lm, [])[:top]:
            b = json.loads(x["breakdown_json"])
            fs = sorted(((k, f) for k, f in b["factors"].items() if f["points"]), key=lambda kf: -kf[1]["points"])
            out["top"][lm].append(f"{x['score']:5.1f} {x['band']:6} {b['evidence_level']} {x['req_key']} | "
                                  + ", ".join(f"{k} {f['points']:.1f}" for k, f in fs[:3])
                                  + (f" | mods {b['modifiers']}" if any(b["modifiers"].values()) else "")
                                  + (f" | {','.join(json.loads(x['flags_json']))}" if x["flags_json"] != "[]" else ""))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"], required=True)
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--pilot", type=int, help="gate only: check the first N requirements, print, store nothing")
    ap.add_argument("--only", nargs="*", help="gate pilot: restrict to these requirement keys")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    conn = connect()
    if a.report:
        print(json.dumps(report(conn, a.checkpoint), indent=1, ensure_ascii=False))
        return
    spent = lambda: conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE job LIKE 'gate:%'").fetchone()[0]  # noqa: E731
    for stage in [a.stage] if a.stage else STAGES:
        before = spent()
        if stage == "gate":
            from bmw_req.prioritize.gate import run
            out = run(conn, a.checkpoint, pilot=a.pilot, only=a.only)
        else:
            from bmw_req.prioritize.score import run
            out = run(conn, a.checkpoint)
        out["cost_usd"] = round(spent() - before, 4)
        print(json.dumps({stage: out}, indent=1, ensure_ascii=False, default=str))
        if a.pilot:
            break


if __name__ == "__main__":
    main()
