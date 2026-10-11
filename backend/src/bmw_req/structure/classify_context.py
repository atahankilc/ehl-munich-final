"""Stage `classify`, non-comment sources (D-043): customer study, research and options into the shared aspect space.

- `source_aspect` gets one row per study item / research item / option (aspect + category + how it was mapped).
- Signals (source_kind study | research) are written where the source says something about customers:
  study rows clearly below / above their own column (z ≤ −0.8 → performance_gap, z ≥ +0.8 → like; intensity from
  |z|), and research items of kind study / event / trend (nature from the model; `explicit` false when the item's
  customer relevance is an assumption). Metrics, policy and sales stay context, never signals (Q-015).
- Aspect mapping uses luna in batches; the study mapping is one call over the distinct item labels.
Signals attach to the latest classify run of the item's checkpoint; tracks use the `classified:<kind>:` prefix so
they don't disturb the comment tracks of the same run.

`uv run python -m bmw_req.structure.classify_context`
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.structure.events import log
from bmw_req.structure.taxonomy import ALL_ASPECTS, CATEGORY_OF, taxonomy_text

VERSION = "extract-v4"
Aspect = Literal[tuple(ALL_ASPECTS)]  # type: ignore[valid-type]

SCHEMA = """CREATE TABLE IF NOT EXISTS source_aspect (
    source_item_id INTEGER NOT NULL REFERENCES source_item(id),
    key TEXT NOT NULL,                 -- study item label, research ref or option id
    aspect TEXT NOT NULL, category TEXT,
    method TEXT NOT NULL,              -- luna | rule
    PRIMARY KEY (source_item_id, key)
)"""


class Mapped(BaseModel):
    key: str
    aspect: Aspect


class MappedBatch(BaseModel):
    items: list[Mapped]


class ResearchSignal(BaseModel):
    key: str
    aspect: Aspect
    nature: Literal["like", "performance_gap", "missing_feature", "trend", "context"]
    need_statement: str | None


class ResearchBatch(BaseModel):
    items: list[ResearchSignal]


MAP_INSTRUCTIONS = f"""Map each item to exactly one customer-facing aspect of a car from this fixed list (category: aspects):
{taxonomy_text()}
Return one entry per input key, with the key unchanged. Use 'other' only when nothing fits (e.g. overall
satisfaction, value for money, dealer topics)."""

RESEARCH_INSTRUCTIONS = f"""Each input is a cited web-research item about the car market (headline + what it suggests for
premium car buyers). For every key return:
- aspect: the customer-facing aspect it is about, from this fixed list (category: aspects):
{taxonomy_text()}
  Use 'other' for market-wide items without a product aspect (sales volumes, policy, prices).
- nature: like (customers value it), performance_gap (customers find it lacking), missing_feature (customers expect
  something that is not offered), trend (a rising expectation or competitor move), context (background only).
