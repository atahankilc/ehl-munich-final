"""Merge and validate the checkpoint research (research/checkpoints/raw/*.json → research/checkpoints/checkpoints.json).

`uv run python scripts/checkpoints_merge.py`

Checks the SCHEMA.md rules: checkpoint matches the publication date (no item known only after its checkpoint),
nothing published after the last cut-off, required fields present, unique ids. Problems are printed and the
offending items are dropped or re-assigned (an item published before 2026-02-01 always belongs to 2026-01).
"""

import calendar
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research" / "checkpoints"
CUTOFFS = {"2026-01": date(2026, 1, 31), "2026-07": date(2026, 7, 31)}
REQUIRED = ("id", "checkpoint", "kind", "region", "entity", "headline", "source")


def checkpoint_for(published: date) -> str | None:
    for cp, cut in CUTOFFS.items():   # ordered: earliest cut-off first
        if published <= cut:
            return cp
    return None


def main() -> int:
    items, gaps, problems = [], {}, []
    seen = set()
    for f in sorted((ROOT / "raw").glob("*.json")):
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            problems.append(f"{f.name}: invalid JSON ({e})")
            continue
        topic = doc.get("topic") or f.stem
        gaps[topic] = doc.get("gaps") or []
        for it in doc.get("items") or []:
            missing = [k for k in REQUIRED if not it.get(k)]
            if missing:
                problems.append(f"{topic}:{it.get('id')}: missing {missing} — dropped")
                continue
            raw_pub = (it["source"].get("published_at") or "").strip()
            if not raw_pub:
                # undated reference page (e.g. predecessor history): background, known at the first checkpoint
                it["undated"] = True
                raw_pub = "2026-01-01"
            elif len(raw_pub) == 7:   # YYYY-MM → end of that month (latest possible publication)
                y, m = map(int, raw_pub.split("-"))
                raw_pub = str(date(y, m, calendar.monthrange(y, m)[1]))
            try:
                pub = date.fromisoformat(raw_pub[:10])
            except ValueError:
                problems.append(f"{topic}:{it['id']}: no valid published_at — dropped")
                continue
            cp = checkpoint_for(pub)
            if cp is None:
                problems.append(f"{topic}:{it['id']}: published {pub}, after the last cut-off — dropped")
                continue
            if cp != it["checkpoint"]:
                # an item may sit at a LATER checkpoint than its publication (still known then), never earlier
                if it["checkpoint"] not in CUTOFFS or CUTOFFS[it["checkpoint"]] < pub:
                    problems.append(f"{topic}:{it['id']}: checkpoint {it['checkpoint']} but published {pub} → {cp}")
                    it["checkpoint"] = cp
            iid = it["id"] if it["id"] not in seen else f"{topic}:{it['id']}"
            if iid in seen:
                problems.append(f"{topic}:{it['id']}: duplicate id — dropped")
                continue
            seen.add(iid)
            it["id"], it["topic"] = iid, topic
            items.append(it)

    out = {"checkpoints": {k: str(v) for k, v in CUTOFFS.items()}, "items": items, "gaps": gaps}
    (ROOT / "checkpoints.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    by = Counter((i["topic"], i["checkpoint"]) for i in items)
    for topic in sorted({t for t, _ in by}):
        print(f"{topic:22} 2026-01 {by[(topic, '2026-01')]:4}   2026-07 {by[(topic, '2026-07')]:4}")
    pairs = Counter(i.get("pair_key") for i in items if i.get("pair_key"))
    print(f"undated background items {sum(1 for i in items if i.get('undated'))}")
    print(f"items {len(items)} · verified {sum(1 for i in items if i.get('verified'))} · "
          f"complete pairs {sum(1 for v in pairs.values() if v >= 2)} · "
          f"tiers {dict(Counter(i['source'].get('trust_tier') for i in items))}")
    for p in problems:
        print("!", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
