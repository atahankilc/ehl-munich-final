"""Stage `contextualize` (D-043): clusters → standardized insights → themes → evidence graph, per checkpoint.

1. Standardize (luna, batches): one insight per cluster with ≥ 3 comments — title, need statement, need type,
   quality-issue flag, whether a product decision is possible. cp2 re-standardizes only new / strengthened /
   weakened clusters; held clusters carry their cp1 insight.
2. Duplicates: insight pairs with statement-embedding cosine ≥ 0.86 → luna judge → `duplicate_of` / `sub_need_of`.
3. Themes: insights grouped by meaning within their category (complete linkage on statement embeddings, 0.35 —
   average linkage at 0.45 collapsed every category into one theme); luna names each theme. cp2: a new insight joins
   the nearest cp1 theme if cosine ≥ 0.65, else forms a new theme.
4. Connect evidence (RAG): embed research, study items and options once (`node_embedding`); per theme retrieve the
   nearest checkpoint-visible candidates per type, then luna verifies each link with a relation and a reason.
5. Every edge is an `evidence_edge` row with its run id; tracks per insight, theme and edge show what cp2 changed.

`uv run python -m bmw_req.structure.contextualize --checkpoint cp1` (then cp2)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from sklearn.cluster import AgglomerativeClustering

from bmw_req import checkpoints as C
from bmw_req.db import connect, vec as as_vector
from bmw_req.llm import LLM
from bmw_req.structure.cluster import MIN_COMMENTS, base_comments, z_state
from bmw_req.structure.events import log

VERSION = "context-v1"
DUP_SIM, THEME_DIST, THEME_JOIN = 0.86, 0.35, 0.65   # complete linkage: ~70 themes of ≤ 15 findings (tuned on cp1)
K = {"research": 14, "study": 6, "option": 6}   # "research" nodes include the web and reference findings (D-047)
RESEARCH_KINDS = ("research", "web", "reference")



def ensure(conn) -> None:
    """No-op: the tables come from the Alembic migrations (D-059)."""


def vec(v) -> np.ndarray:
    """A stored embedding (pgvector) as a unit vector."""
    v = as_vector(v)
    return v / (np.linalg.norm(v) or 1.0)


def stored(v) -> np.ndarray:
    """An embedding as pgvector stores it (float32)."""
    return as_vector(v)


# ------------------------------------------------------------------------------------------------ 1. standardize
class Insight(BaseModel):
    cluster_key: str
    title: str = Field(description="≤ 8 words, plain customer language")
    statement: str = Field(description="'Customers want/value X when/because Y' — one sentence, solution-neutral")
    need_type: Literal["pain", "must_keep", "want", "expectation"]
    quality_issue: bool = Field(description="True if this is mainly something broken/faulty (quality, not a product decision)")
    product_decision: bool = Field(description="True if BMW could decide or trade off something in the successor car")


class InsightBatch(BaseModel):
    items: list[Insight]


STD_INSTRUCTIONS = """You standardize clusters of customer signals about BMW cars into findings for product managers.
For each cluster you get its category, top aspects, the mix of signal natures, comment counts per car line and
market, and sample need statements. Return one item per cluster_key (unchanged):
- title: ≤ 8 words in plain customer language.
- statement: one solution-neutral sentence 'Customers want/value X when/because Y'.
- need_type: pain (something falls short), must_keep (customers love it; don't lose it), want (a missing feature),
  expectation (a rising standard customers compare against).
- quality_issue: true if the cluster is mainly faults/defects (fix in quality, not a product decision).
- product_decision: true if BMW could decide or trade off something for the successor car.
Only use what the input shows."""


def standardize(conn, llm: LLM, clusters: list[dict], run_id: int | None = None) -> dict[str, Insight]:
    out = {}
    for i in range(0, len(clusters), 15):
        chunk = clusters[i:i + 15]
        res = llm.generate(job="contextualize:standardize", tier="fast", instructions=STD_INSTRUCTIONS,
                           input=json.dumps(chunk, ensure_ascii=False), schema=InsightBatch,
                           reasoning_effort="low", max_output_tokens=8000, flex=True)
        if res.parsed:
            out.update({x.cluster_key: x for x in res.parsed.items})
            log(conn, "contextualize", "standardize", {"clusters": len(res.parsed.items),
                "examples": [x.title for x in res.parsed.items[:3]]}, run_id, llm.model_for("fast"))
    return out


def cluster_digest(conn, run_id: int, key: str, payload: dict) -> dict:
    needs = [r[0] for r in conn.execute(
        """SELECT g.need_statement FROM cluster_member m JOIN signal g ON g.id = m.signal_id
           WHERE m.run_id = ? AND m.cluster_key = ? ORDER BY g.intensity DESC, g.id LIMIT 8""", (run_id, key))]
    cat = conn.execute("SELECT category FROM cluster WHERE key = ?", (key,)).fetchone()[0]
    return {"cluster_key": key, "category": cat, "aspects": payload["aspects"], "natures": payload["natures"],
            "comments": payload["comments"], "by_line_market": payload["by_line_market"], "sample_needs": needs}


# ------------------------------------------------------------------------------------------------ 2. duplicates
class DupJudgement(BaseModel):
    a: str
    b: str
    verdict: Literal["same_need", "sub_need", "different"]


class DupBatch(BaseModel):
    items: list[DupJudgement]


DUP_INSTRUCTIONS = """Pairs of customer findings. Decide per pair: same_need (one product decision would satisfy both),
sub_need (b is a narrower case of a), or different. Return a and b unchanged."""


# ------------------------------------------------------------------------------------------------ 3. themes
class ThemeName(BaseModel):
    theme_key: str
    title: str = Field(description="≤ 6 words")
    statement: str = Field(description="The shared customer need in one sentence")


class ThemeBatch(BaseModel):
    items: list[ThemeName]


THEME_INSTRUCTIONS = """Each group contains customer findings that belong together. Name the shared customer need:
a title of ≤ 6 words and one solution-neutral sentence. Return theme_key unchanged."""


# ------------------------------------------------------------------------------------------------ 4. evidence
class Link(BaseModel):
    node: str = Field(description="The candidate's id as given, e.g. 'research:123'")
    relation: Literal["supports", "contradicts", "context", "competes_with", "trend_for", "available_as_option", "irrelevant"]
    why: str = Field(description="≤ 20 words")


class LinkBatch(BaseModel):
    theme_key: str
    links: list[Link]


LINK_INSTRUCTIONS = """You connect one customer theme about BMW cars to candidate evidence (web research, customer
study items, today's equipment options). For each candidate decide the relation to the theme:
- supports: it confirms the customers' need (e.g. a study item rated low for the same topic, research showing buyers
  value it); contradicts: it points the other way; context: related background only;
- competes_with: a competitor offers or does it; trend_for: a dated market/technology trend that raises this
  expectation; available_as_option: today's BMW already offers it as standard/option/package;
- irrelevant: not about this need (use it freely — precision matters more than recall).
Return every candidate once with a ≤ 20-word reason."""


def node_texts(conn) -> list[tuple[str, int, str]]:
    out = []
    # cited research plus the web-agent findings and the reference layer (competitor features, trends, market facts);
    # all are node type "research" (one source_item id space), the item's kind stays on source_item for provenance
    for r in conn.execute("SELECT id, text, meta_json FROM source_item WHERE kind IN ('research', 'web', 'reference')"):
        m = json.loads(r["meta_json"] or "{}")
        out.append(("research", r["id"], f"{r['text']} | {m.get('customer_relevance') or ''}"))
    for r in conn.execute("SELECT id, item, vehicle_model_id, market_code FROM study_metric"):
        out.append(("study", r["id"], f"Customer study: {r['item']} ({r['vehicle_model_id']}, {r['market_code']})"))
    for r in conn.execute("SELECT id, vehicle_model_id, meta_json FROM source_item WHERE kind = 'option_list'"):
        m = json.loads(r["meta_json"] or "{}")
        out.append(("option", r["id"], f"{r['vehicle_model_id']} option: {m.get('name_en')} ({m.get('category')}, {m.get('availability')})"))
    return out


def embed_nodes(conn, llm: LLM) -> int:
    have = {(r[0], r[1]) for r in conn.execute("SELECT node_type, node_id FROM node_embedding")}
    todo = [t for t in node_texts(conn) if (t[0], t[1]) not in have]
    for i in range(0, len(todo), 512):
        chunk = todo[i:i + 512]
        vecs = llm.embed([t[2][:2000] for t in chunk], job="embed:nodes")
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("INSERT INTO node_embedding VALUES (?, ?, ?, ?)", [(t[0], t[1], t[2], stored(v)) for t, v in zip(chunk, vecs)])
        conn.execute("COMMIT")
    return len(todo)


def visible_nodes(conn, cp: str) -> dict[str, list[int]]:
    """The evidence nodes a theme may link to at this checkpoint: ids per node type (research / study / option)."""
    vis = C.visible_ids(cp)
    q = ",".join("?" * len(vis))
    ok_research = [r[0] for r in conn.execute(f"SELECT id FROM source_item WHERE kind IN ('research', 'web', 'reference') "
                                              f"AND checkpoint IN ({q})", vis)]
    ok_study = [r[0] for r in conn.execute(f"SELECT m.id FROM study_metric m JOIN source_item s ON s.id = m.source_item_id WHERE s.checkpoint IN ({q})", vis)]
    ok_option = [r[0] for r in conn.execute(f"SELECT id FROM source_item WHERE kind='option_list' AND checkpoint IN ({q})", vis)]
    return {"research": ok_research, "study": ok_study, "option": ok_option}


# ------------------------------------------------------------------------------------------------ run
def run_checkpoint(cp: str, actor: str = "system") -> dict:
    conn = connect()
    ensure(conn)
    llm = LLM(conn=conn)
    stats: dict = {"embedded_nodes": embed_nodes(conn, llm)}
    crun = C.latest_run(conn, cp, "cluster")
    if crun is None:
        raise C.CheckpointError(f"Run 'cluster' at {cp} first")
    conn.execute("BEGIN IMMEDIATE")
    run_id = C.start_run(conn, cp, "contextualize", actor)
    conn.execute("COMMIT")
    parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]

    # 1. standardize — clusters with ≥ 3 comments; at cp2 only the changed ones
    ctracks = {r["entity_key"]: r for r in conn.execute("SELECT * FROM track WHERE run_id = ?", (crun["id"],))}
    live = {k: json.loads(t["payload_json"]) for k, t in ctracks.items() if t["state"] != "lost" and t["payload_json"]
            and json.loads(t["payload_json"])["comments"] >= MIN_COMMENTS}
    prev_ins = {}
    if parent:
        prev_ins = {r["cluster_key"]: r for r in conn.execute("SELECT * FROM insight WHERE run_id = ?", (parent,))}
    todo = [k for k in live if k not in prev_ins or ctracks[k]["state"] in ("new", "strengthened", "weakened")]
    log(conn, "contextualize", "start", {"clusters": len(live), "to_standardize": len(todo)}, run_id)
    std = standardize(conn, llm, [cluster_digest(conn, crun["id"], k, live[k]) for k in todo], run_id)
    rows = []
    for k, p in live.items():
        cat = conn.execute("SELECT category FROM cluster WHERE key = ?", (k,)).fetchone()[0]
        aspect = next(iter(p["aspects"]), None)
        if k in std:
            x = std[k]
            rows.append((run_id, k, x.title, x.statement, x.need_type, int(x.quality_issue), int(x.product_decision), cat, aspect, json.dumps(p)))
        elif k in prev_ins:
            o = prev_ins[k]
            rows.append((run_id, k, o["title"], o["statement"], o["need_type"], o["quality_issue"], o["product_decision"], cat, aspect, json.dumps(p)))
    conn.execute("BEGIN IMMEDIATE")
    conn.executemany("INSERT INTO insight (run_id, cluster_key, title, statement, need_type, quality_issue, product_decision,"
                     " category, aspect, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.execute("COMMIT")
    stats["insights"], stats["standardized"] = len(rows), len(std)

    # embed insight statements (reuse cp1 vectors when the text is unchanged)
    ins = conn.execute("SELECT cluster_key, statement, category, embedding FROM insight WHERE run_id = ?", (run_id,)).fetchall()
    old_vec = {}
    if parent:
        old_vec = {(r[0], r[1]): r[2] for r in conn.execute("SELECT cluster_key, statement, embedding FROM insight WHERE run_id = ?", (parent,)) if r[2] is not None}
    need = [r for r in ins if (r["cluster_key"], r["statement"]) not in old_vec]
    vecs = {}
    for i in range(0, len(need), 512):
        chunk = need[i:i + 512]
        for r, v in zip(chunk, llm.embed([f"{r['category']} | {r['statement']}" for r in chunk], job="embed:insights")):
            vecs[r["cluster_key"]] = stored(v)
    conn.execute("BEGIN IMMEDIATE")
    for r in ins:
        b = vecs.get(r["cluster_key"])
        if b is None:
            b = old_vec.get((r["cluster_key"], r["statement"]))
        conn.execute("UPDATE insight SET embedding = ? WHERE run_id = ? AND cluster_key = ?", (b, run_id, r["cluster_key"]))
    conn.execute("COMMIT")
    ins = conn.execute("SELECT * FROM insight WHERE run_id = ?", (run_id,)).fetchall()
    V = {r["cluster_key"]: vec(r["embedding"]) for r in ins}
    edges: list[tuple] = []

    # 2. duplicates (pairs touching at least one re-standardized insight)
    keys = list(V)
    M = np.stack([V[k] for k in keys]) if keys else np.zeros((0, 1))
    S = M @ M.T if len(keys) else np.zeros((0, 0))
    pairs = [(keys[i], keys[j]) for i in range(len(keys)) for j in range(i + 1, len(keys))
             if S[i, j] >= DUP_SIM and (keys[i] in std or keys[j] in std)]
    title = {r["cluster_key"]: r["statement"] for r in ins}
    for i in range(0, len(pairs), 30):
        chunk = pairs[i:i + 30]
        res = llm.generate(job="contextualize:duplicates", tier="fast", instructions=DUP_INSTRUCTIONS,
                           input=json.dumps([{"a": a, "a_text": title[a], "b": b, "b_text": title[b]} for a, b in chunk]),
                           schema=DupBatch, reasoning_effort="low", max_output_tokens=4000, flex=True)
        hits = [j for j in (res.parsed.items if res.parsed else []) if j.verdict != "different"]
        log(conn, "contextualize", "duplicates", {"pairs": len(chunk), "merged": len(hits)}, run_id, llm.model_for("fast"))
        for j in (res.parsed.items if res.parsed else []):
            if j.verdict != "different":
                edges.append((run_id, "insight", j.b, "insight", j.a, "duplicate_of" if j.verdict == "same_need" else "sub_need_of",
                              None, "luna", None, llm.model_for("fast")))
    if parent:   # carry cp1 duplicate edges whose insights are unchanged
        for e in conn.execute("SELECT * FROM evidence_edge WHERE run_id = ? AND relation IN ('duplicate_of','sub_need_of')", (parent,)):
            if e["src_id"] in V and e["dst_id"] in V and e["src_id"] not in std and e["dst_id"] not in std:
                edges.append((run_id, e["src_type"], e["src_id"], e["dst_type"], e["dst_id"], e["relation"], e["weight"], e["method"], e["rationale"], e["model"]))
    stats["duplicate_pairs"] = len(pairs)

    # 3. themes
    assign: dict[str, str] = {}
    new_groups: list[list[str]] = []
    if parent:
        prev_member = {r[0]: r[1] for r in conn.execute("SELECT cluster_key, theme_key FROM theme_member WHERE run_id = ?", (parent,))}
        tvec = {r["key"]: vec(r["embedding"]) for r in conn.execute("SELECT key, embedding FROM theme WHERE embedding IS NOT NULL")}
        tcat = {r[0]: r[1] for r in conn.execute("SELECT key, category FROM theme")}
        loose = defaultdict(list)
        for r in ins:
            k = r["cluster_key"]
            if k in prev_member and k not in std:
                assign[k] = prev_member[k]
                continue
            cands = [(float(V[k] @ v), t) for t, v in tvec.items() if tcat[t] == r["category"]]
            best = max(cands, default=(0.0, None))
            if best[0] >= THEME_JOIN:
                assign[k] = best[1]
            else:
                loose[r["category"]].append(k)
        for cat, ks in loose.items():
            new_groups.extend(_group(ks, V))
    else:
        by_cat = defaultdict(list)
        for r in ins:
            by_cat[r["category"]].append(r["cluster_key"])
        for cat, ks in by_cat.items():
            new_groups.extend(_group(ks, V))
    cat_of = {r["cluster_key"]: r["category"] for r in ins}
    groups_payload = []
    for g in new_groups:
        anchor = max(g, key=lambda k: json.loads(next(r["payload_json"] for r in ins if r["cluster_key"] == k))["comments"])
        tk = f"th:{anchor}"
        for k in g:
            assign[k] = tk
        groups_payload.append({"theme_key": tk, "findings": [title[k] for k in g][:10]})
    names = {}
    for i in range(0, len(groups_payload), 20):
        res = llm.generate(job="contextualize:themes", tier="fast", instructions=THEME_INSTRUCTIONS,
                           input=json.dumps(groups_payload[i:i + 20], ensure_ascii=False), schema=ThemeBatch,
                           reasoning_effort="low", max_output_tokens=5000, flex=True)
        got = res.parsed.items if res.parsed else []
        names.update({t.theme_key: t for t in got})
        log(conn, "contextualize", "themes", {"themes": len(got), "examples": [t.title for t in got[:3]]}, run_id, llm.model_for("fast"))
    theme_vecs = {}
    if names:
        tl = list(names.values())
        for t, v in zip(tl, llm.embed([f"{t.title} | {t.statement}" for t in tl], job="embed:themes")):
            theme_vecs[t.theme_key] = stored(v)
    conn.execute("BEGIN IMMEDIATE")
    for g in groups_payload:
        t = names.get(g["theme_key"])
        if t:
            cat = cat_of[g["theme_key"][3:]]
            # a re-run of the same checkpoint refreshes the theme; a later checkpoint never renames an earlier theme
            conn.execute("""INSERT INTO theme (key, title, statement, category, born_run_id, born_checkpoint, embedding)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET title = excluded.title, statement = excluded.statement,
                              category = excluded.category, born_run_id = excluded.born_run_id, embedding = excluded.embedding
                            WHERE theme.born_checkpoint = excluded.born_checkpoint""",
                         (t.theme_key, t.title, t.statement, cat, run_id, cp, theme_vecs.get(t.theme_key)))
    conn.executemany("INSERT INTO theme_member (run_id, theme_key, cluster_key) VALUES (?, ?, ?)",
                     [(run_id, t, k) for k, t in assign.items() if conn.execute("SELECT 1 FROM theme WHERE key = ?", (t,)).fetchone()])
    for k, t in assign.items():
        edges.append((run_id, "insight", k, "theme", t, "belongs_to", None, "embed", None, None))
    conn.execute("COMMIT")

    # 4. connect evidence — dirty themes only at cp2 (new members, or new evidence visible)
    themes = conn.execute("""SELECT t.key, t.title, t.statement, t.embedding FROM theme t
                             WHERE t.key IN (SELECT theme_key FROM theme_member WHERE run_id = ?)""", (run_id,)).fetchall()
    nodes = visible_nodes(conn, cp)
    newly = set()
    if parent:
        q = "SELECT id FROM source_item WHERE checkpoint = ?"
        newly = {r[0] for r in conn.execute(q, (cp,))}
    dirty_members = {assign[k] for k in std if k in assign}
    prev_links = defaultdict(list)
    if parent:
        for e in conn.execute("SELECT * FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme' AND src_type IN ('research','study','option')", (parent,)):
            prev_links[e["dst_id"]].append(e)
    verified = 0
    for t in themes:
        if t["embedding"] is None:
            continue
        cand = candidates(conn, t, nodes)
        dirty = not parent or t["key"] in dirty_members or t["key"] not in prev_links or \
            any(typ == "research" and nid in newly for typ, nid, _ in cand)
        if not dirty:
            for e in prev_links[t["key"]]:
                edges.append((run_id, e["src_type"], e["src_id"], e["dst_type"], e["dst_id"], e["relation"], e["weight"], e["method"], e["rationale"], e["model"]))
            continue
        edges += link_theme(conn, llm, run_id, t, cand)
        verified += 1
    stats["themes"], stats["themes_verified"] = len(themes), verified

    # 5. store edges + tracks
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("""INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, weight, method,
                            rationale, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", edges)
        n_by_theme = Counter()
        share = {k: json.loads(r["payload_json"])["comments"] for r in ins for k in [r["cluster_key"]]}
        for k, t in assign.items():
            n_by_theme[t] += share.get(k, 0)
        ent = {f"insight:{k}": (float(share.get(k, 0)), None) for k in V}
        st = {f"insight:{k}": ("held" if k not in std else None) for k in V if parent}
        st = {k: v for k, v in st.items() if v}
        for k in V:   # insight state mirrors its cluster's significance-tested state
            ct = ctracks.get(k)
            if ct is not None:
                st[f"insight:{k}"] = ct["state"]
        t1 = C.write_tracks(conn, run_id, ent, prefix="insight:", states=st)
        t2 = theme_tracks(conn, run_id, parent, cp, n_by_theme)
        t3 = C.write_tracks(conn, run_id, {f"edge:{e[1]}:{e[2]}>{e[5]}>{e[4]}": (1.0, None) for e in edges if e[3] == "theme" and e[1] != "insight"},
                            prefix="edge:")
        stats["tracks"] = {"insights": t1, "themes": t2, "edges": t3}
        stats["edges"] = Counter(e[5] for e in edges)
        C.finish_run(conn, run_id, stats)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}


