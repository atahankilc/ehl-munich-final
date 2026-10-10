"""Requirement derivation v2 (sol): findings → customer requirements with targets, evidence links,
horizon/Kano, assumptions and uncertainties (D-012, D-028).

`uv run python -m bmw_req.pipeline.requirements derive "5 Series" --wave 1 [--n 16] [--dry-run]`

Always incremental: the model sees the existing requirements of the line and only proposes requirements for
needs they don't cover yet (wave 1 starts empty). AI creates in status `proposed` only (AGENTS rule 5).
Every cited finding ID is validated; a draft without a valid supporting finding is dropped.
"""

import argparse
import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.pipeline.extract import Category
from bmw_req.portfolio import LINES, SUCCESSOR_LAUNCH, TARGETS

PROMPT_VERSION = "derive-v6"
MAX_IMPROVE_FINDINGS = 110
MAX_LIKE_FINDINGS = 30


class TargetDraft(BaseModel):
    vehicle_model_id: str
    market_code: str
    realization: Literal["carry_over", "platform_wide", "derivative_specific", "market_variant", "package"]
    market_note: str = Field(description="Why this market needs it (or needs it differently); cite evidence or say 'assumption'")


class RequirementDraft(BaseModel):
    title: str = Field(description="≤ 12 words, customer-facing")
    description: str = Field(description="What the customer must be able to experience; solution-neutral where possible")
    category: Category
    target_metric: str = Field(description="Customer-perceivable measure with a proposed numeric target")
    acceptance_criteria: str
    horizon: Literal["today", "at_successor_launch"]
    horizon_reason: str
    kano_class: Literal["basic", "performance", "delighter"]
    kano_drift: str = Field(description="Expected Kano class at successor launch and why, or 'stable'")
    must_not_lose: bool = Field(description="True if this protects a praised strength rather than fixing a gap")
    effort: Literal["S", "M", "L"] = Field(description="Rough incremental effort vs. today's car: S = keep/protect, software, calibration, packaging; M = new content within an existing area; L = new hardware, package space or body change")
    effort_reason: str
    targets: list[TargetDraft]
    supporting_finding_ids: list[int]
    conflicting_finding_ids: list[int]
    conflicting_evidence: str = Field(description="Contradicting evidence and cross-market differences in plain language, or 'none found'")
    evidence_summary: str = Field(description="2–3 sentences: what the cited evidence shows, per market. Facts only")
    assumptions: list[str] = Field(description="Forward-looking beliefs (3–5 yr) incl. every proposed target value")
    uncertainties: list[str] = Field(description="What could make this wrong; evidence gaps")


class DerivationResult(BaseModel):
    requirements: list[RequirementDraft]


