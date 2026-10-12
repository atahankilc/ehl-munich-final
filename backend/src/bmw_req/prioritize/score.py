"""Stage `prioritize` (D-050): deterministic prio-v1 score per requirement × car line × market. No LLM, free.

Same machinery as score-v3 (its helpers now live in `prioritize/factors.py`, D-057): weighted factors 0–1, renormalised over the
factors that have data (missing ones are evidence gaps), × confidence multiplier, + effort / market-fit modifiers;
bands Must ≥ 60 · Should ≥ 45 · Could; customer voice with shrinkage + log curve and the D-038 borrow (×0.5) and cap for
markets without their own comments; D-038 one band for Expected (Kano basic) needs; templated rationale (rule 11).

What is new against score-v3 (the inputs are the D-048 definition layer, not the legacy requirement tables):
- customer voice = the area's comments from this line × market (`req_area.metrics.by_line_market`) vs. the in-scope
  comment base of that line × market at the checkpoint; prior = the line-wide share;
- satisfaction gap = study items the requirement cites (and its area's supporting study edges), looked up by item text
  for the line's derivatives × market (−z/2 to improve; +z/2 for keep_strength = must-not-lose);
- competitive gap = BMW baseline vs. the cited rival threshold on the ladder (clip(gap / 20 %)); while ladders are
  thin it falls back to tier-weighted `competes_with` evidence on the area's themes, and says so (`method`);
- market weight = 0.75 × BMW volume share (stylized, Q-015, relative only) + 0.25 × cited public trend (D-046);
  BMW-vs-public conflicts are flagged, never corrected — capped at 10 of 100 weight so the stylized file can't dominate;
- portfolio leverage = spread over targets + enabler credit (Σ enables strength/3 × enabled base/100, cap 0.5);
- the PM's ladder rung (`def_choice`, else the AI's recommended rung) sets effort and the basis mix of confidence;
- links never penalise: synergy / enables bundles share their strongest member's band per line × market; two Musts
  that conflict / compete for a resource get a `choose_jointly` flag.
A band that differs from the PM-confirmed band (or the parent checkpoint's band) becomes a `prio_proposal`.
"""

from __future__ import annotations

import json
from collections import defaultdict

from bmw_req import checkpoints as C
from bmw_req.definition.domains import ASPECT_RESOURCES
from bmw_req.prioritize import factors as S
from bmw_req.audit import audit
from bmw_req.portfolio import LINES, MIN_MARKET_VERBATIMS
from bmw_req.prioritize import BAND_RANK, ensure
from bmw_req.structure.classify import VERSION as EXTRACT_VERSION
from bmw_req.structure.events import log
from bmw_req.structure.market import LABEL as MARKET_LABEL, LINE_OF_CAR, market_context

SCHEME = "prio-v1"
DEFAULT_WEIGHTS = {"customer_voice": 30, "satisfaction_gap": 15, "competitive_gap": 15, "market_weight": 10,
                   "portfolio_leverage": 10, "future_relevance": 20}
DEFAULT_BANDS = {name: lo for name, lo in S.PRIORITY_BANDS if name != "Could"}   # Must ≥ 60 · Should ≥ 45 (PM-editable)
DIMENSION = {"customer_voice": "customer", "satisfaction_gap": "customer", "competitive_gap": "business",
             "market_weight": "business", "portfolio_leverage": "business", "future_relevance": "future"}
LABELS = {"customer_voice": "Customer voice", "satisfaction_gap": "Satisfaction gap", "competitive_gap": "Competitive gap",
          "market_weight": "Market weight", "portfolio_leverage": "Portfolio leverage", "future_relevance": "Future relevance"}
BASIS_W = {"cited": 1.0, "projected": 0.7, "assumption": 0.5, "gap": 0.3}
EFFORT_OF_TYPE = {"keep_strength": "S", "package_variant": "S", "market_variant": "M", "change_design": "M",
                  "add_feature": "M", "raise_capability": "L"}
STEPS = ("S", "M", "L")
RUNG_SHIFT = {"threshold": -1, "target": 0, "stretch": 1}
GAP_FULL = 0.20            # a rival 20 % ahead on the metric = full competitive gap
LINK_MIN = 2               # links below this strength are info only
ENABLER_CAP = 0.5
MEDIUM = 2 / 3             # area comments carry no severity: each counts at score-v3's medium severity (2 of 3)
OWN_COMMENTS = 3           # fewer comments from a line × market is not its own evidence (define.MIN_MARKET_COMMENTS)
STAGES_UP = ("define", "specify", "couple", "areas", "contextualize", "gate")


def _loads(s, default=None):
    return json.loads(s) if s else default


# ------------------------------------------------------------------------------------------------ weights
def band_for(score: float, bands: dict | None = None) -> str:
    """Band of a score under the weights version's thresholds (default Must ≥ 60 · Should ≥ 45, score-v3's)."""
    bands = bands or DEFAULT_BANDS
    return "Must" if score >= bands["Must"] else "Should" if score >= bands["Should"] else "Could"


def _bands_of(cfg: dict) -> dict:
    return {**DEFAULT_BANDS, **{k: float(v) for k, v in (cfg.get("bands") or {}).items() if k in DEFAULT_BANDS}}


def stored_config(conn) -> tuple[int | None, dict, dict]:
    """(version id, factor weights, bands) of the current prio-v1 weights version — read-only (defaults if none stored)."""
    r = conn.execute("SELECT id, weights_json FROM weights_version WHERE (weights_json::json ->> 'scheme') = ? "
                     "ORDER BY id DESC LIMIT 1", (SCHEME,)).fetchone()
    if not r:
        return None, dict(DEFAULT_WEIGHTS), dict(DEFAULT_BANDS)
    cfg = json.loads(r["weights_json"])
    return r["id"], {**DEFAULT_WEIGHTS, **cfg["weights"]}, _bands_of(cfg)


def current_config(conn) -> tuple[int, dict, dict]:
    """prio-v1 weights live in `weights_version` as {"scheme": "prio-v1", "weights": …, "bands": …} (score-v3 skips such
    rows); the first call stores the defaults."""
    wid, weights, bands = stored_config(conn)
    if wid is not None:
        return wid, weights, bands
    new = {"scheme": SCHEME, "weights": DEFAULT_WEIGHTS, "bands": DEFAULT_BANDS}
    wid = conn.execute("INSERT INTO weights_version (weights_json, created_by, rationale) VALUES (?, 'system', ?) RETURNING id",
                       (json.dumps(new), "Default prio-v1 weights (D-050)")).fetchone()[0]
    audit(conn, actor_type="system", actor_id="prioritize", action="create", entity_type="weights_version",
          entity_id=str(wid), new=new, rationale="Default prio-v1 weights (D-050)")
    return wid, dict(DEFAULT_WEIGHTS), dict(DEFAULT_BANDS)


