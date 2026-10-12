"""Scoring helpers of prio-v1 (`prioritize/score.py`, D-050), carried over unchanged from score-v3 (D-029, D-038) when
the wave pipeline was retired (D-057): evidence-level confidence, modifiers, bands, the customer-voice curve and
shrinkage, renormalisation over available factors, the no-comment cap, one band for Expected needs, rationale text
and the explanation of a score change."""

import json
import math

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


def voice_curve(pct: float) -> float:
    """Share of a market's comments (in %, severity-adjusted where available) → 0–1 on a log curve (~10 % saturates)."""
    return min(1.0, math.log1p(pct * 4) / math.log1p(40))


def shrink(n: float, base: float, prior: float, k: float = SHRINK_K) -> float:
    """Empirical-Bayes share: a small base is pulled toward the wider (prior) share by k pseudo-observations."""
    return (n + k * prior) / (base + k)


def renormalised(factors: dict[str, tuple], weights: dict) -> tuple[float, float]:
    """(base 0–1, weight sum) over the factors with data — missing factors drop out and the weights renormalize."""
    avail = {k: v for k, v in factors.items() if v[0] is not None}
    wsum = sum(weights[k] for k in avail) or 1
    return sum(weights[k] * v[0] for k, v in avail.items()) / wsum, wsum


def cap_unobserved(bs: list[dict], own: tuple[str, str] = ("satisfaction_gap", "competitive_pressure")) -> None:
    """D-038 rule 1 on breakdowns of one requirement: a market without its own comments (`voice_observed` False) may
    not outrank the requirement's comment-backed markets unless both `own` factors are ≥ OWN_EVIDENCE_MIN there."""
    observed = [b["score"] for b in bs if b.get("voice_observed")]
    cap = max(observed) if observed else None
    for b in bs:
        if cap is None or b.get("voice_observed") or b["score"] <= cap:
            continue
        fs = b["factors"]
        if all((fs[k]["value"] or 0) >= OWN_EVIDENCE_MIN for k in own):
            b["cap_note"] = (f"ranks above the markets with customer comments (best {cap:.0f}) on its own study gap and "
                             f"competitor evidence")
            continue
        b["modifiers"]["no_comment_cap"] = round(cap - b["score"], 1)
        b["cap_note"] = (f"capped at {cap:.0f}, the best market with customer comments — no comments of its own and no "
                         f"study gap plus competitor evidence to justify ranking higher")
        b["score"] = round(cap, 1)


def align_basic(kano: str | None, items: list[tuple[str, dict]]) -> None:
    """D-038 rule 2: an 'Expected' (Kano basic) need gets one priority everywhere. `items` = (target label, breakdown)."""
    if (kano or "") != "basic" or not items:
        return
    top = max(items, key=lambda x: x[1]["score"])
    prio = top[1]["priority"]
    for _, b in items:
        if b["priority"] != prio:
            b["priority_note"] = (f"Expected (basic) need: same priority in every market — set by the strongest market "
                                  f"{top[0]} ({top[1]['score']:.0f}); this market alone would score {b['priority']}")
        b["priority"] = prio


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