INSTRUCTIONS = """You are a senior BMW product-requirements analyst. You derive CUSTOMER REQUIREMENTS for the
SUCCESSOR of a BMW vehicle line (launch in 3–5 years) from evidence findings. A customer requirement is a
customer-relevant attribute of the car.

Input: the vehicle line, its derivatives and the target markets (derivative × market), market profiles,
brand guardrails, sales per target, existing requirements (already proposed — do NOT duplicate them),
and findings with IDs:
- verbatim findings: clustered customer feedback, with per-market counts (verbatims, share of that market's
  in-scope feedback, severity-weighted count). Markets differ: US, EU, RoW (Japan/Korea/Canada…) are separate
  customer groups. There are NO China verbatims.
- study findings: customer-study satisfaction items that are notably weak or strong for a model × market.
- web findings: cited competitor advantages, reviews, market trends, customer expectations per market.

Task: propose up to {n} NEW requirements — the most important customer needs the evidence supports that the
existing requirements don't cover. Prefer strong, multi-source needs; include must-not-lose strengths that a
successor could lose (e.g. through a new UI or platform); include forward-looking needs where web trends and
market evidence support them (e.g. China, where only study + web evidence exists).

Rules:
- Cite supporting_finding_ids (only IDs from the input; ≥ 1, ideally verbatim + study/web together). Cite
  conflicting_finding_ids and describe conflicts and cross-market differences — never hide them.
- Customer-facing only. No component specs, suppliers, architecture, regulatory/homologation or safety
  performance, no pricing/business case. Driver assistance only as experienced (usability, availability, trust).
- Solution-neutral where possible (the need, not the part), but concrete enough to act on.
- One customer need per requirement: do not bundle independent features (split them, or pick the strongest).
- target_metric: ONE primary customer-perceivable measure with a proposed numeric target (and per-line or
  per-market values where segments/markets differ). acceptance_criteria: how it is verified — the test method
  (e.g. customer clinic with N target customers, owner survey, defined road/climate test), the task set or
  conditions, and the pass threshold. Every target value is an assumption — list it in `assumptions`.
- targets: only from the allowed target list. Add a market ONLY if a cited finding for that market (verbatims
  there, a study item or web finding for it) supports the need, or the market profile makes it clearly
  relevant — then say so in market_note ("assumption: …"). Do not spread every requirement to every market:
  markets are different customers. Use `market_variant` or `package` when only some markets need it and
  `platform_wide` only for needs evidenced across markets.
- effort: rate the INCREMENTAL effort versus today's car. Protecting an existing strength or fixing software
  behaviour is S; most requirements are S or M; L only for new hardware, package space or body changes.
- Cover the spread of the evidence, in this order: (1) the largest pain points by severity-weighted count —
  every one of the ~10 biggest pain/want findings should be cited by some requirement unless out of scope;
  (2) must-not-lose strengths (at most a quarter of the requirements); (3) at least two requirements where the
  markets clearly differ (e.g. China-specific needs from study/web).
- Brand & segment fit: must fit BMW ("Sheer Driving Pleasure", driver focus, premium quality) and this segment.
- horizon: `today` = current shortcoming/strength, needed regardless of trends; `at_successor_launch` = the
  need grows or changes by launch. Kano: classify by today's reaction, drift in kano_drift.
- Separate evidence (evidence_summary) from assumptions. Do not invent numbers, quotes or facts."""


# ---------------------------------------------------------------------------------------------- context
def _wave_metrics(metrics: dict, wave: int) -> dict:
    by = metrics.get("by_wave", {}).get(str(min(wave, 2)))
    return by or {"verbatims": 0, "markets": {}}


def visible_findings(conn: sqlite3.Connection, derivatives: list[str], wave: int) -> list[dict]:
    q = ",".join("?" * len(derivatives))
    rows = conn.execute(
        f"""SELECT * FROM finding WHERE (vehicle_model_id IN ({q}) OR vehicle_model_id IS NULL)
            AND COALESCE(first_wave, 1) <= ? ORDER BY id""",
        (*derivatives, wave),
    ).fetchall()
    return [dict(r) for r in rows]