def current_weights(conn) -> tuple[int, dict]:
    wid, weights, _ = current_config(conn)
    return wid, weights


def validate(weights: dict, bands: dict | None) -> tuple[dict, dict]:
    """Factors: exactly the six prio-v1 keys, each ≥ 0, sum > 0. Bands: 0 < Should < Must ≤ 100."""
    if set(weights) != set(DEFAULT_WEIGHTS) or any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 for v in weights.values()):
        raise ValueError(f"weights need exactly {sorted(DEFAULT_WEIGHTS)} with values ≥ 0")
    if sum(weights.values()) <= 0:
        raise ValueError("weights must not all be 0")
    bands = {**DEFAULT_BANDS, **(bands or {})}
    if set(bands) != set(DEFAULT_BANDS) or not all(isinstance(v, (int, float)) for v in bands.values()):
        raise ValueError("bands need Must and Should")
    if not 0 < bands["Should"] < bands["Must"] <= 100:
        raise ValueError("bands need 0 < Should < Must ≤ 100")
    return {k: float(v) for k, v in weights.items()}, {k: float(v) for k, v in bands.items()}


def set_weights(conn, weights: dict, actor: str, rationale: str, bands: dict | None = None) -> int:
    """New prio-v1 weights version (factors + band thresholds) + human audit_event (caller holds the transaction).
    `bands` omitted = keep the current thresholds."""
    old_id, old, old_bands = current_config(conn)
    weights, bands = validate(weights, bands if bands is not None else old_bands)
    new = {"scheme": SCHEME, "weights": weights, "bands": bands}
    wid = conn.execute("INSERT INTO weights_version (weights_json, created_by, rationale) VALUES (?, ?, ?) RETURNING id",
                       (json.dumps(new), actor, rationale)).fetchone()[0]
    audit(conn, actor_type="human", actor_id=actor, action="change_weights", entity_type="weights_version",
          entity_id=str(wid), old={"scheme": SCHEME, "weights": old, "bands": old_bands, "id": old_id}, new=new,
          rationale=rationale)
    return wid


def weights_history(conn, limit: int = 20) -> list[dict]:
    """prio-v1 weights versions, newest first. `version` numbers the versions WITHIN the scheme (v1 = the default row;
    `weights_version.id` is shared with score-v3, so it is `id` here); `default` = the system's default row."""
    rows = conn.execute("SELECT id, weights_json, created_by, created_at, rationale FROM weights_version "
                        "WHERE (weights_json::json ->> 'scheme') = ? ORDER BY id", (SCHEME,)).fetchall()
    out = []
    for n, r in enumerate(rows, 1):
        cfg = json.loads(r["weights_json"])
        out.append({"version": n, "id": r["id"], "factors": {**DEFAULT_WEIGHTS, **cfg["weights"]}, "bands": _bands_of(cfg),
                    "actor": r["created_by"], "at": r["created_at"], "rationale": r["rationale"], "default": r["created_by"] == "system"})
    return out[::-1][:limit]


def current_meta(conn) -> dict:
    """The current prio-v1 version as the page names it: {id, version (within the scheme), actor, at, rationale, default}."""
    h = weights_history(conn, 1)
    if not h:
        return {"id": None, "version": 1, "actor": "system", "at": None, "rationale": "Default prio-v1 weights (D-050)", "default": True}
    return {k: h[0][k] for k in ("id", "version", "actor", "at", "rationale", "default")}


# ------------------------------------------------------------------------------------------------ context
def comment_base(conn, cp: str) -> dict[str, int]:
    """In-scope customer comments visible at `cp`, per 'line:market'."""
    vis = C.visible_ids(cp)
    out: dict[str, int] = defaultdict(int)
    for r in conn.execute(f"""SELECT s.vehicle_model_id car, s.market_code m, COUNT(DISTINCT s.id) n FROM verbatim_extraction e
                              JOIN source_item s ON s.id = e.source_item_id WHERE e.extractor_version = ? AND e.in_scope = 1
                              AND s.checkpoint IN ({','.join('?' * len(vis))}) GROUP BY 1, 2""", (EXTRACT_VERSION, *vis)):
        if r["car"] in LINE_OF_CAR and r["m"]:
            out[f"{LINE_OF_CAR[r['car']]}:{r['m']}"] += r["n"]
    return dict(out)


def choices_at(conn, cp: str) -> dict[tuple, dict]:
    """Latest PM ladder choice per (key, line, market) made at `cp` or an ancestor (or without a checkpoint)."""
    vis = set(C.visible_ids(cp))
    out = {}
    for r in conn.execute("SELECT * FROM def_choice ORDER BY id"):
        if r["checkpoint_id"] in vis or r["checkpoint_id"] is None:
            out[(r["req_key"], r["line"], r["market"])] = dict(r)
    return out


def decisions_at(conn, cp: str | None = None) -> dict[tuple, dict]:
    vis = set(C.visible_ids(cp)) if cp else None
    out = {}
    for r in conn.execute("SELECT * FROM prio_decision ORDER BY id"):
        if vis is None or r["checkpoint_id"] in vis or r["checkpoint_id"] is None:
            out[(r["req_key"], r["line"], r["market"])] = dict(r)
    return out


