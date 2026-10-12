"""Stage `gate` (D-050): brand / segment fit per requirement and line, market / feasibility per line × market target,
for the definition-layer requirements (`def_requirement` + its ladder). The only LLM step of prioritization.

Reuses the score-v3 fit check (now `prioritize/fitcheck.py`): its instructions, the luna → sol re-check (`luna_then_sol`: every
brand / segment / market warn or fail is re-examined by sol, whose verdict is final; feasibility is non-blocking
context, D-030) and the same reference data (brand guardrails, platforms, plants, market profiles), re-shaped:
- the static part (instructions + portfolio reference: brand, the three lines with their segments, platforms, plants,
  markets) is identical for every call, so it is sent first and served from the prompt cache;
- the per-call part is one requirement: statement, metric, the recommended ladder level per line × market;
- segment is judged per car line (a requirement can target the 1 and the 7 Series at once).
Brand `fail` blocks a PM approve unless overridden with a rationale (D-008); the gate also feeds the market-fit
modifier of prio-v1 (pass +2 / warn −5 / fail −10). cp2 re-checks only new or re-versioned requirements (or changed
targets); the rest is carried forward from the cp1 gate run.

`uv run python -m bmw_req.prioritize.run --checkpoint cp1 --stage gate [--pilot 5]`
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.definition.define import generate
from bmw_req.llm import LLM
from bmw_req.prioritize.fitcheck import INSTRUCTIONS as FIT_INSTRUCTIONS, Result, luna_then_sol
from bmw_req.portfolio import LINES
from bmw_req.prioritize.score import _loads, targets_of
from bmw_req.structure.events import log

PROMPT_VERSION = "gate-v1"
Line = Literal["1 Series", "5 Series", "7 Series"]
SEGMENT_NOTE = {"1 Series": "premium compact — young, urban, dynamic premium entry; quality and driving fun, never a value car",
                "5 Series": "business / executive — 'business athlete': dynamics plus long-distance comfort; China LWB adds "
                            "chauffeured rear comfort",
                "7 Series": "luxury flagship — craftsmanship, rear-seat luxury, quiet effortless technology, driver-and-chauffeur "
                            "duality; never budget or de-contented features"}


class SegmentFit(BaseModel):
    line: Line
    segment: Result
    segment_rationale: str = Field(description="≤ 30 words, name the segment expectation that applies")


class TargetGate(BaseModel):
    line: Line
    market: Literal["EU", "US", "CN", "RoW"]
    market_fit: Result
    market_rationale: str = Field(description="≤ 30 words: climate, usage, culture, infrastructure of this market")
    feasibility: Result
    feasibility_rationale: str = Field(description="≤ 30 words: platform / successor timing / plant serving this market; no engineering specs")


class GateResult(BaseModel):
    brand: Result
    brand_rationale: str = Field(description="≤ 40 words, cite the guardrail that applies")
    segments: list[SegmentFit]
    targets: list[TargetGate]


INSTRUCTIONS = FIT_INSTRUCTIONS + """

ADAPTED FOR THE REQUIREMENT-DEFINITION LAYER. You get ONE requirement: its statement, decision type, Kano class,
customer-experienced metric and the recommended target level per car line × market. Judge:
- brand once, against BMW's premium positioning and the guardrails in `reference.brand`. Anything that cheapens the
  brand (de-contenting, cost-down materials, paywalls for fitted hardware, gimmicks) fails; a requirement to keep an
  existing BMW strength normally passes.
- segment once PER CAR LINE in the requirement's targets, against `reference.lines[line].segment` and its guardrails
  (`brand.guardrails_json.segments`): 1 Series premium compact, 5 Series business/executive, 7 Series luxury. A feature
  that is ordinary for a compact can be a fail for the 7 Series if it reads as budget; a luxury gadget can be a warn
  for the 1 Series. Judge the requirement as it would be realised for that line.
