"""Stage `specify` (D-048): requirements → measurable metric, acceptance criteria and a target ladder per line × market.

BMW step 3, second half ("Range: 600 or 700 mi?"). sol gets, per requirement, the cited numeric benchmarks visible at
the checkpoint (`benchmarks.facts_for` on its aspects), customer-study items for its aspects / lines / markets
(today's satisfaction — CN/EU mean of 10 and US 7-point top-2 share are different scales and never converted), option
availability (German price list → US/CN equipment is an assumption), the requirement's own evidence and trend ids.
It returns ONE customer-experienced metric, ≤ 4 acceptance criteria with market conditions, and per line × market a
ladder baseline (today's BMW) → threshold (competitive parity) → target (need at successor launch) → stretch, a
recommended rung and its rationale. The PM chooses the rung (`def_choice`), never the AI.

Code checks (no LLM) — every number keeps an honest basis:
- `cited`: source ids must be among the ids the model was given, the value (if any) must literally be a value of one
  of the cited facts / study items / research texts, cited facts may not mix test cycles (CLTC ≠ WLTP ≠ EPA), and an
  unverified fact supports `cited` only together with another source — else the level becomes `assumption` + note.
- `projected` must name a dated trend / competitor id (research trend id or a benchmark fact), else `assumption`.
- `gap` has no value; every gap level gets an entry in `gaps` (an open question / research task). Never invent.
- target never below threshold, stretch never below target in the metric direction (swapped back with a note).
- rungs only for the requirement's targets; a missing target gets an all-gap rung; markets without own evidence keep
  the `[assumption …]` label on the rationale.
cp2: re-specify only requirements whose define version changed or whose aspects got new verified facts in the
metric's own tangible unit (`fact_delta` → `moved_facts`, "the bar moved"); the previous spec is passed in and the change_note must cite the new fact ids; the rest carry forward.
Tracks `spec:<key>`: payload = recommended value per line × market; state strengthened / weakened when the bar moved
up / down in the metric direction (payload.moved says how), held otherwise.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.definition import benchmarks as B
from bmw_req.definition.define import area_context, generate
from bmw_req.llm import LLM
from bmw_req.structure.elicit import describe
from bmw_req.structure.events import log
from bmw_req.structure.market import LINE_OF_CAR

BATCH = 4
FACTS = 20
STUDY = 8
RUNGS = ("baseline", "threshold", "target", "stretch")


# ------------------------------------------------------------------------------------------------ schema (LLM)
class Level(BaseModel):
    value: float | None = Field(description="Number in the metric's unit; null for gap or a text-only level")
    text: str = Field(description="≤ 8 words, e.g. '≥ 600 km highway range'")
    basis: Literal["cited", "projected", "assumption", "gap"]
    source_ids: list[str] = Field(description="cited: fact/study/evidence ids holding this value; projected: the trend ids")
    note: str = Field(description="≤ 10 words, may be empty")


class Rung(BaseModel):
    line: Literal["1 Series", "5 Series", "7 Series"]
    market: Literal["EU", "US", "CN", "RoW"]
    baseline: Level | None
    threshold: Level
    target: Level
    stretch: Level | None
    recommended: Literal["threshold", "target", "stretch"]
    rationale: str = Field(description="≤ 20 words: why this rung for this car × market")


class Metric(BaseModel):
    name: str = Field(description="Customer-experienced measure, e.g. 'Real-world highway range at 120 km/h'")
    unit: str
    direction: Literal["higher", "lower", "binary"]
    method: str = Field(description="How it is measured at launch: road/climate test, customer clinic, owner survey")
    conditions: str = Field(description="Test conditions incl. the markets' climates/usage")


class Acceptance(BaseModel):
    criterion: str
    condition: str
    pass_threshold: str


class Spec(BaseModel):
    req_key: str
    keep_previous: bool = Field(description="True only if a previous spec was given and the new facts do not move it")
    metric: Metric | None
    acceptance: list[Acceptance]
    ladder: list[Rung]
    gaps: list[str] = Field(description="Open questions / research tasks for every missing number")
    assumptions: list[str] = Field(description="≤ 3, terse")
    change_note: str | None = Field(description="Only with a previous spec: what moved and why, citing new fact ids")


class Batch(BaseModel):
    specs: list[Spec]


INSTRUCTIONS = """You turn proposed BMW customer requirements (successor cars, launch ~2029–2031) into MEASURABLE
specifications: one metric, acceptance criteria and a target ladder per car line × market. The product manager
chooses the ladder level; you only recommend — but you must recommend a NUMBER (or, for a binary metric, a clear
offered / not offered), never "pending".