def build_context(conn: sqlite3.Connection, line: str, wave: int) -> tuple[dict, set[int]]:
    derivs = LINES[line]["derivatives"]
    findings = visible_findings(conn, derivs, wave)
    allowed_ids: set[int] = set()

    verbatim, study, web = [], [], []
    for f in findings:
        m = json.loads(f["metrics_json"] or "{}")
        if f["source_kind"] == "verbatim":
            wm = _wave_metrics(m, wave)
            if wm["verbatims"] < 3:
                continue
            markets = {
                mk: {"verbatims": v["verbatims"], "share_pct": round(100 * (v["share"] or 0), 2),
                     "severity_weighted": v["severity_weighted"], "types": v["types"]}
                for mk, v in wm["markets"].items()
            }
            sw = sum(v["severity_weighted"] for v in wm["markets"].values())
            quotes = [r["quote"] for r in conn.execute(
                "SELECT quote FROM finding_source WHERE finding_id = ? AND quote IS NOT NULL LIMIT 2", (f["id"],))]
            verbatim.append({"id": f["id"], "new_in_this_wave": (f["first_wave"] or 1) == wave,
                             "derivative": f["vehicle_model_id"], "category": f["category"],
                             "type": f["type"], "title": f["title"], "summary": f["summary"],
                             "polarity": f["polarity"], "markets": markets, "_sw": sw, "example_quotes": quotes})
        elif f["source_kind"] == "study":
            if not m.get("notable"):
                continue   # average items reach requirements via the evidence linker, not derivation
            study.append({"id": f["id"], "new_in_this_wave": (f["first_wave"] or 1) == wave,
                          "derivative": f["vehicle_model_id"], "market": f["market_code"],
                          "type": f["type"], "title": f["title"], "summary": f["summary"]})
        elif f["source_kind"] == "web":
            web.append({"id": f["id"], "new_in_this_wave": (f["first_wave"] or 1) == wave,
                        "derivative": f["vehicle_model_id"], "market": f["market_code"],
                        "type": f["type"], "category": f["category"], "title": f["title"], "summary": f["summary"],
                        "sources": m.get("n_sources"), "tiers": m.get("tiers")})
    improve = sorted([v for v in verbatim if v["polarity"] != "like"], key=lambda v: -v["_sw"])[:MAX_IMPROVE_FINDINGS]
    likes = sorted([v for v in verbatim if v["polarity"] == "like"], key=lambda v: -v["_sw"])[:MAX_LIKE_FINDINGS]
    for v in improve + likes:
        v.pop("_sw")
    if wave == 1:   # everything is new in wave 1; the flag only matters for incremental waves
        for group in (improve, likes, study, web):
            for x in group:
                x.pop("new_in_this_wave", None)
    for group in (improve, likes, study, web):
        allowed_ids |= {x["id"] for x in group}

    targets = [{"derivative": d, "market": mk} for d in derivs for mk in TARGETS[d]]
    sales = {}
    for r in conn.execute(
        f"""SELECT s.vehicle_model_id, s.market_code, s.year, s.units FROM sales s JOIN source_item i ON i.id = s.source_item_id
            WHERE s.vehicle_model_id IN ({",".join("?" * len(derivs))}) AND i.wave <= ?""", (*derivs, wave)):
        sales.setdefault(f"{r['vehicle_model_id']}×{r['market_code']}", {})[r["year"]] = r["units"]
    markets = {r["code"]: {k: r[k] for k in ("name", "climate", "usage_patterns", "cultural_expectations",
                                              "infrastructure", "powertrain_mix") if r[k]}
               for r in conn.execute("SELECT * FROM market")}
    brand = conn.execute("SELECT positioning, core_values_json, guardrails_json FROM brand WHERE id = 'BMW'").fetchone()
    existing = [
        {"id": r["id"], "title": r["title"], "category": r["category"],
         "findings": [x[0] for x in conn.execute("SELECT finding_id FROM requirement_finding WHERE requirement_id = ?", (r["id"],))]}
        for r in conn.execute(
            f"""SELECT DISTINCT q.* FROM requirement q JOIN requirement_target t ON t.requirement_id = q.id
                WHERE t.vehicle_model_id IN ({",".join("?" * len(derivs))}) ORDER BY q.id""", derivs)
    ]
    ctx = {
        "vehicle_line": line, "segment": LINES[line]["segment"], "derivatives": derivs,
        "successor_launch": {d: SUCCESSOR_LAUNCH[d] for d in derivs},
        "allowed_targets": targets, "sales_units_bmw_internal_relative_only": sales,
        "market_profiles": markets,
        "brand": dict(brand) if brand else {"positioning": "Sheer Driving Pleasure; driver focus; premium quality"},
        "existing_requirements": existing,
        "verbatim_findings_improve": improve, "verbatim_findings_strengths": likes,
        "study_findings": study, "web_findings": web,
    }
    return ctx, allowed_ids


# ---------------------------------------------------------------------------------------------- derive
INCREMENTAL = """

LATER WAVE: this is a re-run months later. Existing requirements already cover most needs. Propose a new
requirement ONLY if it is grounded in evidence marked new_in_this_wave=true (e.g. a newly arrived study gap or a
new competitor/market event) or in a large pain finding that no existing requirement cites. Do not restate or
slightly vary existing requirements. Returning fewer than {n} — or none — is correct when nothing new is needed."""


def derive(llm: LLM, ctx: dict, *, n: int, job: str, effort: str = "high", wave: int = 1) -> tuple[DerivationResult, object]:
    instructions = INSTRUCTIONS.format(n=n) + (INCREMENTAL.format(n=n) if wave > 1 else "")
    res = llm.generate(
        job=job, tier="smart", instructions=instructions,
        input=json.dumps(ctx, ensure_ascii=False, default=str), schema=DerivationResult,
        reasoning_effort=effort, max_output_tokens=40_000, flex=True,
    )
    return res.parsed, res


