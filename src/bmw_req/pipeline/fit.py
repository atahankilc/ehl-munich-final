"""Fit checks per requirement target (D-008, D-009, D-030): brand, segment, market, feasibility.

luna checks everything; every `warn`/`fail` is re-checked by sol, whose verdict is final (D-010 tiering).
- brand `fail` blocks approval unless the PM overrides with a rationale (AGENTS rule 8).
- feasibility is realization context only (Q-010 option b): shown to the PM, never blocking or scored.

`uv run python -m bmw_req.pipeline.fit [REQ-0001 ...]` — checks requirements without fit checks.
"""

import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline.requirements import audit
from bmw_req.portfolio import LINES, line_of

PROMPT_VERSION = "fit-v1"
Result = Literal["pass", "warn", "fail"]


class TargetFit(BaseModel):
    vehicle_model_id: str
    market_code: str
    market: Result
    market_rationale: str = Field(description="How climate, usage, culture, infrastructure of this market affect the need")
    feasibility: Result
    feasibility_rationale: str = Field(description="Can the derivative's platform/successor and a plant serving this market realize it in time? Context only, no engineering specs")


class FitResult(BaseModel):
    brand: Result
    brand_rationale: str = Field(description="Cite the guardrail that applies")
    segment: Result
    segment_rationale: str
    targets: list[TargetFit]


INSTRUCTIONS = """You check whether a proposed customer requirement for a BMW successor vehicle fits.
Return pass / warn / fail with a short, specific rationale for:
- brand: BMW brand fit, judged ONLY against the given brand guardrails (pass/warn/fail lists). fail only if it
  clearly contradicts a fail guardrail (e.g. paywalling hardware already in the car, touch-only core driving
  controls, soft numb chassis as default). Comfort-only features without driving-pleasure link are at most warn.
- segment: fit with the vehicle line's segment and its customers (no budget features in luxury, no luxury
  gadgets that break the compact segment's positioning).
- per target market: does the market profile (climate, usage, culture, infrastructure, powertrain mix) support
  the need? warn if the need is weaker or different there, fail if it contradicts the market.
- per target feasibility (context only): given the platform, its successor (Neue Klasse timing) and plants
  serving that market, is realization plausible by successor launch? Use only the given reference data; when
  data is missing say so and use warn. Never output component specifications.
Be strict but fair; most solid requirements pass."""

RECHECK = """\n\nSECOND OPINION: a first reviewer returned the verdicts in `first_pass`. Re-examine every warn/fail
carefully and return your own final verdicts for all checks (you may confirm, soften or harden them)."""


def reference_context(conn: sqlite3.Connection, req: dict, targets: list[dict]) -> dict:
    derivs = sorted({t["vehicle_model_id"] for t in targets})
    models = {r["id"]: {k: r[k] for k in r.keys() if r[k] is not None}
              for r in conn.execute(f"SELECT * FROM vehicle_model WHERE id IN ({','.join('?' * len(derivs))})", derivs)}
    platforms = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM platform")}
    production = [dict(r) for r in conn.execute(
        f"""SELECT p.*, pl.name plant_name, pl.country plant_country, pl.platforms_json, pl.powertrains_json pl_powertrains,
                   pl.nk_ready_from FROM production p JOIN plant pl ON pl.id = p.plant_id
            WHERE p.vehicle_model_id IN ({','.join('?' * len(derivs))})""", derivs)]
    markets = {r["code"]: {k: r[k] for k in ("name", "climate", "usage_patterns", "cultural_expectations",
                                              "infrastructure", "powertrain_mix") if r[k]}
               for r in conn.execute("SELECT * FROM market")}
    brand = conn.execute("SELECT positioning, core_values_json, guardrails_json FROM brand WHERE id = 'BMW'").fetchone()
    line = line_of(derivs[0])
    return {
        "requirement": {k: req[k] for k in ("id", "title", "description", "category", "target_metric", "horizon",
                                            "kano_class", "effort")},
        "targets": [{"vehicle_model_id": t["vehicle_model_id"], "market_code": t["market_code"],
                     "realization": t["realization"]} for t in targets],
        "vehicle_line": line, "segment": LINES[line]["segment"],
        "brand": dict(brand) if brand else None, "models": models,
        "platforms": {k: v for k, v in platforms.items() if any(v["id"] == m.get("platform_id") or
                      v["id"] == platforms.get(m.get("platform_id"), {}).get("successor_platform_id") for m in models.values())},
        "production": production, "markets": {t["market_code"]: markets.get(t["market_code"]) for t in targets},
    }