- need_statement: the customer need in one solution-neutral sentence, or null for context.
Do not invent facts beyond the item."""


def _ensure(conn) -> None:
    conn.execute(SCHEMA)


def _batches(rows, n):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def map_study(conn, llm: LLM) -> int:
    labels = sorted({r[0] for r in conn.execute("SELECT DISTINCT item FROM study_metric")})
    out = {}
    for chunk in _batches(labels, 70):
        res = llm.generate(job="classify:study-aspects", tier="fast", instructions=MAP_INSTRUCTIONS,
                           input=json.dumps([{"key": l} for l in chunk]), schema=MappedBatch,
                           reasoning_effort="low", max_output_tokens=6000, flex=True)
        out.update({m.key: m.aspect for m in res.parsed.items})
    rows = conn.execute("SELECT source_item_id, item FROM study_metric").fetchall()
    conn.executemany("INSERT OR REPLACE INTO source_aspect VALUES (?, ?, ?, ?, 'luna')",
                     [(r[0], r[1], out.get(r[1], "other"), CATEGORY_OF.get(out.get(r[1], "other"))) for r in rows])
    return len(out)


def map_options(conn, llm: LLM) -> int:
    rows = conn.execute("SELECT id, meta_json FROM source_item WHERE kind = 'option_list'").fetchall()
    items = [{"key": str(r["id"]), "name": json.loads(r["meta_json"]).get("name_en"),
              "category": json.loads(r["meta_json"]).get("category")} for r in rows]
    n = 0
    for chunk in _batches(items, 60):
        res = llm.generate(job="classify:option-aspects", tier="fast", instructions=MAP_INSTRUCTIONS,
                           input=json.dumps(chunk, ensure_ascii=False), schema=MappedBatch,
                           reasoning_effort="low", max_output_tokens=6000, flex=True)
        got = {m.key: m.aspect for m in res.parsed.items}
        conn.executemany("INSERT OR REPLACE INTO source_aspect VALUES (?, ?, ?, ?, 'luna')",
                         [(int(k), k, a, CATEGORY_OF.get(a)) for k, a in got.items()])
        n += len(got)
    return n


def map_research(conn, llm: LLM) -> dict:
    rows = conn.execute("SELECT id, ref, text, meta_json FROM source_item WHERE kind = 'research'").fetchall()
    items = []
    for r in rows:
        m = json.loads(r["meta_json"] or "{}")
        items.append({"key": str(r["id"]), "headline": r["text"], "relevance": m.get("customer_relevance"),
                      "entity": m.get("entity"), "kind": m.get("kind"), "_meta": m})
    by_key = {i["key"]: i for i in items}
    res_all: dict[str, ResearchSignal] = {}
    for chunk in _batches(items, 40):
        payload = [{k: v for k, v in i.items() if k != "_meta"} for i in chunk]
        res = llm.generate(job="classify:research", tier="fast", instructions=RESEARCH_INSTRUCTIONS,
                           input=json.dumps(payload, ensure_ascii=False), schema=ResearchBatch,
                           reasoning_effort="low", max_output_tokens=10_000, flex=True)
        res_all.update({s.key: s for s in res.parsed.items if s.key in by_key})
    conn.executemany("INSERT OR REPLACE INTO source_aspect VALUES (?, ?, ?, ?, 'luna')",
                     [(int(k), by_key[k]["_meta"].get("pair_key") or k, s.aspect, CATEGORY_OF.get(s.aspect))
                      for k, s in res_all.items()])
    return res_all


def _classified(conn, source_item_id: int, run_id: int) -> None:
    """A signal must point at its source's classification row (FK signal → verbatim_extraction)."""
    conn.execute("""INSERT OR IGNORE INTO verbatim_extraction (source_item_id, extractor_version, in_scope, out_of_scope_reason,
                    classify_run_id) VALUES (?, ?, 1, NULL, ?)""", (source_item_id, VERSION, run_id))


