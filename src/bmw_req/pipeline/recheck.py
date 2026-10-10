"""Second pass on out-of-scope verdicts with the reasoning model (Q-019, D-023).

`uv run python -m bmw_req.pipeline.recheck G60 [--workers 4] [--cap-usd 0.3]`
Only verbatims with in_scope = 0 and no recheck yet. A flip to in_scope adds signals (same extractor
version, provenance via signal.llm_usage_id) and writes an audit_event with before/after.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bmw_req.db import connect
from bmw_req.llm import LLM, BudgetExceeded, budget
from bmw_req.pipeline.extract import EXTRACTOR_VERSION, INSTRUCTIONS, BatchResult, check_batch, quote_ok
from bmw_req.pipeline.run_extract import insert_signal

BATCH_SIZE = 25
RECHECK_INSTRUCTIONS = INSTRUCTIONS + """

SECOND PASS: a first pass judged every verbatim below as out of scope; its reason is given as
first_pass_reason. Re-examine each one. Many verbatims mix dealer, service, sales or charging-network
content with a real product signal — extract every in-scope signal even if most of the verbatim is out of
scope (e.g. "the car only fast charges to 80%, which I hated" is a Range & Charging signal even when a
salesperson is also mentioned; confusion about how a vehicle function works is a difficult_to_use signal).
Keep in_scope=false only if there is truly no customer-facing product signal."""


def pending(conn, derivative: str) -> list[dict]:
    rows = conn.execute(
        """SELECT s.id, s.external_id, s.text, s.meta_json, e.out_of_scope_reason
           FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
           WHERE s.vehicle_model_id = ? AND e.extractor_version = ? AND e.in_scope = 0
             AND e.recheck_llm_usage_id IS NULL
           ORDER BY s.external_id""",
        (derivative, EXTRACTOR_VERSION),
    ).fetchall()
    return [
        {"source_item_id": r["id"], "id": r["external_id"], "text": r["text"] or "",
         "engine": json.loads(r["meta_json"])["engine"], "first_pass_reason": r["out_of_scope_reason"]}
        for r in rows
    ]


def recheck_batch(llm: LLM, chunk: list[dict], job: str):
    payload = [{"verbatim_id": v["id"], "engine": v["engine"], "first_pass_reason": v["first_pass_reason"],
                "text": v["text"]} for v in chunk]
    res = llm.generate(
        job=job, tier="smart", instructions=RECHECK_INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False), schema=BatchResult,
        reasoning_effort="low", max_output_tokens=12_000, flex=True,
        prompt_cache_options={"mode": "explicit"},
    )
    return res.parsed, res


def store(conn, chunk, batch: BatchResult, usage_id: int, model: str) -> dict:
    by_id = {v["id"]: v for v in chunk}
    flipped = signals = unverified = confirmed = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        seen = set()
        for r in batch.results:
            v = by_id.get(r.verbatim_id)
            if v is None or r.verbatim_id in seen:
                continue
            seen.add(r.verbatim_id)
            if r.in_scope and r.signals:
                conn.execute(
                    "UPDATE verbatim_extraction SET in_scope = 1, out_of_scope_reason = NULL, recheck_llm_usage_id = ?"
                    " WHERE source_item_id = ? AND extractor_version = ?",
                    (usage_id, v["source_item_id"], EXTRACTOR_VERSION),
                )
                for s in r.signals:
                    ok = quote_ok(s.quote, v["text"])
                    unverified += not ok
                    insert_signal(conn, v["source_item_id"], s, ok, usage_id)
                    signals += 1
                conn.execute(
                    """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, field,
                                                old_value, new_value, rationale, model, prompt_ref)
                       VALUES ('ai', 'pipeline.recheck', 'recheck_scope', 'verbatim_extraction', ?, 'in_scope',
                               ?, ?, 'Q-019 second pass on out-of-scope verdict', ?, ?)""",
                    (f"{v['id']}:{EXTRACTOR_VERSION}", json.dumps({"in_scope": 0, "reason": v["first_pass_reason"]}),
                     json.dumps({"in_scope": 1, "signals": len(r.signals)}), model, f"{EXTRACTOR_VERSION}+recheck"),
                )
                flipped += 1
            else:
                conn.execute(
                    "UPDATE verbatim_extraction SET recheck_llm_usage_id = ? WHERE source_item_id = ? AND extractor_version = ?",
                    (usage_id, v["source_item_id"], EXTRACTOR_VERSION),
                )
                confirmed += 1
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"flipped": flipped, "confirmed": confirmed, "signals": signals, "unverified_quotes": unverified}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("derivative")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cap-usd", type=float, default=0.3)
    args = ap.parse_args()
    conn = connect()
    todo = pending(conn, args.derivative)
    chunks = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    start = budget.committed_usd(conn)
    print(f"{len(todo)} out-of-scope verbatims → {len(chunks)} calls; committed ${start:.4f}", flush=True)
    job = f"recheck:{args.derivative}:{EXTRACTOR_VERSION}"

    def work(chunk):
        llm = LLM(conn=connect())
        if budget.committed_usd(llm.conn) - start > args.cap_usd:
            raise BudgetExceeded(f"run cap ${args.cap_usd} reached")
        batch, res = recheck_batch(llm, chunk, job)
        checks = check_batch(chunk, batch)
        return {"cost": res.cost_usd, "missing": len(checks["missing_ids"]),
                **store(llm.conn, chunk, batch, res.usage_id, llm.model_for("smart"))}

    t0, totals = time.time(), {"flipped": 0, "confirmed": 0, "signals": 0, "unverified_quotes": 0, "missing": 0, "failed": 0}
    with ThreadPoolExecutor(args.workers) as pool:
        for n, f in enumerate(as_completed([pool.submit(work, c) for c in chunks]), 1):
            try:
                r = f.result()
            except Exception as e:
                totals["failed"] += 1
                print(f"[{n}/{len(chunks)}] FAILED {e!r:.300}", flush=True)
                continue
            for k in totals:
                totals[k] += r.get(k, 0)
            print(f"[{n}/{len(chunks)}] {time.time() - t0:.0f}s ${r['cost']:.4f} | {totals}", flush=True)
    print(f"DONE in {time.time() - t0:.0f}s: run spend ${budget.spent_usd(conn) - start:.4f}, "
          f"total spent ${budget.spent_usd(conn):.4f} | {totals}", flush=True)


if __name__ == "__main__":
    main()
