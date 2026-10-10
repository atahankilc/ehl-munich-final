"""Verbatim findings (D-025): embed extracted signals, cluster them, label clusters with luna.

`uv run python -m bmw_req.pipeline.findings G60 [--threshold 0.4] [--dry-run]`

- Signals of one derivative are clustered within (polarity group × category): polarity `improve`
  (defect, difficult_to_use, complaint, want) or `like` (must-not-lose). Agglomerative clustering,
  cosine distance, average linkage, fixed distance threshold → deterministic for fixed embeddings.
- A cluster with ≥ MIN_VERBATIMS distinct verbatims becomes a `finding`; smaller ones stay as long tail
  (still in `signal`, reachable via search).
- Findings span all markets of the derivative; `metrics_json` holds per-market and per-wave counts
  (D-011, D-027), so scoring can use the market-specific evidence and the simulated time.
"""

import argparse
import json
import sqlite3
from collections import Counter, defaultdict

import numpy as np
from pydantic import BaseModel, Field
from sklearn.cluster import AgglomerativeClustering

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline.extract import EXTRACTOR_VERSION

METHOD = "cluster-v1"
MIN_VERBATIMS = 3
DEFAULT_THRESHOLD = 0.35
EMBED_BATCH = 512
IMPROVE_TYPES = {"defect", "difficult_to_use", "complaint", "want"}
SEVERITY_W = {"low": 1.0, "medium": 2.0, "high": 3.0}


# ---------------------------------------------------------------------------------------------- embedding
def signal_text(r) -> str:
    return f"{r['category']} | {r['topic']} | {r['need_statement']}"


def embed_signals(conn: sqlite3.Connection, llm: LLM, derivative: str) -> int:
    rows = conn.execute(
        """SELECT g.id, g.category, g.topic, g.need_statement FROM signal g
           JOIN source_item s ON s.id = g.source_item_id
           WHERE s.vehicle_model_id = ? AND g.extractor_version = ?
             AND g.id NOT IN (SELECT rowid FROM signal_embedding)""",
        (derivative, EXTRACTOR_VERSION),
    ).fetchall()
    for i in range(0, len(rows), EMBED_BATCH):
        chunk = rows[i:i + EMBED_BATCH]
        vecs = llm.embed([signal_text(r) for r in chunk], job=f"embed:signals:{derivative}")
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT INTO signal_embedding (rowid, embedding) VALUES (?, ?)",
            [(r["id"], np.asarray(v, dtype=np.float32).tobytes()) for r, v in zip(chunk, vecs)],
        )
        conn.execute("COMMIT")
    return len(rows)