def validate(drafts: DerivationResult, allowed_ids: set[int], derivatives: list[str]) -> tuple[list, list[str]]:
    ok, problems = [], []
    allowed_targets = {(d, m) for d in derivatives for m in TARGETS[d]}
    for d in drafts.requirements:
        bad = [i for i in d.supporting_finding_ids + d.conflicting_finding_ids if i not in allowed_ids]
        if bad:
            problems.append(f"{d.title}: dropped unknown finding ids {bad}")
        d.supporting_finding_ids = [i for i in d.supporting_finding_ids if i in allowed_ids]
        d.conflicting_finding_ids = [i for i in d.conflicting_finding_ids if i in allowed_ids and i not in d.supporting_finding_ids]
        bad_t = [(t.vehicle_model_id, t.market_code) for t in d.targets if (t.vehicle_model_id, t.market_code) not in allowed_targets]
        if bad_t:
            problems.append(f"{d.title}: dropped invalid targets {bad_t}")
        seen, targets = set(), []
        for t in d.targets:
            key = (t.vehicle_model_id, t.market_code)
            if key in allowed_targets and key not in seen:
                seen.add(key)
                targets.append(t)
        d.targets = targets
        if not d.supporting_finding_ids or not d.targets:
            problems.append(f"{d.title}: DROPPED (no valid supporting finding or target)")
            continue
        ok.append(d)
    return ok, problems


# ---------------------------------------------------------------------------------------------- portfolio merge
class MergeGroup(BaseModel):
    members: list[int] = Field(description="Indices of drafts (≥ 2, from different vehicle lines) that state the same customer need")
    title: str
    description: str
    target_metric: str
    acceptance_criteria: str
    reason: str


class MergeResult(BaseModel):
    groups: list[MergeGroup]


MERGE_INSTRUCTIONS = """You consolidate customer requirements for a BMW PORTFOLIO. Drafts come from separate vehicle
lines (1, 5, 7 Series). Group drafts that state the SAME customer need so it becomes one portfolio requirement
with targets on several derivatives (e.g. 'tactile everyday controls' in the 5 and 7 Series). Only group drafts
from different lines whose need and direction match — even if the numeric targets differ per segment (then
state targets per line). Also group drafts about the same need for different derivatives in one market (e.g.
China urban assistance for G68 and G70). Only needs that are genuinely segment-specific (e.g. luxury rear lounge
vs compact practicality) stay separate. For each group write a merged, segment-neutral title,
description, target metric and acceptance criteria (keep numeric targets; if they differ by segment, state
them per line). Return no groups if nothing matches."""


def lines_of(d: "RequirementDraft") -> str:
    from bmw_req.portfolio import line_of
    return " + ".join(sorted({line_of(t.vehicle_model_id) for t in d.targets}))


