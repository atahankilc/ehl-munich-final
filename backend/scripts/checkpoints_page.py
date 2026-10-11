"""Build the Checkpoint Atlas page: research/checkpoints/atlas.template.html + checkpoints.json → atlas.html.

`uv run python scripts/checkpoints_merge.py && uv run python scripts/checkpoints_page.py`

Only public web research goes into the page (no BMW challenge data).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research" / "checkpoints"
KEEP = ("id", "checkpoint", "topic", "kind", "region", "entity", "segment", "metric", "period_covered", "value", "unit",
        "yoy_pct", "headline", "driver", "customer_relevance", "pair_key", "quote", "verified", "notes", "undated")

data = json.loads((ROOT / "checkpoints.json").read_text())
items = [{k: i[k] for k in KEEP if i.get(k) is not None} | {"source": {k: i["source"].get(k) for k in
         ("url", "publisher", "published_at", "trust_tier")}} for i in data["items"]]
for i in items:
    i["source"]["published_at"] = i["source"]["published_at"] or ""
payload = json.dumps({"items": items, "gaps": data["gaps"]}, ensure_ascii=False, separators=(",", ":"))
payload = payload.replace("</", "<\\/")   # never close the <script> early
html = (ROOT / "atlas.template.html").read_text().replace("__DATA__", payload)
(ROOT / "atlas.html").write_text(html)
print(f"atlas.html {len(html) / 1024:.0f} KB, {len(items)} items")