def theme_tracks(conn, run_id: int, parent: int | None, cp: str, n_by_theme: dict[str, int]) -> dict:
    """Theme tracks: weight = share of the visible in-scope comment base (payload keeps the count). At cp2 a theme is
    strengthened / weakened only if its share of the NEW comments differs significantly from its cp1 share (same rule
    as clusters); raw counts roughly double between checkpoints and must not read as change."""
    n_all = base_comments(conn, C.visible_ids(cp)) or 1
    ents = {f"theme:{t}": (n / n_all, {"comments": n}) for t, n in n_by_theme.items()}
    states = {}
    if parent:
        pcp = conn.execute("SELECT checkpoint_id FROM checkpoint_run WHERE id = ?", (parent,)).fetchone()[0]
        n1 = base_comments(conn, C.visible_ids(pcp)) or 1
        nd = max(n_all - n1, 1)
        for r in conn.execute("SELECT entity_key, weight, payload_json FROM track WHERE run_id = ? AND entity_key LIKE 'theme:%' "
                              "AND state != 'lost'", (parent,)):
            if r["entity_key"] not in ents:
                continue
            p = json.loads(r["payload_json"]) if r["payload_json"] else {}
            c1 = int(p.get("comments") or (r["weight"] if (r["weight"] or 0) > 1 else round((r["weight"] or 0) * n1)))
            n = ents[r["entity_key"]][1]["comments"]
            states[r["entity_key"]] = z_state(c1, n1, max(n - c1, 0), nd)
    return C.write_tracks(conn, run_id, ents, prefix="theme:", states=states)


