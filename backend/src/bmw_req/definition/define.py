"""Stage `define` (D-048): requirement AREAS → concrete requirements, per checkpoint (BMW step 3, first half).

The successor of `structure/elicit.py` (never run), re-targeted from themes to areas. sol drafts 1–3 requirements per
non-quality area in batches; each is ONE product decision (D-038): defects never become requirements, a `keep` area
becomes a `keep_strength` requirement whose metric later says what must not be lost. The model picks aspects from the
taxonomy (primary first) — domain and car zones are derived from them in code (`domains.py`), never by the model.
Context per area: the area itself (need, kind, why_now, open questions, comments per line × market, market context)
plus its themes' insights and evidence from the latest `contextualize` run (research / web / reference / study /
option edges, D-047), trimmed to the supporting, contradicting, trend and competitor links plus a few context links.

Code checks (no LLM), as in elicit.validate: cited ids must be in the area's own evidence; `at_successor_launch`
needs a dated trend/competitor id, else the horizon falls back to `today` with a note; a line × market target without
evidence from that market (comments there, a study item for that car and market, or research for that market) is
labelled `[assumption: …]`; today_status other than unknown/not_offered needs an option edge in the area.
cp2: areas whose track is held and whose themes got no new evidence edge carry their requirements forward; the
others are re-drafted with the previous version passed in (keep it, or recalibrate with a change_note). Keys
`rq:<area-slug>:<n>` are stable across checkpoints; edges def_requirement→area `derived_from`, →parent
`recalibrates`, →evidence `cites`. Requirements stay `proposed` — the PM decides (rule 5).

This module also owns the schema of all def_* tables (spec_fact belongs to `benchmarks.py`).
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.definition.domains import domain_for, zones_for
from bmw_req.llm import LLM
from bmw_req.portfolio import LINES, TARGETS
from bmw_req.structure.elicit import describe
from bmw_req.structure.events import log
from bmw_req.structure.market import LINE_OF_CAR
from bmw_req.structure.taxonomy import ALL_ASPECTS, taxonomy_text

BATCH = 5
MAX_REQ = 3
MAX_TARGETS = 4
MIN_MARKET_COMMENTS = 3   # fewer comments from a line × market is not its own evidence
MEANINGFUL = ("supports", "contradicts", "trend_for", "competes_with")
CONTEXT_EDGES = 3          # 'context' research/study links kept per area (the rest is support/contradiction/trend)
LINE_MARKETS: dict[str, list[str]] = {
    line: [m for d in cfg["derivatives"] for m in TARGETS[d]] for line, cfg in LINES.items()}
ASPECTS = [a for a in ALL_ASPECTS if a != "other"]




# ------------------------------------------------------------------------------------------------ schema (LLM)
class Target(BaseModel):
    line: Literal["1 Series", "5 Series", "7 Series"]
    market: Literal["EU", "US", "CN", "RoW"]
    note: str = Field(description="Why this car × market needs it, ≤ 12 words")


class ReqDraft(BaseModel):
    replaces: str | None = Field(description="Key of the previous requirement this continues (only when previous versions are given)")
    title: str = Field(description="≤ 10 words, the decision, not the problem")
    statement: str = Field(description="What the successor car should offer, one product decision, ≤ 40 words")
    aspects: list[str] = Field(description="1–3 aspect slugs from the taxonomy, primary first")
    decision_type: Literal["add_feature", "raise_capability", "change_design", "keep_strength", "package_variant", "market_variant"]
    today_status: Literal["standard", "optional", "package", "not_offered", "unknown"]
    targets: list[Target]
    horizon: Literal["today", "at_successor_launch"]
    horizon_year: int | None
    kano: Literal["basic", "performance", "delighter"]
    evidence_ids: list[str] = Field(description="ids from the area's findings/evidence that support this requirement")
    trend_ids: list[str] = Field(description="dated research ids that show the expectation rising (subset of evidence)")
    assumptions: list[str] = Field(description="≤ 3, each ≤ 15 words")
    change_note: str | None = Field(description="Only when recalibrating a previous version: what changed and why, citing new ids")


class AreaReqs(BaseModel):
    area_key: str
    keep_previous: bool = Field(description="True only if previous versions were given and are still right as they are")
    requirements: list[ReqDraft]


class Batch(BaseModel):
    areas: list[AreaReqs]


INSTRUCTIONS = f"""You define CUSTOMER REQUIREMENTS for the successor generation of BMW cars (launch ~2029–2031) from
potential-requirement AREAS and their evidence. The product manager decides; you only propose (status 'proposed').

