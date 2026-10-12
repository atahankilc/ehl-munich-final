"""Stage `areas` (D-043): themes + evidence graph → potential requirement AREAS, per checkpoint.

This stage structures, it does not draft requirements (that is the next step). sol groups the themes into areas a
PM would recognise ("Rear-seat comfort on long trips"), each with the underlying need, its kind (improve / keep /
emerging expectation), why it matters now (citing the evidence it was given) and ≤ 3 open questions requirement
drafting must answer. Code adds the hard numbers: comments, car line × market coverage, evidence counts by relation.
Themes that are only quality issues go to a separate quality list, not into areas.
Market context (D-046, `market.py`): the model also sees how much of BMW's volume each line × market holds (BMW's
internal, stylized file: a relative weight only), the latest cited public sales trend per line × market, and where the
two disagree; every area gets `metrics.market` with the same, for the markets its comments come from.
cp2 passes the cp1 areas: the model keeps them, attaches new themes, and records a change note where an area moved;
keys stay stable so tracks show new / held / strengthened / weakened / lost.

`uv run python -m bmw_req.structure.areas --checkpoint cp1` (then cp2)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.structure import market
from bmw_req.structure.cluster import z_state
from bmw_req.structure.events import log



class Area(BaseModel):
    key: str = Field(description="A previous area's key if this continues it, else a new short slug like 'rear-seat-comfort'")
    title: str = Field(description="≤ 8 words, the area as a PM would name it")
    need: str = Field(description="The underlying customer need in one solution-neutral sentence")
    kind: Literal["improve", "keep", "emerging"]
    theme_keys: list[str]
    why_now: str = Field(description="≤ 35 words, why this area matters, referring to the given evidence counts/sources")
    open_questions: list[str] = Field(description="≤ 3 questions requirement drafting must answer next")
    change_note: str | None = Field(description="Only for a previous area that changed: what changed and why")


class AreaSet(BaseModel):
    areas: list[Area]


INSTRUCTIONS = """You structure customer evidence about BMW cars into POTENTIAL REQUIREMENT AREAS for product managers.
You do NOT write requirements — no targets, metrics or solutions. You group themes into areas and explain them.

Input: themes (customer needs the AI found in comments), each with its comment count, need types, the car lines and
markets the comments come from, and how much research / study / option evidence supports, contradicts or adds
competitor/trend context to it. Some inputs also carry the previous checkpoint's areas.

Return 15–40 areas. Rules:
- Each theme goes into at most one area; themes that fit nowhere stay out. Prefer areas a PM would recognise
  ("Rear-seat comfort on long trips", "Phone connectivity that just works", "Keep the driving dynamics").
- kind: improve (customers find it lacking), keep (customers love it — protect it in the successor),
  emerging (a rising expectation shown mainly by trend/competitor evidence).
- why_now: ≤ 35 words, grounded only in the counts and evidence given.
- open_questions: ≤ 3 questions the next step (requirement drafting) must answer, e.g. which markets, how much better,
  trade-offs.
- market_context: bmw_volume_share says how big a line × market is for BMW (internal, stylized: use it only to say a
  market is large or small, never as a trend). public_trend gives cited sales changes; you may use them in why_now
  ("5 Series sales in China fell 19 % in H1 2026, src 12269") but any cause you infer is an assumption and must be
  worded as one ("possibly because…"). Where bmw_vs_public_conflicts lists a market, do not rely on BMW's figure there.
