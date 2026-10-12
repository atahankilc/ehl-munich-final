"""Stage `elicit` (D-043): themes + evidence graph → potential (candidate) requirements, per checkpoint.

sol drafts 0–2 candidates per theme in batches; each must be ONE product decision BMW could take or trade off.
Code checks (no LLM): themes that are only quality issues go to the quality hand-over; `at_successor_launch` needs a
dated trend/competitor edge, otherwise the horizon is set back to `today` and the gap is written as an assumption;
cited evidence ids must be among the theme's own edges; a market target without evidence from that market is
labelled an assumption. cp2 redrafts only dirty themes (theme track not held, or new edges) and passes the cp1
candidate so the model recalibrates instead of rewriting; clean themes carry their candidate forward (`held`).
Candidates stay proposals — they never touch PM decisions (rule 5).

`uv run python -m bmw_req.structure.elicit --checkpoint cp1` (then cp2)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.structure.events import log

BATCH = 6


class Metric(BaseModel):
    name: str
    unit: str
    method: str = Field(description="How it would be measured at launch")


class Target(BaseModel):
    line: Literal["1 Series", "5 Series", "7 Series"]
    market: Literal["EU", "US", "CN", "RoW"]
    rationale: str = Field(description="Why this car × market needs it, ≤ 25 words")
    evidence_ids: list[str]


class Draft(BaseModel):
    theme_key: str
    title: str = Field(description="≤ 10 words, the decision, not the problem")
    statement: str = Field(description="What the successor car should offer, as one product decision")
    decision_type: Literal["add_feature", "raise_capability", "change_design", "keep_strength", "package_variant", "market_variant"]
    today_status: Literal["standard", "optional", "package", "not_offered", "unknown"]
    metric: Metric
    targets: list[Target]
    horizon: Literal["today", "at_successor_launch"]
    horizon_year: int | None
    kano: Literal["basic", "performance", "delighter"]
    evidence_ids: list[str] = Field(description="ids from the theme's evidence list that support this candidate")
    trend_ids: list[str] = Field(description="dated research ids that justify a future need (subset of evidence)")
    assumptions: list[str]
    change_note: str | None = Field(description="Only when a previous version is given: what changed and why")


class ThemeDrafts(BaseModel):
    theme_key: str
    keep_previous: bool = Field(description="True if a previous version was given and is still right as it is")
    drafts: list[Draft]


class Batch(BaseModel):
    themes: list[ThemeDrafts]


INSTRUCTIONS = """You draft POTENTIAL customer requirements for the successor generation of BMW cars (launch ~2029–2030)
from customer themes and their evidence. The product manager decides; you only propose.

For each theme return 0–2 drafts. Each draft is ONE product decision BMW could take or trade off (add a feature,
raise a capability, change a design, keep a strength customers love, offer a package/variant, adapt for a market).
Never turn a defect into a requirement ("X must work reliably" is quality, not a requirement) — return no draft for
themes that are only about faults.
- today_status: use the 'available_as_option' evidence (standard/optional/package) — 'not_offered' only if the
  evidence shows it is missing; else 'unknown'.
- metric: something measurable at launch (name, unit, method).
- targets: only car line × market combinations the evidence supports; say why in ≤ 25 words with evidence ids.
  Markets are different customers — do not copy a target to markets without their own evidence.
- horizon: 'at_successor_launch' only if a dated trend or competitor item (trend_ids) shows the expectation is rising;
  otherwise 'today'. kano: basic (expected), performance (more is better), delighter (unexpected).
- evidence_ids / trend_ids: only ids from the theme's evidence list. assumptions: anything not backed by evidence.
- If a previous version is given: keep it (keep_previous=true, no drafts) unless the new evidence changes it; then
  return the recalibrated draft with change_note citing the new evidence ids.
