"""Checkpoints and the raw evidence space (D-041).

GET /api/checkpoints            the two checkpoints, what each makes visible, and the acquire run lineage
GET /api/scan/points            every customer comment as a point (fixed 3D layout) with its first checkpoint
GET /api/scan/comment/{id}      one comment, verbatim, with its provenance
GET /api/scan/sources?cp=       the other raw sources visible at a checkpoint (study, sales, options, research, web)
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Query

from api.deps import db, not_found
from bmw_req.checkpoints import BY_ID, CHECKPOINTS, latest_run, visible_ids

router = APIRouter(prefix="/api", tags=["scan"])

CARS = ["F70", "G60", "G68", "G70"]
MARKETS = ["EU", "US", "CN", "RoW"]
CHANNELS = ["Source A", "Source B", "Source C", "Source D"]
ENGINES = ["ICE", "PHEV", "BEV"]
TYPES = ["Likes", "Wants", "Difficult to Use", "Defect", None]   # BMW's own label (first one), None = unlabelled
KINDS = ["feedback", "study", "sales", "option_list", "research", "web", "reference"]


# Research that is about one of our car lines moves from the date ring onto that car's rings (D-042):
# public sales figures → sales ring, ratings/reviews/studies → study ring, product news → options ring.
CAR_PATTERNS = {"G70": r"7 Series|\bi7\b|\bG70\b|\bG11\b|\bG12\b", "G60": r"5 Series|\bi5\b|\bG60\b|\bG68\b|\bG30\b",
                "F70": r"1 Series|\bF70\b|\bF40\b"}
SALES_METRICS = {"deliveries", "registrations", "retail_sales", "market_share"}


def research_cars(entity: str | None, headline: str) -> list[str]:
    """Car lines an item is about: by its entity, or by its headline when the entity is BMW as a whole."""
    ent = entity or ""
    hit = [c for c, p in CAR_PATTERNS.items() if re.search(p, ent)]
    if not hit and ent.strip() in ("BMW", "BMW AG", "BMW Group"):
        hit = [c for c, p in CAR_PATTERNS.items() if re.search(p, headline)]
    return hit


def research_ring(meta: dict) -> str:
    if meta.get("metric") in SALES_METRICS:
        return "sales"
    if meta.get("topic") == "consumer_studies" or meta.get("kind") == "study":
        return "study"
    return "options"


def _cp(cp: str) -> str:
    if cp not in BY_ID:
        raise not_found(f"No checkpoint {cp!r}; use one of {', '.join(BY_ID)}")
    return cp


@router.get("/checkpoints")
def checkpoints() -> list[dict]:
    out = []
    with db() as conn:
        for c in CHECKPOINTS:
            vis = visible_ids(c.id)
            q = ",".join("?" * len(vis))
            counts = {k: {"visible": 0, "new": 0} for k in KINDS}
            for r in conn.execute(f"""SELECT kind, SUM(checkpoint IN ({q})) visible, SUM(checkpoint = ?) new
                                      FROM source_item GROUP BY kind""", (*vis, c.id)):
                if r["kind"] in counts:
                    counts[r["kind"]] = {"visible": r["visible"] or 0, "new": r["new"] or 0}
            run = latest_run(conn, c.id, "acquire")
            out.append({"id": c.id, "label": c.label, "cutoff": c.cutoff.isoformat(), "parent_id": c.parent_id,
                        "position": c.position, "sources": counts,
                        "acquire": {"run_id": run["id"], "parent_run_id": run["parent_run_id"],
                                    "tracks": json.loads(run["stats_json"] or "{}")} if run else None})
    return out


@router.get("/scan/points")
def points() -> dict:
    """Columnar payload (~10k rows): parallel arrays index into the dictionaries, positions are rounded to 1e-3."""
    cols = {k: [] for k in ("id", "x", "y", "z", "car", "market", "channel", "engine", "type", "len", "cp")}
    with db() as conn:
        rows = conn.execute("""SELECT s.id, s.vehicle_model_id car, s.market_code market, s.meta_json, s.checkpoint,
                                      LENGTH(s.text) len, l.x, l.y, l.z
                               FROM source_item s JOIN source_layout l ON l.source_item_id = s.id
                               WHERE s.kind = 'feedback' AND s.checkpoint IS NOT NULL ORDER BY s.id""").fetchall()
    for r in rows:
        meta = json.loads(r["meta_json"] or "{}")
        labels = meta.get("bmw_labels") or [{}]
        t = labels[0].get("feedback_type")
        cols["id"].append(r["id"])
        for k in ("x", "y", "z"):
            cols[k].append(round(r[k], 3))
        cols["car"].append(CARS.index(r["car"]) if r["car"] in CARS else -1)
        cols["market"].append(MARKETS.index(r["market"]) if r["market"] in MARKETS else -1)
        cols["channel"].append(CHANNELS.index(meta.get("channel")) if meta.get("channel") in CHANNELS else -1)
        cols["engine"].append(ENGINES.index(meta.get("engine")) if meta.get("engine") in ENGINES else -1)
        cols["type"].append(TYPES.index(t) if t in TYPES else len(TYPES) - 1)
        cols["len"].append(r["len"] or 0)
        cols["cp"].append(BY_ID[r["checkpoint"]].position)
    return {"dict": {"car": CARS, "market": MARKETS, "channel": CHANNELS, "engine": ENGINES, "type": TYPES,
                     "cp": {c.position: c.id for c in CHECKPOINTS}},
            "n": len(rows), "cols": cols}


@router.get("/scan/comment/{sid}")
def comment(sid: int) -> dict:
    with db() as conn:
        r = conn.execute("""SELECT id, external_id, vehicle_model_id, market_code, country, text, meta_json, checkpoint, ref
                            FROM source_item WHERE id = ? AND kind = 'feedback'""", (sid,)).fetchone()
    if r is None:
        raise not_found(f"No comment {sid}")
    meta = json.loads(r["meta_json"] or "{}")
    return {"id": r["id"], "external_id": r["external_id"], "car": r["vehicle_model_id"], "market": r["market_code"],
            "country": r["country"], "text": r["text"], "channel": meta.get("channel"), "engine": meta.get("engine"),
            "bmw_labels": meta.get("bmw_labels") or [], "checkpoint": r["checkpoint"], "ref": r["ref"]}


@router.get("/scan/sources")
def sources(cp: str = Query("cp2")) -> dict:
    """Everything that is not a comment, visible at `cp`; `new` marks what this checkpoint added over its parent."""
    cp = _cp(cp)
    vis = visible_ids(cp)
    q = ",".join("?" * len(vis))
    with db() as conn:
        sales = [dict(r) for r in conn.execute(
            f"""SELECT sa.vehicle_model_id car, sa.market_code market, sa.year, sa.units, sa.is_forecast
                FROM sales sa JOIN source_item s ON s.id = sa.source_item_id WHERE s.checkpoint IN ({q})
                ORDER BY 1, 2, 3""", vis)]
        study = [dict(r) for r in conn.execute(
            f"""SELECT m.id, m.vehicle_model_id car, m.market_code market, m.scale, m.item,
                       ROUND(m.z_within_column, 3) z, ROUND(COALESCE(m.mean, m.top2), 3) value
                FROM study_metric m JOIN source_item s ON s.id = m.source_item_id WHERE s.checkpoint IN ({q})
                ORDER BY m.vehicle_model_id, m.market_code, m.z_within_column DESC""", vis)]
        options = []
        for r in conn.execute(f"""SELECT id, vehicle_model_id car, external_id code, meta_json FROM source_item
                                  WHERE kind = 'option_list' AND checkpoint IN ({q}) ORDER BY vehicle_model_id, id""", vis):
            m = json.loads(r["meta_json"] or "{}")
            options.append({"id": r["id"], "car": r["car"], "code": r["code"], "name": m.get("name_en"),
                            "category": m.get("category"), "availability": m.get("availability"),
                            "package": m.get("package_name")})
        research = []
        for r in conn.execute(
                f"""SELECT id, market_code market, trust_tier tier, published_at, text, url, meta_json,
                           checkpoint = ? AS is_new
                    FROM source_item WHERE kind = 'research' AND checkpoint IN ({q}) ORDER BY published_at""",
                (cp, *vis)):
            m = json.loads(r["meta_json"] or "{}")
            headline = r["text"].split(" — ")[0]
            cars = research_cars(m.get("entity"), headline)
            research.append({"id": r["id"], "cars": cars, "ring": research_ring(m) if cars else None,
                             "market": r["market"], "region": m.get("region"), "tier": r["tier"],
                             "topic": m.get("topic"), "kind": m.get("kind"), "entity": m.get("entity"),
                             "published_at": r["published_at"], "headline": headline,
                             "yoy": m.get("yoy_pct"), "value": m.get("value"), "unit": m.get("unit"),
                             "pair_key": m.get("pair_key"), "url": r["url"], "new": bool(r["is_new"])})
        web = conn.execute(f"SELECT COUNT(*) n, SUM(checkpoint = ?) new FROM source_item WHERE kind = 'web' "
                           f"AND checkpoint IN ({q})", (cp, *vis)).fetchone()
    return {"checkpoint": cp, "sales": sales, "study": study, "options": options, "research": research,
            "web": {"n": web["n"] or 0, "new": web["new"] or 0}}