def load(conn, cp: str) -> dict:
    """Everything prio-v1 reads at `cp` (latest completed upstream runs)."""
    from api.routers.definition import _links   # PM reviews applied: removed links flagged, PM-added links included

    ensure(conn)
    runs = {s: C.latest_run(conn, cp, s) for s in STAGES_UP}
    if not runs["define"] or not runs["specify"]:
        raise C.CheckpointError(f"Run 'define' and 'specify' at {cp} first")
    reqs = [dict(r) for r in conn.execute("SELECT * FROM def_requirement WHERE run_id = ? ORDER BY key", (runs["define"]["id"],))]
    specs = {r["req_key"]: dict(r) for r in conn.execute("SELECT * FROM def_spec WHERE run_id = ?", (runs["specify"]["id"],))}
    areas = {}
    if runs["areas"]:
        areas = {r["key"]: {"metrics": _loads(r["metrics_json"], {}), "themes": _loads(r["theme_keys_json"], [])}
                 for r in conn.execute("SELECT key, metrics_json, theme_keys_json FROM req_area WHERE run_id = ?", (runs["areas"]["id"],))}
    edges: dict[str, list[tuple]] = defaultdict(list)
    if runs["contextualize"]:
        for e in conn.execute("""SELECT src_type, src_id, dst_id, relation FROM evidence_edge WHERE run_id = ? AND dst_type = 'theme'
                                 AND relation IN ('supports', 'contradicts', 'competes_with', 'trend_for')
                                 AND src_type IN ('research', 'study')""", (runs["contextualize"]["id"],)):
            edges[e["dst_id"]].append((e["src_type"], e["src_id"], e["relation"]))
    rids = {int(s[1]) for es in edges.values() for s in es if s[0] == "research"}
    rids |= {int(i.split(":")[1]) for r in reqs for i in _loads(r["trend_ids_json"], []) if i.startswith("research:")}
    src = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT id, trust_tier, market_code, published_at, kind FROM source_item WHERE id IN ({','.join('?' * len(rids))})",
        tuple(rids))} if rids else {}
    study = {r["id"]: dict(r) for r in conn.execute("SELECT id, item, vehicle_model_id, market_code, z_within_column z FROM study_metric")}
    by_item: dict[tuple, dict] = {(s["item"], s["vehicle_model_id"], s["market_code"]): s for s in study.values()}
    keys = {r["key"] for r in reqs}
    links = _links(conn, runs["couple"]["id"] if runs["couple"] else None, keys)
    links = [l for l in links if (l.get("review") or {}).get("verdict") != "removed"]
    fit: dict[tuple, dict] = defaultdict(dict)
    if runs["gate"]:
        for r in conn.execute("SELECT * FROM prio_fit WHERE run_id = ? ORDER BY id", (runs["gate"]["id"],)):
            fit[(r["req_key"], r["line"], r["market"])][r["check_type"]] = {"result": r["result"], "rationale": r["rationale"],
                                                                             "checked_by": r["checked_by"]}
    spec_tracks = {}
    for r in conn.execute("SELECT entity_key, state, payload_json FROM track WHERE run_id = ? AND entity_key LIKE 'spec:%'",
                          (runs["specify"]["id"],)):
        spec_tracks[r["entity_key"][5:]] = {"state": r["state"], "moved": (_loads(r["payload_json"], {}) or {}).get("moved")}
    return {"cp": cp, "runs": runs, "reqs": reqs, "specs": specs, "areas": areas, "edges": edges, "src": src,
            "study": study, "by_item": by_item, "base": comment_base(conn, cp), "market": market_context(conn, cp),
            "choices": choices_at(conn, cp), "links": links, "fit": fit, "spec_tracks": spec_tracks}


def targets_of(req: dict, spec: dict | None) -> list[tuple[str, str]]:
    """Line × market targets: the requirement's targets, plus any extra rung on its ladder."""
    out = [(t["line"], t["market"]) for t in _loads(req["targets_json"], [])]
    for r in _loads(spec["ladder_json"], []) if spec else []:
        if (r["line"], r["market"]) not in out:
            out.append((r["line"], r["market"]))
    return out


# ------------------------------------------------------------------------------------------------ factors
def theme_edges(ctx: dict, req: dict) -> list[tuple]:
    area = ctx["areas"].get(req["area_key"]) or {}
    return [e for t in area.get("themes", []) for e in ctx["edges"].get(t, [])]


def _src_in_market(ctx: dict, sid: int, market: str) -> bool:
    s = ctx["src"].get(sid)
    return bool(s) and s["market_code"] in (None, "", market)


def customer_voice(ctx: dict, req: dict, line: str, market: str) -> tuple[float | None, str, bool, int]:
    """(value, explanation, observed, own comments)."""
    area = ctx["areas"].get(req["area_key"])
    lm = dict((area or {}).get("metrics", {}).get("by_line_market") or {})
    if not area:   # area not in the latest areas run: fall back to the counts define stored per target
        lm = {f"{t['line']}:{t['market']}": t.get("comments") or 0 for t in _loads(req["targets_json"], [])}
    key = f"{line}:{market}"
    n, base = lm.get(key, 0), ctx["base"].get(key, 0)
    line_keys = [k for k in ctx["base"] if k.startswith(f"{line}:")]
    if base >= MIN_MARKET_VERBATIMS:
        lb = sum(ctx["base"][k] for k in line_keys)
        prior = sum(lm.get(k, 0) for k in line_keys) / lb if lb else 0.0
        val = S.voice_curve(100 * S.shrink(n, base, prior) * MEDIUM)
        return val, (f"{n} of {base} comments from {line} {market} ({100 * n / base:.1f}%)"
                     + (f"; small base, pulled toward the {line}-wide rate" if base < 2 * S.SHRINK_K else "")), True, n
    others = [k for k in line_keys if k != key]
    ob = sum(ctx["base"][k] for k in others)
    if ob >= MIN_MARKET_VERBATIMS:
        on = sum(lm.get(k, 0) for k in others)
        val = S.BORROW_DISCOUNT * S.voice_curve(100 * on / ob * MEDIUM)
        return val, (f"no comment base of its own ({base} comments from {line} {market}) — borrowed the {line} rate "
                     f"from its other markets ({on} of {ob}) at ×{S.BORROW_DISCOUNT}"), False, n
    return None, f"evidence gap: {base} comments from {line} {market}, none elsewhere in the {line} line", False, n


def satisfaction_gap(ctx: dict, req: dict, line: str, market: str) -> tuple[float | None, str]:
    ids = [int(i.split(":")[1]) for i in _loads(req["evidence_ids_json"], []) if i.startswith("study:")]
    via_area = [int(e[1]) for e in theme_edges(ctx, req) if e[0] == "study" and e[2] in ("supports", "contradicts")]
    items = {ctx["study"][i]["item"] for i in ids + via_area if i in ctx["study"]}
    if not items:
        return None, "no customer-study item linked to this requirement"
    rows = [ctx["by_item"][(it, d, market)] for it in sorted(items) for d in LINES[line]["derivatives"]
            if (it, d, market) in ctx["by_item"] and ctx["by_item"][(it, d, market)]["z"] is not None]
    if not rows:
        return None, f"linked study items have no {line} {market} column"
    keep = req["decision_type"] == "keep_strength"
    r = max(rows, key=lambda x: x["z"]) if keep else min(rows, key=lambda x: x["z"])
    val = min(1.0, max(0.0, (r["z"] if keep else -r["z"]) / 2))
    return val, (f"{len(rows)} study item(s) for {r['vehicle_model_id']} {market}, "
                 f"{'strongest' if keep else 'weakest'} z = {r['z']:+.2f} ('{r['item']}')"
                 + (" — must-not-lose strength" if keep else ""))


