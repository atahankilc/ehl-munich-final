"""Scoring robustness: rank stability per market under random ±25 % weight perturbations (read-only, no LLM).

`uv run python scripts/benchmark_scoring.py [--wave 2] [--trials 40]`

Reports per market: mean Kendall tau vs the default ranking, share of top-5 that stays top-5, and how often a
target's proposed priority band changes. High stability = the priority order is driven by the evidence, not by
the exact weights.
"""

import argparse
import itertools
import json
import random
from collections import defaultdict

from bmw_req.db import connect
from bmw_req.pipeline import scoring


def kendall_tau(a: list, b: list) -> float:
    pos = {x: i for i, x in enumerate(b)}
    conc = disc = 0
    for x, y in itertools.combinations(a, 2):
        s = pos[y] - pos[x]   # x precedes y in `a`; concordant if it also precedes in `b`
        conc += s > 0
        disc += s < 0
    n = conc + disc
    return (conc - disc) / n if n else 1.0


def scores(conn, wave, weights):
    reqs = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM requirement WHERE status != 'rejected'")}
    tg = defaultdict(list)
    for t in conn.execute("SELECT * FROM requirement_target"):
        if t["requirement_id"] in reqs:
            tg[t["requirement_id"]].append(dict(t))
    out = defaultdict(dict)
    for rid, ts in tg.items():
        for t in ts:
            b = scoring.score_target(conn, reqs[rid], t, wave, weights, len(ts))
            out[t["market_code"]][(rid, t["vehicle_model_id"])] = b["score"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, default=2)
    ap.add_argument("--trials", type=int, default=40)
    a = ap.parse_args()
    conn = connect()
    base = scores(conn, a.wave, scoring.DEFAULT_WEIGHTS)
    rng = random.Random(7)
    stats = defaultdict(lambda: {"tau": [], "top5": [], "band_change": []})
    for _ in range(a.trials):
        w = {k: v * rng.uniform(0.75, 1.25) for k, v in scoring.DEFAULT_WEIGHTS.items()}
        pert = scores(conn, a.wave, w)
        for m, sc in base.items():
            r0 = sorted(sc, key=lambda k: -sc[k])
            r1 = sorted(pert[m], key=lambda k: -pert[m][k])
            stats[m]["tau"].append(kendall_tau(r0, r1))
            stats[m]["top5"].append(len(set(r0[:5]) & set(r1[:5])) / min(5, len(r0)))
            stats[m]["band_change"].append(sum(scoring.priority_for(sc[k]) != scoring.priority_for(pert[m][k]) for k in sc) / len(sc))
    res = {m: {"targets": len(base[m]), "mean_kendall_tau": round(sum(s["tau"]) / len(s["tau"]), 3),
               "top5_retained": round(sum(s["top5"]) / len(s["top5"]), 3),
               "band_change_rate": round(sum(s["band_change"]) / len(s["band_change"]), 3)} for m, s in stats.items()}
    print(json.dumps(res, indent=1))
    with open("data/eval/scoring_robustness.json", "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
