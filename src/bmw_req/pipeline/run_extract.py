"""Run signal extraction over ingested verbatims, in parallel Flex calls, storing results (D-022).

`uv run python -m bmw_req.pipeline.run_extract G60 [--ids-file f] [--workers 16] [--cap-usd 1.0]`
Idempotent: verbatims that already have a row for EXTRACTOR_VERSION are skipped.
"""

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

from bmw_req.db import connect
from bmw_req.llm import LLM, BudgetExceeded, budget
from bmw_req.pipeline.extract import EXTRACTOR_VERSION, check_batch, extract_batch, quote_ok

BATCH_SIZE = 25
RETRIES = 4


def pending(conn, derivative: str, ids: list[str] | None) -> list[dict]:
    rows = conn.execute(
        """SELECT s.id, s.external_id, s.text, s.meta_json FROM source_item s
           WHERE s.kind = 'feedback' AND s.vehicle_model_id = ?
             AND NOT EXISTS (SELECT 1 FROM verbatim_extraction e
                             WHERE e.source_item_id = s.id AND e.extractor_version = ?)
           ORDER BY s.external_id""",
        (derivative, EXTRACTOR_VERSION),
    ).fetchall()
    out = [
        {"source_item_id": r["id"], "id": r["external_id"], "text": r["text"] or "",
         "engine": json.loads(r["meta_json"])["engine"]}
        for r in rows
    ]
    if ids is not None:
        out = [v for v in out if v["id"] in set(ids)]
    return out


def store(conn, chunk: list[dict], batch, usage_id: int | None, model: str) -> dict:
    by_id = {v["id"]: v for v in chunk}
    stored = signals = unverified = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        seen = set()
        for r in batch.results:
            v = by_id.get(r.verbatim_id)
            if v is None or r.verbatim_id in seen:
                continue   # invented or duplicate ID: ignore; missing ones stay pending
            seen.add(r.verbatim_id)
            conn.execute(
                "INSERT INTO verbatim_extraction (source_item_id, extractor_version, in_scope, out_of_scope_reason,"
                " llm_usage_id) VALUES (?, ?, ?, ?, ?)",
                (v["source_item_id"], EXTRACTOR_VERSION, int(r.in_scope), r.out_of_scope_reason, usage_id),
            )
            for s in r.signals:
                ok = quote_ok(s.quote, v["text"])
                unverified += not ok
                conn.execute(
                    "INSERT INTO signal (source_item_id, extractor_version, category, topic, feedback_type, severity,"
                    " need_statement, quote, quote_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (v["source_item_id"], EXTRACTOR_VERSION, s.category, s.topic, s.feedback_type, s.severity,
                     s.need_statement, s.quote, int(ok)),
                )
                signals += 1
            stored += 1
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, model, prompt_ref)
               VALUES ('ai', 'pipeline.extract', 'extract_signals', 'llm_usage', ?, ?, ?, ?)""",
            (str(usage_id), json.dumps({"verbatims": stored, "signals": signals, "unverified_quotes": unverified}),
             model, EXTRACTOR_VERSION),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"stored": stored, "signals": signals, "unverified_quotes": unverified}


_local = threading.local()


def _llm() -> LLM:
    if not hasattr(_local, "llm"):
        _local.llm = LLM(conn=connect())
    return _local.llm


def process(chunk: list[dict], job: str, cap_usd: float, start_usd: float) -> dict:
    llm = _llm()
    for attempt in range(RETRIES):
        if budget.committed_usd(llm.conn) - start_usd > cap_usd:
            raise BudgetExceeded(f"run cap ${cap_usd} reached")
        try:
            batch, res = extract_batch(llm, chunk, job=job)
            break
        except (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError, openai.APIConnectionError) as e:
            if attempt == RETRIES - 1:
                return {"error": repr(e)[:300], "ids": [v["id"] for v in chunk]}
            time.sleep(15 * 2 ** attempt + random.random() * 5)
    checks = check_batch(chunk, batch)
    stats = store(llm.conn, chunk, batch, res.usage_id, llm.model_for("fast"))
    return {"cost": res.cost_usd, "checks": checks, **stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("derivative")
    ap.add_argument("--ids-file", help="JSON list of verbatim IDs to restrict to")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--cap-usd", type=float, default=1.0, help="abort when this run's committed spend passes this")
    args = ap.parse_args()

    conn = connect()
    ids = json.load(open(args.ids_file)) if args.ids_file else None
    todo = pending(conn, args.derivative, ids)
    chunks = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    start = budget.committed_usd(conn)
    print(f"{len(todo)} verbatims pending → {len(chunks)} calls, {args.workers} workers; committed ${start:.4f}", flush=True)
    job = f"extract:{args.derivative}:{EXTRACTOR_VERSION}"

    t0 = time.time()
    totals = {"done": 0, "signals": 0, "unverified": 0, "missing": 0, "invented": 0, "failed": 0}
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(process, c, job, args.cap_usd, start) for c in chunks]
        for n, f in enumerate(as_completed(futures), 1):
            try:
                r = f.result()
            except BudgetExceeded as e:
                print(f"ABORT: {e}", flush=True)
                for other in futures:
                    other.cancel()
                break
            except Exception as e:   # e.g. structured-output parse failure; the batch stays pending
                totals["failed"] += 1
                print(f"[{n}/{len(chunks)}] FAILED {e!r:.300}", flush=True)
                continue
            if "error" in r:
                totals["failed"] += 1
                print(f"[{n}/{len(chunks)}] FAILED {r['error']}", flush=True)
                continue
            totals["done"] += r["stored"]
            totals["signals"] += r["signals"]
            totals["unverified"] += r["unverified_quotes"]
            totals["missing"] += len(r["checks"]["missing_ids"])
            totals["invented"] += len(r["checks"]["invented_ids"])
            print(f"[{n}/{len(chunks)}] {time.time() - t0:.0f}s ${r['cost']:.4f} | run ${budget.committed_usd(conn) - start:.4f}"
                  f" | {totals}", flush=True)
    print(f"DONE in {time.time() - t0:.0f}s: run spend ${budget.spent_usd(conn) - (start):.4f}, "
          f"total spent ${budget.spent_usd(conn):.4f}, committed ${budget.committed_usd(conn):.4f} | {totals}", flush=True)
    if totals["failed"] or totals["missing"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