Customer-facing scope only: no regulation, engineering specs or pricing."""



def theme_context(conn, ctx_run: int, theme_key: str) -> dict:
    ins = conn.execute("""SELECT i.cluster_key, i.title, i.statement, i.need_type, i.quality_issue, i.product_decision, i.payload_json
                          FROM insight i JOIN theme_member m ON m.cluster_key = i.cluster_key AND m.run_id = i.run_id
                          WHERE i.run_id = ? AND m.theme_key = ?""", (ctx_run, theme_key)).fetchall()
    findings, markets = [], Counter()
    for r in ins:
        p = json.loads(r["payload_json"])
        markets.update(p["by_line_market"])
        findings.append({"id": f"insight:{r['cluster_key']}", "title": r["title"], "statement": r["statement"],
                         "need_type": r["need_type"], "quality_issue": bool(r["quality_issue"]),
                         "comments": p["comments"], "by_line_market": p["by_line_market"]})
    evidence = []
    for e in conn.execute("SELECT src_type, src_id, relation, rationale FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme' "
                          "AND dst_id = ? AND src_type IN ('research','study','option')", (ctx_run, theme_key)):
        evidence.append({"id": f"{e['src_type']}:{e['src_id']}", "relation": e["relation"], "why": e["rationale"],
                         **describe(conn, e["src_type"], int(e["src_id"]))})
    t = conn.execute("SELECT title, statement, category FROM theme WHERE key = ?", (theme_key,)).fetchone()
    return {"theme_key": theme_key, "title": t["title"], "statement": t["statement"], "category": t["category"],
            "comments_by_line_market": dict(markets), "findings": findings, "evidence": evidence}


def describe(conn, typ: str, nid: int) -> dict:
    if typ == "research":
        r = conn.execute("SELECT text, published_at, trust_tier, market_code FROM source_item WHERE id = ?", (nid,)).fetchone()
        return {"text": r["text"][:300], "published": r["published_at"], "tier": r["trust_tier"], "market": r["market_code"]}
    if typ == "study":
        r = conn.execute("SELECT item, vehicle_model_id, market_code, z_within_column, COALESCE(mean, top2) v FROM study_metric WHERE id = ?", (nid,)).fetchone()
        return {"text": f"{r['item']} ({r['vehicle_model_id']} {r['market_code']})", "z": round(r["z_within_column"] or 0, 2), "value": r["v"]}
    r = conn.execute("SELECT vehicle_model_id, meta_json FROM source_item WHERE id = ?", (nid,)).fetchone()
    m = json.loads(r["meta_json"] or "{}")
    return {"text": f"{r['vehicle_model_id']}: {m.get('name_en')}", "availability": m.get("availability"), "package": m.get("package_name")}


def validate(d: Draft, ctx: dict) -> tuple[Draft, list[str]]:
    """Code checks: allowed evidence ids, dated support for future claims, market evidence per target."""
    ev = {e["id"]: e for e in ctx["evidence"]} | {f["id"]: f for f in ctx["findings"]}
    notes = []
    d.evidence_ids = [i for i in d.evidence_ids if i in ev]
    dated = {i for i, e in ev.items() if i.startswith("research:") and e.get("relation") in ("trend_for", "competes_with") and e.get("published")}
    d.trend_ids = [i for i in d.trend_ids if i in dated]
    if d.horizon == "at_successor_launch" and not d.trend_ids:
        d.horizon, d.horizon_year = "today", None
        notes.append("No dated trend or competitor evidence: horizon set to 'today'.")
    voice = ctx["comments_by_line_market"]
    for t in d.targets:
        t.evidence_ids = [i for i in t.evidence_ids if i in ev]
        own = voice.get(f"{t.line}:{t.market}", 0) > 0 or any(ev[i].get("market") == t.market for i in t.evidence_ids if i.startswith("research:"))
        if not own:
            t.rationale = f"[assumption: no own evidence for {t.market}] {t.rationale}"
    return d, notes


def run_checkpoint(cp: str, actor: str = "system") -> dict:
    conn = connect()
    llm = LLM(conn=conn)
    ctx_run = C.latest_run(conn, cp, "contextualize")
    if ctx_run is None:
        raise C.CheckpointError(f"Run 'contextualize' at {cp} first")
    conn.execute("BEGIN IMMEDIATE")
    run_id = C.start_run(conn, cp, "elicit", actor)
    conn.execute("COMMIT")
    parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    theme_keys = [r[0] for r in conn.execute("SELECT DISTINCT theme_key FROM theme_member WHERE run_id = ?", (ctx_run["id"],))]
    tstate = {r["entity_key"][6:]: r["state"] for r in conn.execute("SELECT entity_key, state FROM track WHERE run_id = ? AND entity_key LIKE 'theme:%'", (ctx_run["id"],))}
    prev = defaultdict(list)
    if parent:
        for r in conn.execute("SELECT * FROM candidate WHERE run_id = ?", (parent,)):
            prev[r["theme_key"]].append(r)
    new_edge_themes = set()
    if parent:
        new_edge_themes = {r["entity_key"].split(">")[-1] for r in conn.execute(
            "SELECT entity_key FROM track WHERE run_id = ? AND entity_key LIKE 'edge:%' AND state = 'new'", (ctx_run["id"],))}

    rows, carried, quality = [], 0, 0
    todo = []
    for tk in theme_keys:
        ctx = theme_context(conn, ctx_run["id"], tk)
        if ctx["findings"] and all(f["quality_issue"] for f in ctx["findings"]):
            rows.append(dict(key=f"cand:{tk}:q", version=1, parent_id=None, theme_key=tk, status="quality", title=ctx["title"],
                             statement=ctx["statement"], decision_type=None, today_status=None, horizon=None, horizon_year=None,
                             kano=None, detail={"reason": "only quality issues — quality hand-over"}, model=None))
            quality += 1
            continue
        dirty = not parent or tstate.get(tk) not in ("held", None) or tk in new_edge_themes or tk not in prev
        if not dirty:
            for p in prev[tk]:
                rows.append(dict(key=p["key"], version=p["version"], parent_id=p["id"], theme_key=tk, status=p["status"], title=p["title"],
                                 statement=p["statement"], decision_type=p["decision_type"], today_status=p["today_status"],
                                 horizon=p["horizon"], horizon_year=p["horizon_year"], kano=p["kano"],
                                 detail=json.loads(p["detail_json"] or "{}"), model=p["model"]))
                carried += 1
            continue
        if parent and prev.get(tk):
            ctx["previous"] = [{"title": p["title"], "statement": p["statement"], **json.loads(p["detail_json"] or "{}")} for p in prev[tk]]
        todo.append(ctx)

    log(conn, "elicit", "start", {"themes": len(theme_keys), "to_draft": len(todo), "carried": carried, "quality": quality}, run_id)
    drafted = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        res = llm.generate(job=f"elicit:{cp}", tier="smart", instructions=INSTRUCTIONS,
                           input=json.dumps(chunk, ensure_ascii=False, default=str), schema=Batch,
                           reasoning_effort="medium", max_output_tokens=20_000, flex=True)
        ctx_by = {c["theme_key"]: c for c in chunk}
        got = res.parsed.themes if res.parsed else []
        log(conn, "elicit", "draft", {"themes": len(chunk), "drafts": sum(len(t.drafts) for t in got),
            "examples": [d.title for t in got for d in t.drafts][:3]}, run_id, llm.model_for("smart"))
        for th in (res.parsed.themes if res.parsed else []):
            ctx = ctx_by.get(th.theme_key)
            if ctx is None:
                continue
            if th.keep_previous and prev.get(th.theme_key):
                for p in prev[th.theme_key]:
                    rows.append(dict(key=p["key"], version=p["version"], parent_id=p["id"], theme_key=th.theme_key, status=p["status"],
                                     title=p["title"], statement=p["statement"], decision_type=p["decision_type"],
                                     today_status=p["today_status"], horizon=p["horizon"], horizon_year=p["horizon_year"],
                                     kano=p["kano"], detail=json.loads(p["detail_json"] or "{}"), model=p["model"]))
                continue
            for n, d in enumerate(th.drafts[:2]):
                d, notes = validate(d, ctx)
                old = prev.get(th.theme_key, [])
                parent_row = old[n] if n < len(old) else None
                rows.append(dict(key=parent_row["key"] if parent_row else f"cand:{th.theme_key}:{n}",
                                 version=(parent_row["version"] + 1) if parent_row else 1,
                                 parent_id=parent_row["id"] if parent_row else None, theme_key=th.theme_key, status="candidate",
                                 title=d.title, statement=d.statement, decision_type=d.decision_type, today_status=d.today_status,
                                 horizon=d.horizon, horizon_year=d.horizon_year, kano=d.kano,
                                 detail={"metric": d.metric.model_dump(), "targets": [t.model_dump() for t in d.targets],
                                         "evidence_ids": d.evidence_ids, "trend_ids": d.trend_ids,
                                         "assumptions": d.assumptions + notes, "change_note": d.change_note},
                                 model=llm.model_for("smart")))
                drafted += 1

    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in rows:
            cur = conn.execute("""INSERT INTO candidate (key, version, run_id, parent_id, theme_key, status, title, statement, decision_type,
                                  today_status, horizon, horizon_year, kano, detail_json, model)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                               (r["key"], r["version"], run_id, r["parent_id"], r["theme_key"], r["status"], r["title"], r["statement"],
                                r["decision_type"], r["today_status"], r["horizon"], r["horizon_year"], r["kano"],
                                json.dumps(r["detail"]), r["model"]))
            cid = str(cur.fetchone()[0])
            if r["parent_id"] and r["version"] > 1:
                conn.execute("""INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, method)
                                VALUES (?, 'candidate', ?, 'candidate', ?, 'recalibrates', 'sol')""", (run_id, cid, str(r["parent_id"])))
            conn.execute("""INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, method)
                            VALUES (?, 'candidate', ?, 'theme', ?, 'derived_from', 'sol')""", (run_id, cid, r["theme_key"]))
        weight = {}
        for r in conn.execute("SELECT entity_key, weight FROM track WHERE run_id = ? AND entity_key LIKE 'theme:%'", (ctx_run["id"],)):
            weight[r[0][6:]] = r[1] or 0
        ents, states = {}, {}
        for r in rows:
            ents[f"cand:{r['key']}"] = (float(weight.get(r["theme_key"], 0)), {"version": r["version"], "status": r["status"]})
            if parent and r["parent_id"]:
                states[f"cand:{r['key']}"] = "held" if r["version"] == 1 or not r["detail"].get("change_note") else \
                    ("strengthened" if tstate.get(r["theme_key"]) == "strengthened" else "weakened" if tstate.get(r["theme_key"]) == "weakened" else "held")
        tracks = C.write_tracks(conn, run_id, ents, states=states)
        stats = {"themes": len(theme_keys), "drafted": drafted, "carried": carried, "quality": quality,
                 "candidates": sum(r["status"] == "candidate" for r in rows), "tracks": tracks}
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