def _rung(spec: dict | None, line: str, market: str) -> dict | None:
    return next((r for r in _loads(spec["ladder_json"], []) if r["line"] == line and r["market"] == market), None) if spec else None


def competitive_gap(ctx: dict, req: dict, spec: dict | None, line: str, market: str) -> tuple[float, str, str, int]:
    """(value, explanation, method numeric | fallback | none, competitor evidence count)."""
    metric = _loads(spec["metric_json"], {}) if spec else {}
    rung = _rung(spec, line, market) or {}
    b, t = rung.get("baseline") or {}, rung.get("threshold") or {}
    comp = [e for e in theme_edges(ctx, req) if e[0] == "research" and e[2] == "competes_with" and _src_in_market(ctx, int(e[1]), market)]
    comp = list({e[1]: e for e in comp}.values())
    d = metric.get("direction")
    if isinstance(b.get("value"), (int, float)) and isinstance(t.get("value"), (int, float)) and b["value"] and d in ("higher", "lower") \
            and t.get("basis") in ("cited", "projected"):
        gap = (t["value"] - b["value"]) / abs(b["value"]) if d == "higher" else (b["value"] - t["value"]) / abs(b["value"])
        val = min(1.0, max(0.0, gap / GAP_FULL))
        unit = metric.get("unit") or ""
        return val, (f"rival threshold {t['value']:g} {unit} vs BMW baseline {b['value']:g} {unit} "
                     + (f"({gap:+.0%} behind)" if gap > 0 else "(BMW at or ahead of parity)")), "numeric", len(comp)
    w = sum(S.TIER_W.get((ctx["src"].get(int(e[1])) or {}).get("trust_tier"), 0.5) for e in comp)
    if comp:
        return min(1.0, w / 4), (f"fallback (no cited BMW-vs-rival number on the ladder): {len(comp)} competitor source(s) "
                                 f"on the area's themes for {market}, tier-weighted {w:.1f}"), "fallback", len(comp)
    return 0.0, (f"fallback (no cited BMW-vs-rival number on the ladder): no competitor evidence for {market} — "
                 f"counts 0, not renormalised"), "none", 0


def market_weight(ctx: dict, line: str, market: str) -> tuple[float, str, bool]:
    key = f"{line}:{market}"
    w = ctx["market"]["bmw_weight"]
    share, mx = w.get(key, 0.0), max(w.values(), default=0) or 1
    tr = ctx["market"]["public_trend"].get(key)
    conflict = any(c["key"] == key for c in ctx["market"]["conflicts"])
    tv = min(1.0, max(0.0, 0.5 + tr["yoy"] / 40)) if tr else 0.5
    expl = (f"{share:.1%} of BMW volume (stylized, Q-015, relative only)"
            + (f"; public trend {tr['yoy']:+.0f}% {tr['period']} ({tr['region']}, {tr['tier']}, src {tr['source_id']})" if tr
               else "; no cited public trend (neutral)")
            + ("; BMW file conflicts with public figures — flagged, not corrected" if conflict else ""))
    return 0.75 * share / mx + 0.25 * tv, expl, conflict


def future_relevance(ctx: dict, req: dict, market: str, n_comp: int) -> tuple[float, str]:
    h = 0.5 if req["horizon"] == "at_successor_launch" else 0.2
    trends = {i for i in _loads(req["trend_ids_json"], [])}
    trends |= {f"research:{e[1]}" for e in theme_edges(ctx, req)
               if e[0] == "research" and e[2] == "trend_for" and _src_in_market(ctx, int(e[1]), market)}
    t = min(0.3, 0.1 * len(trends))
    drift = 0.2 if req["kano"] in ("performance", "delighter") and (n_comp or trends) else 0.0
    return min(1.0, h + t + drift), (f"horizon {req['horizon']}" + (f" ({req['horizon_year']})" if req["horizon_year"] else "")
                                     + f", {len(trends)} dated trend source(s)"
                                     + (f", Kano {req['kano']} drifting toward expected (rivals/trends)" if drift else f", Kano {req['kano']}"))


def portfolio_leverage(n_targets: int, credit: float, credit_note: str) -> tuple[float, str]:
    spread = min(0.5, (n_targets - 1) / 6)
    return min(1.0, spread + credit), f"{n_targets} line × market target(s)" + (f"; enabler credit +{credit:.2f} ({credit_note})" if credit else "")


def effort(req: dict, rung: str) -> tuple[str, str]:
    step = STEPS.index(EFFORT_OF_TYPE.get(req["decision_type"], "M"))
    res = {r for a in _loads(req["aspects_json"], []) for r in ASPECT_RESOURCES.get(a, [])}
    why = [f"{req['decision_type']}"]
    if len(res) >= 3:
        step += 1
        why.append(f"draws on {len(res)} resources ({', '.join(sorted(res))})")
    if rung == "baseline":
        step = 0
        why.append("rung baseline = keep today's level")
    elif RUNG_SHIFT.get(rung):
        step += RUNG_SHIFT[rung]
        why.append(f"rung {rung} {RUNG_SHIFT[rung]:+d} step")
    e = STEPS[max(0, min(2, step))]
    return e, ", ".join(why)


def confidence(rung_row: dict | None, chosen: str, n_own: int, has_study: bool, own_flag: bool) -> dict:
    levels = {k: (rung_row or {}).get(k) for k in ("baseline", "threshold", "target", "stretch")}
    levels = {k: v for k, v in levels.items() if v}
    mix: dict[str, int] = defaultdict(int)
    for v in levels.values():
        mix[v.get("basis") or "gap"] += 1
    mean = sum(BASIS_W.get(v.get("basis"), 0.3) for v in levels.values()) / len(levels) if levels else 0.3
    ch = BASIS_W.get((levels.get(chosen) or {}).get("basis"), 0.3)
    basis = round(0.5 * ch + 0.5 * mean, 3)
    if n_own >= 20 and (has_study or basis >= 0.7):
        lvl = "E1"
    elif n_own >= 10 or (n_own >= OWN_COMMENTS and (has_study or basis >= 0.6)) or (has_study and basis >= 0.7):
        lvl = "E2"
    elif n_own >= OWN_COMMENTS or has_study or basis >= 0.5 or own_flag:
        lvl = "E3"
    else:
        lvl = "E4"
    return {"level": lvl, "mult": S.CONFIDENCE[lvl], "basis_mix": dict(mix), "basis_score": basis, "comments": n_own,
            "study": has_study}


