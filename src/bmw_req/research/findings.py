"""Web findings: group web evidence per (derivative, market, wave) and let luna cluster it into findings.

`uv run python -m bmw_req.research.findings [--only-wave N]` — one LLM call per group, idempotent per group
(audit_event action 'build_web_findings'). Every finding links >= 1 source item of its group (IDs validated);
conflicting items are linked with relation 'contradicts'. Wave-1 and wave-3 items are grouped separately so that
'market event' evidence surfaces as findings with first_wave = 3.
"""

import argparse
import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline.extract import Category

log = logging.getLogger(__name__)
FINDINGS_VERSION = "web-findings-v2"
JOB = "research:findings"

FindingType = Literal["competitor_advantage", "market_trend", "customer_expectation", "review_criticism",
                      "review_praise", "market_profile"]


class WebFinding(BaseModel):
    type: FindingType
    title: str = Field(description="Short, factual title (max ~12 words)")
    summary: str = Field(description="2-4 factual sentences that only restate the cited items; mention conflicts")
    category: Category | None
    scope_level: Literal["market", "derivative"] = Field(
        description="'derivative' if about this BMW model or its direct rivals, 'market' if a market-wide trend/profile")
    supporting_ids: list[int] = Field(description="IDs of the items that support this finding (>= 1)")
    contradicting_ids: list[int] = Field(description="IDs of items that contradict or qualify it (may be empty)")


class FindingsOut(BaseModel):
    findings: list[WebFinding]


INSTRUCTIONS = """You group cited web evidence items into findings for a BMW product-requirements team.
- Merge items that make the same or a closely related point (same rival advantage, same expectation, same
  review theme) into one finding. Aim for roughly one finding per 2-3 items; singletons only for genuinely
  distinct points. One item may support several findings. Use only the given item IDs.
- Finding types: competitor_advantage (a rival offers customers something BMW lacks/does worse), market_trend,
  customer_expectation (what buyers expect now or in 3-5 years), review_criticism / review_praise (professional
  reviews; say which model), market_profile (climate, usage, culture, infrastructure, powertrain mix).
- Summaries are factual and cite nothing beyond the items; no recommendations, no opinions.
- If items disagree (e.g. different figures or verdicts), keep both: put the disagreeing ones in contradicting_ids
  and say so in the summary. Do not hide conflicting evidence.
- Every item should end up in at least one finding."""


def load_groups(conn, only_wave: int | None = None) -> dict[tuple, list[dict]]:
    groups = defaultdict(list)
    for r in conn.execute("SELECT id, trust_tier, vehicle_model_id, market_code, url, published_at, text, quote, meta_json, wave "
                          "FROM source_item WHERE kind = 'web' ORDER BY id"):
        if only_wave is not None and r["wave"] != only_wave:
            continue
        m = json.loads(r["meta_json"] or "{}")
        groups[(r["vehicle_model_id"], r["market_code"], r["wave"])].append({
            "id": r["id"], "tier": r["trust_tier"], "publisher": m.get("publisher"), "date": r["published_at"],
            "evidence_type": m.get("evidence_type"), "category": m.get("category"), "competitor": m.get("competitor"),
            "claim": r["text"], "quote": (r["quote"] or "")[:300], "url": r["url"], "wave": r["wave"],
        })
    return dict(groups)


def group_key(g: tuple) -> str:
    vm, mk, wave = g
    return f"{FINDINGS_VERSION}:{vm or '-'}|{mk}|w{wave}"


def validate(out: FindingsOut, items: list[dict]) -> tuple[list[WebFinding], dict]:
    """Keep only IDs from the group; drop findings without valid support. Returns (findings, stats)."""
    valid = {i["id"] for i in items}
    kept, stats = [], {"dropped_findings": 0, "invalid_ids": 0, "uncovered_items": 0}
    for f in out.findings:
        sup = [i for i in dict.fromkeys(f.supporting_ids) if i in valid]
        con = [i for i in dict.fromkeys(f.contradicting_ids) if i in valid and i not in sup]
        stats["invalid_ids"] += (len(set(f.supporting_ids) | set(f.contradicting_ids)) - len(set(sup) | set(con)))
        if not sup:
            stats["dropped_findings"] += 1
            continue
        kept.append(f.model_copy(update={"supporting_ids": sup, "contradicting_ids": con}))
    covered = {i for f in kept for i in f.supporting_ids + f.contradicting_ids}
    stats["uncovered_items"] = len(valid - covered)
    return kept, stats


def metrics(ids: list[int], by_id: dict[int, dict]) -> dict:
    its = [by_id[i] for i in ids]
    tiers = defaultdict(int)
    for i in its:
        tiers[i["tier"]] += 1
    dates = [i["date"] for i in its if i["date"]]
    return {"n_sources": len(its), "tiers": dict(tiers), "publishers": sorted({i["publisher"] for i in its if i["publisher"]}),
            "newest_date": max(dates) if dates else None}


