"""Run the web research plan: `uv run python -m bmw_req.research.run [--only-wave N] [--pilot] [--cap-usd X] [--task ID ...]`

Parallel (<= 6 workers), idempotent (a task with a 'web_research' audit_event is skipped), budget-capped.
Stores source_item(kind='web') rows and one audit_event per task (queries, cited URLs, counts).
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from bmw_req.db import connect
from bmw_req.llm import LLM, BudgetExceeded
from bmw_req.research.agents import AGENT_VERSION, AGENTS, UA, AgentResult, Task, clean_url, verify_quote
from bmw_req.research.plan import PILOT_TASK_IDS, build_plan

log = logging.getLogger(__name__)
JOB_PREFIX = "research"
MAX_WORKERS = 6


def web_ref(url: str, claim: str) -> str:
    return "web:" + hashlib.sha1((url + claim).encode()).hexdigest()[:12]


def norm_date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", s.strip())
    if not m:
        return None
    y, mo, d = m.groups()
    return y + (f"-{int(mo):02d}" if mo else "") + (f"-{int(d):02d}" if mo and d else "")


def research_spend(conn) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END), 0) FROM llm_usage "
        "WHERE job LIKE ?", (f"{JOB_PREFIX}:%",)).fetchone()[0]


def done_task_ids(conn) -> set[str]:
    return {r["entity_id"] for r in conn.execute(
        "SELECT entity_id FROM audit_event WHERE action = 'web_research' AND entity_type = 'research_task'")}


def execute(task: Task, verify: bool = True) -> tuple[AgentResult, list[int | None]]:
    """Worker: one agent call (own DB connection) + quote verification. No DB writes besides llm_usage."""
    llm = LLM(conn=connect())
    try:
        res = AGENTS[task.agent](llm, task)
    finally:
        llm.conn.close()
    verified = []
    if verify:
        with httpx.Client(follow_redirects=True, timeout=8.0,
                          headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}) as client:
            verified = [verify_quote(clean_url(it.url), it.quote, client=client) for it in res.kept]
    else:
        verified = [None] * len(res.kept)
    return res, verified


def store(conn, res: AgentResult, verified: list[int | None], batch_id: int | None = None) -> list[int]:
    """Persist kept items + the task's audit event in one short transaction. Idempotent on (kind, ref)."""
    t = res.task
    ids = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        if batch_id is None:
            kind = "competitor_event" if t.wave > 1 else "web_refresh"
            desc = f"web research wave {t.wave} ({AGENT_VERSION})"
            row = conn.execute("SELECT id FROM ingest_batch WHERE kind = ? AND description = ?", (kind, desc)).fetchone()
            batch_id = row["id"] if row else conn.execute(
                "INSERT INTO ingest_batch (kind, description) VALUES (?, ?) RETURNING id", (kind, desc)).fetchone()[0]
        for it, qv in zip(res.kept, verified):
            url = clean_url(it.url)
            ref = web_ref(url, it.claim)
            meta = {
                "publisher": it.publisher, "evidence_type": it.evidence_type, "competitor": it.competitor,
                "models": it.vehicle_models, "category": it.category, "task_id": t.id, "agent": t.agent,
                "agent_version": AGENT_VERSION, "quote_verified": qv, "query": t.focus, "item_market": it.market_code,
                "llm_usage_id": res.usage_id, "model": res.model,
            }
            conn.execute(
                """INSERT OR IGNORE INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code, url,
                   published_at, text, quote, meta_json, ingest_batch_id, wave)
                   VALUES ('web', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ref, t.id, it.trust_tier, t.vehicle_model_id, t.market_code, url, norm_date(it.published_date),
                 it.claim, it.quote, json.dumps(meta, ensure_ascii=False), batch_id, t.wave))
            ids.append(conn.execute("SELECT id FROM source_item WHERE kind = 'web' AND ref = ?", (ref,)).fetchone()["id"])
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, rationale, model, prompt_ref)
               VALUES ('ai', ?, 'web_research', 'research_task', ?, ?, ?, ?, ?)""",
            (f"agent:{t.agent}", t.id, json.dumps({
                "queries": res.queries, "cited_urls": sorted(set(res.cited.values())),
                "kept_urls": [clean_url(i.url) for i in res.kept], "dropped_urls": [i.url for i in res.dropped],
                "n_kept": len(res.kept), "n_dropped_uncited": len(res.dropped), "source_item_ids": ids,
                "quote_verified": verified, "wave": t.wave, "vehicle_model_id": t.vehicle_model_id,
                "market_code": t.market_code, "llm_usage_id": res.usage_id, "cost_usd": res.cost_usd,
            }, ensure_ascii=False), f"Web research task: {t.focus}", res.model, AGENT_VERSION))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return ids