def consolidate(llm: LLM, drafts: list[tuple[str, RequirementDraft]], job: str) -> tuple[list[RequirementDraft], list[str]]:
    """drafts: [(line, draft)] → merged list. Union of targets, findings, assumptions; notes for the audit trail."""
    payload = [{"index": i, "line": line, "title": d.title, "category": d.category, "description": d.description,
                "target_metric": d.target_metric, "must_not_lose": d.must_not_lose}
               for i, (line, d) in enumerate(drafts)]
    res = llm.generate(job=job, tier="smart", instructions=MERGE_INSTRUCTIONS, input=json.dumps(payload, ensure_ascii=False),
                       schema=MergeResult, reasoning_effort="medium", max_output_tokens=16_000, flex=True)
    used, merged, notes = set(), [], []
    for g in res.parsed.groups:
        idx = [i for i in g.members if 0 <= i < len(drafts) and i not in used]
        if len({drafts[i][0] for i in idx}) < 2 and len(idx) < 2:
            continue
        used |= set(idx)
        base = drafts[idx[0]][1].model_copy(deep=True)
        others = [drafts[i][1] for i in idx[1:]]
        base.title, base.description = g.title, g.description
        base.target_metric, base.acceptance_criteria = g.target_metric, g.acceptance_criteria
        for o in others:
            base.targets += [t for t in o.targets if (t.vehicle_model_id, t.market_code) not in
                             {(x.vehicle_model_id, x.market_code) for x in base.targets}]
            base.supporting_finding_ids = sorted(set(base.supporting_finding_ids) | set(o.supporting_finding_ids))
            base.conflicting_finding_ids = sorted(set(base.conflicting_finding_ids) | set(o.conflicting_finding_ids))
            base.assumptions += [a for a in o.assumptions if a not in base.assumptions]
            base.uncertainties += [u for u in o.uncertainties if u not in base.uncertainties]
            base.evidence_summary += " " + o.evidence_summary
            if o.conflicting_evidence and o.conflicting_evidence.lower() != "none found":
                base.conflicting_evidence += " " + o.conflicting_evidence
            base.effort = max(base.effort, o.effort, key="SML".index)
            base.horizon = "at_successor_launch" if "at_successor_launch" in (base.horizon, o.horizon) else "today"
        lines = sorted({drafts[i][0] for i in idx})
        base.evidence_summary = f"[Portfolio requirement merged across {', '.join(lines)}: {g.reason}] " + base.evidence_summary
        merged.append(base)
        notes.append(f"merged {[drafts[i][1].title for i in idx]} → {g.title}")
    merged += [d for i, (_, d) in enumerate(drafts) if i not in used]
    return merged, notes


# ---------------------------------------------------------------------------------------------- dedup vs existing (Q-022)
class ExistingMatch(BaseModel):
    draft_index: int
    existing_id: str | None = Field(description="ID of the existing requirement that states the SAME customer need, or null")
    reason: str


class ExistingMatchResult(BaseModel):
    matches: list[ExistingMatch]


MATCH_INSTRUCTIONS = """You keep a BMW PORTFOLIO requirement backlog free of duplicates. New drafts come from a later
review wave; the existing requirements may belong to other vehicle lines (1, 5, 7 Series). For every draft, return
the ID of the existing requirement that states the SAME customer need in the same direction — even if it targets
other derivatives/markets or has other numeric targets (the draft would then add its targets and evidence to it).
Return null if the draft is a different need, a clearly narrower/other sub-need with its own customer value, or
genuinely segment-specific (e.g. luxury rear lounge vs compact practicality). Return exactly one entry per draft."""


def match_existing(llm: LLM, drafts: list["RequirementDraft"], existing: list[dict], job: str) -> list[ExistingMatch]:
    """Map each new draft to an existing requirement with the same need (or None). Unknown IDs are dropped."""
    if not drafts or not existing:
        return [ExistingMatch(draft_index=i, existing_id=None, reason="no existing requirements") for i in range(len(drafts))]
    payload = {
        "existing": existing,
        "drafts": [{"index": i, "lines": lines_of(d), "title": d.title, "category": d.category,
                    "description": d.description, "target_metric": d.target_metric} for i, d in enumerate(drafts)],
    }
    res = llm.generate(job=job, tier="smart", instructions=MATCH_INSTRUCTIONS, input=json.dumps(payload, ensure_ascii=False),
                       schema=ExistingMatchResult, reasoning_effort="medium", max_output_tokens=8000, flex=True)
    ids = {e["id"] for e in existing}
    by_idx = {m.draft_index: m for m in res.parsed.matches if 0 <= m.draft_index < len(drafts)}
    out = []
    for i in range(len(drafts)):
        m = by_idx.get(i)
        if m is None or m.existing_id not in ids:
            m = ExistingMatch(draft_index=i, existing_id=None, reason=m.reason if m else "not matched")
        out.append(m)
    return out


def existing_for_match(conn: sqlite3.Connection) -> list[dict]:
    """Non-rejected requirements of ALL lines, compact, as match candidates."""
    out = []
    for r in conn.execute("SELECT id, title, category, description FROM requirement WHERE status != 'rejected' ORDER BY id"):
        tg = [f"{t[0]}×{t[1]}" for t in conn.execute(
            "SELECT vehicle_model_id, market_code FROM requirement_target WHERE requirement_id = ?", (r["id"],))]
        out.append({"id": r["id"], "title": r["title"], "category": r["category"], "description": r["description"],
                    "targets": tg})
    return out


