"""D-014 pilot: 50 G60 US verbatims (luna) → 5 requirements (sol). Measures real tokens and cost.

Usage: uv run python scripts/pilot.py   — results in data/pilot/. Aborts if pilot spend would pass PILOT_CAP_USD.
"""

import json
import random
import sys
import time
from pathlib import Path

from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req.llm import LLM, budget
from bmw_req.pipeline.derive import check_derivation, derive
from bmw_req.pipeline.extract import check_batch, extract_batch

SEED = 42
PER_CHANNEL = {"Source B": 20, "Source A": 10, "Source C": 10, "Source D": 10}
BATCH_SIZE = 25
PILOT_CAP_USD = 1.00
JOB = "pilot"


def spend_line(conn, start):
    return f"pilot so far ${budget.committed_usd(conn) - start:.4f} | total committed ${budget.committed_usd(conn):.4f}"


def main():
    out = get_settings().data_dir / "pilot"
    out.mkdir(parents=True, exist_ok=True)
    conn = connect()
    llm = LLM(conn=conn)
    start = budget.committed_usd(conn)
    print(f"start: total committed ${start:.4f}")

    rng = random.Random(SEED)
    sample = []
    for channel, n in PER_CHANNEL.items():
        rows = conn.execute(
            "SELECT external_id, text, meta_json FROM source_item WHERE vehicle_model_id = 'G60' AND market_code = 'US' "
            "AND json_extract(meta_json, '$.channel') = ? ORDER BY external_id", (channel,)
        ).fetchall()
        for r in rng.sample(rows, n):
            meta = json.loads(r["meta_json"])
            sample.append({"id": r["external_id"], "text": r["text"], "engine": meta["engine"],
                           "channel": channel, "bmw_labels": meta["bmw_labels"]})
    rng.shuffle(sample)

    batches, all_results = [], []
    for i in range(0, len(sample), BATCH_SIZE):
        chunk = sample[i:i + BATCH_SIZE]
        if budget.committed_usd(conn) - start > PILOT_CAP_USD:
            sys.exit(f"ABORT: pilot cap ${PILOT_CAP_USD} reached")
        t0 = time.time()
        parsed, res = extract_batch(llm, chunk, job=f"{JOB}:extract")
        checks = check_batch(chunk, parsed)
        print(f"extract batch {i // BATCH_SIZE + 1}: {time.time() - t0:.0f}s, ${res.cost_usd:.4f}, "
              f"tier={getattr(res.response, 'service_tier', None)}, cached={res.cached}, checks={checks}")
        print("  " + spend_line(conn, start))
        batches.append({"usage_id": res.usage_id, "cost_usd": res.cost_usd, "checks": checks})
        all_results += [r.model_dump() for r in parsed.results]

    (out / "sample.json").write_text(json.dumps(sample, indent=2, ensure_ascii=False))
    (out / "extraction.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False))

    signals = [{"verbatim_id": r["verbatim_id"], **s} for r in all_results for s in r["signals"]]
    if budget.committed_usd(conn) - start > PILOT_CAP_USD:
        sys.exit(f"ABORT: pilot cap ${PILOT_CAP_USD} reached")
    t0 = time.time()
    context = {"derivative": "G60 (BMW 5 Series sedan, incl. i5)", "market": "US", "segment": "premium upper-mid-size",
               "evidence_base": f"{len(sample)} sampled verbatims (pilot)"}
    parsed, res = derive(llm, context, signals, n=5, job=f"{JOB}:derive")
    checks = check_derivation(parsed, {v["id"] for v in sample})
    print(f"derive: {time.time() - t0:.0f}s, ${res.cost_usd:.4f}, tier={getattr(res.response, 'service_tier', None)}, "
          f"cached={res.cached}, checks={checks}")
    print("  " + spend_line(conn, start))
    (out / "requirements.json").write_text(json.dumps(parsed.model_dump(), indent=2, ensure_ascii=False))
    print(f"done: {spend_line(conn, start)}")


if __name__ == "__main__":
    main()