- market and feasibility per listed target, using `reference.markets` and the platform/plant data.
Return exactly one `segments` entry per line and one `targets` entry per listed target. Be concise."""


def reference(conn) -> dict:
    """Static portfolio reference for every gate call (sorted, deterministic → identical prompt prefix)."""
    brand = conn.execute("SELECT positioning, core_values_json, guardrails_json FROM brand WHERE id = 'BMW'").fetchone()
    cars = [d for cfg in LINES.values() for d in cfg["derivatives"]]
    q = ",".join("?" * len(cars))
    models = {r["id"]: {k: r[k] for k in ("line", "body", "segment", "platform_id", "generation", "sop", "powertrains_json",
                                         "market_variants_json", "profile_json") if r[k]}
              for r in conn.execute(f"SELECT * FROM vehicle_model WHERE id IN ({q}) ORDER BY id", cars)}
    production = [{k: r[k] for k in ("vehicle_model_id", "plant", "country", "market_variant", "markets_served_json",
                                     "platforms_json", "nk_ready_from") if r[k]}
                  for r in conn.execute(f"""SELECT p.*, pl.name plant, pl.country, pl.platforms_json, pl.nk_ready_from FROM production p
                                            JOIN plant pl ON pl.id = p.plant_id WHERE p.vehicle_model_id IN ({q})
                                            ORDER BY p.vehicle_model_id, p.plant_id""", cars)]
    platforms = {r["id"]: {k: r[k] for k in ("powertrains_json", "introduced", "phase_out", "successor_platform_id") if r[k]}
                 for r in conn.execute("SELECT * FROM platform WHERE id IN ('NK', 'CLAR', 'FAAR') ORDER BY id")}
    markets = {r["code"]: {k: r[k] for k in ("name", "climate", "usage_patterns", "cultural_expectations", "infrastructure",
                                             "powertrain_mix") if r[k]} for r in conn.execute("SELECT * FROM market ORDER BY code")}
    return {"brand": dict(brand) if brand else None,
            "lines": {ln: {"derivatives": cfg["derivatives"], "segment": SEGMENT_NOTE[ln]} for ln, cfg in LINES.items()},
            "models": models, "platforms": platforms, "production": production, "markets": markets}


def req_view(req: dict, spec: dict | None) -> dict:
    metric = _loads(spec["metric_json"], {}) if spec else {}
    rec = {}
    for r in _loads(spec["ladder_json"], []) if spec else []:
        lv = r.get(r.get("recommended") or "target") or {}
        rec[f"{r['line']}:{r['market']}"] = f"{r.get('recommended')}: {lv.get('text')}"
    return {"key": req["key"], "title": req["title"], "statement": req["statement"], "domain": req["domain"],
            "aspects": _loads(req["aspects_json"], []), "decision_type": req["decision_type"], "today_status": req["today_status"],
            "horizon": req["horizon"], "kano": req["kano"], "metric": metric.get("name"), "recommended_level": rec,
            "targets": [{"line": ln, "market": m} for ln, m in targets_of(req, spec)]}


def flagged(r: GateResult) -> bool:
    return any(x != "pass" for x in [r.brand] + [s.segment for s in r.segments] + [t.market_fit for t in r.targets])


def check(llm: LLM, instructions: str, view: dict) -> tuple[GateResult, list]:
    return luna_then_sol(llm, job="gate", instructions=instructions, ctx={"requirement": view}, schema=GateResult,
                         flagged=flagged, generate=lambda **kw: generate(llm, **kw), sol_effort="low")


def rows_for(view: dict, res: GateResult, by: str, model: str) -> list[tuple]:
    """One brand / segment / market / feasibility row per target (missing verdicts → warn 'not returned')."""
    seg = {s.line: s for s in res.segments}
    tg = {(t.line, t.market): t for t in res.targets}
    out = []
    for t in view["targets"]:
        ln, m = t["line"], t["market"]
        s, g = seg.get(ln), tg.get((ln, m))
        out += [(ln, m, "brand", res.brand, res.brand_rationale),
                (ln, m, "segment", s.segment if s else "warn", s.segment_rationale if s else "segment verdict not returned"),
                (ln, m, "market", g.market_fit if g else "warn", g.market_rationale if g else "market verdict not returned"),
                (ln, m, "feasibility", g.feasibility if g else "warn", g.feasibility_rationale if g else "feasibility verdict not returned")]
    return [(*r, by, model) for r in out]


def run(conn, cp: str, actor: str = "system", pilot: int | None = None, only: list[str] | None = None, workers: int = 4) -> dict:
    drun, srun = C.latest_run(conn, cp, "define"), C.latest_run(conn, cp, "specify")
    if drun is None or srun is None:
        raise C.CheckpointError(f"Run 'define' and 'specify' at {cp} first")
    reqs = [dict(r) for r in conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY key", (drun["id"],))]
    specs = {r["req_key"]: dict(r) for r in conn.execute("SELECT * FROM def_spec WHERE run_id = ?", (srun["id"],))}
    views = {r["key"]: req_view(r, specs.get(r["key"])) for r in reqs}
    version = {r["key"]: r["version"] for r in reqs}
    run_id = parent = None
    if not pilot:
        conn.execute("BEGIN IMMEDIATE")
        run_id = C.start_run(conn, cp, "gate", actor)
        conn.execute("COMMIT")
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    carried: dict[str, list] = {}
    if parent:   # cp2: carry verdicts of unchanged requirements whose targets are the same
        prev: dict[str, list] = {}
        for r in conn.execute("SELECT * FROM prio_fit WHERE run_id = ? ORDER BY id", (parent,)):
            prev.setdefault(r["req_key"], []).append(dict(r))
        for k, rows in prev.items():
            if k in views and rows[0]["req_version"] == version[k] and \
                    {(r["line"], r["market"]) for r in rows} == {(t["line"], t["market"]) for t in views[k]["targets"]}:
                carried[k] = rows
    todo = [k for k in views if k not in carried and (not only or k in only)][: pilot or None]
    instructions = INSTRUCTIONS + "\n\nREFERENCE (static portfolio data):\n" + json.dumps(reference(conn), ensure_ascii=False, default=str)
    if run_id:
        log(conn, "gate", "start", {"requirements": len(views), "to_check": len(todo), "carried": len(carried)}, run_id)

    def work(k):
        c = connect()
        llm = LLM(conn=c)
        try:
            res, usage = check(llm, instructions, views[k])
            return k, res, usage, None
        except Exception as e:   # one failing requirement must not abort the run
            return k, None, [], repr(e)[:300]
        finally:
            c.close()

    results = []
    with ThreadPoolExecutor(workers) as pool:   # one `check` event per finished requirement = Agent-panel progress
        for fut in as_completed([pool.submit(work, k) for k in todo]):
            k, res, usage, err = fut.result()
            results.append((k, res, usage, err))
            if run_id:
                log(conn, "gate", "check", {"key": k, "checked": len(results), "to_check": len(todo), "error": err,
                                            "brand": res.brand if res else None,
                                            "segments": {x.line: x.segment for x in res.segments} if res else None,
                                            "markets": {f"{t.line}:{t.market}": t.market_fit for t in res.targets} if res else None,
                                            "by": ("sol" if len(usage) > 1 else "luna") if res else None},
                    run_id, usage[-1][1] if usage else None)
    if pilot:
        return {"pilot": [{"key": k, "view": {x: views[k][x] for x in ("title", "decision_type", "kano", "targets")},
                           "verdict": res.model_dump() if res else None, "rechecked": len(u) > 1, "error": err}
                          for k, res, u, err in results]}
    failed = [k for k, res, _, err in results if res is None]
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = {"pass": 0, "warn": 0, "fail": 0}
        rechecked = 0
        for k, res, usage, err in results:
            if res is None:
                continue
            by = "sol" if len(usage) > 1 else "luna"
            rechecked += len(usage) > 1
            rows = rows_for(views[k], res, by, usage[-1][1])
            conn.executemany("""INSERT INTO prio_fit (run_id, req_key, req_version, line, market, check_type, result, rationale, checked_by, model)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", [(run_id, k, version[k], *r) for r in rows])
        for k, rows in carried.items():
            conn.executemany("""INSERT INTO prio_fit (run_id, req_key, req_version, line, market, check_type, result, rationale, checked_by, model)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                             [(run_id, k, r["req_version"], r["line"], r["market"], r["check_type"], r["result"], r["rationale"],
                               f"carried:{r['checked_by']}", r["model"]) for r in rows])
        dist: dict[str, dict] = {}
        for r in conn.execute("SELECT check_type, result, COUNT(*) n FROM prio_fit WHERE run_id = ? GROUP BY 1, 2", (run_id,)):
            dist.setdefault(r["check_type"], {})[r["result"]] = r["n"]
        brand_by_req = {}
        for r in conn.execute("SELECT req_key, result FROM prio_fit WHERE run_id = ? AND check_type = 'brand'", (run_id,)):
            brand_by_req[r["req_key"]] = r["result"]
        for v in brand_by_req.values():
            n[v] = n.get(v, 0) + 1
        stats = {"requirements": len(views), "checked": len(todo) - len(failed), "carried": len(carried), "failed": failed,
                 "rechecked_by_sol": rechecked, "brand_by_requirement": n, "rows_by_check": dist, "prompt": PROMPT_VERSION,
                 "upstream": {"define": drun["id"], "specify": srun["id"]}}
        log(conn, "gate", "finished", stats, run_id)
        C.finish_run(conn, run_id, stats)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}