def candidates(conn, t, nodes: dict[str, list[int]]) -> list[tuple[str, int, str]]:
    """Per node type the K evidence nodes nearest to the theme (cosine), exact, in the database (pgvector, D-059 P2).
    Ties go to the higher node id, as before. Exact on purpose: ~2k nodes take milliseconds, and an approximate HNSW
    index could return other neighbours — it comes when the knowledge base grows (Q-027)."""
    tv = vec(t["embedding"])
    cand = []
    for typ, k in K.items():
        ids = nodes.get(typ) or []
        if not ids:
            continue
        rows = conn.execute("SELECT node_id, text FROM node_embedding WHERE node_type = ? AND node_id = ANY(?) "
                            "ORDER BY embedding <=> ?, node_id DESC LIMIT ?", (typ, ids, tv, k)).fetchall()
        cand += [(typ, r[0], r[1]) for r in rows]
    return cand


def link_theme(conn, llm: LLM, run_id: int, t, cand) -> list[tuple]:
    """One luna call: the theme against its nearest candidates; returns evidence_edge rows (irrelevant dropped)."""
    res = llm.generate(job="contextualize:link", tier="fast", instructions=LINK_INSTRUCTIONS,
                       input=json.dumps({"theme_key": t["key"], "theme": f"{t['title']}: {t['statement']}",
                                         "candidates": [{"node": f"{typ}:{nid}", "text": txt[:400]} for typ, nid, txt in cand]},
                                        ensure_ascii=False),
                       schema=LinkBatch, reasoning_effort="low", max_output_tokens=4000, flex=True)
    kept = [l for l in (res.parsed.links if res.parsed else []) if l.relation != "irrelevant"]
    log(conn, "contextualize", "link", {"theme": t["title"], "candidates": len(cand), "linked": len(kept),
        "relations": dict(Counter(l.relation for l in kept))}, run_id, llm.model_for("fast"))
    out = []
    for l in kept:
        if ":" not in l.node:
            continue
        typ, nid = l.node.split(":", 1)
        if typ in K:
            out.append((run_id, typ, nid, "theme", t["key"], l.relation, None, "embed+luna", l.why, llm.model_for("fast")))
    return out


