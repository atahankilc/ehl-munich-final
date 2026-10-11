"""Evidence: findings explorer (incl. uncovered findings), finding detail with sources and signals (the
finding → signal → verbatim chain), quality hand-over list and its logged CSV export."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from api import labels as L
from api.deps import db, get_actor, not_found
from api.queries import current_wave, loads, metrics_wave
from bmw_req import service
from bmw_req.pipeline.requirements import QUALITY_DEFECT_SHARE

router = APIRouter(prefix="/api", tags=["evidence"])

MK = L.MARKETS
HIDDEN_META = {"price_eur", "price_note"}   # prices are out of scope; never shipped


def _all_findings(conn, mw: str) -> list[dict]:
    n_req = dict(conn.execute("SELECT finding_id, COUNT(*) FROM requirement_finding GROUP BY 1").fetchall())
    n_src = dict(conn.execute("SELECT finding_id, COUNT(*) FROM finding_source GROUP BY 1").fetchall())
    out = []
    for r in conn.execute("""SELECT id, source_kind, type, category, title, summary, vehicle_model_id, market_code,
                                    metrics_json, first_wave, polarity FROM finding ORDER BY id"""):
        mt = loads(r["metrics_json"], {}) or {}
        bw = ((mt.get("by_wave") or {}).get(mw) or {}) if r["source_kind"] == "verbatim" else {}
        bym = bw.get("markets") or {}
        out.append({
            "id": r["id"], "source_kind": r["source_kind"], "type": r["type"], "category": r["category"],
            "title": r["title"], "summary": r["summary"], "vehicle": r["vehicle_model_id"], "market": r["market_code"],
            "polarity": r["polarity"], "first_wave": r["first_wave"],
            "scope": f"{r['vehicle_model_id'] or 'line'} × {r['market_code'] or 'all'}",
            "verbatims": int(bw.get("verbatims") or 0),
            "by_market": {m: int((bym.get(m) or {}).get("verbatims") or 0) for m in MK},
            "n_sources": n_src.get(r["id"], 0), "n_requirements": n_req.get(r["id"], 0),
        })
    return out


@router.get("/findings")
def findings(vehicle: str | None = Query(None, description="derivative, or 'line' for line-level findings"),
             market: str | None = None, kind: str | None = None, category: str | None = None,
             type: str | None = None, q: str | None = None, uncovered: bool = False, visible_only: bool = True,
             polarity: str | None = Query(None, description="comma-separated, e.g. pain_or_want,context"),
             limit: int = Query(50, ge=1, le=2000), offset: int = Query(0, ge=0)) -> dict:
    with db() as conn:
        w = current_wave(conn)
        mw = metrics_wave(w)
        items = _all_findings(conn, mw)
    sel = items
    if vehicle:
        sel = [f for f in sel if (f["vehicle"] is None if vehicle == "line" else f["vehicle"] == vehicle)]
    if market:
        sel = [f for f in sel if f["market"] == market or f["by_market"].get(market, 0) > 0]
    if kind:
        sel = [f for f in sel if f["source_kind"] == kind]
    if category:
        sel = [f for f in sel if f["category"] == category]
    if type:
        sel = [f for f in sel if f["type"] == type]
    if polarity:
        pols = {p.strip() for p in polarity.split(",") if p.strip()}
        sel = [f for f in sel if f.get("polarity") in pols]
    if q:
        ql = q.lower()
        sel = [f for f in sel if ql in (f["title"] or "").lower() or ql in (f["summary"] or "").lower()]
    if visible_only and w:
        sel = [f for f in sel if (f["first_wave"] or 1) <= w]
    used = sum(f["n_requirements"] > 0 for f in sel)
    total_unfiltered_unc = len(sel) - used
    if uncovered:
        sel = [f for f in sel if f["n_requirements"] == 0]
    sel.sort(key=lambda f: (-f["verbatims"], -f["n_sources"], f["id"]))
    # used/uncovered describe the filtered set BEFORE the uncovered filter (for the summary line); total is after it
    return {"total": len(sel), "used": used, "uncovered": total_unfiltered_unc, "metrics_wave": mw,
            "facets": {"categories": sorted({f["category"] for f in items if f["category"]}),
                       "types": sorted({f["type"] for f in items if f["type"]})},
            "items": sel[offset: offset + limit]}


@router.get("/findings/{fid}")
def finding(fid: int) -> dict:
    with db() as conn:
        r = conn.execute("SELECT * FROM finding WHERE id = ?", (fid,)).fetchone()
        if r is None:
            raise not_found(f"No finding F{fid}")
        used = [dict(x) for x in conn.execute(
            """SELECT r.id AS req_id, r.title, r.status, rf.relation FROM requirement_finding rf
               JOIN requirement r ON r.id = rf.requirement_id WHERE rf.finding_id = ? ORDER BY r.id""", (fid,))]
        n_src = conn.execute("SELECT COUNT(*) FROM finding_source WHERE finding_id = ?", (fid,)).fetchone()[0]
        n_sig = conn.execute("SELECT COUNT(*) FROM finding_signal WHERE finding_id = ?", (fid,)).fetchone()[0]
        mw = metrics_wave(current_wave(conn))
    f = dict(r)
    metrics = loads(f.pop("metrics_json", None), {}) or {}
    out = {**f, "vehicle": f["vehicle_model_id"], "market": f["market_code"], "metrics": metrics,
           "n_sources": n_src, "n_signals": n_sig, "used_by": used, "metrics_wave": mw}
    if f.get("source_kind") == "verbatim":
        out["markets"] = ((metrics.get("by_wave") or {}).get(mw) or {}).get("markets") or {}
    return out


def _meta(s) -> dict:
    meta = loads(s, {}) or {}
    return {k: v for k, v in meta.items() if k not in HIDDEN_META} if isinstance(meta, dict) else {}


@router.get("/findings/{fid}/sources")
def finding_sources(fid: int, limit: int = Query(30, ge=1, le=500), offset: int = Query(0, ge=0)) -> list[dict]:
    with db() as conn:
        if conn.execute("SELECT 1 FROM finding WHERE id = ?", (fid,)).fetchone() is None:
            raise not_found(f"No finding F{fid}")
        rows = conn.execute(
            """SELECT s.id, s.kind, s.external_id, s.ref, s.country, s.market_code, s.vehicle_model_id, s.url,
                      s.published_at, s.retrieved_at, s.trust_tier, s.wave, s.text, s.meta_json,
                      COALESCE(fs.quote, s.quote) AS quote, fs.relation
               FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id WHERE fs.finding_id = ?
               ORDER BY s.id LIMIT ? OFFSET ?""", (fid, limit, offset)).fetchall()
    return [{"id": r["id"], "kind": r["kind"], "external_id": r["external_id"], "ref": r["ref"], "country": r["country"],
             "market": r["market_code"], "vehicle": r["vehicle_model_id"], "url": r["url"],
             "published_at": r["published_at"], "retrieved_at": r["retrieved_at"], "trust_tier": r["trust_tier"],
             "wave": r["wave"], "relation": r["relation"], "quote": r["quote"], "text": r["text"],
             "meta": _meta(r["meta_json"])} for r in rows]


@router.get("/findings/{fid}/signals")
def finding_signals(fid: int, limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[dict]:
    with db() as conn:
        if conn.execute("SELECT 1 FROM finding WHERE id = ?", (fid,)).fetchone() is None:
            raise not_found(f"No finding F{fid}")
        rows = conn.execute(
            """SELECT g.id, g.feedback_type, g.severity, g.category, g.topic, g.need_statement, g.quote, g.quote_verified,
                      g.support_question, g.extractor_version, s.id sid, s.external_id, s.market_code, s.country,
                      s.vehicle_model_id, s.wave, json_extract(s.meta_json, '$.channel') channel
               FROM finding_signal fs JOIN signal g ON g.id = fs.signal_id JOIN source_item s ON s.id = g.source_item_id
               WHERE fs.finding_id = ?
               ORDER BY CASE g.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, g.quote_verified DESC, g.id
               LIMIT ? OFFSET ?""", (fid, limit, offset)).fetchall()
    return [{"signal_id": r["id"], "feedback_type": r["feedback_type"], "severity": r["severity"],
             "category": r["category"], "topic": r["topic"], "need_statement": r["need_statement"], "quote": r["quote"],
             "quote_verified": bool(r["quote_verified"]), "support_question": bool(r["support_question"]),
             "extractor_version": r["extractor_version"],
             "source": {"id": r["sid"], "external_id": r["external_id"], "market": r["market_code"],
                        "country": r["country"], "vehicle": r["vehicle_model_id"], "channel": r["channel"],
                        "wave": r["wave"]}} for r in rows]


# ------------------------------------------------------------------------------------------------ quality hand-over
def _quality(conn, vehicle: str | None, category: str | None, quotes: bool = True) -> dict:
    mw = metrics_wave(current_wave(conn))
    rows = [dict(r) for r in conn.execute(
        """SELECT f.id, f.vehicle_model_id, f.category, f.title, f.summary, f.metrics_json, COUNT(*) n_signals,
                  AVG(g.feedback_type = 'defect') defect_share, SUM(g.severity = 'high') n_high,
                  (SELECT GROUP_CONCAT(rf.requirement_id) FROM requirement_finding rf
                    WHERE rf.finding_id = f.id AND rf.relation = 'supports') reqs
           FROM finding f JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
           WHERE f.source_kind = 'verbatim' AND COALESCE(f.polarity, '') != 'like'
           GROUP BY f.id HAVING defect_share >= ? ORDER BY n_signals DESC""", (QUALITY_DEFECT_SHARE,))]
    if vehicle:
        rows = [r for r in rows if r["vehicle_model_id"] == vehicle]
    if category:
        rows = [r for r in rows if r["category"] == category]
    items = []
    for r in rows:
        mk = ((loads(r["metrics_json"], {}) or {}).get("by_wave", {}).get(mw, {}) or {}).get("markets", {}) or {}
        item = {"finding_id": r["id"], "vehicle": r["vehicle_model_id"], "car": L.car(r["vehicle_model_id"]),
                "category": r["category"], "title": r["title"], "summary": r["summary"], "n_signals": r["n_signals"],
                "defect_share": round(r["defect_share"], 4), "n_high": int(r["n_high"] or 0),
                "markets": {k: (v or {}).get("verbatims") for k, v in
                            sorted(mk.items(), key=lambda kv: -((kv[1] or {}).get("verbatims") or 0))},
                "cited_by": sorted((r["reqs"] or "").split(",")) if r["reqs"] else []}
        if quotes:
            item["quotes"] = [dict(x) for x in conn.execute(
                """SELECT s.external_id, s.market_code AS market, g.quote FROM finding_signal fs
                   JOIN signal g ON g.id = fs.signal_id JOIN source_item s ON s.id = g.source_item_id
                   WHERE fs.finding_id = ? AND g.feedback_type = 'defect' AND g.quote_verified = 1
                   ORDER BY CASE g.severity WHEN 'high' THEN 0 ELSE 1 END, g.id LIMIT 4""", (r["id"],))]
        items.append(item)
    return {"n_issues": len(items), "n_signals": sum(i["n_signals"] for i in items),
            "n_high": sum(i["n_high"] for i in items), "n_cited": sum(bool(i["cited_by"]) for i in items),
            "defect_share_min": QUALITY_DEFECT_SHARE, "metrics_wave": mw, "items": items}


@router.get("/quality")
def quality(vehicle: str | None = None, category: str | None = None) -> dict:
    with db() as conn:
        return _quality(conn, vehicle, category)


@router.get("/quality.csv")
def quality_csv(vehicle: str | None = None, category: str | None = None, actor: str = Depends(get_actor)) -> Response:
    with db() as conn:
        data = _quality(conn, vehicle, category, quotes=False)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["theme", "car", "category", "signals", "defect share", "high severity", "markets", "cited by"])
        for i in data["items"]:
            w.writerow([i["title"], i["car"], i["category"], i["n_signals"], i["defect_share"], i["n_high"],
                        ", ".join(f"{L.mkt(k)} {v}" for k, v in i["markets"].items()), ", ".join(i["cited_by"]) or "–"])
        flt = ", ".join(f"{k}={v}" for k, v in (("vehicle", vehicle), ("category", category)) if v) or "none"
        # fixes the Streamlit gap: this export is now an access event like every other download
        service.log_access(conn, actor, "export", "export", "quality_handover.csv",
                           f"{len(data['items'])} rows; filters: {flt}")
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="quality_handover.csv"'})