def score_target(ctx: dict, req: dict, line: str, market: str, weights: dict, credit: float = 0.0, credit_note: str = "",
                 rung_override: str | None = None, bands: dict | None = None) -> dict:
    spec = ctx["specs"].get(req["key"])
    rung_row = _rung(spec, line, market)
    choice = ctx["choices"].get((req["key"], line, market))
    recommended = (rung_row or {}).get("recommended") or "target"
    chosen = rung_override or (choice["level"] if choice else recommended)
    tgts = targets_of(req, spec)
    own_flag = next((bool(t.get("own_evidence")) for t in _loads(req["targets_json"], []) if (t["line"], t["market"]) == (line, market)), False)

    factors: dict[str, tuple] = {}
    v, e, observed, n_own = customer_voice(ctx, req, line, market)
    factors["customer_voice"] = (v, e)
    factors["satisfaction_gap"] = satisfaction_gap(ctx, req, line, market)
    cv, ce, cmethod, n_comp = competitive_gap(ctx, req, spec, line, market)
    factors["competitive_gap"] = (cv, ce)
    mv, me, mconflict = market_weight(ctx, line, market)
    factors["market_weight"] = (mv, me)
    factors["portfolio_leverage"] = portfolio_leverage(len(tgts), credit, credit_note)
    factors["future_relevance"] = future_relevance(ctx, req, market, n_comp)

    base, wsum = S.renormalised(factors, weights)
    conf = confidence(rung_row, chosen, n_own, factors["satisfaction_gap"][0] is not None, own_flag)
    gates = {k: (ctx["fit"].get((req["key"], line, market)) or {}).get(k) for k in ("brand", "segment", "market", "feasibility")}
    mres = (gates["market"] or {}).get("result")
    mfit = S.MARKET_FIT_MOD.get(mres, 0.0)
    eff, eff_why = effort(req, chosen)
    effm = S.EFFORT_MOD[eff]
    score = max(0.0, min(100.0, 100 * base * conf["mult"] + mfit + effm))
    b = {
        "version": SCHEME, "checkpoint": ctx["cp"], "score": round(score, 1), "base": round(100 * base, 1),
        "evidence_level": conf["level"], "confidence": conf["mult"], "confidence_detail": conf,
        "modifiers": {"market_fit": mfit, "effort": effm},
        "modifier_why": {"market_fit": f"market gate {mres}" if mres else "market gate not run yet",
                         "effort": f"effort {eff}: {eff_why}"},
        "factors": {k: {"label": LABELS[k], "dimension": DIMENSION[k], "value": None if fv is None else round(fv, 3),
                        "weight": weights[k], "available": fv is not None, "explanation": fe,
                        "points": None if fv is None else round(100 * weights[k] * fv / wsum * conf["mult"], 1)}
                    for k, (fv, fe) in factors.items()},
        "gaps": [LABELS[k] for k, (fv, _) in factors.items() if fv is None],
        "gates": {k: (g or {}).get("result") for k, g in gates.items()},
        "gate_detail": gates, "voice_observed": observed, "comments": n_own,
        "competitive_method": cmethod, "market_conflict": mconflict, "effort": eff,
        "rung": {"chosen": chosen, "recommended": recommended, "by": "pm" if choice and not rung_override else
                 "what_if" if rung_override else "ai", "choice": {k: choice[k] for k in ("level", "rationale", "actor", "created_at")} if choice else None},
    }
    b["factors"]["competitive_gap"]["method"] = cmethod
    b["bands"] = dict(bands or DEFAULT_BANDS)
    b["priority"] = band_for(b["score"], bands)
    return b


# ------------------------------------------------------------------------------------------------ requirement + portfolio rules
def enabler_credit(ctx: dict, base: dict[tuple, float]) -> dict[tuple, tuple[float, str]]:
    """(key, line, market) → (credit, note): Σ strength/3 × enabled requirement's base/100 (same line × market, else its
    best target), cap 0.5 — over non-removed `enables` links with strength ≥ 2."""
    best: dict[str, float] = defaultdict(float)
    for (k, _, _), v in base.items():
        best[k] = max(best[k], v)
    out: dict[tuple, list] = defaultdict(list)
    for l in ctx["links"]:
        if l["relation"] != "enables" or (l.get("strength") or 0) < LINK_MIN:
            continue
        pairs = {"a_to_b": [(l["a"], l["b"])], "b_to_a": [(l["b"], l["a"])]}.get(l["direction"], [(l["a"], l["b"]), (l["b"], l["a"])])
        for src, dst in pairs:
            for (k, line, m) in base:
                if k == src:
                    nb = base.get((dst, line, m), best.get(dst, 0.0))
                    out[(k, line, m)].append((l["strength"] / 3 * nb / 100, dst, l["via"]))
    return {t: (min(ENABLER_CAP, sum(c for c, _, _ in xs)), ", ".join(f"enables {d} via {v}" for _, d, v in xs)) for t, xs in out.items()}


def requirement_rules(req: dict, items: list[tuple[str, str, dict]], bands: dict | None = None) -> None:
    """D-038 on one requirement's targets: no-comment cap, then one band for Expected (Kano basic) needs."""
    S.cap_unobserved([b for _, _, b in items], own=("satisfaction_gap", "competitive_gap"))
    for _, _, b in items:
        b["priority"] = band_for(b["score"], bands)
    S.align_basic(req["kano"], [(f"{line} × {m}", b) for line, m, b in items])


def apply_links(ctx: dict, results: dict[tuple, dict]) -> tuple[list[dict], dict]:
    """Bundles (one band per line × market = strongest member's) and choose-jointly flags. Returns (bundles, bundle_of)."""
    from api.routers.definition import bundles as components

    keys = {k for k, _, _ in results}
    comps = components([l for l in ctx["links"] if l["relation"] in ("synergy", "enables")], keys)
    out, bundle_of = [], {}
    for c in comps:
        band_by = {}
        lms = sorted({(line, m) for k, line, m in results if k in c["keys"]})
        for line, m in lms:
            members = [(k, results[(k, line, m)]) for k in c["keys"] if (k, line, m) in results]
            top_k, top = min(members, key=lambda kb: (BAND_RANK[kb[1]["priority"]], -kb[1]["score"]))
            band_by[f"{line}:{m}"] = top["priority"]
            for k, b in members:
                b["bundle_id"] = c["id"]
                if len(members) > 1 and b["priority"] != top["priority"]:
                    b["bundle_note"] = (f"bundled with {top_k} ({c['reason']}): shares its band {top['priority']} in "
                                        f"{line} {m}; alone it would be {b['priority']}")
                    b["own_priority"] = b["priority"]
                    b["priority"] = top["priority"]
        for k in c["keys"]:
            bundle_of[k] = c["id"]
        out.append({"id": c["id"], "keys": c["keys"], "relations": c["reason"], "conflict": c["conflict"], "band_by_target": band_by})
    for l in ctx["links"]:
        if l["relation"] not in ("conflicts", "competes_for") or (l.get("strength") or 0) < LINK_MIN:
            continue
        for (k, line, m), b in results.items():
            if k != l["a"]:
                continue
            o = results.get((l["b"], line, m))
            if o and b["priority"] == "Must" and o["priority"] == "Must":
                b.setdefault("joint", []).append({"with": l["b"], "relation": l["relation"], "via": l["via"]})
                o.setdefault("joint", []).append({"with": l["a"], "relation": l["relation"], "via": l["via"]})
    return out, bundle_of