For each area return 1–3 requirements. Each requirement is ONE product decision BMW could take or trade off: add a
feature, raise a capability, change a design, keep a strength, offer a package/variant, adapt for a market. Split
independent decisions; never bundle. Fewer, sharper requirements beat many vague ones: 1–2 is typical, 3 only when
the area clearly holds three independent decisions.
- Never turn a defect into a requirement ("X must work reliably" is quality, not a product decision). If an area mixes
  faults and a real decision, draft only the decision.
- kind 'keep' → decision_type 'keep_strength': state what customers love and what the successor must not lose.
- aspects: 1–3 slugs from the taxonomy below, primary first (the primary aspect decides where the requirement sits on
  the car). Use only these slugs.
- targets: car line × market combinations. Valid: 1 Series: EU, RoW · 5 Series: US, EU, RoW, CN (China = long-wheelbase
  G68) · 7 Series: US, CN, EU, RoW. Add a target only where the area's comments_by_line_market, a study item for that
  car and market, or market-specific research supports it; markets are different customers — do not copy a target to
  every market. At most {MAX_TARGETS} targets, strongest evidence first.
- today_status: from the 'available_as_option' evidence (standard / optional / package, German price list); 'not_offered'
  only if the evidence shows it is missing; else 'unknown'.
- horizon: 'at_successor_launch' only if a dated trend or competitor item (trend_ids) shows the expectation rising;
  else 'today'. kano: basic (expected), performance (more is better), delighter (unexpected).
- evidence_ids / trend_ids: only ids from that area's findings and evidence lists; cite every finding and evidence
  item that supports the requirement (typically 2–6). assumptions: what is not backed by evidence (forward-looking
  needs, market transfer, equipment outside Germany) — ≤ 3, terse.
- No metric or numbers here (that is the next step). Customer-facing scope only: no regulation, engineering or
  component specs, suppliers or pricing. Assistance only as experienced (availability, usability, trust).
- If previous versions are given: keep them (keep_previous=true, no requirements) unless the new evidence changes
  them; otherwise return the recalibrated requirements with `replaces` = previous key and change_note citing the new ids.

