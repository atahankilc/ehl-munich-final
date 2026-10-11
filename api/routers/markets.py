"""Markets are different customers (D-011): per market its profile (cited), its car targets, the requirements that
rank differently here than in the same car's other markets, competitors, web signals and study highlights."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from api import labels as L
from api.deps import db, not_found
from api.queries import (PRIORITY_RANK, current_wave, effective, evidence_gaps, loads, target_obj,
                         target_rows, verbatim_base)
from bmw_req.portfolio import TARGETS

router = APIRouter(prefix="/api", tags=["markets"])


def _cars_in(code: str) -> list[str]:
    return [v for v, ms in TARGETS.items() if code in ms]


def _by_target(conn) -> tuple[dict, dict]:
    rows = [r for r in target_rows(conn) if r["status"] != "rejected"]
    by_t = defaultdict(list)
    for r in rows:
        by_t[(r["vehicle_model_id"], r["market_code"])].append(r)
    titles = {r[0]: r[1] for r in conn.execute("SELECT id, title FROM requirement")}
    return by_t, titles


@router.get("/markets")
def markets() -> list[dict]:
    with db() as conn:
        w = current_wave(conn)
        rows = conn.execute("SELECT code, name FROM market").fetchall()
        by_t, _ = _by_target(conn)
        base = verbatim_base(conn, w)
        gaps = evidence_gaps(conn, w, base)
    names = {r["code"]: r["name"] for r in rows}
    out = []
    for code in L.MARKETS:
        if code not in names and not _cars_in(code):
            continue
        cars = _cars_in(code)
        ts = [r for v in cars for r in by_t[(v, code)]]
        g = sorted({x for v in cars for x in gaps.get((v, code), [])})
        out.append({"code": code, "name": names.get(code, L.MARKET_NAMES.get(code, code)), "label": L.mkt(code),
                    "targets": [target_obj(v, code) for v in cars],
                    "n_requirements": len({r["requirement_id"] for r in ts}),
                    "must": sum(effective(r["pm_priority"], r["proposed_priority"]) == "Must" for r in ts),
                    "voice_base": sum(base.get((v, code), {}).get("in_scope", 0) for v in cars), "gaps": g})
    return out


def _r(x):
    return None if x is None else round(float(x), 1)


@router.get("/markets/{code}")
def market(code: str) -> dict:
    with db() as conn:
        m = conn.execute("SELECT * FROM market WHERE code = ?", (code,)).fetchone()
        if m is None:
            raise not_found(f"Unknown market {code}; one of {', '.join(L.MARKETS)}")
        w = current_wave(conn)
        W = w or 99
        cars = _cars_in(code)
        by_t, titles = _by_target(conn)
        base = verbatim_base(conn, w)
        gaps = evidence_gaps(conn, w, base)
        src_ids = [int(x) for x in (loads(m["profile_source_ids_json"], []) or []) if str(x).isdigit()]
        sources = []
        if src_ids:
            for s in conn.execute(f"""SELECT id, url, ref, trust_tier, meta_json FROM source_item
                                      WHERE id IN ({','.join('?' * len(src_ids))}) ORDER BY id""", src_ids):
                meta = loads(s["meta_json"], {}) or {}
                sources.append({"id": s["id"], "url": s["url"], "ref": s["ref"], "trust_tier": s["trust_tier"],
                                "title_or_ref": meta.get("title") or meta.get("publisher") or meta.get("origin_doc") or s["ref"]})
        comps = []
        for r in conn.execute("""SELECT v.id, v.line, v.brand_id, b.name brand_name, v.segment, v.profile_json
                                 FROM vehicle_model v LEFT JOIN brand b ON b.id = v.brand_id
                                 WHERE v.is_bmw_group = 0 ORDER BY v.id"""):
            prof = loads(r["profile_json"], {}) or {}
            if code in (prof.get("markets") or []) or set(prof.get("competes_with") or []) & set(cars):
                comps.append({"id": r["id"], "name": r["line"] or r["id"], "brand": r["brand_name"] or r["brand_id"],
                              "strengths": prof.get("strengths"), "segment": r["segment"],
                              "competes_with": prof.get("competes_with") or [], "markets": prof.get("markets") or []})
        n_src = dict(conn.execute("""SELECT fs.finding_id, COUNT(*) FROM finding_source fs JOIN finding f
                                     ON f.id = fs.finding_id WHERE f.market_code = ? GROUP BY 1""", (code,)).fetchall())
        web = []
        for f in conn.execute("""SELECT id, title, type, vehicle_model_id, metrics_json FROM finding
                                 WHERE source_kind = 'web' AND market_code = ? AND COALESCE(first_wave, 1) <= ?""", (code, W)):
            mt = loads(f["metrics_json"], {}) or {}
            tiers = sorted((mt.get("tiers") or {}).keys())
            web.append({"finding_id": f["id"], "title": f["title"], "type": f["type"], "vehicle": f["vehicle_model_id"],
                        "best_tier": tiers[0] if tiers else None, "publishers": mt.get("publishers") or [],
                        "newest_date": mt.get("newest_date"), "n_sources": n_src.get(f["id"], 0)})
        web.sort(key=lambda x: (x["n_sources"], x["newest_date"] or ""), reverse=True)
        study = []
        for f in conn.execute("""SELECT id, title, type, vehicle_model_id, metrics_json FROM finding
                                 WHERE source_kind = 'study' AND market_code = ? AND COALESCE(first_wave, 1) <= ?""", (code, W)):
            z = (loads(f["metrics_json"], {}) or {}).get("z")
            if z is not None and abs(z) >= 1:
                study.append({"finding_id": f["id"], "title": f["title"], "type": f["type"],
                              "vehicle": f["vehicle_model_id"], "z": z})
        study.sort(key=lambda x: -abs(x["z"]))

    targets = []
    for v in cars:
        ts = by_t[(v, code)]
        pc = {"Must": 0, "Should": 0, "Could": 0}
        for r in ts:
            p = effective(r["pm_priority"], r["proposed_priority"])
            if p in pc:
                pc[p] += 1
        top = sorted(ts, key=lambda r: -(r["score"] or 0))[:6]
        targets.append({"target": target_obj(v, code), "n": len(ts), "must": pc["Must"], "should": pc["Should"],
                        "could": pc["Could"], "voice_base": base.get((v, code), {}).get("in_scope", 0),
                        "gaps": gaps.get((v, code), []),
                        "top": [{"req_id": r["requirement_id"], "title": titles.get(r["requirement_id"]),
                                 "score": _r(r["score"]), "priority": effective(r["pm_priority"], r["proposed_priority"]),
                                 "ai_only": r["pm_priority"] is None, "evidence_level": r["target_evidence"]} for r in top]})

    # requirements whose priority here differs by ≥ 1 band from the same car in another market
    distinctive = []
    for v in cars:
        for here in by_t[(v, code)]:
            ph = effective(here["pm_priority"], here["proposed_priority"])
            if ph not in PRIORITY_RANK:
                continue
            best = None
            for om in TARGETS[v]:
                if om == code:
                    continue
                other = next((r for r in by_t[(v, om)] if r["requirement_id"] == here["requirement_id"]), None)
                po = other and effective(other["pm_priority"], other["proposed_priority"])
                if po not in PRIORITY_RANK:
                    continue
                gap = abs(PRIORITY_RANK[ph] - PRIORITY_RANK[po])
                sd = abs((here["score"] or 0) - (other["score"] or 0))
                if gap >= 1 and (best is None or (gap, sd) > best[0]):
                    best = ((gap, sd), other, po)
            if best:
                (_, other, po) = best
                distinctive.append({"req_id": here["requirement_id"], "title": titles.get(here["requirement_id"]),
                                    "target": target_obj(v, code),
                                    "this_market": {"priority": ph, "score": _r(here["score"])},
                                    "elsewhere": {"priority": po, "score": _r(other["score"]), "market": other["market_code"],
                                                  "market_label": L.mkt(other["market_code"])},
                                    "direction": "higher" if PRIORITY_RANK[ph] < PRIORITY_RANK[po] else "lower",
                                    "_k": best[0]})
    distinctive.sort(key=lambda x: (-x["_k"][0], -x["_k"][1], x["req_id"]))
    for d in distinctive:
        d.pop("_k")
    return {
        "code": m["code"], "name": m["name"], "label": L.mkt(m["code"]),
        "profile": {"climate": m["climate"], "usage_patterns": m["usage_patterns"],
                    "cultural_expectations": m["cultural_expectations"], "infrastructure": m["infrastructure"],
                    "powertrain_mix": m["powertrain_mix"], "profile_valid_from": m["profile_valid_from"],
                    "countries": loads(m["countries_json"], []) or [], "sources": sources},
        "targets": targets, "distinctive": distinctive[:10], "competitors": comps,
        "web_signals": web[:10], "study_highlights": study[:8],
    }

