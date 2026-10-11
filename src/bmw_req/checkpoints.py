"""Two real-date checkpoints (D-041, replaces the simulated waves of D-027).

A checkpoint is what a PM could know on its cut-off day. Every source item gets the FIRST checkpoint at which it is
knowable (`source_item.checkpoint`); it stays visible at every later checkpoint. Checkpoint 2 never starts from
scratch: each pipeline stage runs once per checkpoint, and a run at checkpoint 2 names the completed run of the same
stage at checkpoint 1 as its parent, reads the parent's outputs plus the newly visible sources (the delta), and writes
`track` rows that say what happened to every entity: new, held, strengthened, weakened or lost (track-while-scan).

Visibility rules (Atahan, 2026-10-11):
- customer comments: the stratified 50/50 split of D-027 (seed 2026) — first half at cp1, second half at cp2;
- customer study, sales (incl. the 2030 forecast), option lists: known at cp1 (they exist by January);
- web and research items: by publication date; nothing published after the last cut-off is ever visible;
  a web item without a date is never visible (no leak); a curated reference item or research item marked
  `undated` (predecessor history) is background, known at cp1.
"""

from __future__ import annotations

import calendar
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bmw_req.config import ROOT


@dataclass(frozen=True)
class Checkpoint:
    id: str
    label: str
    cutoff: date
    parent_id: str | None
    position: int


CHECKPOINTS = (
    Checkpoint("cp1", "JAN 26", date(2026, 1, 31), None, 1),
    Checkpoint("cp2", "JUL 26", date(2026, 7, 31), "cp1", 2),
)
BY_ID = {c.id: c for c in CHECKPOINTS}
RESEARCH_FILE = ROOT / "research" / "checkpoints" / "checkpoints.json"
REGION_MARKET = {"EU": "EU", "DE": "EU", "UK": "EU", "US": "US", "CN": "CN", "JP": "RoW", "KR": "RoW"}
STATES = ("new", "held", "strengthened", "weakened", "lost")
CHANGE = 0.10   # relative weight change that counts as strengthened / weakened


class CheckpointError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ visibility
def parse_date(value: str | None) -> date | None:
    """'2026-03-14' → that day; '2026-03' → month end; '2024' → year end (latest possible publication)."""
    v = (value or "").strip()[:10]
    try:
        if len(v) == 10:
            return date.fromisoformat(v)
        if len(v) == 7:
            y, m = int(v[:4]), int(v[5:7])
            return date(y, m, calendar.monthrange(y, m)[1])
        if len(v) == 4:
            return date(int(v), 12, 31)
    except ValueError:
        return None
    return None


def checkpoint_for(published: date | None) -> str | None:
    if published is None:
        return None
    for c in CHECKPOINTS:   # ordered by cut-off
        if published <= c.cutoff:
            return c.id
    return None


def visible_ids(cp: str) -> tuple[str, ...]:
    """Checkpoint ids whose items are visible at `cp` (itself and all ancestors)."""
    out, c = [], BY_ID[cp]
    while c:
        out.append(c.id)
        c = BY_ID.get(c.parent_id) if c.parent_id else None
    return tuple(out)


def ensure(conn: sqlite3.Connection) -> None:
    """Write the checkpoint table (idempotent)."""
    conn.executemany(
        "INSERT INTO checkpoint (id, label, cutoff, parent_id, position) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET label = excluded.label, cutoff = excluded.cutoff, "
        "parent_id = excluded.parent_id, position = excluded.position",
        [(c.id, c.label, c.cutoff.isoformat(), c.parent_id, c.position) for c in CHECKPOINTS],
    )