- If previous areas are given: keep their keys and titles unless the evidence changed them; attach new themes to the
  best existing area or create a new area; set change_note only where an area changed."""


def ensure(conn) -> None:
    """No-op: the tables come from the Alembic migrations (D-059)."""


def theme_digest(conn, ctx_run: int) -> list[dict]:
    out = []
    themes = conn.execute("""SELECT DISTINCT t.key, t.title, t.statement, t.category FROM theme t
                             JOIN theme_member m ON m.theme_key = t.key AND m.run_id = ?""", (ctx_run,)).fetchall()
    for t in themes:
        ins = conn.execute("""SELECT i.need_type, i.quality_issue, i.payload_json FROM insight i JOIN theme_member m
                              ON m.cluster_key = i.cluster_key AND m.run_id = i.run_id WHERE i.run_id = ? AND m.theme_key = ?""",
                           (ctx_run, t["key"])).fetchall()
        lm, comments = Counter(), 0
        for r in ins:
            p = json.loads(r["payload_json"])
            lm.update(p["by_line_market"]); comments += p["comments"]
        rel = Counter(r[0] for r in conn.execute(
            "SELECT relation FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme' AND dst_id = ? AND src_type IN ('research','study','option')",
            (ctx_run, t["key"])))
        ex = [r[0][:120] for r in conn.execute(
            """SELECT s.text FROM evidence_edge e JOIN source_item s ON s.id = CAST(e.src_id AS INTEGER)
               WHERE e.run_id = ? AND e.dst_id = ? AND e.src_type = 'research' AND e.relation IN ('trend_for','competes_with','supports') LIMIT 2""",
            (ctx_run, t["key"]))]
        out.append({"theme_key": t["key"], "title": t["title"], "statement": t["statement"], "category": t["category"],
                    "comments": comments, "need_types": dict(Counter(r["need_type"] for r in ins)),
                    "quality_only": all(r["quality_issue"] for r in ins) if ins else False,
                    "by_line_market": dict(lm), "evidence": dict(rel), "evidence_examples": ex})
    return out


def run_checkpoint(cp: str, actor: str = "system") -> dict:
    conn = connect()
    ensure(conn)
    llm = LLM(conn=conn)
    ctx = C.latest_run(conn, cp, "contextualize")
    if ctx is None:
        raise C.CheckpointError(f"Run 'contextualize' at {cp} first")
    conn.execute("BEGIN IMMEDIATE")
    run_id = C.start_run(conn, cp, "areas", actor)
    conn.execute("COMMIT")
    parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    digest = theme_digest(conn, ctx["id"])
    by_theme = {d["theme_key"]: d for d in digest}
    quality = [d for d in digest if d["quality_only"]]
    themes_in = [{k: v for k, v in d.items() if k != "quality_only"} for d in digest if not d["quality_only"]]
    prev = [dict(r) for r in conn.execute("SELECT * FROM req_area WHERE run_id = ? AND kind != 'quality'", (parent,))] if parent else []
    mctx = market.market_context(conn, cp)
    payload = {"themes": themes_in, "market_context": market.for_prompt(mctx)}
    if prev:
        payload["previous_areas"] = [{"key": a["key"], "title": a["title"], "need": a["need"], "kind": a["kind"],
                                      "theme_keys": json.loads(a["theme_keys_json"])} for a in prev]
    log(conn, "areas", "start", {"themes": len(themes_in), "quality": len(quality), "previous_areas": len(prev)}, run_id)
    res = llm.generate(job=f"areas:{cp}", tier="smart", instructions=INSTRUCTIONS,
                       input=json.dumps(payload, ensure_ascii=False), schema=AreaSet,
                       reasoning_effort="medium", max_output_tokens=24_000, flex=True)
    areas = res.parsed.areas if res.parsed else []
    log(conn, "areas", "grouped", {"areas": len(areas), "examples": [a.title for a in areas[:3]]}, run_id, llm.model_for("smart"))

    used, rows = set(), []
    prev_keys = {a["key"] for a in prev}
    for a in areas:
        tk = [t for t in a.theme_keys if t in by_theme and t not in used]
        if not tk:
            continue
        used.update(tk)
        key = a.key if a.key in prev_keys else f"ar:{a.key.removeprefix('ar:')}"
        lm, comments, ev = Counter(), 0, Counter()
        for t in tk:
            lm.update(by_theme[t]["by_line_market"]); comments += by_theme[t]["comments"]; ev.update(by_theme[t]["evidence"])
        rows.append((key, run_id, a.title, a.need, a.kind, json.dumps(tk), a.why_now, json.dumps(a.open_questions[:3]),
                     json.dumps({"comments": comments, "by_line_market": dict(lm), "evidence": dict(ev), "themes": len(tk),
                                 "market": market.area_market(dict(lm), mctx)}),
                     a.change_note if key in prev_keys else None, llm.model_for("smart")))
    if quality:   # one quality list, kept apart from the areas
        lm, comments = Counter(), 0
        for d in quality:
            lm.update(d["by_line_market"]); comments += d["comments"]
        rows.append(("ar:quality", run_id, "Quality hand-over", "Faults customers report — fix in quality, not a product decision.",
                     "quality", json.dumps([d["theme_key"] for d in quality]), None, "[]",
                     json.dumps({"comments": comments, "by_line_market": dict(lm), "evidence": {}, "themes": len(quality),
                                 "market": market.area_market(dict(lm), mctx)}), None, None))

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("""INSERT INTO req_area (key, run_id, title, need, kind, theme_keys_json, why_now, open_questions_json,
                            metrics_json, change_note, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (run_id, key) DO UPDATE SET title = excluded.title, need = excluded.need,
                            kind = excluded.kind, theme_keys_json = excluded.theme_keys_json, why_now = excluded.why_now,
                            open_questions_json = excluded.open_questions_json, metrics_json = excluded.metrics_json,
                            change_note = excluded.change_note, model = excluded.model""", rows)
        for r in rows:
            for t in json.loads(r[5]):
                conn.execute("INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, method) "
                             "VALUES (?, 'theme', ?, 'area', ?, 'belongs_to', 'sol')", (run_id, t, r[0]))
        # tracks: weight = comments; at cp2 the state is significance-tested like clusters
        total = sum(json.loads(r[8])["comments"] for r in rows) or 1
        ents = {f"area:{r[0]}": (json.loads(r[8])["comments"] / total, {"title": r[2]}) for r in rows}
        states = {}
        if parent:
            pm = {a["key"]: json.loads(a["metrics_json"])["comments"] for a in prev}
            ptot = sum(pm.values()) or 1
            for r in rows:
                if r[0] in pm:
                    c2 = json.loads(r[8])["comments"]
                    states[f"area:{r[0]}"] = z_state(pm[r[0]], ptot, max(c2 - pm[r[0]], 0), max(total - ptot, 1))
        tracks = C.write_tracks(conn, run_id, ents, states=states)
        stats = {"themes": len(digest), "areas": sum(r[4] != "quality" for r in rows), "quality_themes": len(quality),
                 "unassigned_themes": len(themes_in) - len(used), "tracks": tracks}
        C.finish_run(conn, run_id, stats)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["cp1", "cp2"], required=True)
    print(json.dumps(run_checkpoint(ap.parse_args().checkpoint), indent=1, default=str))
