"""Stage `cluster` (D-043): comment signals → clusters, checkpoint-incremental, deterministic (no LLM).

Design (clustering review 2026-10-11):
- Portfolio-wide within (polarity × category): polarity `like` vs `improve` (everything else). Twins across car lines
  share one cluster; per car line × market counts live in the payload (D-011 markets stay apart, D-042 5 Series).
- cp1: average-linkage agglomerative clustering, cosine distance 0.35, plus a recursive split of oversized clusters
  (> 15 % of the group and > 60 signals; threshold −0.05 per level, depth ≤ 3) against chaining into "like" blobs.
- Stable keys: `cl:<polarity>:<category-slug>:<anchor signal id>` — the anchor is the medoid at birth, never moved.
- cp2 (parent = cp1 run): each newly visible signal joins the cp1 cluster of its group with the smallest mean cosine
  distance to the members, if ≤ 0.35; leftovers are clustered among themselves into new clusters.
- Tracks per cluster: weight = share of the visible in-scope comment base; strengthened / weakened only if the cp2
  delta share differs from the cp1 share by ≥ 10 % relative AND |z| ≥ 1.96 (two-proportion test); else held.
  A random split must not look like change.

`uv run python -m bmw_req.structure.cluster --checkpoint cp1` (then cp2)
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from bmw_req import checkpoints as C
from bmw_req.db import connect, vec
from bmw_req.llm import LLM
from bmw_req.portfolio import LINES
from bmw_req.structure.events import log

VERSION = "extract-v4"
THRESHOLD = 0.35
SPLIT_SHARE, SPLIT_MIN, SPLIT_DEPTH, SPLIT_STEP = 0.15, 60, 3, 0.05
MIN_COMMENTS = 3            # a cluster with fewer distinct comments is long tail (kept, flagged)
EMBED_BATCH = 512




def line_of(car: str) -> str:
    for line, spec in LINES.items():
        if car in spec["derivatives"]:
            return line
    return car


def polarity(nature: str) -> str:
    return "like" if nature == "like" else "improve"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def signal_text(r) -> str:
    return f"{r['category']} | {r['aspect']} | {r['need_statement']}"


def embed_missing(conn, llm: LLM) -> int:
    rows = conn.execute("""SELECT id, category, aspect, need_statement FROM signal WHERE extractor_version = ?
                           AND source_kind = 'feedback' AND id NOT IN (SELECT signal_id FROM signal_embedding) ORDER BY id""",
                        (VERSION,)).fetchall()
    for i in range(0, len(rows), EMBED_BATCH):
        chunk = rows[i:i + EMBED_BATCH]
        vecs = llm.embed([signal_text(r) for r in chunk], job="embed:signals:v4")
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("INSERT INTO signal_embedding (signal_id, embedding) VALUES (?, ?)",
                         [(r["id"], vec(v)) for r, v in zip(chunk, vecs)])
        conn.execute("COMMIT")
    return len(rows)


def load(conn, cps: tuple[str, ...]) -> list[dict]:
    q = ",".join("?" * len(cps))
    rows = conn.execute(
        f"""SELECT g.id, g.source_item_id, g.category, g.aspect, g.nature, g.intensity, s.vehicle_model_id car,
                   s.market_code market, s.checkpoint, e.embedding
            FROM signal g JOIN source_item s ON s.id = g.source_item_id JOIN signal_embedding e ON e.signal_id = g.id
            WHERE g.extractor_version = ? AND g.source_kind = 'feedback' AND s.checkpoint IN ({q}) ORDER BY g.id""",
        (VERSION, *cps)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        v = vec(d.pop("embedding"))
        d["v"] = v / (np.linalg.norm(v) or 1.0)
        d["pol"] = polarity(d["nature"])
        d["line"] = line_of(d["car"])
        out.append(d)
    return out


def agglomerate(sigs: list[dict], threshold: float) -> list[list[dict]]:
    if len(sigs) == 1:
        return [sigs]
    X = np.stack([s["v"] for s in sigs])
    labels = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                     distance_threshold=threshold).fit_predict(X)
    groups = defaultdict(list)
    for s, l in zip(sigs, labels):
        groups[l].append(s)
    return list(groups.values())


def split_big(clusters: list[list[dict]], group_size: int, threshold: float, depth: int = 0) -> list[list[dict]]:
    out = []
    for c in clusters:
        if depth < SPLIT_DEPTH and len(c) > SPLIT_MIN and len(c) > SPLIT_SHARE * group_size:
            parts = agglomerate(c, threshold - SPLIT_STEP)
            out.extend(split_big(parts, group_size, threshold - SPLIT_STEP, depth + 1) if len(parts) > 1 else [c])
        else:
            out.append(c)
    return out


def medoid(c: list[dict]) -> dict:
    X = np.stack([s["v"] for s in c])
    m = X.mean(axis=0)
    return c[int(np.argmax(X @ m))]


def payload(members: list[dict]) -> dict:
    comments = {s["source_item_id"] for s in members}
    by_line_market = Counter()
    for sid in comments:
        s = next(m for m in members if m["source_item_id"] == sid)
        by_line_market[f"{s['line']}:{s['market']}"] += 1
    return {"signals": len(members), "comments": len(comments),
            "intensity": round(sum(s["intensity"] or 1 for s in members), 1),
            "natures": dict(Counter(s["nature"] for s in members)),
            "aspects": dict(Counter(s["aspect"] for s in members).most_common(3)),
            "by_line_market": dict(by_line_market), "tail": len(comments) < MIN_COMMENTS}


def base_comments(conn, cps: tuple[str, ...]) -> int:
    q = ",".join("?" * len(cps))
    return conn.execute(f"""SELECT COUNT(*) FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
                            WHERE e.extractor_version = ? AND e.in_scope = 1 AND s.checkpoint IN ({q})""",
                        (VERSION, *cps)).fetchone()[0]


def z_state(c1: int, n1: int, d: int, nd: int) -> str:
    """held unless the delta share differs from the cp1 share by ≥ 10 % relative and |z| ≥ 1.96."""
    if n1 == 0 or nd == 0:
        return "held"
    p1, p2 = c1 / n1, d / nd
    p = (c1 + d) / (n1 + nd)
    se = math.sqrt(max(p * (1 - p) * (1 / n1 + 1 / nd), 1e-12))
    z = (p2 - p1) / se
    if abs(z) < 1.96 or p1 == 0 or abs(p2 - p1) / p1 < 0.10:
        return "held"
    return "strengthened" if p2 > p1 else "weakened"


def run_checkpoint(cp: str, actor: str = "system") -> dict:
    conn = connect()
    embedded = embed_missing(conn, LLM(conn=conn))
    vis = C.visible_ids(cp)
    sigs = load(conn, vis)
    conn.execute("BEGIN IMMEDIATE")
    try:
        run_id = C.start_run(conn, cp, "cluster", actor)
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
        assign: dict[int, str] = {}           # signal id → cluster key
        born: list[tuple[str, dict]] = []     # new clusters: (key, anchor)
        groups = defaultdict(list)
        for s in sigs:
            groups[(s["pol"], s["category"])].append(s)

        if parent:  # carry cp1 membership, assign the delta, cluster the leftovers
            prev = {r[0]: r[1] for r in conn.execute("SELECT signal_id, cluster_key FROM cluster_member WHERE run_id = ?", (parent,))}
            for (pol, cat), g in groups.items():
                old = [s for s in g if s["id"] in prev]
                new = [s for s in g if s["id"] not in prev]
                for s in old:
                    assign[s["id"]] = prev[s["id"]]
                by_key = defaultdict(list)
                for s in old:
                    by_key[prev[s["id"]]].append(s["v"])
                keys = list(by_key)
                left = []
                if keys:
                    M = np.stack([np.mean(by_key[k], axis=0) for k in keys])   # mean member vector per cluster
                    for s in new:
                        sims = M @ s["v"]
                        j = int(np.argmax(sims))
                        if 1 - sims[j] <= THRESHOLD:
                            assign[s["id"]] = keys[j]
                        else:
                            left.append(s)
                else:
                    left = new
                for c in (agglomerate(left, THRESHOLD) if left else []):
                    a = medoid(c)
                    key = f"cl:{pol}:{slug(cat)}:{a['id']}"
                    born.append((key, a))
                    for s in c:
                        assign[s["id"]] = key
        else:
            for (pol, cat), g in groups.items():
                for c in split_big(agglomerate(g, THRESHOLD), len(g), THRESHOLD):
                    a = medoid(c)
                    key = f"cl:{pol}:{slug(cat)}:{a['id']}"
                    born.append((key, a))
                    for s in c:
                        assign[s["id"]] = key

        conn.executemany("INSERT OR IGNORE INTO cluster (key, polarity, category, anchor_signal_id, born_run_id, born_checkpoint)"
                         " VALUES (?, ?, ?, ?, ?, ?)", [(k, a["pol"], a["category"], a["id"], run_id, cp) for k, a in born])
        conn.executemany("INSERT INTO cluster_member (run_id, cluster_key, signal_id) VALUES (?, ?, ?)",
                         [(run_id, k, sid) for sid, k in assign.items()])

        members = defaultdict(list)
        by_id = {s["id"]: s for s in sigs}
        for sid, k in assign.items():
            members[k].append(by_id[sid])
        n_all = base_comments(conn, vis)
        entities, states = {}, {}
        if parent:
            n1 = base_comments(conn, C.visible_ids(BY_PARENT[cp]))
            nd = n_all - n1
        for k, ms in members.items():
            p = payload(ms)
            entities[k] = (p["comments"] / max(n_all, 1), p)
            if parent:
                c1 = len({s["source_item_id"] for s in ms if s["checkpoint"] != cp})
                d = len({s["source_item_id"] for s in ms if s["checkpoint"] == cp})
                if c1 > 0:
                    states[k] = z_state(c1, n1, d, nd)
        tracks = C.write_tracks(conn, run_id, entities, states=states)
        stats = {"signals": len(sigs), "clusters": len(members), "born": len(born), "embedded": embedded,
                 "findings": sum(not v[1]["tail"] for v in entities.values()), "tracks": tracks}
        C.finish_run(conn, run_id, stats)
        log(conn, "cluster", "clustered", {"signals": len(sigs), "clusters": len(members), "born": len(born),
            "findings": stats["findings"]}, run_id)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}


BY_PARENT = {c.id: c.parent_id for c in C.CHECKPOINTS}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"], required=True)
    print(json.dumps(run_checkpoint(ap.parse_args().checkpoint), indent=1))