def reverify(conn, only_status=(0, None)) -> dict:
    """Re-run quote verification (free, no LLM) for web items whose quote_verified is in `only_status`."""
    rows = conn.execute("SELECT id, url, quote, meta_json FROM source_item WHERE kind = 'web'").fetchall()
    rows = [r for r in rows if json.loads(r["meta_json"]).get("quote_verified") in only_status]
    changes = {}
    with httpx.Client(follow_redirects=True, timeout=8.0, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}) as client:
        for r in rows:
            v = verify_quote(r["url"], r["quote"], client=client)
            if v != json.loads(r["meta_json"]).get("quote_verified"):
                changes[r["id"]] = v
    conn.execute("BEGIN IMMEDIATE")
    try:
        for sid, v in changes.items():
            conn.execute("UPDATE source_item SET meta_json = json_set(meta_json, '$.quote_verified', ?) WHERE id = ?", (v, sid))
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, rationale)
               VALUES ('system', 'research.run', 'reverify_quotes', 'source_item', 'web', ?, ?)""",
            (json.dumps({"checked": len(rows), "changed": changes}), "Re-checked web quotes against fetched pages"))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"checked": len(rows), "changed": len(changes)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-wave", type=int)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--cap-usd", type=float, default=4.5, help="stop submitting when research spend reaches this")
    ap.add_argument("--task", nargs="*", help="run only these task ids")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--reverify", action="store_true", help="only re-check quotes of unverified/unfetchable items")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    conn = connect()
    if args.reverify:
        print(reverify(conn))
        return
    tasks = build_plan()
    if args.pilot:
        tasks = [t for t in tasks if t.id in PILOT_TASK_IDS]
    if args.task:
        tasks = [t for t in tasks if t.id in set(args.task)]
    if args.only_wave is not None:
        tasks = [t for t in tasks if t.wave == args.only_wave]
    done = done_task_ids(conn)
    todo = [t for t in tasks if t.id not in done]
    log.info("plan: %d tasks selected, %d already done, %d to run; research spend so far $%.4f",
             len(tasks), len(tasks) - len(todo), len(todo), research_spend(conn))

    # Worst case per task ~ $0.04 search + ~$0.02 tokens; keep a margin under the cap.
    per_task_margin = 0.08
    totals = {"kept": 0, "dropped": 0, "verified": 0, "unverified": 0, "unfetchable": 0, "failed": 0}
    with ThreadPoolExecutor(max_workers=min(args.workers, MAX_WORKERS)) as pool:
        futures, queue = {}, list(todo)
        while queue or futures:
            while queue and len(futures) < args.workers:
                if research_spend(conn) + per_task_margin * (len(futures) + 1) > args.cap_usd:
                    log.warning("cap $%.2f reached; %d tasks not started", args.cap_usd, len(queue))
                    queue = []
                    break
                t = queue.pop(0)
                futures[pool.submit(execute, t)] = t
            if not futures:
                break
            fut = next(as_completed(futures))
            t = futures.pop(fut)
            try:
                res, verified = fut.result()
            except BudgetExceeded as e:
                log.error("budget guard: %s", e)
                queue = []
                totals["failed"] += 1
                continue
            except Exception as e:  # noqa: BLE001 - keep the batch going, task stays not-done
                log.error("task %s failed: %r", t.id, e)
                totals["failed"] += 1
                continue
            ids = store(conn, res, verified)
            totals["kept"] += len(res.kept)
            totals["dropped"] += len(res.dropped)
            totals["verified"] += sum(1 for v in verified if v == 1)
            totals["unverified"] += sum(1 for v in verified if v == 0)
            totals["unfetchable"] += sum(1 for v in verified if v is None)
            log.info("%-22s kept %d dropped %d verified %s ids %s $%.4f", t.id, len(res.kept), len(res.dropped),
                     verified, ids, res.cost_usd)
    log.info("done: %s; research spend $%.4f", totals, research_spend(conn))
    if totals["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