def relink(cp: str, actor: str = "system") -> dict:
    """Re-run only the evidence linking (step 4) as a NEW contextualize run (D-047): copies the latest completed run's
    insights, theme membership and non-evidence edges, links every theme against the current candidate pool, writes
    tracks the usual way and supersedes the old run. Lineage stays intact: run cp1 first, then cp2 (whose parent is then
    the new cp1 run, so its edge states compare against the new cp1 edges)."""
    conn = connect()
    ensure(conn)
    llm = LLM(conn=conn)
    src = C.latest_run(conn, cp, "contextualize")
    if src is None:
        raise C.CheckpointError(f"No completed contextualize run at {cp}")
    embedded = embed_nodes(conn, llm)
    conn.execute("BEGIN IMMEDIATE")
    run_id = C.start_run(conn, cp, "contextualize", actor)
    cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() "
                                       "AND table_name = 'insight' ORDER BY ordinal_position") if r[0] != "run_id"]
    conn.execute(f"INSERT INTO insight (run_id, {', '.join(cols)}) SELECT ?, {', '.join(cols)} FROM insight WHERE run_id = ?",
                 (run_id, src["id"]))
    conn.execute("INSERT INTO theme_member (run_id, theme_key, cluster_key) SELECT ?, theme_key, cluster_key FROM theme_member "
                 "WHERE run_id = ?", (run_id, src["id"]))
    conn.execute("""INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, weight, method, rationale, model)
                    SELECT ?, src_type, src_id, dst_type, dst_id, relation, weight, method, rationale, model FROM evidence_edge
                    WHERE run_id = ? AND NOT (dst_type = 'theme' AND src_type IN ('research', 'study', 'option'))""",
                 (run_id, src["id"]))
    conn.execute("COMMIT")
    log(conn, "contextualize", "start", {"relink_of_run": src["id"], "embedded_nodes": embedded}, run_id)

    themes = conn.execute("""SELECT t.key, t.title, t.statement, t.embedding FROM theme t
                             WHERE t.key IN (SELECT theme_key FROM theme_member WHERE run_id = ?)""", (run_id,)).fetchall()
    nodes = visible_nodes(conn, cp)
    edges: list[tuple] = []
    for t in themes:
        if t["embedding"] is not None:
            edges += link_theme(conn, llm, run_id, t, candidates(conn, t, nodes))

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("""INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, weight, method,
                            rationale, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", edges)
        # insight tracks are unchanged by a relink: carry them over; theme tracks are recomputed with the shared rule
        conn.execute("""INSERT INTO track (run_id, entity_key, state, weight, prev_weight, payload_json)
                        SELECT ?, entity_key, state, weight, prev_weight, payload_json FROM track
                        WHERE run_id = ? AND entity_key LIKE 'insight:%'""", (run_id, src["id"]))
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
        n_by_theme = Counter()
        for r in conn.execute("""SELECT m.theme_key, i.payload_json FROM theme_member m JOIN insight i
                                 ON i.cluster_key = m.cluster_key AND i.run_id = m.run_id WHERE m.run_id = ?""", (run_id,)):
            n_by_theme[r["theme_key"]] += json.loads(r["payload_json"])["comments"]
        t2 = theme_tracks(conn, run_id, parent, cp, n_by_theme)
        t3 = C.write_tracks(conn, run_id, {f"edge:{e[1]}:{e[2]}>{e[5]}>{e[4]}": (1.0, None) for e in edges}, prefix="edge:")
        stats = {**json.loads(src["stats_json"] or "{}"), "relink_of_run": src["id"], "embedded_nodes": embedded,
                 "themes_verified": len(themes), "edges": dict(Counter(e[5] for e in edges)),
                 "tracks": {**(json.loads(src["stats_json"] or "{}").get("tracks") or {}), "themes": t2, "edges": t3}}
        C.finish_run(conn, run_id, stats)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, "relink_of_run": src["id"], "themes": len(themes), "edges": stats["edges"], "edge_tracks": t3}


def _group(keys: list[str], V: dict) -> list[list[str]]:
    if len(keys) == 1:
        return [keys]
    X = np.stack([V[k] for k in keys])
    labels = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="complete",
                                     distance_threshold=THEME_DIST).fit_predict(X)
    g = defaultdict(list)
    for k, l in zip(keys, labels):
        g[l].append(k)
    return list(g.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"], required=True)
    ap.add_argument("--relink", action="store_true", help="re-run only the evidence linking as a new run (D-047)")
    a = ap.parse_args()
    print(json.dumps(relink(a.checkpoint) if a.relink else run_checkpoint(a.checkpoint), indent=1, default=str))
