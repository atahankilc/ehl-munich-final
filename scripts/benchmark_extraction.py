"""Benchmark extraction versions against BMW's own feedback-type labels (aggregate numbers only — no raw text
is printed, AGENTS rule 1).

`uv run python scripts/benchmark_extraction.py [G60 F70 G70]`

For every verbatim BMW labelled with a feedback type, does our extraction produce a signal of the mapped type?
BMW labels are a hint, not truth (the pilot found BMW 'Difficult to Use' on real faults), so we report
recall per type, the confusion of the main mismatch, and in-scope rate — useful for comparing versions.
"""

import json
import sys
from collections import Counter, defaultdict

from bmw_req.db import connect

MAP = {"Likes": {"like"}, "Defect": {"defect"}, "Difficult to Use": {"difficult_to_use"}, "Wants": {"want"}}
LENIENT = {"Likes": {"like"}, "Defect": {"defect", "complaint"}, "Difficult to Use": {"difficult_to_use", "defect", "complaint"},
           "Wants": {"want", "complaint"}}


def main(derivs):
    conn = connect()
    versions = [r[0] for r in conn.execute("SELECT DISTINCT extractor_version FROM verbatim_extraction ORDER BY 1")]
    out = {}
    for d in derivs:
        items = conn.execute("SELECT id, meta_json FROM source_item WHERE kind = 'feedback' AND vehicle_model_id = ?", (d,)).fetchall()
        labels = {r["id"]: {l["feedback_type"] for l in json.loads(r["meta_json"])["bmw_labels"] if l["feedback_type"]} for r in items}
        for v in versions:
            ext = {r["source_item_id"]: r["in_scope"] for r in conn.execute(
                """SELECT e.source_item_id, e.in_scope FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
                   WHERE s.vehicle_model_id = ? AND e.extractor_version = ?""", (d, v))}
            if len(ext) < 0.9 * len(items):
                continue
            sig = defaultdict(set)
            for r in conn.execute(
                """SELECT g.source_item_id, g.feedback_type FROM signal g JOIN source_item s ON s.id = g.source_item_id
                   WHERE s.vehicle_model_id = ? AND g.extractor_version = ?""", (d, v)):
                sig[r["source_item_id"]].add(r["feedback_type"])
            strict, lenient, conf = Counter(), Counter(), defaultdict(Counter)
            total = Counter()
            for sid, ls in labels.items():
                if sid not in ext:
                    continue
                for l in ls:
                    if l not in MAP:
                        continue
                    total[l] += 1
                    strict[l] += bool(MAP[l] & sig[sid])
                    lenient[l] += bool(LENIENT[l] & sig[sid])
                    conf[l].update(sig[sid] or {"<none>"})
            n_scope = sum(ext.values())
            out[(d, v)] = {
                "verbatims": len(ext), "in_scope_rate": round(n_scope / len(ext), 3),
                "signals_per_in_scope": round(sum(len(s) for s in sig.values()) / max(n_scope, 1), 2),
                "recall_strict": {l: round(strict[l] / total[l], 3) for l in total},
                "recall_lenient": {l: round(lenient[l] / total[l], 3) for l in total},
                "macro_strict": round(sum(strict[l] / total[l] for l in total) / len(total), 3),
                "dtu_confusion": dict(conf["Difficult to Use"].most_common(4)),
            }
    for k, v in out.items():
        print(k, json.dumps(v))
    return out


if __name__ == "__main__":
    main(sys.argv[1:] or ["G60", "F70", "G70"])
