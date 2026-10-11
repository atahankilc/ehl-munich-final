"""Requirement-set quality benchmark: deterministic checks + optional LLM-judge rubric (sol).

`uv run python scripts/benchmark_requirements.py [--judge] [--out data/eval/req_bench.json]`

Deterministic: traceability (every req ≥ 1 finding, every finding ≥ 1 source), evidence mix, numeric targets,
scope red-flag terms, market spread, coverage of the top pain findings per derivative, near-duplicate titles,
evidence levels and proposed priorities. Judge: each requirement rated 1–5 on customer-facing, actionable,
measurable, evidence-grounded, brand/segment fit, evidence-vs-assumption separation.
"""

import argparse
import json
import re
from collections import Counter

from pydantic import BaseModel

from bmw_req.db import connect
from bmw_req.llm import LLM

SCOPE_FLAGS = re.compile(r"\b(price|pricing|cost|homologation|regulat\w*|supplier|emission|type approval|crash|NCAP|"
                         r"business case|margin)\b", re.I)


def deterministic(conn) -> dict:
    reqs = [dict(r) for r in conn.execute("SELECT * FROM requirement WHERE status != 'rejected'")]
    out = {"requirements": len(reqs)}
    kinds, no_find, nums, flags, spread = Counter(), 0, 0, [], Counter()
    for r in reqs:
        ks = {x[0] for x in conn.execute("""SELECT f.source_kind FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
                                             WHERE rf.requirement_id = ? AND rf.relation = 'supports'""", (r["id"],))}
        no_find += not ks
        kinds[len(ks)] += 1
        nums += bool(re.search(r"\d", r["target_metric"] or ""))
        text = " ".join(str(r[k] or "") for k in ("title", "description", "target_metric", "acceptance_criteria"))
        if SCOPE_FLAGS.search(text):
            flags.append((r["id"], SCOPE_FLAGS.findall(text)[:3]))
        spread[conn.execute("SELECT COUNT(*) FROM requirement_target WHERE requirement_id = ?", (r["id"],)).fetchone()[0]] += 1
    out.update({
        "without_supporting_finding": no_find,
        "evidence_kinds_per_req": dict(kinds),
        "numeric_target_rate": round(nums / max(len(reqs), 1), 2),
        "scope_flag_terms": flags,
        "targets_per_req": dict(sorted(spread.items())),
        "findings_without_source": conn.execute(
            "SELECT COUNT(*) FROM finding f WHERE NOT EXISTS (SELECT 1 FROM finding_source s WHERE s.finding_id = f.id)").fetchone()[0],
    })
    # coverage of top-20 pain findings (severity-weighted, all markets) per derivative
    cov = {}
    for d in ("F70", "G60", "G70"):
        rows = conn.execute("""SELECT id, metrics_json FROM finding WHERE vehicle_model_id = ? AND source_kind = 'verbatim'
                               AND polarity != 'like'""", (d,)).fetchall()
        ranked = sorted(rows, key=lambda r: -sum(m["severity_weighted"] for m in json.loads(r["metrics_json"])["by_wave"]["2"]["markets"].values()))[:20]
        linked = {x[0] for x in conn.execute("SELECT finding_id FROM requirement_finding")}
        cov[d] = round(sum(r["id"] in linked for r in ranked) / max(len(ranked), 1), 2)
    out["top20_pain_coverage"] = cov
    out["evidence_levels_targets"] = dict(Counter(r[0] for r in conn.execute("SELECT evidence_level FROM requirement_target")))
    out["proposed_priority_by_market"] = {
        m: dict(Counter(r[0] for r in conn.execute("SELECT proposed_priority FROM requirement_target WHERE market_code = ?", (m,))))
        for m in ("US", "EU", "CN", "RoW")}
    out["fit_results"] = {k: dict(Counter(r[0] for r in conn.execute("SELECT result FROM fit_check WHERE check_type = ?", (k,))))
                          for k in ("brand", "segment", "market", "feasibility")}
    return out


class Rating(BaseModel):
    id: str
    customer_facing: int
    actionable: int
    measurable: int
    evidence_grounded: int
    brand_segment_fit: int
    evidence_vs_assumption: int
    main_weakness: str


class Ratings(BaseModel):
    ratings: list[Rating]


JUDGE = """You are a strict reviewer of customer requirements for BMW successor vehicles (hackathon judge persona:
BMW product management). Rate each requirement 1–5 (5 = excellent) on: customer_facing (customer-perceivable
attribute, no engineering spec/regulation/pricing), actionable (clear what must be achieved), measurable
(target metric + acceptance criteria testable), evidence_grounded (claims match the cited evidence summary),
brand_segment_fit (fits BMW and the segment), evidence_vs_assumption (forward-looking beliefs separated and
honest). Name the main weakness in one sentence. Be critical; 5 is rare."""


def judge(conn) -> dict:
    reqs = []
    for r in conn.execute("SELECT * FROM requirement WHERE status != 'rejected' ORDER BY id"):
        dj = json.loads(r["derivation_json"] or "{}")
        targets = [f"{t[0]}×{t[1]}" for t in conn.execute(
            "SELECT vehicle_model_id, market_code FROM requirement_target WHERE requirement_id = ?", (r["id"],))]
        reqs.append({"id": r["id"], "title": r["title"], "description": r["description"], "targets": targets,
                     "target_metric": r["target_metric"], "acceptance_criteria": r["acceptance_criteria"],
                     "evidence_summary": dj.get("evidence_summary"), "assumptions": r["assumptions"],
                     "uncertainties": r["uncertainties"], "conflicting_evidence": r["conflicting_evidence"]})
    llm = LLM(conn=conn)
    res = llm.generate(job="bench:judge", tier="smart", instructions=JUDGE, input=json.dumps(reqs, ensure_ascii=False),
                       schema=Ratings, reasoning_effort="medium", max_output_tokens=20_000, flex=True)
    ratings = res.parsed.ratings
    dims = ["customer_facing", "actionable", "measurable", "evidence_grounded", "brand_segment_fit", "evidence_vs_assumption"]
    return {"cost": res.cost_usd, "mean": {d: round(sum(getattr(x, d) for x in ratings) / len(ratings), 2) for d in dims},
            "overall": round(sum(getattr(x, d) for x in ratings for d in dims) / (len(ratings) * len(dims)), 2),
            "lowest": sorted([(x.id, sum(getattr(x, d) for d in dims), x.main_weakness) for x in ratings], key=lambda t: t[1])[:6]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--out", default="data/eval/req_bench.json")
    a = ap.parse_args()
    c = connect()
    res = {"deterministic": deterministic(c)}
    if a.judge:
        res["judge"] = judge(c)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