def write_signals(conn, research: dict) -> dict:
    """Study + research signals, attached to the classify run of each item's checkpoint."""
    runs = {c.id: C.latest_run(conn, c.id, "classify") for c in C.CHECKPOINTS}
    conn.execute("DELETE FROM signal WHERE extractor_version = ? AND source_kind IN ('study', 'research')", (VERSION,))
    n = {"study": 0, "research": 0}
    aspect = {(r[0], r[1]): r[2] for r in conn.execute("SELECT source_item_id, key, aspect FROM source_aspect")}
    for m in conn.execute("""SELECT m.source_item_id, m.item, m.z_within_column z, s.checkpoint FROM study_metric m
                             JOIN source_item s ON s.id = m.source_item_id"""):
        z = m["z"]
        if z is None or abs(z) < 0.8 or not runs.get(m["checkpoint"]):
            continue
        nature = "like" if z > 0 else "performance_gap"
        a = aspect.get((m["source_item_id"], m["item"]), "other")
        _classified(conn, m["source_item_id"], runs[m["checkpoint"]]["id"])
        conn.execute(
            """INSERT INTO signal (source_item_id, extractor_version, category, topic, feedback_type, severity,
                 need_statement, quote, quote_verified, aspect, nature, intensity, impact, explicit, classify_run_id, source_kind)
               VALUES (?, ?, ?, ?, ?, 'low', ?, ?, 1, ?, ?, ?, ?, 1, ?, 'study')""",
            (m["source_item_id"], VERSION, CATEGORY_OF.get(a, "Design & Quality Perception"), m["item"],
             "like" if z > 0 else "complaint",
             f"'{m['item']}' is rated {'above' if z > 0 else 'below'} this car's average in the customer study",
             m["item"], a, nature, 1 if abs(z) < 1.2 else 2 if abs(z) < 1.6 else 3, "none" if z > 0 else "annoyance",
             runs[m["checkpoint"]]["id"]))
        n["study"] += 1
    for k, s in research.items():
        row = conn.execute("SELECT checkpoint, meta_json FROM source_item WHERE id = ?", (int(k),)).fetchone()
        meta = json.loads(row["meta_json"] or "{}")
        if meta.get("kind") not in ("study", "event", "trend") or s.nature == "context" or not runs.get(row["checkpoint"]):
            continue
        assumption = str(meta.get("customer_relevance") or "").lower().startswith("assumption")
        _classified(conn, int(k), runs[row["checkpoint"]]["id"])
        conn.execute(
            """INSERT INTO signal (source_item_id, extractor_version, category, topic, feedback_type, severity,
                 need_statement, quote, quote_verified, aspect, nature, intensity, impact, explicit, future_cue,
                 classify_run_id, source_kind)
               VALUES (?, ?, ?, ?, ?, 'low', ?, NULL, 0, ?, ?, 2, 'none', ?, ?, ?, 'research')""",
            (int(k), VERSION, CATEGORY_OF.get(s.aspect, "Design & Quality Perception"), meta.get("entity"),
             {"like": "like", "performance_gap": "complaint", "missing_feature": "want", "trend": "want"}[s.nature],
             s.need_statement, s.aspect, s.nature, int(not assumption), int(s.nature == "trend"),
             runs[row["checkpoint"]]["id"]))
        n["research"] += 1
    return n


def write_context_tracks(conn) -> dict:
    """Tracks for the classified context items, per checkpoint, in that checkpoint's classify run."""
    out = {}
    for c in C.CHECKPOINTS:
        run = C.latest_run(conn, c.id, "classify")
        if not run:
            continue
        vis = C.visible_ids(c.id)
        q = ",".join("?" * len(vis))
        ents = {f"classified:ctx:{r['id']}": (float(r["n"]), None) for r in conn.execute(
            f"""SELECT s.id, COUNT(g.id) n FROM source_item s LEFT JOIN signal g ON g.source_item_id = s.id
                AND g.extractor_version = ? AND g.source_kind IN ('study', 'research')
                WHERE s.kind IN ('study', 'research', 'option_list') AND s.checkpoint IN ({q}) GROUP BY s.id""", (VERSION, *vis))}
        conn.execute("DELETE FROM track WHERE run_id = ? AND entity_key LIKE 'classified:ctx:%'", (run["id"],))
        out[c.id] = C.write_tracks(conn, run["id"], ents, prefix="classified:ctx:")
    return out


def main() -> dict:
    conn = connect()
    _ensure(conn)
    llm = LLM(conn=conn)
    stats = {"study_labels": map_study(conn, llm)}
    log(conn, "classify", "map_study", {"items": stats["study_labels"]}, model=llm.model_for("fast"))
    stats["options"] = map_options(conn, llm)
    log(conn, "classify", "map_options", {"items": stats["options"]}, model=llm.model_for("fast"))
    research = map_research(conn, llm)
    log(conn, "classify", "map_research", {"items": len(research)}, model=llm.model_for("fast"))
    stats["research"] = len(research)
    conn.execute("BEGIN IMMEDIATE")
    try:
        stats["signals"] = write_signals(conn, research)
        stats["tracks"] = write_context_tracks(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return stats


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