def propose_extensions(conn: sqlite3.Connection, pairs: list[tuple["RequirementDraft", ExistingMatch]], *, wave: int,
                       model: str) -> list[str]:
    """A draft that restates an existing requirement becomes an `extend` change proposal on it (new targets + new
    evidence links) instead of a duplicate requirement. The PM decides (AGENTS rule 5). Returns log lines."""
    log = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        for d, m in pairs:
            rid = m.existing_id
            have_t = {(t[0], t[1]) for t in conn.execute(
                "SELECT vehicle_model_id, market_code FROM requirement_target WHERE requirement_id = ?", (rid,))}
            have_f = {r[0] for r in conn.execute("SELECT finding_id FROM requirement_finding WHERE requirement_id = ?", (rid,))}
            targets = [{"vehicle_model_id": t.vehicle_model_id, "market_code": t.market_code, "realization": t.realization,
                        "market_note": t.market_note} for t in d.targets if (t.vehicle_model_id, t.market_code) not in have_t]
            sup = [f for f in d.supporting_finding_ids if f not in have_f]
            con = [f for f in d.conflicting_finding_ids if f not in have_f and f not in sup]
            audit(conn, actor_type="ai", actor_id="pipeline.requirements", action="match_existing", entity_type="requirement",
                  entity_id=rid, field="duplicate_draft",
                  new={"draft_title": d.title, "new_targets": [f"{t['vehicle_model_id']}×{t['market_code']}" for t in targets],
                       "new_supports": sup, "new_contradicts": con, "wave": wave},
                  rationale=m.reason, model=model, prompt_ref=PROMPT_VERSION)
            if not targets and not sup and not con:
                log.append(f"  draft '{d.title}' = {rid}: nothing new, dropped")
                continue
            summary = "; ".join(x for x in (
                ("add targets " + ", ".join(f"{t['vehicle_model_id']}×{t['market_code']}" for t in targets)) if targets else "",
                (f"link {len(sup)} supporting finding(s)") if sup else "",
                (f"link {len(con)} contradicting finding(s)") if con else "") if x)
            conn.execute(
                """INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, evidence_delta_json, kind)
                   VALUES (?, 'extend', NULL, ?, ?, ?, 'extend')""",
                (rid, summary, f"Same need raised again in wave {wave} ('{d.title}'): {m.reason}",
                 json.dumps({"draft_title": d.title, "draft_description": d.description, "targets": targets,
                             "supports": sup, "contradicts": con, "wave": wave}, ensure_ascii=False)))
            log.append(f"  draft '{d.title}' = {rid}: extend proposal ({summary})")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return log


def next_req_id(conn: sqlite3.Connection) -> int:
    r = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM requirement").fetchone()[0]
    return (r or 0) + 1


