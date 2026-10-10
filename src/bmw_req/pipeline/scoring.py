"""Explainable per-market scoring, evidence levels, prioritization runs and change proposals
(requirement-model.md v4, D-011, D-013, D-029 — resolves Q-004).

Score of one requirement target (derivative × market) as of a wave:

    base  = Σ weight_f · value_f / Σ weight_f        over the factors that have data for this target
    score = 100 · base · confidence(evidence level) + market-fit modifier + effort modifier   (clipped 0–100)

- Factors without data for the target (e.g. no China verbatims, no study before wave 2) are left out and the
  weights renormalized — and shown as an explicit evidence gap, so a market is not punished for missing data
  but its evidence level (and so its confidence) stays honest.
- Brand fit is a gate only (fail blocks approval without PM override), not a score factor (no double counting).
- Feasibility is realization context only (Q-010 option b, D-030): shown, never scored or blocking.
- AI recomputes scores (logged, D-013); priority changes against a PM-confirmed priority become change
  proposals the PM must accept or reject.
"""

import json
import math
import sqlite3
from collections import defaultdict

from bmw_req.pipeline.requirements import audit
from bmw_req.portfolio import LINES, MIN_MARKET_VERBATIMS, line_of

SCORING_VERSION = "score-v3"

DEFAULT_WEIGHTS = {
    "customer_voice": 30,        # severity-weighted share of this market's feedback (verbatim findings)
    "satisfaction_gap": 15,      # customer study: item weak (or, for must-not-lose, strong) vs other items
    "market_volume": 15,         # BMW sales of the derivative in this market + 2030 momentum (relative only, Q-015)
    "competitive_pressure": 15,  # cited competitor advantages / review criticism in this market
    "future_relevance": 15,      # horizon, Kano drift, cited trends/expectations
    "portfolio_leverage": 10,    # how many derivative × market targets benefit
}
FACTOR_LABELS = {
    "customer_voice": "Customer voice", "satisfaction_gap": "Satisfaction gap", "market_volume": "Market volume",
    "competitive_pressure": "Competitive pressure", "future_relevance": "Future relevance",
    "portfolio_leverage": "Portfolio leverage",
}
CONFIDENCE = {"E1": 1.0, "E2": 0.92, "E3": 0.75, "E4": 0.5}   # D-038: thin evidence costs real points
EFFORT_MOD = {"S": 0.0, "M": -3.0, "L": -6.0}
MARKET_FIT_MOD = {"pass": 2.0, "warn": -5.0, "fail": -10.0}
PRIORITY_BANDS = [("Must", 60.0), ("Should", 45.0), ("Could", 0.0)]
TIER_W = {"T1": 1.0, "T2": 0.8, "T3": 0.5}
COMPETITIVE_TYPES = {"competitor_advantage", "review_criticism", "competitor_feature"}
TREND_TYPES = {"market_trend", "customer_expectation"}
SUPPORT_Q_WEIGHT = 0.5      # Q-020: support-call questions count half
SHRINK_K = 150              # pseudo-verbatims pulling a small market's share toward the derivative-wide share
SEVERITY_W = {"low": 1.0, "medium": 2.0, "high": 3.0}
BORROW_DISCOUNT = 0.5       # D-038: customer voice borrowed from other markets of the line counts half
OWN_EVIDENCE_MIN = 0.5      # D-038: study gap AND competitive pressure ≥ this lets a no-comment market exceed the cap


def priority_for(score: float) -> str:
    for name, lo in PRIORITY_BANDS:
        if score >= lo:
            return name
    return "Could"


# ---------------------------------------------------------------------------------------------- evidence
def market_base(conn, derivative: str, market: str, wave: int) -> int:
    return conn.execute(
        """SELECT COUNT(*) FROM verbatim_extraction e JOIN source_item s ON s.id = e.source_item_id
           WHERE s.vehicle_model_id = ? AND s.market_code = ? AND s.wave <= ? AND e.in_scope = 1
             AND e.extractor_version = (SELECT MAX(extractor_version) FROM verbatim_extraction)""",
        (derivative, market, wave),
    ).fetchone()[0]