Per requirement:
- metric — BENCHMARK-AWARE. `benchmark_attributes` lists the measurable attributes for this requirement's aspects
  with how many cited facts exist. If a non-survey attribute (unit not %, pts or PP100) has facts, the metric MUST be
  that attribute, in its canonical unit and stated cycle/condition (range_km at WLTP or real-world, charge_10_80_min,
  boot_l, accel_0_100_s, screen_in, seat_massage_programs, hands_off_kmh, rear_legroom_mm …). Otherwise choose a
  physical or functional quantity the customer experiences directly — km, minutes, litres, bottles, seconds, steps
  or taps, degrees, mm, dB, °C reached within N min — or a binary feature metric ("offered as standard on all
  trims", "available on the long-wheelbase body"). A satisfaction share (study scale) ONLY for pure perception
  aspects (styling, brand image, perceived material quality) — then name the study item as the baseline. A
  task-success share ONLY for usability aspects (display_ui, controls_layout, voice) and concrete ("≥ 95 % of
  first-time users set a destination in ≤ 3 steps / 20 s"). Never a component spec (battery kWh, compressor,
  supplier), regulation or price. keep_strength: a must-not-lose metric (today's level is the floor).
- acceptance: ≤ 4 criteria, each with the test condition and a pass threshold (test method, conditions, pass
  threshold). Conditions follow the markets: heat soak for US-South/China, −7 °C for EU winter, chauffeured rear use
  for China long-wheelbase, dense-city parking, long highway trips.
- ladder: one rung per target given (line × market):
  baseline = today's BMW (a cited BMW fact, study item in its own scale, option status) or null;
  threshold = competitive parity: a numeric threshold comes from SAME-attribute, SAME-cycle rival facts (cite them);
    for binary / feature metrics cite the competitor evidence (`competitor_evidence`: "E-Class offers X as standard",
    its id); gap only if neither exists;
  target = the need at successor launch — NEVER gap: projected (rests on a trend or rival fact id: "best cited rival
    + 5 %, rival improvements trend") or assumption (a value AND one line of reasoning in note);
  stretch = best-in-class or delighter when a cited one exists (e.g. a rival's 900 km or 1,500 kW), else null;
  recommended = the rung you advise (normally target) with a ≤ 20-word rationale; it must carry a value. If no value
    can be reasoned at all, recommend the threshold.
- Every level has a basis:
  cited — the value is literally in the given facts / study items / evidence (ids in source_ids);
  projected — forward value resting on a dated trend or rival fact (name its id);
  assumption — reasoned without evidence (reason in note);
  gap — no data (baseline / threshold only): value null + an open question / research task in `gaps`.
  Never present an invented number as cited.
- Fact rules: never compare CLTC with WLTP or EPA (read `cycle`); read `condition` (km_added_10min and
  charge_10_80_min may hold another duration or window); pp100 values are often per-category problem rates; dc_peak_kw
  covers cars AND chargers (read `entity`); unverified facts are weak — cite them only together with another source.
  Prefer facts from the rung's market and segment; say so in note when you transfer.
- Customer study: CN/EU means on a 10-point scale, US 7-point distributions (top2 = share rating 6–7) — never convert
  between them. Option list: German equipment status; for US/CN it is an assumption.
- Be terse: short texts, empty notes where the basis says it all.
- If a previous spec is given (cp2): keep it (keep_previous=true, metric null, empty lists) unless `new_facts` or the
  changed requirement move it; then return the full new spec with change_note citing the new fact ids."""


# ------------------------------------------------------------------------------------------------ context
def study_items(conn, aspects: list[str], lines: list[str]) -> list[dict]:
    """Customer-study items mapped to the requirement's aspects, for its car lines (all markets of the line)."""
    q = ",".join("?" * len(aspects))
    out = []
    for r in conn.execute(f"""SELECT DISTINCT m.id, m.item, m.vehicle_model_id, m.market_code, m.scale, m.mean, m.top2, m.z_within_column
                              FROM study_metric m JOIN source_aspect a ON a.source_item_id = m.source_item_id
                              WHERE a.aspect IN ({q}) ORDER BY ABS(m.z_within_column) DESC""", aspects):
        line = LINE_OF_CAR.get(r["vehicle_model_id"])
        if line not in lines:
            continue
        out.append({"id": f"study:{r['id']}", "item": r["item"], "car": r["vehicle_model_id"], "line": line,
                    "market": r["market_code"], "scale": r["scale"],
                    "mean": round(r["mean"], 2) if r["mean"] is not None else None,
                    "top2": round(r["top2"], 3) if r["top2"] is not None else None,
                    "z_vs_other_items": round(r["z_within_column"] or 0, 2)})
    return out[:STUDY]


def compact_fact(f: dict) -> dict:
    return {k: f.get(k) for k in ("id", "attribute", "entity", "market", "value", "value_max", "unit", "raw_value", "raw_unit",
                                  "cycle", "condition", "tier", "published_at")} | {"quote": (f.get("quote") or "")[:110],
                                                                                    "unverified": f.get("unverified") or None}


def req_context(conn, req, xrun: int, cp: str, areas: dict) -> dict:
    aspects = json.loads(req["aspects_json"])
    lines = json.loads(req["lines_json"])
    targets = json.loads(req["targets_json"] or "[]")
    actx = areas.get(req["area_key"])
    ev_by = {e["id"]: e for e in (actx["evidence"] if actx else [])} | {f["id"]: f for f in (actx["findings"] if actx else [])}
    evidence = []
    for i in json.loads(req["evidence_ids_json"]):
        e = ev_by.get(i)
        if e is None and i.split(":")[0] in ("research", "study", "option"):
            typ, nid = i.split(":", 1)
            e = {"id": i, **describe(conn, typ, int(nid))}
        if e:
            evidence.append({k: v for k, v in e.items() if k in ("id", "relation", "text", "title", "statement", "value", "z",
                                                                 "published", "tier", "market", "availability", "package",
                                                                 "line", "comments")})
    all_facts = B.facts_for(conn, aspects, cp, limit=200)
    facts = [compact_fact(f) for f in all_facts[:FACTS]]
    n_by_attr = Counter(f["attribute"] for f in all_facts)
    attrs = [{"attribute": k, "label": a["label"], "unit": a["unit"], "direction": a["direction"], "facts": n_by_attr.get(k, 0)}
             for k, a in B.ATTRIBUTES.items() if a["aspect"] in aspects or (n_by_attr.get(k) and a["unit"] not in ("%", "pts", "PP100"))]
    have = {e["id"] for e in evidence}
    rivals = [{k: v for k, v in e.items() if k in ("id", "relation", "text", "published", "tier", "market")}
              for e in (actx["evidence"] if actx else []) if e["id"].startswith("research:") and e.get("relation") in ("competes_with", "trend_for")
              and e["id"] not in have][:6]
    evidence += rivals
    study = [s for s in study_items(conn, aspects, lines) if s["id"] not in {e["id"] for e in evidence}]
    trends = set(json.loads(req["trend_ids_json"])) | {e["id"] for e in evidence if e.get("relation") in ("trend_for", "competes_with")}
    return {"req_key": req["key"], "title": req["title"], "statement": req["statement"], "decision_type": req["decision_type"],
            "kano": req["kano"], "horizon": req["horizon"], "horizon_year": req["horizon_year"], "today_status": req["today_status"],
            "aspects": aspects, "targets": [{"line": t["line"], "market": t["market"], "own_evidence": t["own_evidence"]}
                                            for t in targets],
            "benchmark_attributes": sorted(attrs, key=lambda x: -x["facts"])[:10], "evidence": evidence,
            "competitor_evidence": [r["id"] for r in rivals], "study": study, "facts": facts, "trend_ids": sorted(trends | {r["id"] for r in rivals})}


# ------------------------------------------------------------------------------------------------ code checks
NUM = re.compile(r"\d[\d,\.]*")


def _nums(s: str | None) -> set[float]:
    out = set()
    for m in NUM.findall(s or ""):
        try:
            out.add(float(m.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _close(a: float, b: float | None) -> bool:
    return b is not None and abs(a - b) <= max(abs(b) * 0.01, 0.005)


def source_values(src: dict) -> set[float]:
    """Numbers a cited value may equal: fact values (canonical + as written), study means/shares (also as %), numbers
    in an evidence text."""
    vals: set[float] = set()
    for k in ("value", "value_max", "raw_value", "mean", "top2"):
        v = src.get(k)
        if isinstance(v, (int, float)):
            vals.add(float(v))
            if k == "top2":
                vals.add(round(float(v) * 100, 1))
    for k in ("text", "statement", "quote", "title"):
        vals |= _nums(src.get(k))
    return vals


def unit_ok(fact: dict, metric_unit: str | None) -> bool:
    """A cited fact's canonical (or as-written) unit appears in the metric's unit."""
    if not metric_unit or not fact.get("id", "").startswith("fact:"):
        return True
    mu = metric_unit.lower().replace(" ", "")
    return any(u and u.lower().replace(" ", "") in mu for u in (fact.get("unit"), fact.get("raw_unit")))


def check_level(lv: dict | None, ctx: dict, notes: list[str], gaps: list[str], where: str, unit_binary: bool,
                metric_unit: str | None = None) -> dict | None:
    if lv is None:
        return None
    pool = {f["id"]: f for f in ctx["facts"]} | {s["id"]: s for s in ctx["study"]} | {e["id"]: e for e in ctx["evidence"]}
    ids = [i for i in dict.fromkeys(lv["source_ids"]) if i in pool]
    dropped = [i for i in lv["source_ids"] if i not in pool]
    basis, note = lv["basis"], lv["note"]

    def downgrade(why: str):
        nonlocal basis, note
        basis, note = "assumption", f"{why} {note}".strip()
        notes.append(f"{where}: {why}")

    if dropped:
        notes.append(f"{where}: dropped ids not in the input {dropped}")
    if basis == "gap":
        lv["value"] = None
        line, market = " ".join(where.split(" ")[:2]), where.split(" ")[2]
        if not any(line in g and market in g for g in gaps):
            gaps.append(f"{where}: {lv['text']} — no data; research task")
    elif basis == "cited":
        cited = [pool[i] for i in ids]
        cycles = {f.get("cycle") for f in cited if f.get("id", "").startswith("fact:") and f.get("cycle")}
        weak = [f for f in cited if f.get("unverified")]
        if not ids:
            downgrade("Cited without a valid source id → assumption.")
        elif len(cycles) > 1:
            downgrade(f"Cited facts mix test cycles {sorted(cycles)} → assumption.")
        elif lv["value"] is not None and not any(unit_ok(f, metric_unit) for f in cited):
            downgrade(f"Cited facts are not in the metric unit ({metric_unit}) → assumption.")
        elif weak and len(cited) == len(weak) and len(cited) < 2:
            downgrade("Only an unverified fact supports it → assumption.")
        elif lv["value"] is not None and not any(_close(float(lv["value"]), v) for f in cited for v in source_values(f)):
            downgrade(f"Value {lv['value']:g} not found in the cited sources → assumption.")
        elif lv["value"] is None and not unit_binary and not lv["text"]:
            downgrade("Cited level without value or text → assumption.")
    elif basis == "projected":
        trend_ok = set(ctx["trend_ids"]) | {f["id"] for f in ctx["facts"]}
        if not any(i in trend_ok for i in ids):
            downgrade("Projected without a dated trend or competitor id → assumption.")
    return {"value": lv["value"], "text": lv["text"], "basis": basis, "source_ids": ids, "note": note}


PERCEPTION = {"exterior_design", "interior_design", "materials", "paint_body", "brand_image", "build_quality", "lighting",
              "wheels_tyres", "engine_sound", "interior_lighting"}
USABILITY = {"display_ui", "controls_layout", "voice", "navigation", "phone_projection", "app_remote", "charging_planning"}
RATING = re.compile(r"(\brat(e|es|ed|ing)\b|-rated\b|\bsatisf\w*|\btop[- ]?2\b|\bagree\w*|\bscore\b|\bof (7|10)\b|/(7|10)\b|"
                    r"\bseven-point\b|\bnative[- ]scale\b)", re.I)
TASK = re.compile(r"\b(complet\w*|success\w*|correctly|identif\w*|detect\w*|without (help|error|correction))\b", re.I)


def metric_flag(metric: dict, aspects: list[str]) -> str | None:
    """A rating / share-of-customers metric where a tangible quantity belongs. Satisfaction ratings (share or mean)
    only for perception aspects, task-success shares only for usability aspects (primary aspect decides)."""
    text = f"{metric.get('name', '')} {metric.get('unit', '')}"
    share = "%" in text or re.search(r"\b(share|percent\w*|proportion)\b", text, re.I)
    primary = aspects[0] if aspects else ""
    if RATING.search(text) and primary not in PERCEPTION:
        return f"satisfaction share used for '{primary}', which is not a perception aspect — use a tangible quantity"
    if share and TASK.search(text) and primary not in USABILITY | PERCEPTION:
        return f"task-success share used for '{primary}', which is not a usability aspect — use a tangible quantity"
    return None


def _worse(a: float, b: float, direction: str) -> bool:
    """a is less demanding than b in the metric direction."""
    return a < b if direction == "higher" else a > b if direction == "lower" else False


def validate(s: Spec, ctx: dict) -> dict:
    notes: list[str] = []
    gaps = list(dict.fromkeys(s.gaps))
    metric = s.metric.model_dump() if s.metric else {"name": ctx["title"], "unit": "", "direction": "binary", "method": "", "conditions": ""}
    direction = metric["direction"]
    binary = direction == "binary"
    want = {(t["line"], t["market"]): t for t in ctx["targets"]}
    ladder, seen = [], set()
    for r in s.ladder:
        k = (r.line, r.market)
        if k not in want or k in seen:
            continue
        seen.add(k)
        where = f"{r.line} {r.market}"
        d = r.model_dump()
        lv = {n: check_level(d[n], ctx, notes, gaps, f"{where} {n}", binary, metric["unit"]) for n in RUNGS}
        b0, th = lv["baseline"], lv["threshold"]
        if b0 and th and th["value"] is not None and th["value"] == b0["value"] and th["basis"] != "cited":
            lv["threshold"] = {**th, "value": None, "basis": "gap", "source_ids": [],
                               "note": f"Threshold equalled the baseline without a rival citation. {th['note']}".strip()}
            notes.append(f"{where}: threshold equal to baseline without citation → gap.")
        for lo, hi in (("threshold", "target"), ("target", "stretch")):
            a, b = lv[lo], lv[hi]
            if a and b and a["value"] is not None and b["value"] is not None and _worse(b["value"], a["value"], direction):
                lv[lo], lv[hi] = b, a
                notes.append(f"{where}: {hi} was below {lo} in the metric direction — swapped.")
        rationale = d["rationale"] if want[k]["own_evidence"] else f"[assumption: no own evidence for {where}] {d['rationale']}"
        rec = d["recommended"]
        has = lambda n: lv[n] is not None and lv[n]["basis"] != "gap" and (lv[n]["value"] is not None or binary)  # noqa: E731
        if not has(rec):   # the recommended rung must carry a value
            alt = next((n for n in ("target", "threshold", "stretch") if has(n)), None)
            notes.append(f"{where}: recommended {rec} had no value → {alt or 'none: open question'}.")
            if alt:
                rec = alt
            else:
                gaps.append(f"{where}: no value could be reasoned for any rung — define the bar")
        ladder.append({"line": r.line, "market": r.market, **lv, "recommended": rec, "rationale": rationale})
    for k, t in want.items():
        if k not in seen:
            g = {"value": None, "text": "no level proposed", "basis": "gap", "source_ids": [], "note": ""}
            ladder.append({"line": k[0], "market": k[1], "baseline": None, "threshold": g, "target": g, "stretch": None,
                           "recommended": "target", "rationale": ("" if t["own_evidence"] else
                                                                  f"[assumption: no own evidence for {k[0]} {k[1]}] ") + "No rung proposed — open question."})
            gaps.append(f"{k[0]} {k[1]}: no ladder proposed — define the bar")
    used = sorted({i for r in ladder for n in RUNGS if r[n] for i in r[n]["source_ids"]})
    return {"metric": metric,
            "acceptance": [{"criterion": a.criterion, "condition": a.condition, "pass": a.pass_threshold} for a in s.acceptance[:4]],
            "ladder": ladder, "gaps": gaps, "assumptions": s.assumptions + notes,
            "fact_ids": [i for i in used if i.startswith("fact:")], "input_ids": sorted({f["id"] for f in ctx["facts"]}),
            "change_note": s.change_note}


def recommended_values(ladder: list[dict]) -> dict[str, dict]:
    out = {}
    for r in ladder:
        lv = r.get(r["recommended"]) or r.get("target") or {}
        out[f"{r['line']}:{r['market']}"] = {"level": r["recommended"], "value": lv.get("value"), "text": lv.get("text"),
                                             "basis": lv.get("basis")}
    return out


def moved(prev: dict, now: dict, direction: str) -> str | None:
    """'up' / 'down' / 'mixed' / 'text' when the recommended bar moved, None when it held."""
    signs = []
    for k, v in now.items():
        p = prev.get(k)
        if not p:
            continue
        if v["value"] is not None and p["value"] is not None and v["value"] != p["value"]:
            signs.append(1 if _worse(p["value"], v["value"], direction) else -1)
        elif v["text"] != p["text"] or v["level"] != p["level"]:
            signs.append(0)
    if not signs:
        return None
    if all(s > 0 for s in signs if s) and any(signs):
        return "up" if all(signs) else "mixed"
    if all(s < 0 for s in signs if s) and any(signs):
        return "down" if all(signs) else "mixed"
    return "mixed" if any(signs) else "text"


TANGIBLE_UNITS = {"km", "km/h", "kw", "min", "s", "in", "mm", "m", "l", "kwh/100km", "w", "db"}


def moved_facts(delta: list[dict], metric: dict) -> list[dict]:
    """New facts that can move this requirement's bar: verified and in the metric's own tangible unit (a new 919 km
    range figure moves a km bar; a new survey share or pp100 rate on the same aspect does not)."""
    toks = set(re.split(r"[\s,;()]+", (metric.get("unit") or "").lower())) | {(metric.get("unit") or "").lower().strip()}
    return [f for f in delta if not f.get("unverified") and (f.get("unit") or "").lower() in TANGIBLE_UNITS
            and (f.get("unit") or "").lower() in toks]


# ------------------------------------------------------------------------------------------------ run
def run(conn, cp: str, actor: str = "system", pilot: int | None = None, llm: LLM | None = None, repair: bool = False,
        redo: str | None = None, only: list[str] | None = None) -> dict:
    """A new specify run at the same checkpoint on top of the latest one there (lineage: parent_id + recalibrates):
    `repair=True` / redo='flagged' re-asks only requirements whose metric fails `metric_flag` and carries the rest;
    redo='all' re-specifies every requirement from scratch (e.g. after a prompt change). `only`: restrict to these keys
    (pilot)."""
    redo = redo or ("flagged" if repair else None)
    llm = llm or LLM(conn=conn)
    drun, xrun, arun = C.latest_run(conn, cp, "define"), C.latest_run(conn, cp, "contextualize"), C.latest_run(conn, cp, "areas")
    if drun is None:
        raise C.CheckpointError(f"Run 'define' at {cp} first")
    reqs = conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY domain, key", (drun["id"],)).fetchall()
    areas = {a["key"]: area_context(conn, xrun["id"], a) for a in conn.execute(
        "SELECT * FROM req_area WHERE run_id = ? AND kind != 'quality'", (arun["id"],))}
    run_id = parent = None
    if not pilot:
        conn.execute("BEGIN IMMEDIATE")
        run_id = C.start_run(conn, cp, "specify", actor)
        conn.execute("COMMIT")
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
    elif C.BY_ID[cp].parent_id:
        p = C.latest_run(conn, C.BY_ID[cp].parent_id, "specify")
        parent = p["id"] if p else None
    base = C.latest_run(conn, cp, "specify")["id"] if redo else parent
    prev = {r["req_key"]: r for r in conn.execute("SELECT * FROM def_spec WHERE run_id = ?", (base,))} if base else {}

    rows, todo, carried = [], [], 0
    for r in reqs:
        if only and r["key"] not in only:
            continue
        p = prev.get(r["key"])
        if redo == "all":
            delta, flag = [], None
        elif redo:
            delta = []
            flag = metric_flag(json.loads(p["metric_json"]), json.loads(r["aspects_json"])) if p else "no spec yet"
        else:
            delta = moved_facts(B.fact_delta(conn, json.loads(r["aspects_json"]), C.BY_ID[cp].parent_id, cp),
                                json.loads(p["metric_json"])) if p and C.BY_ID[cp].parent_id else []
            flag = None
        if p and p["req_version"] == r["version"] and not delta and (not redo or not flag) and redo != "all":
            rows.append(_carry(p, r))
            carried += 1
            continue
        ctx = req_context(conn, r, xrun["id"], cp, areas)
        if p and redo != "all":
            ctx["previous"] = {"metric": json.loads(p["metric_json"]), "ladder": [
                {"line": x["line"], "market": x["market"], **{n: (x.get(n) or {}).get("text") for n in RUNGS}, "recommended": x["recommended"]}
                for x in json.loads(p["ladder_json"])]}
            ctx["new_facts"] = [compact_fact(f) | {"previous": compact_fact(f["previous"]) if f.get("previous") else None} for f in delta[:10]]
            ctx["facts"] += [compact_fact(f) for f in delta if f["id"] not in {x["id"] for x in ctx["facts"]}]
            ctx["requirement_changed"] = p["req_version"] != r["version"]
        if flag:
            ctx["repair"] = flag
        todo.append((r, ctx))
    if pilot:
        todo = todo[:pilot]
    else:
        log(conn, "specify", "start", {"requirements": len(reqs), "to_specify": len(todo), "carried": carried}, run_id)

    model = llm.model_for("smart")
    done = kept = repaired = 0
    failed: list[str] = []
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    retry: list[tuple] = []
    while batches:
        chunk = batches.pop(0)
        try:
            res = generate(llm, job=f"specify:{cp}", tier="smart", instructions=INSTRUCTIONS,
                               input=json.dumps([{k: v for k, v in c.items() if k != "flagged"} for _, c in chunk], ensure_ascii=False, default=str), schema=Batch,
                               reasoning_effort="medium", max_output_tokens=32_000, flex=True)
            got = {s.req_key: s for s in (res.parsed.specs if res.parsed else [])}
        except Exception as e:   # one bad batch must not lose the others (its requirements carry or stay unspecified)
            got = {}
            failed += [r["key"] for r, _ in chunk]
            if not pilot:
                log(conn, "specify", "batch_failed", {"requirements": failed[-len(chunk):], "error": repr(e)[:300]}, run_id)
        for r, ctx in chunk:
            s, p = got.get(r["key"]), prev.get(r["key"])
            if s is None:
                if ctx.get("flagged"):   # the repair answer is missing: keep the first answer, flagged
                    ctx["flagged"]["assumptions"].append(f"Metric flagged, repair failed: {ctx['repair']}")
                    rows.append(ctx["flagged"])
                elif p:
                    rows.append(_carry(p, r))
                continue
            if s.keep_previous and p and p["req_version"] == r["version"] and not ctx.get("repair"):
                rows.append(_carry(p, r))
                kept += 1
                continue
            v = validate(s, ctx)
            flag = metric_flag(v["metric"], ctx["aspects"])
            if flag and "repair" not in ctx:   # re-ask once in a small repair batch
                retry.append((r, ctx | {"repair": flag, "rejected_metric": v["metric"]["name"],
                                        "flagged": dict(req_key=r["key"], version=(p["version"] + 1) if p else 1,
                                                        parent_id=p["id"] if p else None, req_version=r["version"], model=model,
                                                        carried=False, **v)}))
                continue
            if flag:
                v["assumptions"].append(f"Metric still flagged after repair: {flag}")
            repaired += bool(ctx.get("repair"))
            rows.append(dict(req_key=r["key"], version=(p["version"] + 1) if p else 1, parent_id=p["id"] if p else None,
                             req_version=r["version"], model=model, carried=False, **v))
            done += 1
        if not pilot:
            log(conn, "specify", "spec", {"requirements": len(chunk), "examples": [s.metric.name for s in got.values() if s.metric][:3]},
                run_id, model)
        if not batches and retry:
            batches = [retry[i:i + BATCH] for i in range(0, len(retry), BATCH)]
            if not pilot:
                log(conn, "specify", "repair", {"requirements": [r["key"] for r, _ in retry]}, run_id)
            retry = []
    if pilot:
        return {"pilot": True, "rows": rows}

    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in rows:
            cur = conn.execute("""INSERT INTO def_spec (run_id, req_key, version, parent_id, req_version, metric_json, acceptance_json,
                                  ladder_json, gaps_json, assumptions_json, fact_ids_json, input_ids_json, change_note, model)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                               (run_id, r["req_key"], r["version"], r["parent_id"], r["req_version"], json.dumps(r["metric"], ensure_ascii=False),
                                json.dumps(r["acceptance"], ensure_ascii=False), json.dumps(r["ladder"], ensure_ascii=False),
                                json.dumps(r["gaps"], ensure_ascii=False), json.dumps(r["assumptions"], ensure_ascii=False),
                                json.dumps(r["fact_ids"]), json.dumps(r["input_ids"]), r["change_note"], r["model"]))
            sid = str(cur.fetchone()[0])
            edges = [(run_id, "def_spec", sid, "def_requirement_key", r["req_key"], "specifies", "sol")]
            if r["parent_id"] and not r["carried"]:
                edges.append((run_id, "def_spec", sid, "def_spec", str(r["parent_id"]), "recalibrates", "sol"))
            edges += [(run_id, "def_spec", sid, "spec_fact", f.split(":")[1], "cites", "sol") for f in r["fact_ids"]]
            conn.executemany("INSERT INTO evidence_edge (run_id, src_type, src_id, dst_type, dst_id, relation, method) VALUES (?, ?, ?, ?, ?, ?, ?)", edges)
        ents, states = {}, {}
        prev_payload = {r["entity_key"][5:]: json.loads(r["payload_json"] or "{}").get("recommended", {}) for r in conn.execute(
            "SELECT entity_key, payload_json FROM track WHERE run_id = ? AND entity_key LIKE 'spec:%'", (parent,))} if parent else {}
        for r in rows:
            rec = recommended_values(r["ladder"])
            mv = moved(prev_payload.get(r["req_key"], {}), rec, r["metric"]["direction"]) if r["req_key"] in prev_payload else None
            cited = sum(1 for x in r["ladder"] for n in RUNGS if x[n] and x[n]["basis"] == "cited")
            ents[f"spec:{r['req_key']}"] = (float(cited), {"recommended": rec, "moved": mv, "version": r["version"]})
            if r["req_key"] in prev_payload:
                states[f"spec:{r['req_key']}"] = {"up": "strengthened", "down": "weakened"}.get(mv, "held")
        tracks = C.write_tracks(conn, run_id, ents, states=states)
        bases = Counter(x[n]["basis"] for r in rows for x in r["ladder"] for n in RUNGS if x[n])
        stats = {"requirements": len(reqs), "specified": done, "carried": carried, "kept": kept, "specs": len(rows), "failed": failed, "repaired": repaired, "redo": redo,
                 "levels_by_basis": dict(bases), "gaps": sum(len(r["gaps"]) for r in rows),
                 "facts_cited": len({f for r in rows for f in r["fact_ids"]}), "tracks": tracks, "upstream": {"define": drun["id"]}}
        C.finish_run(conn, run_id, stats)
        log(conn, "specify", "finish", stats, run_id)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}


def _carry(p, req) -> dict:
    return dict(req_key=p["req_key"], version=p["version"], parent_id=p["id"], req_version=req["version"],
                metric=json.loads(p["metric_json"]), acceptance=json.loads(p["acceptance_json"]), ladder=json.loads(p["ladder_json"]),
                gaps=json.loads(p["gaps_json"]), assumptions=json.loads(p["assumptions_json"]), fact_ids=json.loads(p["fact_ids_json"]),
                input_ids=json.loads(p["input_ids_json"] or "[]"), change_note=None, model=p["model"], carried=True)