def audit(conn, *, actor_type, actor_id, action, entity_type, entity_id, field=None, old=None, new=None,
          rationale=None, model=None, prompt_ref=None, run_id=None):
    conn.execute(
        """INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, field, old_value, new_value,
                                    rationale, model, prompt_ref, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (actor_type, actor_id, action, entity_type, entity_id, field,
         None if old is None else (old if isinstance(old, str) else json.dumps(old, ensure_ascii=False)),
         None if new is None else (new if isinstance(new, str) else json.dumps(new, ensure_ascii=False)),
         rationale, model, prompt_ref, run_id),
    )


def store(conn: sqlite3.Connection, drafts: list[RequirementDraft], *, model: str, usage_id: int | None,
          wave: int, run_id: int | None = None) -> list[str]:
    ids = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = next_req_id(conn)
        for d in drafts:
            rid = f"REQ-{n:04d}"
            n += 1
            content = {
                "title": d.title, "description": d.description, "category": d.category,
                "target_metric": d.target_metric, "acceptance_criteria": d.acceptance_criteria,
                "horizon": d.horizon, "kano_class": d.kano_class, "kano_drift": d.kano_drift,
                "assumptions": "\n".join(f"- {a}" for a in d.assumptions),
                "uncertainties": "\n".join(f"- {u}" for u in d.uncertainties),
                "conflicting_evidence": d.conflicting_evidence, "effort": d.effort,
                "must_not_lose": int(d.must_not_lose),
            }
            conn.execute(
                """INSERT INTO requirement (id, title, description, category, target_metric, acceptance_criteria, horizon,
                       kano_class, kano_drift, assumptions, uncertainties, conflicting_evidence, status, version,
                       effort, must_not_lose, created_by, first_run_id, derivation_json)
                   VALUES (:id, :title, :description, :category, :target_metric, :acceptance_criteria, :horizon,
                       :kano_class, :kano_drift, :assumptions, :uncertainties, :conflicting_evidence, 'proposed', 1,
                       :effort, :must_not_lose, :created_by, :run_id, :derivation_json)""",
                {**content, "id": rid, "created_by": f"ai:{model}", "run_id": run_id,
                 "derivation_json": json.dumps({**d.model_dump(), "wave": wave, "llm_usage_id": usage_id,
                                                "prompt": PROMPT_VERSION}, ensure_ascii=False)},
            )
            audit(conn, actor_type="ai", actor_id="pipeline.requirements", action="create", entity_type="requirement",
                  entity_id=rid, new=content, rationale=d.evidence_summary, model=model, prompt_ref=PROMPT_VERSION,
                  run_id=run_id)
            for t in d.targets:
                conn.execute(
                    """INSERT INTO requirement_target (requirement_id, vehicle_model_id, market_code, realization, rationale)
                       VALUES (?, ?, ?, ?, ?)""",
                    (rid, t.vehicle_model_id, t.market_code, t.realization, t.market_note),
                )
                audit(conn, actor_type="ai", actor_id="pipeline.requirements", action="add_target",
                      entity_type="requirement", entity_id=rid, field="target",
                      new={"target": f"{t.vehicle_model_id}×{t.market_code}", "realization": t.realization},
                      rationale=t.market_note, model=model, prompt_ref=PROMPT_VERSION, run_id=run_id)
            for fid, rel in [(f, "supports") for f in d.supporting_finding_ids] + [(f, "contradicts") for f in d.conflicting_finding_ids]:
                conn.execute("INSERT OR IGNORE INTO requirement_finding (requirement_id, finding_id, relation) VALUES (?, ?, ?)",
                             (rid, fid, rel))
            audit(conn, actor_type="ai", actor_id="pipeline.requirements", action="link_findings",
                  entity_type="requirement", entity_id=rid, field="evidence",
                  new={"supports": d.supporting_finding_ids, "contradicts": d.conflicting_finding_ids},
                  model=model, prompt_ref=PROMPT_VERSION, run_id=run_id)
            ids.append(rid)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["derive", "context"])
    ap.add_argument("line")
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = connect()
    ctx, allowed = build_context(conn, args.line, args.wave)
    if args.cmd == "context":
        s = json.dumps(ctx, ensure_ascii=False, default=str)
        print(f"context: {len(s)} chars; improve {len(ctx['verbatim_findings_improve'])}, likes "
              f"{len(ctx['verbatim_findings_strengths'])}, study {len(ctx['study_findings'])}, web {len(ctx['web_findings'])}")
        return
    llm = LLM(conn=conn)
    result, res = derive(llm, ctx, n=args.n, job=f"derive:{args.line}:w{args.wave}", effort=args.effort, wave=args.wave)
    drafts, problems = validate(result, allowed, LINES[args.line]["derivatives"])
    print(f"cost ${res.cost_usd:.4f}; {len(result.requirements)} drafts, {len(drafts)} valid")
    for p in problems:
        print("  !", p)
    if args.dry_run:
        from bmw_req.config import get_settings
        out = get_settings().data_dir / "eval" / f"derive_dry_{args.line.replace(' ', '')}_w{args.wave}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([d.model_dump() for d in drafts], indent=1, ensure_ascii=False))
        print("wrote", out)
        return
    print(store(conn, drafts, model=llm.model_for("smart"), usage_id=res.usage_id, wave=args.wave))


if __name__ == "__main__":
    main()