def flags_of(b: dict) -> list[str]:
    """Flag strings as page 4 parses them: `kind` or `kind|arg|arg` (choose_jointly|<via>|<partner>, bundle_band|<band>)."""
    f = []
    if b["gates"].get("brand") == "fail":
        f.append("brand_blocked")   # D-008: blocks a PM approve unless overridden with a rationale
    for k in ("brand", "segment"):
        if b["gates"].get(k) in ("fail", "warn"):
            f.append(f"{k}_{b['gates'][k]}")
    if b["gates"].get("brand") is None:
        f.append("gate_pending")
    if not b["voice_observed"]:
        f.append("borrowed_voice")
    if "no_comment_cap" in b["modifiers"]:
        f.append("no_comment_cap")
    if b.get("priority_note"):
        f.append("basic_aligned")
    if b.get("bundle_note"):
        f.append(f"bundle_band|{b['priority']}")
    if b["market_conflict"]:
        f.append("volume_conflict")
    if b["competitive_method"] != "numeric":
        f.append(f"competitive_{b['competitive_method']}")
    f += [f"choose_jointly|{j['via']}|{j['with']}" for j in b.get("joint", [])]
    return f


def rationale(b: dict, req: dict, line: str, market: str) -> str:
    """score-v3's templated rationale + the prio-v1 parts (rung, effort, gates, bundle, joint choice)."""
    parts = [S.rationale(b, line, market)]
    r = b["rung"]
    parts.append(f"Rung {r['chosen']} ({'PM choice' if r['by'] == 'pm' else 'what-if' if r['by'] == 'what_if' else 'AI recommendation'})"
                 f" → effort {b['effort']} ({b['modifiers']['effort']:+.0f}).")
    if b["modifiers"]["market_fit"]:
        parts.append(f"Market gate {b['gates']['market']} ({b['modifiers']['market_fit']:+.0f}).")
    if b["gates"].get("segment") == "fail":
        parts.append("Segment-fit FAIL — check the line's positioning before approving.")
    if b.get("bundle_note"):
        parts.append(b["bundle_note"][0].upper() + b["bundle_note"][1:] + ".")
    for j in b.get("joint", []):
        parts.append(f"Choose ladder levels jointly with {j['with']} ({j['relation']} via {j['via']}) — both are Must here.")
    if b["market_conflict"]:
        parts.append("BMW's volume file conflicts with public figures for this market (flagged, not corrected).")
    return " ".join(parts)


def score_all(ctx: dict, weights: dict, override: tuple | None = None, bands: dict | None = None) -> tuple[dict[tuple, dict], list[dict], dict]:
    """Score every target: pass 1 (no enabler credit) → enabler credit → pass 2 → D-038 rules → links → rationale.
    `override` = (key, line, market, rung) recomputes that target for another rung (what-if); `bands` = band thresholds
    of the weights version (default Must ≥ 60 · Should ≥ 45). The weights preview calls this with proposed weights."""
    reqs = {r["key"]: r for r in ctx["reqs"]}
    tl = {k: targets_of(r, ctx["specs"].get(k)) for k, r in reqs.items()}

    def one(k, line, m, credit=0.0, note=""):
        ov = override[3] if override and override[:3] == (k, line, m) else None
        return score_target(ctx, reqs[k], line, m, weights, credit, note, ov, bands)

    first = {(k, line, m): one(k, line, m) for k, ts in tl.items() for line, m in ts}
    credit = enabler_credit(ctx, {t: b["base"] for t, b in first.items()})
    results = {t: one(*t, *credit[t]) if t in credit else b for t, b in first.items()}
    for k, ts in tl.items():
        requirement_rules(reqs[k], [(line, m, results[(k, line, m)]) for line, m in ts], bands)
    bundles, _ = apply_links(ctx, results)
    for (k, line, m), b in results.items():
        b["flags"] = flags_of(b)
        b["rationale"] = rationale(b, reqs[k], line, m)
    return results, bundles, tl


# ------------------------------------------------------------------------------------------------ run
def _prev_rows(conn, run_id: int, cp: str) -> dict[tuple, dict]:
    """Most recent earlier prio_score per target, from runs at checkpoints visible at `cp` (a cp1 re-score after cp2
    exists must not compare against JUL)."""
    vis = C.visible_ids(cp)
    out = {}
    for r in conn.execute(f"""SELECT s.* FROM prio_score s JOIN checkpoint_run c ON c.id = s.run_id WHERE s.run_id < ?
                              AND c.checkpoint_id IN ({','.join('?' * len(vis))}) ORDER BY s.run_id""", (run_id, *vis)):
        out[(r["req_key"], r["line"], r["market"])] = dict(r)
    return out


def cause_of(prev: dict | None, b: dict, spec_track: dict | None, weights_moved: bool = False) -> tuple[str, dict]:
    """Cause category of a band change + factor deltas (points). `weights_moved` = the weights version changed since the
    previous run at this checkpoint AND that change alone moves this target's band (`weights_changed`)."""
    ob = _loads(prev["breakdown_json"], {}) if prev else {}
    deltas = {k: round((f.get("points") or 0) - ((ob.get("factors") or {}).get(k, {}).get("points") or 0), 1) for k, f in b["factors"].items()}
    if prev and (prev["rung"] or "") != b["rung"]["chosen"] and b["rung"]["by"] == "pm":
        return "pm_rung", deltas
    if weights_moved:
        return "weights_changed", deltas
    if spec_track and (spec_track.get("state") in ("strengthened", "weakened") or spec_track.get("moved")):
        return "new_fact", deltas
    if prev and ((prev["bundle_id"] or None) != b.get("bundle_id") or
                 sorted(x for x in _loads(prev["flags_json"], []) if x.startswith("choose_jointly")) !=
                 sorted(x for x in b["flags"] if x.startswith("choose_jointly"))):
        return "link_changed", deltas
    top = max(deltas, key=lambda k: abs(deltas[k])) if deltas else None
    return {"market_weight": "market_trend", "competitive_gap": "new_fact", "portfolio_leverage": "link_changed"}.get(top, "area_strengthened"), deltas