def load_signals(conn: sqlite3.Connection, derivative: str) -> list[dict]:
    rows = conn.execute(
        """SELECT g.id, g.source_item_id, g.category, g.topic, g.feedback_type, g.severity, g.need_statement,
                  g.quote, g.quote_verified, g.support_question, s.external_id, s.market_code, s.country, s.wave,
                  s.meta_json, e.embedding
           FROM signal g JOIN source_item s ON s.id = g.source_item_id
           JOIN signal_embedding e ON e.rowid = g.id
           WHERE s.vehicle_model_id = ? AND g.extractor_version = ?
           ORDER BY g.id""",
        (derivative, EXTRACTOR_VERSION),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        meta = json.loads(d.pop("meta_json"))
        d["channel"], d["engine"] = meta.get("channel"), meta.get("engine")
        d["vec"] = np.frombuffer(d.pop("embedding"), dtype=np.float32)
        d["polarity"] = "like" if d["feedback_type"] == "like" else "improve"
        out.append(d)
    return out


# ---------------------------------------------------------------------------------------------- clustering
def cluster(signals: list[dict], threshold: float) -> list[list[dict]]:
    groups = defaultdict(list)
    for s in signals:
        groups[(s["polarity"], s["category"])].append(s)
    clusters = []
    for key in sorted(groups):
        members = groups[key]
        if len(members) == 1:
            clusters.append(members)
            continue
        X = np.stack([m["vec"] for m in members])
        labels = AgglomerativeClustering(
            n_clusters=None, metric="cosine", linkage="average", distance_threshold=threshold
        ).fit_predict(X)
        by = defaultdict(list)
        for m, lab in zip(members, labels):
            by[lab].append(m)
        clusters.extend(by.values())
    clusters.sort(key=lambda c: -len({m["source_item_id"] for m in c}))
    return clusters


def n_verbatims(c: list[dict]) -> int:
    return len({m["source_item_id"] for m in c})


# ---------------------------------------------------------------------------------------------- metrics
def market_bases(conn: sqlite3.Connection, derivative: str) -> dict:
    """In-scope verbatims per market and cumulative wave: {wave: {market: n}}."""
    rows = conn.execute(
        """SELECT s.market_code, s.wave, COUNT(*) n FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
           WHERE s.vehicle_model_id = ? AND e.extractor_version = ? AND e.in_scope = 1
           GROUP BY s.market_code, s.wave""",
        (derivative, EXTRACTOR_VERSION),
    ).fetchall()
    out = {}
    for w in (1, 2):
        out[w] = defaultdict(int)
        for r in rows:
            if r["wave"] <= w:
                out[w][r["market_code"]] += r["n"]
    return {w: dict(v) for w, v in out.items()}


def cluster_metrics(c: list[dict], bases: dict) -> dict:
    """Per cumulative wave and market: distinct verbatims, signal types, severity, channels, engines."""
    by_wave = {}
    for w in (1, 2):
        ms = [m for m in c if m["wave"] <= w]
        markets = {}
        for mk in sorted({m["market_code"] for m in ms}):
            mm = [m for m in ms if m["market_code"] == mk]
            verb = {m["source_item_id"] for m in mm}
            # one weight per verbatim: its strongest signal in this cluster; support questions count half (Q-020)
            per_verb = defaultdict(float)
            for m in mm:
                wgt = SEVERITY_W[m["severity"]] * (0.5 if m["support_question"] else 1.0)
                per_verb[m["source_item_id"]] = max(per_verb[m["source_item_id"]], wgt)
            base = bases[w].get(mk, 0)
            markets[mk] = {
                "verbatims": len(verb),
                "share": round(len(verb) / base, 4) if base else None,
                "base": base,
                "severity_weighted": round(sum(per_verb.values()), 2),
                "types": dict(Counter(m["feedback_type"] for m in mm)),
                "severity": dict(Counter(m["severity"] for m in mm)),
                "support_questions": sum(m["support_question"] for m in mm),
                "channels": dict(Counter(m["channel"] for m in {m["source_item_id"]: m for m in mm}.values())),
                "engines": dict(Counter(m["engine"] for m in {m["source_item_id"]: m for m in mm}.values())),
                "countries": dict(Counter(m["country"] for m in {m["source_item_id"]: m for m in mm}.values())),
            }
        by_wave[str(w)] = {"verbatims": len({m["source_item_id"] for m in ms}), "markets": markets}
    return {"method": METHOD, "by_wave": by_wave}


# ---------------------------------------------------------------------------------------------- labelling
class ClusterLabel(BaseModel):
    cluster_id: int
    title: str = Field(description="≤ 10 words, customer language, names the concrete topic (e.g. 'CarPlay connection drops')")
    summary: str = Field(description="1–2 sentences: what customers say, only from the given statements")
    finding_type: str = Field(description="defect | usability_issue | complaint | unmet_need | must_not_lose | mixed")
    coherent: bool = Field(description="True if the statements are about one theme")


class LabelBatch(BaseModel):
    labels: list[ClusterLabel]


LABEL_INSTRUCTIONS = """You label clusters of customer signals about a BMW vehicle for product managers.
Each cluster has customer need statements and quotes extracted from verbatims. For EVERY cluster return its
cluster_id with a short concrete title, a factual summary (do not add facts or numbers that are not in the
input; do not mention counts), finding_type (defect = things broken or misbehaving; usability_issue = hard to
understand/operate; complaint = works but not good enough; unmet_need = requested feature/equipment missing;
must_not_lose = praised strengths; mixed = several of these) and whether the cluster is coherent."""


def label_clusters(llm: LLM, clusters: list[tuple[int, list[dict]]], derivative: str, batch: int = 8,
                   workers: int = 8) -> dict[int, ClusterLabel]:
    from concurrent.futures import ThreadPoolExecutor

    def one(chunk):
        payload = []
        for cid, c in chunk:
            uniq = list({m["need_statement"]: m for m in c}.values())
            payload.append({
                "cluster_id": cid, "category": c[0]["category"],
                "types": dict(Counter(m["feedback_type"] for m in c)),
                "need_statements": [m["need_statement"] for m in uniq[:14]],
                "quotes": [m["quote"] for m in uniq[:6]],
            })
        res = LLM(conn=connect()).generate(
            job=f"findings:label:{derivative}", tier="fast", instructions=LABEL_INSTRUCTIONS,
            input=json.dumps(payload, ensure_ascii=False), schema=LabelBatch, reasoning_effort="low",
            max_output_tokens=6000, flex=True, prompt_cache_options={"mode": "explicit"},
        )
        return res.parsed.labels

    chunks = [clusters[i:i + batch] for i in range(0, len(clusters), batch)]
    out = {}
    with ThreadPoolExecutor(workers) as pool:
        for labels in pool.map(one, chunks):
            for lab in labels:
                out[lab.cluster_id] = lab
    return out


# ---------------------------------------------------------------------------------------------- store
def store_findings(conn, derivative: str, clusters: list[list[dict]], labels: dict, bases: dict, model: str) -> int:
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = 0
        for cid, c in enumerate(clusters):
            lab = labels.get(cid)
            if lab is None:
                continue
            metrics = cluster_metrics(c, bases)
            metrics["coherent"] = lab.coherent
            first_wave = min(m["wave"] for m in c)
            fid = conn.execute(
                """INSERT INTO finding (type, title, summary, scope_level, vehicle_model_id, market_code, metrics_json,
                                        created_by, source_kind, polarity, category, first_wave)
                   VALUES (?, ?, ?, 'derivative', ?, NULL, ?, ?, 'verbatim', ?, ?, ?)""",
                (lab.finding_type, lab.title, lab.summary, derivative, json.dumps(metrics),
                 f"ai:{model}:{METHOD}", "like" if c[0]["polarity"] == "like" else "pain_or_want",
                 c[0]["category"], first_wave),
            ).lastrowid
            conn.executemany("INSERT INTO finding_signal (finding_id, signal_id) VALUES (?, ?)", [(fid, m["id"]) for m in c])
            best = {}
            for m in sorted(c, key=lambda m: (-m["quote_verified"], -SEVERITY_W[m["severity"]])):
                best.setdefault(m["source_item_id"], m["quote"])
            conn.executemany(
                "INSERT INTO finding_source (finding_id, source_item_id, quote, relation) VALUES (?, ?, ?, 'supports')",
                [(fid, sid, q) for sid, q in best.items()],
            )
            n += 1
        conn.execute(
            """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, model, prompt_ref)
               VALUES ('ai', 'pipeline.findings', 'build_findings', 'vehicle_model', ?, ?, ?, ?)""",
            (derivative, json.dumps({"findings": n, "clusters": len(clusters)}), model, METHOD),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("derivative")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--dry-run", action="store_true", help="cluster and print stats only, no labels/store")
    args = ap.parse_args()
    conn = connect()
    llm = LLM(conn=conn)
    print("embedded", embed_signals(conn, llm, args.derivative), "new signals")
    signals = load_signals(conn, args.derivative)
    clusters = cluster(signals, args.threshold)
    big = [c for c in clusters if n_verbatims(c) >= MIN_VERBATIMS]
    covered = sum(len(c) for c in big)
    print(f"{len(signals)} signals → {len(clusters)} clusters; {len(big)} with ≥{MIN_VERBATIMS} verbatims "
          f"cover {covered} signals ({covered / max(len(signals), 1):.0%})")
    if args.dry_run:
        for c in big[:40]:
            print(f"  [{n_verbatims(c):4d}] {c[0]['polarity']:7s} {c[0]['category'][:22]:22s} | "
                  + " || ".join(m['need_statement'][:60] for m in c[:3]))
        return
    if conn.execute("SELECT 1 FROM finding WHERE vehicle_model_id = ? AND source_kind = 'verbatim' LIMIT 1",
                    (args.derivative,)).fetchone():
        raise SystemExit(f"verbatim findings for {args.derivative} exist already; not rebuilding (links would break)")
    labels = label_clusters(llm, list(enumerate(big)), args.derivative)
    n = store_findings(conn, args.derivative, big, labels, market_bases(conn, args.derivative), llm.model_for("fast"))
    print(f"stored {n} findings")


if __name__ == "__main__":
    main()
