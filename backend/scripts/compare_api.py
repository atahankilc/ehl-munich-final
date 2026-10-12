"""Capture and compare the API's answers (D-059 P1): proves the database switch changed no data the app shows.

`uv run python scripts/compare_api.py capture <file>`   every GET the frontend uses, with real ids/keys picked from the
                                                         answers themselves → <file> (JSON)
`uv run python scripts/compare_api.py diff <before> <after>`   field-by-field comparison; floats within 1e-6

Talks to the running API (http://127.0.0.1:8600 or API_URL). Read-only: GET requests only.
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request

API = os.getenv("API_URL", "http://127.0.0.1:8600")
CPS = ("cp1", "cp2")
LINES = ("1 Series", "5 Series", "7 Series")
MARKETS = ("EU", "US", "CN", "RoW")
# the same answer may legitimately differ in these keys (wall-clock, live budget state)
VOLATILE = {"generated_at", "running", "running_job", "last"}


def get(path: str):
    with urllib.request.urlopen(API + path, timeout=120) as r:
        return json.loads(r.read())


def q(**kw) -> str:
    return "?" + urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})


def capture() -> dict:
    out: dict[str, object] = {}

    def take(path: str):
        try:
            out[path] = get(path)
        except Exception as e:   # record failures too: a 500 after the switch must show up in the diff
            out[path] = {"__error__": str(e)}
        return out[path]

    take("/api/checkpoints")
    for cp in CPS:
        pts = take(f"/api/scan/points{q(cp=cp)}")
        take(f"/api/scan/sources{q(cp=cp)}")
        ids = (pts.get("cols", {}).get("id") or [])[:: max(1, len(pts.get("cols", {}).get("id") or []) // 5)][:5] if isinstance(pts, dict) else []
        for i in ids:
            take(f"/api/scan/comment/{i}{q(cp=cp)}")
        st = take(f"/api/structure{q(cp=cp)}")
        take(f"/api/structure/activity{q(cp=cp)}")
        if isinstance(st, dict):
            for c in (st.get("clusters") or [])[:3]:
                take(f"/api/structure/cluster/{urllib.parse.quote(str(c.get('key')))}{q(cp=cp)}")
            for t in (st.get("themes") or [])[:3]:
                take(f"/api/structure/theme/{urllib.parse.quote(str(t.get('key')))}{q(cp=cp)}")
        df = take(f"/api/definition{q(cp=cp)}")
        if isinstance(df, dict):
            for r in (df.get("requirements") or [])[:4]:
                take(f"/api/definition/requirement/{urllib.parse.quote(r['key'])}{q(cp=cp)}")
        pr = take(f"/api/prioritize{q(cp=cp)}")
        if isinstance(pr, dict):
            for t in (pr.get("targets") or [])[:4]:
                key, line, market = t.get("key"), t.get("line"), t.get("market")
                take(f"/api/prioritize/target/{urllib.parse.quote(str(key))}{q(line=line, market=market, cp=cp)}")
                take(f"/api/prioritize/what-if{q(key=key, line=line, market=market, level='stretch', cp=cp)}")
        for line in LINES:
            for m in MARKETS:
                take(f"/api/document{q(cp=cp, line=line, market=m)}")
        take(f"/api/audit/feed{q(scope='all', cp=cp, only_cp='true', limit=500)}")
        for scope in ("evidence", "structure", "definition"):
            take(f"/api/audit/feed{q(scope=scope, cp=cp, limit=300)}")
    take(f"/api/audit/feed{q(scope='all', cp='none', only_cp='true', limit=500)}")
    for line in LINES:
        take(f"/api/document/changes{q(line=line, market='US')}")
    take("/api/prioritize/weights/history")
    take("/api/usage?limit=200")
    take("/api/settings")
    take("/api/agents")
    return out


def diff(a, b, path="$", out=None, limit=60):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in VOLATILE:
                continue
            if k not in a or k not in b:
                out.append(f"{path}.{k}: only in {'after' if k in b else 'before'}")
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} → {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6):
            out.append(f"{path}: {a!r} → {b!r}")
    elif a != b:
        out.append(f"{path}: {str(a)[:80]!r} → {str(b)[:80]!r}")
    return out


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "capture":
        data = capture()
        with open(sys.argv[2], "w") as f:
            json.dump(data, f)
        errors = [p for p, v in data.items() if isinstance(v, dict) and "__error__" in v]
        print(f"captured {len(data)} answers, {len(errors)} errors" + (f": {errors[:5]}" if errors else ""))
        return 0
    if len(sys.argv) >= 4 and sys.argv[1] == "diff":
        before, after = (json.load(open(p)) for p in sys.argv[2:4])
        bad = 0
        for path in sorted(set(before) | set(after)):
            if path not in before or path not in after:
                print(f"{path}: only {'after' if path in after else 'before'}")
                bad += 1
                continue
            d = diff(before[path], after[path])
            if d:
                bad += 1
                print(f"\n{path}  ({len(d)}{'+' if len(d) >= 60 else ''} differences)")
                for line in d[:12]:
                    print("   ", line)
        print(f"\n{len(before)} answers compared, {bad} differ")
        return 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