def check(llm: LLM, conn: sqlite3.Connection, req: dict, targets: list[dict]) -> tuple[FitResult, list]:
    ctx = reference_context(conn, req, targets)
    usage = []
    first = llm.generate(job="fit:luna", tier="fast", instructions=INSTRUCTIONS, input=json.dumps(ctx, ensure_ascii=False, default=str),
                         schema=FitResult, reasoning_effort="low", max_output_tokens=6000, flex=True)
    usage.append((first.usage_id, llm.model_for("fast")))
    res = first.parsed
    # feasibility is non-blocking context (D-030): its warnings don't trigger the sol re-check
    flagged = [res.brand, res.segment] + [t.market for t in res.targets]
    if any(r != "pass" for r in flagged):
        second = llm.generate(job="fit:sol", tier="smart", instructions=INSTRUCTIONS + RECHECK,
                              input=json.dumps({**ctx, "first_pass": res.model_dump()}, ensure_ascii=False, default=str),
                              schema=FitResult, reasoning_effort="medium", max_output_tokens=8000, flex=True)
        usage.append((second.usage_id, llm.model_for("smart")))
        res = second.parsed
    return res, usage


def store(conn: sqlite3.Connection, req_id: str, res: FitResult, model: str, targets: list[dict]) -> None:
    valid = {(t["vehicle_model_id"], t["market_code"]) for t in targets}
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = []
        for t in res.targets:
            if (t.vehicle_model_id, t.market_code) not in valid:
                continue
            rows += [
                (req_id, t.vehicle_model_id, t.market_code, "brand", res.brand, res.brand_rationale),
                (req_id, t.vehicle_model_id, t.market_code, "segment", res.segment, res.segment_rationale),
                (req_id, t.vehicle_model_id, t.market_code, "market", t.market, t.market_rationale),
                (req_id, t.vehicle_model_id, t.market_code, "feasibility", t.feasibility, t.feasibility_rationale),
            ]
        conn.executemany(
            """INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, rationale, checked_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""", [(*r, f"ai:{model}") for r in rows])
        audit(conn, actor_type="ai", actor_id="pipeline.fit", action="fit_check", entity_type="requirement",
              entity_id=req_id, field="fit_checks", new=res.model_dump(), model=model, prompt_ref=PROMPT_VERSION)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def run(conn: sqlite3.Connection, req_ids: list[str] | None = None, workers: int = 6) -> int:
    if req_ids is None:
        req_ids = [r[0] for r in conn.execute(
            "SELECT id FROM requirement WHERE id NOT IN (SELECT DISTINCT requirement_id FROM fit_check) ORDER BY id")]

    def work(rid):
        c = connect()
        llm = LLM(conn=c)
        req = dict(c.execute("SELECT * FROM requirement WHERE id = ?", (rid,)).fetchone())
        targets = [dict(t) for t in c.execute("SELECT * FROM requirement_target WHERE requirement_id = ?", (rid,))]
        res, usage = check(llm, c, req, targets)
        store(c, rid, res, usage[-1][1], targets)
        return rid

    with ThreadPoolExecutor(workers) as pool:
        done = list(pool.map(work, req_ids))
    return len(done)


if __name__ == "__main__":
    c = connect()
    print("checked", run(c, sys.argv[1:] or None))