def assign_visibility(conn: sqlite3.Connection) -> dict:
    """Set `source_item.checkpoint` for every item by the rules above. Deterministic; safe to re-run."""
    ensure(conn)
    updates = []
    for r in conn.execute("SELECT id, kind, wave, published_at FROM source_item"):
        kind = r["kind"]
        if kind == "feedback":
            cp = "cp1" if r["wave"] == 1 else "cp2"
        elif kind in ("study", "sales", "option_list"):
            cp = "cp1"
        elif kind == "reference" or (kind == "research" and not r["published_at"]):
            # curated background: undated reference rows and research marked `undated` (predecessor history)
            cp = checkpoint_for(parse_date(r["published_at"])) if r["published_at"] else "cp1"
        else:   # web, research
            cp = checkpoint_for(parse_date(r["published_at"]))
        updates.append((cp, r["id"]))
    conn.executemany("UPDATE source_item SET checkpoint = ? WHERE id = ?", updates)
    counts: dict[str, int] = {}
    for r in conn.execute("SELECT kind, COALESCE(checkpoint, 'never') cp, COUNT(*) n FROM source_item GROUP BY 1, 2"):
        counts[f"{r['kind']}:{r['cp']}"] = r["n"]
    return counts


def import_research(conn: sqlite3.Connection, path: Path = RESEARCH_FILE) -> int:
    """Load the cited checkpoint research (research/checkpoints/checkpoints.json) as `source_item(kind=research)`.
    Upserts by the item id, so re-running after a new research round adds and updates rows."""
    data = json.loads(path.read_text())
    cur = conn.execute("INSERT INTO ingest_batch (kind, description, file) VALUES ('checkpoint_research', ?, ?)",
                       (f"{len(data['items'])} cited items, D-040", str(path.relative_to(ROOT))))
    batch = cur.lastrowid
    rows = []
    for it in data["items"]:
        src = it.get("source") or {}
        meta = {k: it.get(k) for k in ("topic", "kind", "region", "entity", "segment", "powertrain", "metric",
                                       "period_covered", "value", "unit", "yoy_pct", "pair_key",
                                       "customer_relevance", "verified", "notes", "undated")}
        meta["publisher"] = src.get("publisher")
        text = it["headline"] + (f" — {it['driver']}" if it.get("driver") else "")
        published = None if it.get("undated") else src.get("published_at")
        rows.append(("research", it["id"], it.get("pair_key"), src.get("trust_tier"),
                     REGION_MARKET.get(it.get("region")), it.get("region"), src.get("url"), published,
                     text, it.get("quote"), json.dumps(meta, ensure_ascii=False), batch))
    conn.executemany(
        """INSERT INTO source_item (kind, ref, external_id, trust_tier, market_code, country, url, published_at,
                                    text, quote, meta_json, ingest_batch_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(kind, ref) DO UPDATE SET external_id = excluded.external_id, trust_tier = excluded.trust_tier,
             market_code = excluded.market_code, country = excluded.country, url = excluded.url,
             published_at = excluded.published_at, text = excluded.text, quote = excluded.quote,
             meta_json = excluded.meta_json, ingest_batch_id = excluded.ingest_batch_id""",
        rows,
    )
    return len(rows)


# ------------------------------------------------------------------------------------------------ runs & tracks
def latest_run(conn: sqlite3.Connection, cp: str, stage: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM checkpoint_run WHERE checkpoint_id = ? AND stage = ? AND status = 'completed' "
        "ORDER BY id DESC LIMIT 1", (cp, stage)).fetchone()


def start_run(conn: sqlite3.Connection, cp: str, stage: str, actor: str) -> int:
    """Open a run of `stage` at `cp`. At a child checkpoint the parent checkpoint must already have a completed run
    of the same stage: checkpoint 2 always builds on checkpoint 1's output."""
    c = BY_ID.get(cp)
    if c is None:
        raise CheckpointError(f"Unknown checkpoint {cp!r}")
    parent = None
    if c.parent_id:
        parent = latest_run(conn, c.parent_id, stage)
        if parent is None:
            raise CheckpointError(f"Run '{stage}' at {BY_ID[c.parent_id].label} first: {c.label} builds on it.")
    cur = conn.execute("INSERT INTO checkpoint_run (checkpoint_id, stage, parent_run_id, actor) VALUES (?, ?, ?, ?)",
                       (cp, stage, parent["id"] if parent else None, actor))
    return cur.lastrowid