def verbatim_evidence(conn, req_id: str, derivative: str, market: str, wave: int) -> dict:
    """Distinct verbatims behind the requirement's supporting verbatim findings in this market/wave."""
    rows = conn.execute(
        """SELECT s.id sid, s.meta_json, g.severity, g.support_question FROM requirement_finding rf
           JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
           JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
           JOIN source_item s ON s.id = g.source_item_id
           WHERE rf.requirement_id = ? AND rf.relation = 'supports' AND s.vehicle_model_id = ?
             AND s.market_code = ? AND s.wave <= ?""",
        (req_id, derivative, market, wave),
    ).fetchall()
    per_verb, channels = {}, set()
    for r in rows:
        w = SEVERITY_W.get(r["severity"], 1.0) * (SUPPORT_Q_WEIGHT if r["support_question"] else 1.0)
        per_verb[r["sid"]] = max(per_verb.get(r["sid"], 0.0), w)
        channels.add(json.loads(r["meta_json"]).get("channel"))
    return {"verbatims": len(per_verb), "severity_weighted": round(sum(per_verb.values()), 2),
            "channels": sorted(c for c in channels if c)}


def linked_findings(conn, req_id: str, wave: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT f.*, rf.relation FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
           WHERE rf.requirement_id = ? AND COALESCE(f.first_wave, 1) <= ?""", (req_id, wave))]


def evidence_level(verb: dict, has_study: bool, n_web_strong: int, n_web_any: int) -> str:
    v, ch = verb["verbatims"], len(verb["channels"])
    if v >= 20 and ch >= 2 and (has_study or n_web_strong):
        return "E1"
    if v >= 15 or (v >= 3 and (has_study or n_web_strong)) or (has_study and n_web_strong):
        return "E2"
    if v >= 1 or has_study or n_web_any:
        return "E3"
    return "E4"


# ---------------------------------------------------------------------------------------------- factors
def sales_value(conn, derivative: str, market: str, wave: int) -> tuple[float | None, str]:
    rows = conn.execute(
        """SELECT s.vehicle_model_id d, s.market_code m, s.year, s.units FROM sales s
           JOIN source_item i ON i.id = s.source_item_id WHERE i.wave <= ?""", (wave,)).fetchall()
    if not rows:
        return None, "no sales data"
    latest = {}
    for r in rows:
        if r["year"] <= 2025:
            k = (r["d"], r["m"])
            if k not in latest or r["year"] > latest[k][0]:
                latest[k] = (r["year"], r["units"] or 0)
    mx = max((u for _, u in latest.values()), default=0) or 1
    year, units = latest.get((derivative, market), (None, 0))
    f2030 = next((r["units"] for r in rows if (r["d"], r["m"], r["year"]) == (derivative, market, 2030)), None)
    growth = (f2030 / units - 1) if (f2030 and units) else None
    vol = units / mx
    value = 0.75 * vol + 0.25 * (min(1.0, max(0.0, 0.5 + growth / 0.4)) if growth is not None else 0.5)
    expl = f"{units:,} units {year} (BMW file, relative only)" + (f", {growth:+.0%} to 2030" if growth is not None else "")
    return value, expl


def score_target(conn, req: dict, target: dict, wave: int, weights: dict, n_targets: int) -> dict:
    d, m = target["vehicle_model_id"], target["market_code"]
    links = linked_findings(conn, req["id"], wave)
    factors = {}

    # customer voice — empirical-Bayes shrinkage: a small market's share is pulled toward the derivative-wide share
    base = market_base(conn, d, m, wave)
    verb = verbatim_evidence(conn, req["id"], d, m, wave)
    voice_observed = base >= MIN_MARKET_VERBATIMS
    if not voice_observed:
        # D-038: no usable comment base here (e.g. China). Dropping the factor and renormalizing let the other factors
        # carry 100 % of the score, so the market with the least evidence ranked highest. Instead borrow the line-wide
        # rate (other markets / derivatives of the same car line) at a discount, and say so.
        line_ds = LINES[line_of(d)]["derivatives"]
        pairs = [(dd, mk) for dd in line_ds for mk in ("US", "EU", "CN", "RoW") if (dd, mk) != (d, m)]
        lb = sum(market_base(conn, dd, mk, wave) for dd, mk in pairs)
        lsw = sum(verbatim_evidence(conn, req["id"], dd, mk, wave)["severity_weighted"] for dd, mk in pairs)
        if lb >= MIN_MARKET_VERBATIMS:
            val = BORROW_DISCOUNT * min(1.0, math.log1p(100 * lsw / lb / 3 * 4) / math.log1p(40))
            factors["customer_voice"] = (val, f"no comments of its own ({base} in {m} for {d}) — borrowed the "
                                              f"{line_of(d)} rate from other markets at ×{BORROW_DISCOUNT}")
        else:
            factors["customer_voice"] = (None, f"evidence gap: only {base} in-scope verbatims in {m} for {d}, "
                                               f"none elsewhere in the {line_of(d)} line")
    else:
        all_base = sum(market_base(conn, d, mk, wave) for mk in ("US", "EU", "CN", "RoW"))
        all_sw = sum(verbatim_evidence(conn, req["id"], d, mk, wave)["severity_weighted"] for mk in ("US", "EU", "CN", "RoW"))
        prior = all_sw / all_base if all_base else 0.0
        shrunk = (verb["severity_weighted"] + SHRINK_K * prior) / (base + SHRINK_K)
        pct = 100 * shrunk / 3
        val = min(1.0, math.log1p(pct * 4) / math.log1p(40))
        factors["customer_voice"] = (val, f"{verb['verbatims']} of {base} in-scope verbatims "
                                          f"({100 * verb['verbatims'] / base:.1f}%), channels {', '.join(verb['channels']) or '–'}"
                                          + (f"; small base, pulled toward {d}-wide rate" if base < 2 * SHRINK_K else ""))

    # satisfaction gap (customer study)
    # supports and contradicts both count: a strong study result is evidence against a claimed gap (value → 0)
    study = [f for f in links if f["source_kind"] == "study" and f["vehicle_model_id"] == d and f["market_code"] == m]
    if study:
        zs = [json.loads(f["metrics_json"] or "{}").get("z") for f in study]
        zs = [z for z in zs if z is not None]
        if zs:
            if req["must_not_lose"]:
                z = max(zs)
                val = min(1.0, max(0.0, z / 2))
            else:
                z = min(zs)
                val = min(1.0, max(0.0, -z / 2))
            factors["satisfaction_gap"] = (val, f"{len(study)} study item(s), most extreme z = {z:+.2f} ('{study[0]['title']}')")
        else:
            factors["satisfaction_gap"] = (None, "linked study items without score")
    else:
        factors["satisfaction_gap"] = (None, "no linked customer-study item for this model × market"
                                       + (" (study arrives in wave 2)" if wave < 2 else ""))

    # market volume
    val, expl = sales_value(conn, d, m, wave)
    factors["market_volume"] = (val, expl)

    # competitive pressure + trends (web findings for this market; line-level findings count too)
    def web_for(types):
        out = []
        for f in links:
            if f["source_kind"] != "web" or f["relation"] != "supports" or f["type"] not in types:
                continue
            if f["market_code"] not in (None, m):
                continue
            mt = json.loads(f["metrics_json"] or "{}")
            tiers = mt.get("tiers") or {}
            w = sum(TIER_W.get(t, 0.5) * n for t, n in tiers.items()) if isinstance(tiers, dict) else TIER_W.get(str(tiers), 0.5)
            out.append((f, w or 0.5))
        return out

    comp = web_for(COMPETITIVE_TYPES)
    cw = sum(w for _, w in comp)
    factors["competitive_pressure"] = (min(1.0, cw / 4), f"{len(comp)} competitor/review finding(s) in {m}, "
                                                         f"tier-weighted sources {cw:.1f}")
    trends = web_for(TREND_TYPES)
    fut = 0.6 if req["horizon"] == "at_successor_launch" else 0.3
    drift = (req["kano_drift"] or "").lower()
    if req["kano_class"] != "basic" and "basic" in drift:
        fut += 0.2
    fut += min(0.4, 0.1 * len(trends))
    factors["future_relevance"] = (min(1.0, fut), f"horizon {req['horizon']}, Kano {req['kano_class']}"
                                   + (" drifting to basic" if "basic" in drift and req["kano_class"] != "basic" else "")
                                   + f", {len(trends)} trend/expectation finding(s)")
    lev = min(1.0, (n_targets - 1) / 7 + (0.15 if target["realization"] == "platform_wide" else 0))
    factors["portfolio_leverage"] = (lev, f"{n_targets} derivative × market target(s), realization {target['realization']}")

    avail = {k: v for k, v in factors.items() if v[0] is not None}
    wsum = sum(weights[k] for k in avail) or 1
    base_score = sum(weights[k] * v[0] for k, v in avail.items()) / wsum

    has_study = bool(factors["satisfaction_gap"][0] is not None and factors["satisfaction_gap"][0] > 0.2)
    web_any = [f for f in links if f["source_kind"] == "web" and f["market_code"] in (None, m) and f["relation"] == "supports"]
    strong = [f for f in web_any if "T1" in str(json.loads(f["metrics_json"] or "{}").get("tiers"))
              or "T2" in str(json.loads(f["metrics_json"] or "{}").get("tiers"))]
    level = evidence_level(verb, has_study, len(strong), len(web_any))
    conf = CONFIDENCE[level]

    fit = {r["check_type"]: r["result"] for r in conn.execute(
        """SELECT check_type, result FROM fit_check WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?
           ORDER BY id""", (req["id"], d, m))}
    mfit = MARKET_FIT_MOD.get(fit.get("market"), 0.0)
    eff = EFFORT_MOD.get(req["effort"] or "M", -3.0)
    score = max(0.0, min(100.0, 100 * base_score * conf + mfit + eff))

    breakdown = {
        "version": SCORING_VERSION, "wave": wave, "score": round(score, 1), "base": round(100 * base_score, 1),
        "evidence_level": level, "confidence": conf,
        "modifiers": {"market_fit": mfit, "effort": eff},
        "factors": {
            k: {"label": FACTOR_LABELS[k], "value": None if v[0] is None else round(v[0], 3), "weight": weights[k],
                "points": None if v[0] is None else round(100 * weights[k] * v[0] / wsum * conf, 1),
                "available": v[0] is not None, "explanation": v[1]}
            for k, v in factors.items()
        },
        "gaps": [FACTOR_LABELS[k] for k, v in factors.items() if v[0] is None],
        "gates": {"brand": fit.get("brand"), "segment": fit.get("segment"), "feasibility": fit.get("feasibility")},
        "verbatims": verb, "voice_observed": voice_observed,
    }
    breakdown["priority"] = priority_for(breakdown["score"])
    breakdown["rationale"] = rationale(breakdown, d, m)
    return breakdown


def apply_requirement_rules(req: dict, items: list[tuple[dict, dict]]) -> None:
    """Cross-market rules for one requirement (D-038), applied after every target is scored. `items` = (target, breakdown).

    1. A market without its own customer comments may not outrank the requirement's comment-backed markets, unless it
       has its own strong evidence (a study gap AND competitor pressure in that market) — the cap is shown as a modifier.
    2. An 'Expected' (Kano basic) requirement gets one priority in every market — a basic expectation can't be a Must
       in one market and optional in another. Scores stay per market and visible.
    """
    observed = [b["score"] for _, b in items if b.get("voice_observed")]
    cap = max(observed) if observed else None
    for t, b in items:
        if cap is None or b.get("voice_observed") or b["score"] <= cap:
            continue
        fs = b["factors"]
        own = (fs["satisfaction_gap"]["value"] or 0) >= OWN_EVIDENCE_MIN and \
              (fs["competitive_pressure"]["value"] or 0) >= OWN_EVIDENCE_MIN
        if own:
            b["cap_note"] = (f"ranks above the markets with customer comments (best {cap:.0f}) on its own study gap and "
                             f"competitor evidence")
            continue
        b["modifiers"]["no_comment_cap"] = round(cap - b["score"], 1)
        b["cap_note"] = (f"capped at {cap:.0f}, the best market with customer comments — no comments of its own and no "
                         f"study gap plus competitor evidence to justify ranking higher")
        b["score"] = round(cap, 1)
    for _, b in items:
        b["priority"] = priority_for(b["score"])
    if (req.get("kano_class") or "") == "basic" and items:
        top = max(items, key=lambda x: x[1]["score"])
        prio = top[1]["priority"]
        for t, b in items:
            if b["priority"] != prio:
                b["priority_note"] = (f"Expected (basic) need: same priority in every market — set by the strongest market "
                                      f"{top[0]['vehicle_model_id']} × {top[0]['market_code']} ({top[1]['score']:.0f}); "
                                      f"this market alone would score {b['priority']}")
            b["priority"] = prio
    for t, b in items:
        b["rationale"] = rationale(b, t["vehicle_model_id"], t["market_code"])


def rationale(b: dict, d: str, m: str) -> str:
    fs = b["factors"]
    ranked = sorted([(k, f) for k, f in fs.items() if f["available"]], key=lambda kv: -(kv[1]["points"] or 0))
    top = [f"{f['label'].lower()} ({f['explanation']})" for _, f in ranked[:2] if (f["points"] or 0) > 0]
    weak = [f["label"].lower() for _, f in ranked if (f["value"] or 0) < 0.15]
    parts = [f"{d} × {m}: score {b['score']:.0f} → proposed {b.get('priority') or priority_for(b['score'])}."]
    if b.get("priority_note"):
        parts.append(b["priority_note"] + ".")
    if b.get("cap_note"):
        parts.append(b["cap_note"][0].upper() + b["cap_note"][1:] + ".")
    if b.get("voice_observed") is False and fs["customer_voice"]["available"]:
        parts.append("No customer comments in this market — customer voice borrowed from the line's other markets at half weight.")
    if top:
        parts.append("Driven by " + " and ".join(top) + ".")
    if weak:
        parts.append("Weak on " + ", ".join(weak) + ".")
    if b["gaps"]:
        parts.append("No data for " + ", ".join(g.lower() for g in b["gaps"]) + " — weights renormalized; "
                     f"evidence level {b['evidence_level']} (confidence ×{b['confidence']}).")
    else:
        parts.append(f"Evidence level {b['evidence_level']} (confidence ×{b['confidence']}).")
    if b["gates"].get("brand") == "fail":
        parts.append("Brand-fit FAIL: cannot be approved without a PM override.")
    return " ".join(parts)


# ---------------------------------------------------------------------------------------------- runs
def current_weights(conn) -> tuple[int, dict]:
    r = conn.execute("SELECT id, weights_json FROM weights_version ORDER BY id DESC LIMIT 1").fetchone()
    if r:
        return r["id"], json.loads(r["weights_json"])
    wid = conn.execute(
        "INSERT INTO weights_version (weights_json, created_by, rationale) VALUES (?, 'system', ?)",
        (json.dumps(DEFAULT_WEIGHTS), "Default weights (D-029)"),
    ).lastrowid
    audit(conn, actor_type="system", actor_id="scoring", action="create", entity_type="weights_version",
          entity_id=str(wid), new=DEFAULT_WEIGHTS, rationale="Default weights (D-029)")
    return wid, DEFAULT_WEIGHTS


def set_weights(conn, weights: dict, actor: str, rationale_text: str) -> int:
    old_id, old = current_weights(conn)
    wid = conn.execute("INSERT INTO weights_version (weights_json, created_by, rationale) VALUES (?, ?, ?)",
                       (json.dumps(weights), actor, rationale_text)).lastrowid
    audit(conn, actor_type="human", actor_id=actor, action="change_weights", entity_type="weights_version",
          entity_id=str(wid), old=old, new=weights, rationale=rationale_text)
    return wid


def last_snapshot(conn, req_id, d, m, before_run: int) -> dict | None:
    r = conn.execute(
        """SELECT * FROM score_snapshot WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?
           AND run_id < ? ORDER BY run_id DESC LIMIT 1""", (req_id, d, m, before_run)).fetchone()
    return dict(r) if r else None


def explain_delta(old: dict | None, new: dict) -> str:
    if not old:
        return "first scoring"
    ob = json.loads(old["breakdown_json"])
    parts = [f"score {old['score']:.1f} → {new['score']:.1f} ({new['score'] - old['score']:+.1f})"]
    deltas = []
    for k, f in new["factors"].items():
        of = ob["factors"].get(k, {})
        op, np_ = of.get("points") or 0, f.get("points") or 0
        if of.get("available") != f["available"]:
            deltas.append((abs(np_ - op), f"{f['label']}: {'now available' if f['available'] else 'no longer available'}"
                                          f" ({f['explanation']})"))
        elif abs(np_ - op) >= 0.5:
            deltas.append((abs(np_ - op), f"{f['label']} {np_ - op:+.1f} pts ({f['explanation']})"))
    if ob.get("evidence_level") != new["evidence_level"]:
        deltas.append((99, f"evidence level {ob.get('evidence_level')} → {new['evidence_level']}"))
    deltas.sort(key=lambda x: -x[0])
    return "; ".join([parts[0]] + [t for _, t in deltas[:4]])


def run_prioritization(conn: sqlite3.Connection, *, wave: int, trigger: str, initiated_by: str,
                       ingest_batch_id: int | None = None, note: str | None = None) -> int:
    """Score every requirement target as of `wave`; snapshot; update targets; create change proposals."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        wid, weights = current_weights(conn)
        run_id = conn.execute(
            """INSERT INTO prioritization_run (trigger, ingest_batch_id, weights_version_id, model, initiated_by)
               VALUES (?, ?, ?, ?, ?)""", (trigger, ingest_batch_id, wid, SCORING_VERSION, initiated_by)).lastrowid
        audit(conn, actor_type="system" if initiated_by == "system" else "human", actor_id=initiated_by,
              action="start_run", entity_type="prioritization_run", entity_id=str(run_id),
              new={"wave": wave, "trigger": trigger, "weights_version": wid}, rationale=note, run_id=run_id)
        reqs = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM requirement WHERE status != 'rejected'")}
        targets = defaultdict(list)
        for t in conn.execute("SELECT * FROM requirement_target"):
            if t["requirement_id"] in reqs:
                targets[t["requirement_id"]].append(dict(t))
        results = []
        for rid, ts in targets.items():
            items = [(t, score_target(conn, reqs[rid], t, wave, weights, len(ts))) for t in ts]
            apply_requirement_rules(reqs[rid], items)
            results.extend((rid, t, b) for t, b in items)
        # rank within each derivative × market
        by_target = defaultdict(list)
        for rid, t, b in results:
            by_target[(t["vehicle_model_id"], t["market_code"])].append((rid, t, b))
        n_props = 0
        for key, items in by_target.items():
            items.sort(key=lambda x: -x[2]["score"])
            for rank, (rid, t, b) in enumerate(items, 1):
                prio = b["priority"]
                prev = last_snapshot(conn, rid, *key, run_id)
                conn.execute(
                    """INSERT INTO score_snapshot (run_id, requirement_id, vehicle_model_id, market_code, score,
                                                   breakdown_json, rank, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, rid, *key, b["score"], json.dumps(b, ensure_ascii=False), rank, prio))
                delta = explain_delta(prev, b)
                if t["score"] is None or abs((t["score"] or 0) - b["score"]) >= 0.05:
                    audit(conn, actor_type="ai", actor_id="pipeline.scoring", action="rescore",
                          entity_type="requirement_target", entity_id=f"{rid}:{key[0]}×{key[1]}", field="score",
                          old=None if t["score"] is None else round(t["score"], 1), new=b["score"],
                          rationale=delta, model=SCORING_VERSION, run_id=run_id)
                conn.execute(
                    """UPDATE requirement_target SET score = ?, score_breakdown_json = ?, proposed_priority = ?,
                           evidence_level = ?, rationale = COALESCE(rationale, ''), run_id = ?
                       WHERE requirement_id = ? AND vehicle_model_id = ? AND market_code = ?""",
                    (b["score"], json.dumps(b, ensure_ascii=False), prio, b["evidence_level"], run_id, rid, *key))
                confirmed = t["priority"]
                if confirmed:
                    # an open proposal from an earlier run is stale once this run has scored the target again
                    conn.execute(
                        """UPDATE change_proposal SET status = 'superseded' WHERE requirement_id = ? AND vehicle_model_id = ?
                           AND market_code = ? AND field = 'priority' AND status = 'open'""", (rid, *key))
                if confirmed and confirmed != prio:
                    conn.execute(
                        """INSERT INTO change_proposal (run_id, requirement_id, vehicle_model_id, market_code, field, old_value,
                               proposed_value, reason, evidence_delta_json, kind)
                           VALUES (?, ?, ?, ?, 'priority', ?, ?, ?, ?, 'priority')""",
                        (run_id, rid, *key, confirmed, prio, delta,
                         json.dumps({"previous_run": prev["run_id"] if prev else None, "score": b["score"]})))
                    n_props += 1
        # requirement-level evidence level = best target level
        for rid, ts in targets.items():
            levels = [b["evidence_level"] for r2, _, b in results if r2 == rid]
            best = min(levels) if levels else "E4"
            if reqs[rid]["evidence_level"] != best:
                conn.execute("UPDATE requirement SET evidence_level = ? WHERE id = ?", (best, rid))
                audit(conn, actor_type="ai", actor_id="pipeline.scoring", action="update_evidence_level",
                      entity_type="requirement", entity_id=rid, field="evidence_level",
                      old=reqs[rid]["evidence_level"], new=best, rationale="best evidence level across targets",
                      model=SCORING_VERSION, run_id=run_id)
        audit(conn, actor_type="system", actor_id="pipeline.scoring", action="finish_run",
              entity_type="prioritization_run", entity_id=str(run_id),
              new={"targets": len(results), "change_proposals": n_props}, run_id=run_id)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return run_id


if __name__ == "__main__":
    import argparse

    from bmw_req.db import connect

    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--trigger", default="new_evidence")
    a = ap.parse_args()
    print("run", run_prioritization(connect(), wave=a.wave, trigger=a.trigger, initiated_by="system"))