RENAG_POINTS = 5.0   # a proposal the PM rejected comes back (same bands) only once the score has moved this much


def _rejected(conn, cp: str) -> dict[tuple, dict]:
    """Latest rejected proposal per target (at a checkpoint visible at `cp`) newer than the target's latest PM decision."""
    vis = C.visible_ids(cp)
    last_dec = {t: d["created_at"] for t, d in decisions_at(conn, cp).items()}
    out = {}
    for r in conn.execute(f"""SELECT p.* FROM prio_proposal p JOIN checkpoint_run c ON c.id = p.run_id WHERE p.status = 'rejected'
                              AND c.checkpoint_id IN ({','.join('?' * len(vis))}) ORDER BY p.id""", vis):
        t = (r["req_key"], r["line"], r["market"])
        if (r["decided_at"] or "") >= (last_dec.get(t) or ""):
            out[t] = dict(r)
    return out


def _previous_weights_version(conn, cp: str, run_id: int) -> int | None:
    """Weights version the previous completed prioritize run at this checkpoint used."""
    r = conn.execute("SELECT stats_json FROM checkpoint_run WHERE checkpoint_id = ? AND stage = 'prioritize' AND id < ? "
                     "AND finished_at IS NOT NULL ORDER BY id DESC LIMIT 1", (cp, run_id)).fetchone()
    return (_loads(r["stats_json"], {}) or {}).get("weights_version") if r else None


def run(conn, cp: str, actor: str = "system", trigger: str | None = None) -> dict:
    """One prioritize run at `cp` (a new checkpoint_run; earlier runs stay as lineage). `trigger` is recorded in the
    stats (e.g. `auto:decision`)."""
    ctx = load(conn, cp)
    conn.execute("BEGIN IMMEDIATE")
    try:
        wid, weights, bands = current_config(conn)
        run_id = C.start_run(conn, cp, "prioritize", actor)
        results, bundles, tl = score_all(ctx, weights, bands=bands)
        prev_wid = _previous_weights_version(conn, cp, run_id)
        rejected = _rejected(conn, cp)
        old_res: dict[tuple, dict] = {}
        ow = conn.execute("SELECT weights_json FROM weights_version WHERE id = ?", (prev_wid,)).fetchone() \
            if prev_wid is not None and prev_wid != wid else None
        if ow:   # weights changed since the last run here: same inputs, old weights → which bands did the weights alone move?
            ocfg = json.loads(ow["weights_json"])
            old_res, _, _ = score_all(ctx, {**DEFAULT_WEIGHTS, **(ocfg.get("weights") or {})}, bands=_bands_of(ocfg))
        reqs = {r["key"]: r for r in ctx["reqs"]}
        prev = _prev_rows(conn, run_id, cp)
        decided = decisions_at(conn, cp)
        parent = conn.execute("SELECT parent_run_id FROM checkpoint_run WHERE id = ?", (run_id,)).fetchone()[0]
        parent_rows = {(r["req_key"], r["line"], r["market"]): dict(r) for r in
                       conn.execute("SELECT * FROM prio_score WHERE run_id = ?", (parent,))} if parent else {}
        parent_band = {t: r["band"] for t, r in parent_rows.items()}
        by_lm: dict[tuple, list] = defaultdict(list)
        for (k, line, m), b in results.items():
            by_lm[(line, m)].append((k, b))
        tracks, n_props, rows = {}, 0, []
        for (line, m), items in by_lm.items():
            items.sort(key=lambda kb: (-kb[1]["score"], BAND_RANK[kb[1]["priority"]]))   # rank = score order; band shown beside it
            for rank, (k, b) in enumerate(items, 1):
                t = (k, line, m)
                p = prev.get(t)
                mods = [{"key": key, "points": pts, "why": b["modifier_why"].get(key) or b.get("cap_note")}
                        for key, pts in b["modifiers"].items() if pts]
                conn.execute(
                    """INSERT INTO prio_score (run_id, req_key, req_version, line, market, score, base, band, rank, confidence_json,
                       breakdown_json, modifiers_json, flags_json, bundle_id, rung, rationale) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, k, reqs[k]["version"], line, m, b["score"], b["base"], b["priority"], rank,
                     json.dumps(b["confidence_detail"]), json.dumps(b, ensure_ascii=False, default=str), json.dumps(mods, ensure_ascii=False),
                     json.dumps(b["flags"]), b.get("bundle_id"), b["rung"]["chosen"], b["rationale"]))
                tracks[f"prio:{k}|{line}|{m}"] = (b["score"], {"band": b["priority"], "rank": rank})
                delta = S.explain_delta(p, b) if p else "first scoring"
                if not p or abs(p["score"] - b["score"]) >= 0.05 or p["band"] != b["priority"]:
                    audit(conn, actor_type="ai", actor_id="structure.prioritize", action="rescore", entity_type="prio_target",
                          entity_id=f"{k}|{line}|{m}", field="score", old={"score": p["score"], "band": p["band"]} if p else None,
                          new={"score": b["score"], "band": b["priority"]}, rationale=delta, model=SCHEME, run_id=run_id)
                # an open proposal at THIS checkpoint is stale once this run has scored the target again (as score-v3,
                # D-013); other checkpoints' proposals are theirs to supersede
                conn.execute("UPDATE prio_proposal SET status = 'superseded' WHERE req_key = ? AND line = ? AND market = ? "
                             "AND status = 'open' AND run_id IN (SELECT id FROM checkpoint_run WHERE checkpoint_id = ?)", (*t, cp))
                ref = (decided.get(t) or {}).get("priority") or parent_band.get(t)
                rj = rejected.get(t)
                if ref and ref != b["priority"] and rj and rj["old_band"] == ref and rj["proposed_band"] == b["priority"] \
                        and abs(((_loads(rj["factor_delta_json"], {}) or {}).get("score") or b["score"]) - b["score"]) < RENAG_POINTS:
                    continue   # the PM already rejected exactly this move; don't re-propose until the score really moves
                if ref and ref != b["priority"]:
                    wmoved = t in old_res and old_res[t]["priority"] != b["priority"]
                    # explain the move against the previous checkpoint's score (what the PM decided on), not this
                    # checkpoint's own earlier re-score, which would show "+0.0"
                    base = parent_rows.get(t) or p
                    cause, deltas = cause_of(base, b, ctx["spec_tracks"].get(k), wmoved)
                    conn.execute("""INSERT INTO prio_proposal (run_id, req_key, line, market, old_band, proposed_band, cause, factor_delta_json)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                 (run_id, k, line, m, ref, b["priority"], cause,
                                  json.dumps({"points": deltas, "explain": S.explain_delta(base, b) if base else delta,
                                              "against": "pm" if t in decided else "parent",
                                              "score": b["score"], "prev_score": base["score"] if base else None}, ensure_ascii=False)))
                    n_props += 1
        for bd in bundles:
            conn.execute("INSERT INTO prio_bundle (run_id, bundle_id, keys_json, relations_json, band_by_target_json) VALUES (?, ?, ?, ?, ?)",
                         (run_id, bd["id"], json.dumps(bd["keys"]), json.dumps({"reason": bd["relations"], "conflict": bd["conflict"]}),
                          json.dumps(bd["band_by_target"])))
        counts = C.write_tracks(conn, run_id, tracks, prefix="prio:")
        stats = summary(results)
        stats |= {"requirements": len(tl), "targets": len(results), "bundles": len(bundles), "proposals": n_props, "tracks": counts,
                  "weights_version": wid, "bands": bands, "scheme": SCHEME, "trigger": trigger,
                  "upstream": {s: (r["id"] if r else None) for s, r in ctx["runs"].items()}}
        log(conn, "prioritize", "scored", {k: stats[k] for k in ("targets", "by_band", "bundles", "proposals", "flags")}, run_id, SCHEME)
        C.finish_run(conn, run_id, stats)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"run_id": run_id, **stats}


