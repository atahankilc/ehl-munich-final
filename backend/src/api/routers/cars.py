"""Cars: the portfolio per vehicle — requirements on today's car by zone, market comparison, market profile,
competitors, today's equipment (no prices), plants and the local 3D model. Read-only."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException

from api import labels as L
from api.deps import db
from api.queries import (current_wave, effective, evidence_gaps, loads, requirement_summaries, target_rows,
                         verbatim_base)
from bmw_req.car_zones import CONFIGURATOR_URL, MODELS_GLTF, ZONES, model_url, option_zone
from bmw_req.portfolio import LINES, SUCCESSOR_LAUNCH, TARGETS, line_of

router = APIRouter(prefix="/api", tags=["cars"])


def _model(v: str) -> dict:
    m = MODELS_GLTF.get(v) or {}
    return {"url": model_url(v), "shared_with": m.get("shared_with"), "orientation": m.get("orientation"),
            "stand_in": m.get("stand_in"),
            "attribution": {k: m.get(k) for k in ("name", "author", "license", "source_url")} if m else None}


@router.get("/cars")
def cars() -> list[dict]:
    with db() as conn:
        vm = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM vehicle_model WHERE id IN (%s)" % ",".join(
            "?" * len(TARGETS)), tuple(TARGETS))}
        rows = [r for r in target_rows(conn) if r["status"] != "rejected"]
    by_t = defaultdict(list)
    for r in rows:
        by_t[(r["vehicle_model_id"], r["market_code"])].append(r)
    out = []
    for v, markets in TARGETS.items():
        row = vm.get(v, {})
        out.append({
            "vehicle": v, "car": L.car(v), "line": line_of(v), "body": row.get("body"), "segment": row.get("segment"),
            "line_segment": LINES[line_of(v)]["segment"], "platform": row.get("platform_id"),
            "generation": row.get("generation"), "powertrains": loads(row.get("powertrains_json"), []) or [],
            "markets": [{"market": m, "label": L.mkt(m), "n": len(by_t[(v, m)]),
                         "must": sum(effective(r["pm_priority"], r["proposed_priority"]) == "Must" for r in by_t[(v, m)])}
                        for m in markets],
            "default_market": L.DEFAULT_MARKET.get(v, markets[0]),
            "model_available": model_url(v) is not None,
        })
    return out


def _equipment(conn, v: str) -> dict[str, list]:
    src = L.OPTION_SOURCE.get(v, v)
    options: dict[str, list] = {}
    for o in conn.execute("""SELECT json_extract(meta_json, '$.name_en') AS name, json_extract(meta_json, '$.category') AS category,
                                    json_extract(meta_json, '$.availability') AS avail
                             FROM source_item WHERE kind = 'option_list' AND vehicle_model_id = ? ORDER BY id""", (src,)):
        if not o["name"] or o["category"] == "Variants & Packages":
            continue
        lst = options.setdefault(option_zone(o["name"], o["category"]), [])
        if len(lst) < L.OPTIONS_PER_ZONE and all(x["name"] != o["name"] for x in lst):
            lst.append({"name": o["name"], "availability": L.AVAILABILITY.get(o["avail"], o["avail"] or "")})
    return options


@router.get("/cars/{vehicle}")
def car_detail(vehicle: str, market: str | None = None) -> dict:
    if vehicle not in TARGETS:
        raise HTTPException(404, f"Unknown vehicle {vehicle}; one of {', '.join(TARGETS)}")
    markets = TARGETS[vehicle]
    m = market or L.DEFAULT_MARKET.get(vehicle, markets[0])
    if m not in markets:
        raise HTTPException(404, f"{vehicle} is not a target in market {m}; markets: {', '.join(markets)}")
    with db() as conn:
        w = current_wave(conn)
        summaries = [s for s in requirement_summaries(conn) if s["status"] != "rejected"]
        rows = [r for r in target_rows(conn) if r["status"] != "rejected" and r["vehicle_model_id"] == vehicle]
        meta = {r["id"]: (r["description"], loads(r["derivation_json"], {}) or {}) for r in
                conn.execute("SELECT id, description, derivation_json FROM requirement")}
        base = verbatim_base(conn, w)
        gaps = evidence_gaps(conn, w, base)
        mrow = conn.execute("""SELECT code, name, climate, usage_patterns, cultural_expectations, infrastructure,
                                      powertrain_mix FROM market WHERE code = ?""", (m,)).fetchone()
        comps = []
        for r in conn.execute("""SELECT v.id, v.line, v.brand_id, b.name AS brand_name, v.segment, v.profile_json
                                 FROM vehicle_model v LEFT JOIN brand b ON b.id = v.brand_id
                                 WHERE v.is_bmw_group = 0 ORDER BY v.id"""):
            prof = loads(r["profile_json"], {}) or {}
            if vehicle in (prof.get("competes_with") or []):
                comps.append({"id": r["id"], "name": r["line"] or r["id"], "brand": r["brand_name"] or r["brand_id"],
                              "segment": r["segment"], "strengths": prof.get("strengths"),
                              "markets": prof.get("markets") or []})
        production = [{"plant": r["plant_name"] or r["plant_id"], "plant_id": r["plant_id"], "country": r["country"],
                       "market_variant": r["market_variant"], "markets_served": loads(r["markets_served_json"], []) or [],
                       "nk_ready_from": r["nk_ready_from"]}
                      for r in conn.execute("""SELECT p.plant_id, p.market_variant, p.markets_served_json, pl.name plant_name,
                                                      pl.country, pl.nk_ready_from
                                               FROM production p LEFT JOIN plant pl ON pl.id = p.plant_id
                                               WHERE p.vehicle_model_id = ?""", (vehicle,))]
        equipment = _equipment(conn, vehicle)

    by_m = defaultdict(list)
    for r in rows:
        by_m[r["market_code"]].append(r)
    market_cards = []
    for mk in markets:
        pc = {"Must": 0, "Should": 0, "Could": 0}
        for r in by_m[mk]:
            p = effective(r["pm_priority"], r["proposed_priority"])
            if p in pc:
                pc[p] += 1
        market_cards.append({"market": mk, "label": L.mkt(mk), "n": len(by_m[mk]), "must": pc["Must"],
                             "should": pc["Should"], "could": pc["Could"],
                             "voice_base": base.get((vehicle, mk), {}).get("in_scope", 0),
                             "gaps": gaps.get((vehicle, mk), [])})

    reqs, comparison = [], []
    for s in summaries:
        cells = {t["target"]["market"]: t for t in s["targets"] if t["target"]["vehicle"] == vehicle}
        if not cells:
            continue
        desc, deriv = meta.get(s["id"], (None, {}))
        here = cells.get(m)
        if here is not None:
            reqs.append({
                "id": s["id"], "title": s["title"], "category": s["category"], "status": s["status"], "zone": s["zone"],
                "priority": here["priority"], "ai_only": here["ai_only"], "score": here["score"],
                "evidence_level": here["evidence_level"] or s["evidence_level"], "kano_class": s["kano_class"],
                "horizon": s["horizon"], "product_decision": deriv.get("product_decision"), "description": desc,
                "markets": [{"market": mk, "label": L.mkt(mk), "priority": c["priority"], "ai_only": c["ai_only"],
                             "score": c["score"], "current": mk == m}
                            for mk, c in sorted(cells.items(), key=lambda kv: -(kv[1]["score"] or 0))],
            })
        scores = [c["score"] for c in cells.values() if c["score"] is not None]
        prios = {c["priority"] for c in cells.values() if c["priority"]}
        comparison.append({
            "id": s["id"], "title": s["title"], "zone": s["zone"],
            "cells": {mk: ({"priority": cells[mk]["priority"], "score": cells[mk]["score"],
                            "ai_only": cells[mk]["ai_only"]} if mk in cells else None) for mk in markets},
            "spread": round(max(scores) - min(scores), 1) if len(scores) >= 2 else 0.0,
            "differs": len(cells) >= 2 and len(prios) > 1,
        })
    reqs.sort(key=lambda r: (-(r["score"] or 0), r["id"]))
    comparison.sort(key=lambda r: (not r["differs"], -r["spread"], r["id"]))
    note = L.EQUIPMENT_NOTE
    src = L.OPTION_SOURCE.get(vehicle, vehicle)
    if src != vehicle:
        note = f"No price list for the {L.car(vehicle)}: showing the {L.car(src)} list. " + note
    return {
        "vehicle": vehicle, "car": L.car(vehicle), "market": m, "markets": market_cards,
        "model": _model(vehicle), "zones": ZONES, "requirements": reqs, "comparison": comparison,
        "market_profile": dict(mrow) if mrow else None, "competitors": comps,
        "equipment": equipment, "equipment_note": note,
        "configurator_url": CONFIGURATOR_URL.get(vehicle),
        "production": production, "successor_launch": SUCCESSOR_LAUNCH.get(vehicle),
    }

