"""Run structure & context end to end (D-043): for cp1 then cp2 — wait for `classify`, then cluster → contextualize →
areas; finally classify the non-comment sources and re-check quote flags with the final rule.

`uv run python -m bmw_req.structure.run_all`   (safe to start while classification is still running)
"""

from __future__ import annotations

import json
import time

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.structure import areas, classify, classify_context, cluster, contextualize
from bmw_req.structure.events import log


def wait_classified(cp: str, poll: float = 20.0) -> None:
    while True:
        conn = connect()
        r = conn.execute("SELECT status FROM checkpoint_run WHERE checkpoint_id = ? AND stage = 'classify' ORDER BY id DESC LIMIT 1", (cp,)).fetchone()
        if r and r["status"] == "completed":
            return
        if r and r["status"] == "failed":
            raise RuntimeError(f"classify failed at {cp}")
        time.sleep(poll)


def recheck_quotes() -> int:
    """Re-apply the final quote rule (≥ 4 words, a real span, never survey-prompt text) to every v4 comment signal."""
    conn = connect()
    rows = conn.execute("""SELECT g.id, g.quote, s.text, s.meta_json FROM signal g JOIN source_item s ON s.id = g.source_item_id
                           WHERE g.extractor_version = 'extract-v4' AND g.source_kind = 'feedback'""").fetchall()
    upd = []
    for r in rows:
        sp = classify.hints(r["text"] or "", json.loads(r["meta_json"] or "{}")).get("survey_prompt")
        upd.append((int(classify.quote_good(r["quote"] or "", r["text"] or "", sp)), r["id"]))
    conn.execute("BEGIN IMMEDIATE")
    conn.executemany("UPDATE signal SET quote_verified = ? WHERE id = ?", upd)
    conn.execute("COMMIT")
    return sum(1 for v, _ in upd if not v)


def main() -> dict:
    out = {}
    for cp in ("cp1", "cp2"):
        wait_classified(cp)
        out[cp] = {"cluster": cluster.run_checkpoint(cp), "contextualize": contextualize.run_checkpoint(cp),
                   "areas": areas.run_checkpoint(cp)}
        print(cp, json.dumps(out[cp], default=str)[:600], flush=True)
    out["context_sources"] = classify_context.main()
    out["unverified_quotes"] = recheck_quotes()
    log(connect(), "areas", "pipeline_done", {"unverified_quotes": out["unverified_quotes"]})
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