def preview(conn, cp: str, weights: dict, bands: dict, line: str | None = None, market: str | None = None) -> dict:
    """Score every target at `cp` with PROPOSED weights + bands, in memory (same `score_all` path as a run; nothing is
    written). Compares with the stored latest run (`prev_band`) and the PM-confirmed bands."""
    weights, bands = validate(weights, bands)
    ctx = load(conn, cp)
    results, _, _ = score_all(ctx, weights, bands=bands)
    run = C.latest_run(conn, cp, "prioritize")
    stored = {(r["req_key"], r["line"], r["market"]): dict(r) for r in
              conn.execute("SELECT req_key, line, market, score, band FROM prio_score WHERE run_id = ?", (run["id"],))} if run else {}
    decided = decisions_at(conn, cp)
    targets, changes, moves, affected = [], [], defaultdict(int), []
    by_band: dict[str, int] = defaultdict(int)
    for (k, ln, m), b in sorted(results.items()):
        if (line and ln != line) or (market and m != market):
            continue
        st, dc = stored.get((k, ln, m)), decided.get((k, ln, m))
        conf = dc["priority"] if dc else None
        row = {"key": k, "line": ln, "market": m, "score": b["score"], "band": b["priority"],
               "prev_score": st["score"] if st else None, "prev_band": st["band"] if st else None, "confirmed": conf}
        targets.append(row)
        by_band[b["priority"]] += 1
        if st and st["band"] != b["priority"]:
            changes.append(row)
            moves[f"{st['band']}→{b['priority']}"] += 1
        # a PM decision gets a proposal when the new band differs from it (and it didn't already differ before)
        if conf and conf != b["priority"] and (not st or st["band"] != b["priority"]):
            affected.append(row)
    return {"checkpoint": cp, "weights": weights, "bands": bands, "run_id": run["id"] if run else None, "targets": targets,
            "summary": {"targets": len(targets), "by_band": dict(by_band), "changes": len(changes), "moves": dict(moves),
                        "decisions_affected": len(affected)},
            "changes": changes, "decisions_affected": affected}


def summary(results: dict[tuple, dict]) -> dict:
    by_band: dict[str, int] = defaultdict(int)
    by_market: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    flags: dict[str, int] = defaultdict(int)
    comp: dict[str, int] = defaultdict(int)
    for (k, line, m), b in results.items():
        by_band[b["priority"]] += 1
        by_market[f"{line}:{m}"][b["priority"]] += 1
        comp[b["competitive_method"]] += 1
        for f in b.get("flags", []):
            flags[f.split("|")[0]] += 1
    return {"by_band": dict(by_band), "by_market": {k: dict(v) for k, v in sorted(by_market.items())}, "flags": dict(flags),
            "competitive_method": dict(comp)}


def what_if(conn, cp: str, key: str, line: str, market: str, level: str) -> dict:
    """Recompute one target for another rung without storing; list linked partners exposed (never re-scored)."""
    ctx = load(conn, cp)
    _, weights, bands = stored_config(conn)
    base_res, _, _ = score_all(ctx, weights, bands=bands)
    t = (key, line, market)
    if t not in base_res:
        raise KeyError(f"{key} has no target {line} {market} at {cp}")
    res, _, _ = score_all(ctx, weights, override=(key, line, market, level), bands=bands)
    before, after = base_res[t], res[t]
    titles = {r["key"]: r["title"] for r in ctx["reqs"]}
    exposures = []
    for l in ctx["links"]:   # linked partners exposed via the shared resource: a warning, never a re-score
        if key in (l["a"], l["b"]):
            other = l["b"] if l["a"] == key else l["a"]
            ob = (base_res.get((other, line, market)) or {}).get("priority")
            exposures.append({"key": other, "title": titles.get(other), "via": l["via"] or "—", "relation": l["relation"],
                              "strength": l["strength"], "band": ob,
                              "note": f"{l['relation']} via {l['via']} (strength {l['strength']})" + (f", {ob} here" if ob else "")})
    per_via: dict[str, int] = defaultdict(int)
    for e in exposures:
        per_via[e["via"]] += 1
    return {"key": key, "line": line, "market": market, "level": level,
            "score": after["score"], "band": after["priority"], "base": after["base"],
            "delta": round(after["score"] - before["score"], 1),
            "modifiers": [{"key": k, "points": v, "why": after["modifier_why"].get(k) or after.get("cap_note")}
                          for k, v in after["modifiers"].items() if v],
            "confidence": {"level": after["confidence_detail"]["level"], "mult": after["confidence"],
                           "basis_mix": after["confidence_detail"]["basis_mix"]},
            "effort": after["effort"], "rationale": after["rationale"],
            "before": {"score": before["score"], "band": before["priority"], "rung": before["rung"]["chosen"], "effort": before["effort"]},
            "exposures": exposures,
            "exposure_summary": [f"+{n} exposure via {v}" for v, n in sorted(per_via.items(), key=lambda kv: -kv[1])]}