def build_group(llm: LLM, g: tuple, items: list[dict]):
    vm, mk, wave = g
    header = f"Derivative: {vm or 'none (market-level)'}; market: {mk}; wave: {wave}; {len(items)} items."
    payload = [{k: i[k] for k in ("id", "tier", "publisher", "date", "evidence_type", "category", "competitor", "claim", "quote")}
               for i in items]
    res = llm.generate(job=JOB, tier="fast", instructions=INSTRUCTIONS,
                       input=header + "\nItems:\n" + json.dumps(payload, ensure_ascii=False),
                       schema=FindingsOut, reasoning_effort="low", max_output_tokens=8000)
    return res


def store_group(conn, g: tuple, items: list[dict], findings: list[WebFinding], stats: dict, model: str, usage_id) -> list[int]:
    vm, mk, wave = g
    by_id = {i["id"]: i for i in items}
    ids = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        for f in findings:
            linked = f.supporting_ids + f.contradicting_ids
            scope = "market" if vm is None else f.scope_level   # vehicle_model_id stays = research context
            m = metrics(linked, by_id)
            m["n_supporting"], m["n_contradicting"] = len(f.supporting_ids), len(f.contradicting_ids)
            m["builder"] = FINDINGS_VERSION
            fid = conn.execute(
                """INSERT INTO finding (type, title, summary, scope_level, vehicle_model_id, market_code, metrics_json, created_by,
                   source_kind, polarity, category, first_wave) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'web', 'context', ?, ?)""",
                (f.type, f.title, f.summary, scope, vm, mk, json.dumps(m, ensure_ascii=False),
                 f"ai:{model}", f.category, min(by_id[i]["wave"] for i in linked))).lastrowid
            for i in f.supporting_ids:
                conn.execute("INSERT INTO finding_source (finding_id, source_item_id, quote, relation) VALUES (?, ?, ?, 'supports')",
                             (fid, i, by_id[i]["quote"]))
            for i in f.contradicting_ids:
                conn.execute("INSERT INTO finding_source (finding_id, source_item_id, quote, relation) VALUES (?, ?, ?, 'contradicts')",
                             (fid, i, by_id[i]["quote"]))
            ids.append(fid)
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, rationale, model, prompt_ref)
               VALUES ('ai', 'research.findings', 'build_web_findings', 'finding_group', ?, ?, ?, ?, ?)""",
            (group_key(g), json.dumps({"finding_ids": ids, "n_items": len(items), "llm_usage_id": usage_id, **stats}),
             "Clustered cited web evidence into findings (status: proposed context for derivation).", model, FINDINGS_VERSION))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return ids


def delete_version(conn, version: str) -> int:
    """Remove web findings of an older builder version (only if no requirement links them)."""
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM finding WHERE source_kind = 'web' AND json_extract(metrics_json, '$.builder') = ?", (version,))]
    if not ids:
        return 0
    q = ",".join("?" * len(ids))
    if conn.execute(f"SELECT COUNT(*) FROM requirement_finding WHERE finding_id IN ({q})", ids).fetchone()[0]:
        raise RuntimeError(f"{version} findings are linked to requirements; not deleting")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(f"DELETE FROM finding_source WHERE finding_id IN ({q})", ids)
        conn.execute(f"DELETE FROM finding WHERE id IN ({q})", ids)
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, old_value, rationale)
               VALUES ('system', 'research.findings', 'delete_web_findings', 'finding_group', ?, ?, ?)""",
            (version, json.dumps({"finding_ids": ids}), f"Superseded by {FINDINGS_VERSION} (better clustering)"))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(ids)


def done_groups(conn) -> set[str]:
    return {r["entity_id"] for r in conn.execute("SELECT entity_id FROM audit_event WHERE action = 'build_web_findings'")}


def build_all(conn, llm_factory=None, only_wave: int | None = None, workers: int = 4) -> dict:
    llm_factory = llm_factory or (lambda: LLM(conn=connect()))
    groups = load_groups(conn, only_wave)
    done = done_groups(conn)
    todo = {g: its for g, its in groups.items() if group_key(g) not in done}
    summary = {}

    def work(g):
        llm = llm_factory()
        return g, build_group(llm, g, todo[g]), llm.model_for("fast")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for g, res, model in pool.map(work, list(todo)):
            findings, stats = validate(res.parsed, todo[g])
            ids = store_group(conn, g, todo[g], findings, stats, model, res.usage_id)
            summary[group_key(g)] = {"items": len(todo[g]), "findings": len(ids), **stats, "cost_usd": res.cost_usd}
            log.info("%s: %s", group_key(g), summary[group_key(g)])
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-wave", type=int)
    ap.add_argument("--delete-version", help="first delete unlinked web findings of this older builder version")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.delete_version:
        print("deleted", delete_version(connect(), args.delete_version))
    print(json.dumps(build_all(connect(), only_wave=args.only_wave), indent=1))


if __name__ == "__main__":
    main()
