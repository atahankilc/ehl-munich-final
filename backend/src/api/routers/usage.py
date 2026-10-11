"""Model usage and API spend, read-only (the Audit panel's Usage tab).

GET /api/usage?limit=     budget state, every logged model call grouped by pipeline → step → model / tier (calls,
                          failures, tokens, cost, per checkpoint), the price table, and the latest calls

Source: `llm_usage`, written by the budget-guarded client (`bmw_req.llm.client`, the only path to OpenAI): a worst-case
reservation before each call, settled with the response's actual token counts × `pricing.py` after it. Costs are
therefore computed here from list prices, not read from OpenAI's bill; `reconciliation:*` rows are manual estimates.
"""

from __future__ import annotations

import re
from collections import defaultdict

from fastapi import APIRouter, Query

from api.deps import db
from bmw_req.app_settings import budget_limits
from bmw_req.llm import budget
from bmw_req.llm.pricing import FLEX_FACTOR, all_prices

router = APIRouter(prefix="/api/usage", tags=["usage"])

# Which pipeline a job belongs to, by its name (first match wins).
PIPELINES = [
    ("definition", "Requirement definition (D-048)", r"^(define|specify|couple)\b|^research:benchmarks|^structure\.benchmarks"),
    ("structure", "Structure & context (D-043)",
     r"^(classify|contextualize|areas)\b|^embed:(comments:galaxy|signals:v4|nodes|insights|themes)"),
    ("sources", "Sources: web research & price-list ingest (D-026, D-031)", r"^research:|^ingest:|^websearch"),
    ("legacy", "Earlier pipeline (D-022 – D-033, superseded)", r".*"),
]
CHECKPOINT = re.compile(r":(cp1|cp2)\b")
WAVE = re.compile(r":(w\d|p\d|G\d\d|F\d\d|[1-7] Series)\b")


def pipeline_of(job: str) -> str:
    return next(key for key, _, pat in PIPELINES if re.search(pat, job))


def step_of(job: str) -> str:
    """The step without its checkpoint / car / wave suffix: 'specify:cp1' → 'specify', 'derive:5 Series:w1' → 'derive'."""
    s = CHECKPOINT.sub("", job)
    s = WAVE.sub("", s)
    return s.strip(":") or job


@router.get("")
def usage(limit: int = Query(60, ge=1, le=500)) -> dict:
    with db() as conn:
        rows = conn.execute("""SELECT id, created_at, settled_at, job, demo, kind, model, service_tier, status, reserved_usd,
                                      cost_usd, input_tokens, cached_tokens, cache_write_tokens, output_tokens, reasoning_tokens,
                                      search_calls, response_id, error FROM llm_usage ORDER BY id""").fetchall()
        spent, committed = budget.spent_usd(conn), budget.committed_usd(conn)

    groups: dict[tuple, dict] = {}
    for r in rows:
        pipe, step = pipeline_of(r["job"]), step_of(r["job"])
        g = groups.setdefault((pipe, step, r["model"]), {
            "pipeline": pipe, "step": step, "model": r["model"], "flex_calls": 0, "calls": 0, "failed": 0, "reserved": 0,
            "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "search_calls": 0,
            "usd": 0.0, "failed_usd": 0.0, "first": r["created_at"], "last": r["created_at"], "by_checkpoint": defaultdict(float),
            "manual": r["job"].startswith("reconciliation")})
        g["calls"] += 1
        g["flex_calls"] += r["service_tier"] == "flex"
        g["failed"] += r["status"] == "failed"
        g["reserved"] += r["status"] == "reserved"
        for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "search_calls"):
            g[k] += r[k] or 0
        cost = (r["reserved_usd"] if r["status"] == "reserved" else r["cost_usd"]) or 0.0
        g["usd"] += cost
        if r["status"] == "failed":
            g["failed_usd"] += cost   # an unexpected error keeps the worst-case reservation (conservative, not billed tokens)
        g["last"] = r["created_at"]
        cp = CHECKPOINT.search(r["job"])
        g["by_checkpoint"][cp.group(1) if cp else "—"] += cost

    pipes = []
    for key, label, _ in PIPELINES:
        steps = sorted((g for g in groups.values() if g["pipeline"] == key), key=lambda g: g["first"])
        if not steps:
            continue
        for g in steps:
            g["usd"] = round(g["usd"], 4)
            g["failed_usd"] = round(g["failed_usd"], 4)
            g["by_checkpoint"] = {k: round(v, 4) for k, v in g["by_checkpoint"].items()}
        pipes.append({"key": key, "label": label, "usd": round(sum(g["usd"] for g in steps), 4),
                      "calls": sum(g["calls"] for g in steps), "failed": sum(g["failed"] for g in steps), "steps": steps})

    recent = [{"id": r["id"], "at": r["created_at"], "job": r["job"], "pipeline": pipeline_of(r["job"]), "model": r["model"],
               "tier": r["service_tier"], "status": r["status"], "usd": round((r["cost_usd"] if r["status"] != "reserved" else r["reserved_usd"]) or 0, 5),
               "input_tokens": r["input_tokens"], "cached_tokens": r["cached_tokens"], "output_tokens": r["output_tokens"],
               "reasoning_tokens": r["reasoning_tokens"], "search_calls": r["search_calls"], "response_id": r["response_id"],
               "error": (r["error"] or "")[:240] or None}
              for r in reversed(rows[-limit:])]

    return {
        "budget": {"spent": round(spent, 4), "committed": round(committed, 4),
                   "confirm_above": budget_limits().confirm_above_usd, "stop_at": budget_limits().stop_at_usd},
        "by_model": {m: round(sum(g["usd"] for g in groups.values() if g["model"] == m), 4)
                     for m in sorted({g["model"] for g in groups.values()})},
        "totals": {"calls": len(rows), "failed": sum(r["status"] == "failed" for r in rows),
                   "input_tokens": sum(r["input_tokens"] or 0 for r in rows), "cached_tokens": sum(r["cached_tokens"] or 0 for r in rows),
                   "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
                   "first": rows[0]["created_at"] if rows else None, "last": rows[-1]["created_at"] if rows else None},
        "prices": {m: {"input": p.input, "cached_input": p.cached_input, "output": p.output} for m, p in all_prices().items()},
        "flex_factor": FLEX_FACTOR,
        "pipelines": pipes,
        "recent": recent,
        "method": "Cost = the response's token counts × the list prices in pricing.py (Flex −50 %, cached input at the cached "
                  "rate), computed when each call settles. It is not read from OpenAI's bill; reconciliation rows are manual estimates.",
    }