def _state(prev: float | None, weight: float | None) -> str:
    """State of an entity that existed in the parent run."""
    if prev is None or weight is None or prev == 0:
        return "held"
    change = (weight - prev) / abs(prev)
    return "strengthened" if change >= CHANGE else "weakened" if change <= -CHANGE else "held"


def write_tracks(conn: sqlite3.Connection, run_id: int, entities: dict[str, tuple[float | None, dict | None]],
                 prefix: str | None = None, states: dict[str, str] | None = None) -> dict:
    """Record every entity this run produced as {entity_key: (weight, payload)}. States are computed against the
    parent run: absent there → new; present in both → held / strengthened / weakened by weight change (±10 %);
    present only in the parent → a `lost` row is written so nothing disappears silently.
    `prefix`: compare only parent keys starting with it (a stage may write several entity families in one run).
    `states`: explicit state per key, overriding the ±10 % rule (e.g. a significance-tested cluster change)."""
    run = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()
    prev = {}
    if run["parent_run_id"]:
        prev = {r["entity_key"]: r["weight"] for r in conn.execute(
            "SELECT entity_key, weight FROM track WHERE run_id = ? AND state != 'lost'", (run["parent_run_id"],))
            if prefix is None or r["entity_key"].startswith(prefix)}
    rows, counts = [], dict.fromkeys(STATES, 0)
    for key, (weight, payload) in entities.items():
        p = prev.get(key)
        st = (states or {}).get(key) or (_state(p, weight) if key in prev else "new")
        counts[st] += 1
        rows.append((run_id, key, st, weight, p, json.dumps(payload) if payload is not None else None))
    for key, w in prev.items():
        if key not in entities:
            counts["lost"] += 1
            rows.append((run_id, key, "lost", None, w, None))
    conn.executemany("INSERT INTO track (run_id, entity_key, state, weight, prev_weight, payload_json) "
                     "VALUES (?, ?, ?, ?, ?, ?)", rows)
    return counts


def finish_run(conn: sqlite3.Connection, run_id: int, stats: dict) -> None:
    """Complete a run; an earlier completed run of the same stage at the same checkpoint is superseded."""
    r = conn.execute("SELECT checkpoint_id, stage FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()
    conn.execute("UPDATE checkpoint_run SET status = 'superseded' WHERE checkpoint_id = ? AND stage = ? "
                 "AND status = 'completed' AND id != ?", (r["checkpoint_id"], r["stage"], run_id))
    conn.execute("UPDATE checkpoint_run SET status = 'completed', finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
                 "stats_json = ? WHERE id = ?", (json.dumps(stats), run_id))


def run_acquire(conn: sqlite3.Connection, cp: str, actor: str = "system") -> dict:
    """Stage 0, 'acquire': every source visible at `cp` becomes a track (weight 1). At cp2 the comments of cp1 are
    `held` and the second half arrives as `new` — the first link in the cp1 → cp2 chain later stages extend."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        run_id = start_run(conn, cp, "acquire", actor)
        vis = visible_ids(cp)
        q = ",".join("?" * len(vis))
        entities = {f"{r['kind']}:{r['ref']}": (1.0, None) for r in conn.execute(
            f"SELECT kind, ref FROM source_item WHERE checkpoint IN ({q})", vis)}
        counts = write_tracks(conn, run_id, entities)
        finish_run(conn, run_id, counts)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **counts}


def setup(conn: sqlite3.Connection, research: bool = True) -> dict:
    """One-shot: import research, assign visibility, run 'acquire' at cp1 then cp2."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = import_research(conn) if research and RESEARCH_FILE.exists() else 0
        vis = assign_visibility(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"research_items": n, "visibility": vis,
            "acquire": [run_acquire(conn, c.id) for c in CHECKPOINTS]}


if __name__ == "__main__":
    from bmw_req.db import connect

    print(json.dumps(setup(connect()), indent=1))