Aspect taxonomy:
{taxonomy_text()}"""


# ------------------------------------------------------------------------------------------------ LLM
class FlexUnavailable(Exception):
    pass


def generate(llm: LLM, waits: tuple[int, ...] = (30, 60, 120), **kw):
    """`llm.generate` that waits for Flex capacity before paying the standard price. The wrapper's own fallback (one
    immediate retry at standard processing, 2× price) is intercepted while waits remain; after the last wait it is
    allowed. Flex rejections are not billed (settled at $0)."""
    orig = llm.generate

    def no_fallback(**k):
        if not k.get("flex") and "_cache_key_override" in k:
            raise FlexUnavailable
        return orig(**k)

    for w in waits:
        llm.generate = no_fallback   # instance attribute: the wrapper's recursive self.generate hits it
        try:
            return orig(**kw)
        except FlexUnavailable:
            time.sleep(w)
        finally:
            del llm.generate
    return orig(**kw)


# ------------------------------------------------------------------------------------------------ context
def area_slug(area_key: str) -> str:
    return area_key.removeprefix("ar:")


def area_context(conn, ctx_run: int, area) -> dict:
    """Everything the model and the code checks need about one area (compact: ids, short texts, counts)."""
    themes = json.loads(area["theme_keys_json"])
    metrics = json.loads(area["metrics_json"] or "{}")
    findings, aspects = [], Counter()
    q = ",".join("?" * len(themes))
    for r in conn.execute(f"""SELECT i.cluster_key, i.title, i.statement, i.need_type, i.quality_issue, i.payload_json, m.theme_key
                              FROM insight i JOIN theme_member m ON m.cluster_key = i.cluster_key AND m.run_id = i.run_id
                              WHERE i.run_id = ? AND m.theme_key IN ({q})""", (ctx_run, *themes)):
        p = json.loads(r["payload_json"])
        aspects.update(p.get("aspects") or {})
        findings.append({"id": f"insight:{r['cluster_key']}", "title": r["title"], "statement": r["statement"],
                         "need_type": r["need_type"], "quality_issue": bool(r["quality_issue"]), "comments": p["comments"],
                         "by_line_market": p["by_line_market"]})
    findings.sort(key=lambda f: -f["comments"])
    evidence, seen, n_ctx = [], set(), 0
    rank = {"contradicts": 0, "trend_for": 1, "competes_with": 2, "supports": 3, "available_as_option": 4, "context": 5}
    edges = conn.execute(f"""SELECT src_type, src_id, relation, rationale FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme'
                             AND dst_id IN ({q}) AND src_type IN ('research','study','option')""", (ctx_run, *themes)).fetchall()
    for e in sorted(edges, key=lambda e: rank.get(e["relation"], 9)):
        eid = f"{e['src_type']}:{e['src_id']}"
        if eid in seen:
            continue
        if e["relation"] == "context":
            if n_ctx >= CONTEXT_EDGES:
                continue
            n_ctx += 1
        seen.add(eid)
        d = describe(conn, e["src_type"], int(e["src_id"]))
        if e["src_type"] == "study":
            r = conn.execute("SELECT vehicle_model_id, market_code FROM study_metric WHERE id = ?", (int(e["src_id"]),)).fetchone()
            d["line"], d["market"] = LINE_OF_CAR.get(r["vehicle_model_id"]), r["market_code"]
        if e["src_type"] == "option":
            d["line"] = LINE_OF_CAR.get(conn.execute("SELECT vehicle_model_id FROM source_item WHERE id = ?",
                                                     (int(e["src_id"]),)).fetchone()[0])
        evidence.append({"id": eid, "relation": e["relation"], "why": (e["rationale"] or "")[:160], **d})
    mk = metrics.get("market") or {}
    return {"area_key": area["key"], "title": area["title"], "need": area["need"], "kind": area["kind"],
            "why_now": area["why_now"], "open_questions": json.loads(area["open_questions_json"] or "[]"),
            "comments": metrics.get("comments"), "comments_by_line_market": metrics.get("by_line_market") or {},
            "market": [{k: v for k, v in r.items() if k in ("key", "bmw_share", "trend", "conflict")} for r in mk.get("markets", [])][:6]
            if isinstance(mk, dict) else None,
            "aspect_hint": [a for a, _ in aspects.most_common(5) if a in ASPECTS],
            "findings": findings[:12], "evidence": evidence, "_themes": themes}


def own_evidence(ctx: dict, line: str, market: str, ids: list[str]) -> bool:
    """A line × market has its own evidence: comments from it, a study item for that car and market, or research for
    that market among the cited ids (options are German price-list facts, never market evidence)."""
    if (ctx["comments_by_line_market"].get(f"{line}:{market}") or 0) >= MIN_MARKET_COMMENTS:
        return True
    ev = {e["id"]: e for e in ctx["evidence"]}
    for i in ids:
        e = ev.get(i)
        if not e:
            continue
        if i.startswith("study:") and e.get("line") == line and e.get("market") == market:
            return True
        if i.startswith("research:") and e.get("market") == market:
            return True
    return False


def validate(d: ReqDraft, ctx: dict) -> tuple[dict, list[str]]:
    """Code checks → a row dict (without key/version) and the notes added to its assumptions."""
    ev = {e["id"]: e for e in ctx["evidence"]} | {f["id"]: f for f in ctx["findings"]}
    notes: list[str] = []
    aspects = [a for a in dict.fromkeys(d.aspects) if a in ASPECTS][:3] or ctx["aspect_hint"][:1] or ["equipment_availability"]
    evidence_ids = [i for i in dict.fromkeys(d.evidence_ids) if i in ev]
    if not evidence_ids:
        evidence_ids = [f["id"] for f in ctx["findings"][:3]]
        notes.append("Model cited no valid evidence id: linked to the area's largest findings.")
    dated = {i for i, e in ev.items() if i.startswith("research:") and e.get("relation") in ("trend_for", "competes_with") and e.get("published")}
    trend_ids = [i for i in dict.fromkeys(d.trend_ids) if i in dated]
    horizon, year = d.horizon, d.horizon_year
    if horizon == "at_successor_launch" and not trend_ids:
        horizon, year = "today", None
        notes.append("No dated trend or competitor evidence: horizon set to 'today'.")
    if horizon == "today":
        year = None
    today = d.today_status
    if today in ("standard", "optional", "package") and not any(e.get("relation") == "available_as_option" for e in ctx["evidence"]):
        today = "unknown"
        notes.append("No option-list evidence in the area: today_status set to 'unknown'.")
    targets, seen = [], set()
    for t in d.targets:
        if t.market not in LINE_MARKETS[t.line] or (t.line, t.market) in seen:
            continue
        seen.add((t.line, t.market))
        own = own_evidence(ctx, t.line, t.market, evidence_ids)
        note = t.note if own else f"[assumption: no own evidence for {t.line} {t.market}] {t.note}"
        targets.append({"line": t.line, "market": t.market, "own_evidence": own, "note": note,
                        "comments": ctx["comments_by_line_market"].get(f"{t.line}:{t.market}") or 0})
    targets.sort(key=lambda t: (not t["own_evidence"], -(ctx["comments_by_line_market"].get(f"{t['line']}:{t['market']}") or 0)))
    if len(targets) > MAX_TARGETS:
        notes.append(f"Targets capped at {MAX_TARGETS} (kept those with own evidence first).")
        targets = targets[:MAX_TARGETS]
    if not targets:   # fall back to where the comments come from
        for k, n in sorted(ctx["comments_by_line_market"].items(), key=lambda kv: -kv[1])[:3]:
            line, market = k.split(":")
            if market in LINE_MARKETS.get(line, []):
                targets.append({"line": line, "market": market, "own_evidence": n >= MIN_MARKET_COMMENTS, "note": f"{n} comments",
                                "comments": n})
        notes.append("Model gave no valid target: targets set to the markets the comments come from.")
    decision_type = "keep_strength" if ctx["kind"] == "keep" and d.decision_type not in ("keep_strength", "market_variant") else d.decision_type
    return dict(title=d.title, statement=d.statement, domain=domain_for(aspects), aspects=aspects, zones=zones_for(aspects),
                lines=list(dict.fromkeys(t["line"] for t in targets)), markets=list(dict.fromkeys(t["market"] for t in targets)),
                targets=targets, decision_type=decision_type, today_status=today, horizon=horizon, horizon_year=year,
                kano=d.kano, evidence_ids=evidence_ids, trend_ids=trend_ids, assumptions=d.assumptions + notes,
                change_note=d.change_note), notes


def _carry(p) -> dict:
    return dict(key=p["key"], version=p["version"], parent_id=p["id"], area_key=p["area_key"], title=p["title"],
                statement=p["statement"], domain=p["domain"], aspects=json.loads(p["aspects_json"]), zones=json.loads(p["zones_json"]),
                lines=json.loads(p["lines_json"]), markets=json.loads(p["markets_json"]), targets=json.loads(p["targets_json"] or "[]"),
                decision_type=p["decision_type"], today_status=p["today_status"], horizon=p["horizon"], horizon_year=p["horizon_year"],
                kano=p["kano"], evidence_ids=json.loads(p["evidence_ids_json"]), trend_ids=json.loads(p["trend_ids_json"]),
                assumptions=json.loads(p["assumptions_json"]), change_note=None, model=p["model"], carried=True)


def _prev_view(p) -> dict:
    return {"key": p["key"], "title": p["title"], "statement": p["statement"], "aspects": json.loads(p["aspects_json"]),
            "decision_type": p["decision_type"], "today_status": p["today_status"], "horizon": p["horizon"], "kano": p["kano"],
            "targets": [{k: t[k] for k in ("line", "market")} for t in json.loads(p["targets_json"] or "[]")],
            "evidence_ids": json.loads(p["evidence_ids_json"])}


def llm_input(chunk: list[dict]) -> str:
    return json.dumps([{k: v for k, v in c.items() if not k.startswith("_")} for c in chunk], ensure_ascii=False, default=str)


# ------------------------------------------------------------------------------------------------ run
def run(conn, cp: str, actor: str = "system", pilot: int | None = None, llm: LLM | None = None) -> dict:
    """Run `define` at `cp`. `pilot=N`: draft only the first N areas, print-only (no run, no rows; LLM calls are cached
    so the full run reuses an identical first batch)."""
    llm = llm or LLM(conn=conn)
    arun, xrun = C.latest_run(conn, cp, "areas"), C.latest_run(conn, cp, "contextualize")
    if arun is None or xrun is None:
        raise C.CheckpointError(f"Run 'contextualize' and 'areas' at {cp} first")
    areas = conn.execute("SELECT * FROM req_area WHERE run_id = ? AND kind != 'quality' ORDER BY key", (arun["id"],)).fetchall()
    run_id = parent = None
    if not pilot:
        conn.execute("BEGIN IMMEDIATE")
        run_id = C.start_run(conn, cp, "define", actor)
        conn.execute("COMMIT")
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    elif C.BY_ID[cp].parent_id:
        p = C.latest_run(conn, C.BY_ID[cp].parent_id, "define")
        parent = p["id"] if p else None
    prev = defaultdict(list)
    if parent:
        for r in conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY key", (parent,)):
            prev[r["area_key"]].append(r)
    astate = {r["entity_key"][5:]: r["state"] for r in conn.execute(
        "SELECT entity_key, state FROM track WHERE run_id = ? AND entity_key LIKE 'area:%'", (arun["id"],))}
    aweight = {r["entity_key"][5:]: r["weight"] or 0 for r in conn.execute(
        "SELECT entity_key, weight FROM track WHERE run_id = ? AND entity_key LIKE 'area:%'", (arun["id"],))}
    new_edges = defaultdict(list)   # theme → new evidence ids that can change a requirement (not mere context links)
    if parent:
        for (k,) in conn.execute("SELECT entity_key FROM track WHERE run_id = ? AND entity_key LIKE 'edge:%' AND state = 'new'", (xrun["id"],)):
            src, rel, theme = k[5:].split(">")
            if rel in MEANINGFUL:
                new_edges[theme].append(f"{src} ({rel})")

    rows, todo, carried = [], [], 0
    ctxs = {}
    for a in areas:
        ctx = area_context(conn, xrun["id"], a)
        ctxs[a["key"]] = ctx
        fresh = [e for t in ctx["_themes"] for e in new_edges.get(t, [])]
        # cp2 re-drafts only areas that moved (new / strengthened / weakened); a held area carries its requirements even
        # when relinking added edges (cp2 has ~1,000 new edge tracks, mostly re-found context)
        dirty = not parent or a["key"] not in prev or astate.get(a["key"]) not in ("held", None)
        if not dirty:
            rows += [_carry(p) for p in prev[a["key"]]]
            carried += len(prev[a["key"]])
            continue
        if prev.get(a["key"]):
            ctx["previous"] = [_prev_view(p) for p in prev[a["key"]]]
            ctx["new_evidence"] = fresh[:12]
            ctx["area_change"] = astate.get(a["key"])
        todo.append(ctx)
    if pilot:
        todo = todo[:pilot]
    else:
        log(conn, "define", "start", {"areas": len(areas), "to_draft": len(todo), "carried": carried}, run_id)

    model = llm.model_for("smart")
    drafted, kept, failed = 0, 0, []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:   # ~5k tokens per area is ample; the cap bounds a runaway structured output
            res = generate(llm, job=f"define:{cp}", tier="smart", instructions=INSTRUCTIONS, input=llm_input(chunk), schema=Batch,
                               reasoning_effort="medium", max_output_tokens=4_800 * len(chunk), flex=True)
            got = res.parsed.areas if res.parsed else []
        except Exception as e:   # one bad batch must not lose the others: its areas stay undrafted, logged
            got = []
            failed += [c["area_key"] for c in chunk]
            if not pilot:
                log(conn, "define", "batch_failed", {"areas": [c["area_key"] for c in chunk], "error": repr(e)[:300]}, run_id)
        by = {c["area_key"]: c for c in chunk}
        for ar in got:
            ctx = by.get(ar.area_key)
            if ctx is None:
                continue
            old = prev.get(ar.area_key, [])
            if ar.keep_previous and old:
                rows += [_carry(p) for p in old]
                kept += len(old)
                continue
            used: set[str] = set()
            old_by_key = {p["key"]: p for p in old}
            for n, d in enumerate(ar.requirements[:MAX_REQ]):
                row, _ = validate(d, ctx)
                p = old_by_key.get(d.replaces) if d.replaces in old_by_key and d.replaces not in used else None
                if p is None and old:
                    p = next((o for o in old if o["key"] not in used), None) if not d.replaces else None
                if p is not None:
                    used.add(p["key"])
                    key, version, pid = p["key"], p["version"] + 1, p["id"]
                else:
                    taken = {r["key"] for r in rows} | {o["key"] for o in old}
                    k = n
                    while f"rq:{area_slug(ar.area_key)}:{k}" in taken:
                        k += 1
                    key, version, pid = f"rq:{area_slug(ar.area_key)}:{k}", 1, None
                rows.append(dict(key=key, version=version, parent_id=pid, area_key=ar.area_key, model=model, **row))
                drafted += 1
        if not pilot:
            log(conn, "define", "draft", {"areas": len(chunk), "requirements": sum(len(a.requirements) for a in got),
                "examples": [d.title for a in got for d in a.requirements][:3]}, run_id, model)
    if pilot:
        return {"pilot": True, "areas": [c["area_key"] for c in todo], "rows": rows}

    conn.execute("BEGIN IMMEDIATE")
    try:
        ids = {}
        for r in rows:
            cur = conn.execute("""INSERT INTO def_requirement (key, version, run_id, parent_id, area_key, status, title, statement, domain,
                                  aspects_json, zones_json, lines_json, markets_json, targets_json, decision_type, today_status, horizon,
                                  horizon_year, kano, evidence_ids_json, trend_ids_json, assumptions_json, change_note, model)
                                  VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                               (r["key"], r["version"], run_id, r["parent_id"], r["area_key"], r["title"], r["statement"], r["domain"],
                                json.dumps(r["aspects"]), json.dumps(r["zones"]), json.dumps(r["lines"]), json.dumps(r["markets"]),
                                json.dumps(r["targets"], ensure_ascii=False), r["decision_type"], r["today_status"], r["horizon"],
                                r["horizon_year"], r["kano"], json.dumps(r["evidence_ids"]), json.dumps(r["trend_ids"]),
                                json.dumps(r["assumptions"], ensure_ascii=False), r["change_note"], r["model"]))
            rid = str(cur.fetchone()[0])
            ids[r["key"]] = rid
            edges = [(run_id, "def_requirement", rid, "area", r["area_key"], "derived_from", "sol")]
            if r["parent_id"] and not r.get("carried"):
                edges.append((run_id, "def_requirement", rid, "def_requirement", str(r["parent_id"]), "recalibrates", "sol"))
            for e in r["evidence_ids"]:
                typ, nid = e.split(":", 1)
                edges.append((run_id, "def_requirement", rid, typ, nid, "cites", "sol"))
            conn.executemany("INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, method) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", edges)
        ents = {f"rq:{r['key']}": (float(aweight.get(r["area_key"], 0)), {"version": r["version"], "title": r["title"],
                                                                         "domain": r["domain"]}) for r in rows}
        states = {}
        for r in rows:
            if parent and r["parent_id"]:
                st = astate.get(r["area_key"], "held")
                states[f"rq:{r['key']}"] = "held" if r.get("carried") or not r["change_note"] else \
                    (st if st in ("strengthened", "weakened") else "strengthened")
        tracks = C.write_tracks(conn, run_id, ents, states=states)
        stats = {"areas": len(areas), "drafted": drafted, "carried": carried, "kept": kept, "requirements": len(rows), "failed_areas": failed,
                 "by_domain": dict(Counter(r["domain"] for r in rows)), "tracks": tracks,
                 "upstream": {"areas": arun["id"], "contextualize": xrun["id"]}}
        C.finish_run(conn, run_id, stats)
        log(conn, "define", "finish", stats, run_id)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}
