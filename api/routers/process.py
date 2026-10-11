"""Process & governance: waves (+ opening one as a background job), jobs, prioritization runs and their diff,
scoring weights (re-run, no LLM), audit trail (+ logged CSV), the deliverable export (logged), OpenAI budget,
pipeline stats and demo snapshots (restore)."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from api import jobs, labels as L
from api.deps import DB, LOCK, conflict, db, get_actor, need_rationale, not_found
from api.queries import current_wave, latest_extractor, loads, parse_key, run_waves, spend_by_prefix, tkey
from bmw_req import service
from bmw_req.config import ROOT, get_settings
from bmw_req.llm import budget
from bmw_req.pipeline import scoring
from bmw_req.pipeline.requirements import audit
from bmw_req.pipeline.waves import WAVES

router = APIRouter(prefix="/api", tags=["process"])


# ------------------------------------------------------------------------------------------------ waves & jobs
@router.get("/waves")
def waves() -> list[dict]:
    with db() as conn:
        cur = current_wave(conn)
        opened = {}
        for r in conn.execute("SELECT entity_id, ts, actor_id FROM audit_event WHERE action = 'open_wave' ORDER BY id"):
            if str(r["entity_id"]).isdigit():
                opened[int(r["entity_id"])] = {"ts": r["ts"], "actor": r["actor_id"]}   # latest opening wins
        brought = defaultdict(lambda: {"feedback": 0, "study": 0, "sales": 0, "web": 0})
        for w, kind, n in conn.execute("""SELECT wave, kind, COUNT(*) FROM source_item
                                          WHERE kind IN ('feedback', 'study', 'sales', 'web') GROUP BY 1, 2"""):
            brought[w][kind] = n
        rw = run_waves(conn)
        stats = {r[0]: (r[1], r[2]) for r in conn.execute(
            """SELECT r.id, (SELECT COUNT(*) FROM score_snapshot s WHERE s.run_id = r.id),
                      (SELECT COUNT(*) FROM change_proposal p WHERE p.run_id = r.id)
               FROM prioritization_run r WHERE r.trigger = 'new_evidence' ORDER BY r.id""")}
    out = []
    for n, wv in WAVES.items():
        state = "done" if n < cur else "now" if n == cur else "next" if n == cur + 1 else "later"
        run_id = next((rid for rid in sorted(stats, reverse=True) if rw.get(rid) == n), None)
        out.append({"n": n, **wv, "state": state, "opened": opened.get(n) if n <= cur else None,
                    "brought": dict(brought[n]),
                    "run": {"id": run_id, "targets_scored": stats[run_id][0], "proposals": stats[run_id][1]}
                    if run_id else None})
    return out


class OpenWaveBody(BaseModel):
    rationale: str | None = None


@router.post("/waves/{n}/open", status_code=202)
def open_wave(n: int, body: OpenWaveBody | None = None, actor: str = Depends(get_actor)) -> JSONResponse:
    with db() as conn:
        cur = current_wave(conn)
    if n not in WAVES or n != cur + 1:
        raise conflict(f"Only the next wave can be opened (current wave {cur}; next "
                       f"{cur + 1 if cur + 1 in WAVES else 'none — all waves are open'}).")
    jid = jobs.start("wave", jobs.run_wave(n, actor), {"wave": n})
    if jid is None:
        raise conflict(f"Another job is running ({(jobs.running() or {}).get('id')}); try again when it has finished.")
    reason = ((body.rationale if body else None) or "").strip()
    if reason:   # the pipeline's open_wave event carries the wave label; the PM's own reason is kept beside it
        with db() as conn:
            service.audit(conn, actor_type="human", actor_id=actor, action="open_wave_reason", entity_type="ingest_wave",
                          entity_id=str(n), rationale=reason)
    return JSONResponse({"job_id": jid}, status_code=202)


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict:
    j = jobs.get(job_id)
    if j is None:
        raise not_found(f"No job {job_id} (jobs live in memory until the server restarts)")
    return j


# ------------------------------------------------------------------------------------------------ runs & weights
def _runs(conn) -> list[dict]:
    out = []
    for r in conn.execute(
            """SELECT r.id, r.ts, r.trigger, r.initiated_by, r.weights_version_id, r.model,
                      (SELECT COUNT(*) FROM score_snapshot s WHERE s.run_id = r.id) targets_scored,
                      (SELECT COUNT(*) FROM change_proposal p WHERE p.run_id = r.id) proposals,
                      (SELECT a.new_value FROM audit_event a WHERE a.action = 'start_run' AND a.entity_type = 'prioritization_run'
                         AND a.entity_id = CAST(r.id AS TEXT) LIMIT 1) start,
                      (SELECT a.rationale FROM audit_event a WHERE a.action = 'start_run' AND a.entity_type = 'prioritization_run'
                         AND a.entity_id = CAST(r.id AS TEXT) LIMIT 1) note
               FROM prioritization_run r ORDER BY r.id DESC"""):
        d = dict(r)
        d["wave"] = (loads(d.pop("start"), {}) or {}).get("wave")
        out.append(d)
    return out


@router.get("/runs")
def runs() -> list[dict]:
    with db() as conn:
        return _runs(conn)


@router.get("/runs/diff")
def runs_diff(older: int | None = None, newer: int | None = None,
              targets: str | None = Query(None, description="comma-separated target keys, e.g. G60×US,G68×CN")) -> dict:
    with db() as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM prioritization_run ORDER BY id DESC")]
        if newer is None:
            newer = ids[0] if ids else None
        if older is None:
            older = next((i for i in ids if newer is not None and i < newer), None)
        if newer is None or older is None:
            raise conflict("Needs at least two prioritization runs.")
        if newer not in ids or older not in ids:
            raise not_found("Unknown run id")
        snaps = defaultdict(dict)
        titles = {}
        for r in conn.execute("""SELECT s.run_id, s.requirement_id, s.vehicle_model_id v, s.market_code m, s.score, s.rank,
                                        s.priority, r.title FROM score_snapshot s JOIN requirement r ON r.id = s.requirement_id
                                 WHERE s.run_id IN (?, ?)""", (older, newer)):
            snaps[(r["requirement_id"], r["v"], r["m"])][r["run_id"]] = dict(r)
            titles[r["requirement_id"]] = r["title"]
        causes = {r[0]: r[1] for r in conn.execute(
            "SELECT entity_id, rationale FROM audit_event WHERE action = 'rescore' AND run_id = ?", (newer,))}
        wv = {r[0]: r[1] for r in conn.execute("SELECT id, weights_version_id FROM prioritization_run WHERE id IN (?, ?)",
                                               (older, newer))}
        wmap = {r[0]: loads(r[1], {}) for r in conn.execute("SELECT id, weights_json FROM weights_version")}
    want = {parse_key(k) for k in targets.split(",") if k.strip()} if targets else None
    rows = []
    for (rid, v, m), by in snaps.items():
        if want and (v, m) not in want:
            continue
        a, b = by.get(older), by.get(newer)
        so, sn = (a or {}).get("score"), (b or {}).get("score")
        change = "new" if a is None else "dropped" if b is None else (
            f"{a['priority']} → {b['priority']}" if a["priority"] != b["priority"] else "")
        ro, rn = (a or {}).get("rank"), (b or {}).get("rank")
        rows.append({"req_id": rid, "title": titles.get(rid), "target_key": tkey(v, m),
                     "score_old": None if so is None else round(so, 1), "score_new": None if sn is None else round(sn, 1),
                     "delta": None if so is None or sn is None else round(sn - so, 1),
                     "rank_old": ro, "rank_new": rn, "rank_move": None if ro is None or rn is None else ro - rn,
                     "change": change, "cause": causes.get(f"{rid}:{tkey(v, m)}", "")})
    rows.sort(key=lambda x: (-(abs(x["delta"]) if x["delta"] is not None else 1e9), x["req_id"], x["target_key"]))
    wo, wn = wmap.get(wv.get(older)) or {}, wmap.get(wv.get(newer)) or {}
    weight_changes = [{"factor": k, "label": scoring.FACTOR_LABELS.get(k, k), "old": wo.get(k), "new": wn.get(k)}
                      for k in dict.fromkeys(list(wo) + list(wn)) if wo.get(k) != wn.get(k)]
    stats = {"compared": len(rows), "moved": sum(r["delta"] is not None and abs(r["delta"]) >= 0.5 for r in rows),
             "priority_changed": sum("→" in r["change"] for r in rows),
             "new_or_dropped": sum(r["change"] in ("new", "dropped") for r in rows)}
    return {"older": older, "newer": newer, "weight_changes": weight_changes, "rows": rows, "stats": stats}


def _current_weights(conn) -> dict:
    r = conn.execute("SELECT id, weights_json, created_by, created_at, rationale FROM weights_version ORDER BY id DESC LIMIT 1").fetchone()
    if r is None:
        return {"id": None, "weights": dict(scoring.DEFAULT_WEIGHTS), "created_by": None, "created_at": None,
                "rationale": "Default weights (D-029) — no weight version stored yet"}
    return {"id": r["id"], "weights": {**scoring.DEFAULT_WEIGHTS, **(loads(r["weights_json"], {}) or {})},
            "created_by": r["created_by"], "created_at": r["created_at"], "rationale": r["rationale"]}


@router.get("/weights")
def weights() -> dict:
    with db() as conn:
        cur = _current_weights(conn)
        wave = max(current_wave(conn), 1)
    return {"current": cur, "defaults": scoring.DEFAULT_WEIGHTS, "labels": scoring.FACTOR_LABELS,
            "help": L.FACTOR_HELP, "min": 0, "max": 60, "rerun_wave": wave}


class WeightsBody(BaseModel):
    weights: dict[str, int]
    rationale: str


@router.post("/weights")
def set_weights(body: WeightsBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale, "A rationale for the weight change")
    unknown = sorted(set(body.weights) - set(scoring.DEFAULT_WEIGHTS))
    if unknown:
        raise HTTPException(422, f"Unknown factor(s): {', '.join(unknown)}")
    bad = [k for k, v in body.weights.items() if not 0 <= v <= 60]
    if bad:
        raise HTTPException(422, f"Weights must be between 0 and 60: {', '.join(bad)}")
    with db() as conn:
        cur = _current_weights(conn)
        new = {k: int(body.weights.get(k, cur["weights"].get(k, d))) for k, d in scoring.DEFAULT_WEIGHTS.items()}
        if sum(new.values()) <= 0:
            raise conflict("At least one weight must be > 0.")
        if new == cur["weights"]:
            raise conflict("Weights unchanged — nothing to re-run.")
        if not conn.execute("SELECT COUNT(*) FROM requirement").fetchone()[0]:
            raise conflict("No requirements yet — weights can be changed once requirements exist.")
        wave = max(current_wave(conn), 1)
        wid = scoring.set_weights(conn, new, actor, why)
        run_id = scoring.run_prioritization(conn, wave=wave, trigger="weight_change", initiated_by=actor, note=why)
    return {"weights_version_id": wid, "run_id": run_id, "weights": new, "wave": wave}


# ------------------------------------------------------------------------------------------------ audit
AUDIT_COLS = ["id", "ts", "actor_type", "actor_id", "action", "entity_type", "entity_id", "field", "old_value",
              "new_value", "rationale", "model", "prompt_ref", "run_id"]


def _multi(v: list[str] | None) -> list[str]:
    return [x.strip() for item in (v or []) for x in item.split(",") if x.strip()]


def _audit_where(actor_type, actor, action, entity_type, date_from, date_to, q) -> tuple[str, list]:
    where, params = [], []
    for col, vals in (("actor_type", _multi(actor_type)), ("actor_id", _multi(actor)), ("action", _multi(action)),
                      ("entity_type", _multi(entity_type))):
        if vals:
            where.append(f"{col} IN ({','.join('?' * len(vals))})")
            params += vals
    if date_from:
        where.append("substr(ts, 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        where.append("substr(ts, 1, 10) <= ?")
        params.append(date_to)
    if q:
        where.append("(entity_id LIKE ? OR rationale LIKE ? OR old_value LIKE ? OR new_value LIKE ? OR field LIKE ?)")
        params += [f"%{q}%"] * 5
    return " AND ".join(where) or "1 = 1", params


def _audit_query(conn, limit, **flt) -> tuple[int, list[dict]]:
    where, params = _audit_where(**flt)
    total = conn.execute(f"SELECT COUNT(*) FROM audit_event WHERE {where}", params).fetchone()[0]
    items = [dict(r) for r in conn.execute(f"SELECT {', '.join(AUDIT_COLS)} FROM audit_event WHERE {where} "
                                           f"ORDER BY id DESC LIMIT ?", (*params, limit))]
    return total, items


@router.get("/audit")
def audit_trail(actor_type: list[str] | None = Query(None), actor: list[str] | None = Query(None),
                action: list[str] | None = Query(None), entity_type: list[str] | None = Query(None),
                date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
                q: str | None = None, limit: int = Query(2000, ge=1, le=10000), hide_views: bool = False) -> dict:
    with db() as conn:
        total, items = _audit_query(conn, limit if not hide_views else 10000, actor_type=actor_type, actor=actor,
                                    action=action, entity_type=entity_type, date_from=date_from, date_to=date_to, q=q)
    if hide_views:
        items = [e for e in items if e["action"] != "view"][:limit]
        total = len(items)
    with db() as conn:
        facets_rows = conn.execute("""SELECT actor_type, actor_id, action, entity_type, MIN(ts), MAX(ts) FROM audit_event
                                      GROUP BY 1, 2, 3, 4""").fetchall()
    facets = {"actor_types": sorted({r[0] for r in facets_rows}), "actors": sorted({r[1] for r in facets_rows if r[1]}),
              "actions": sorted({r[2] for r in facets_rows}), "entity_types": sorted({r[3] for r in facets_rows}),
              "min_ts": min((r[4] for r in facets_rows), default=None), "max_ts": max((r[5] for r in facets_rows), default=None)}
    by_type = defaultdict(int)
    for e in items:
        by_type[e["actor_type"]] += 1
    return {"total": total, "shown": len(items), "by_actor_type": dict(by_type), "facets": facets, "items": items}


@router.get("/audit.csv")
def audit_csv(actor_type: list[str] | None = Query(None), actor_q: list[str] | None = Query(None, alias="actor"),
              action: list[str] | None = Query(None), entity_type: list[str] | None = Query(None),
              date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
              q: str | None = None, limit: int = Query(2000, ge=1, le=10000), who: str = Depends(get_actor)) -> Response:
    flt = dict(actor_type=actor_type, actor=actor_q, action=action, entity_type=entity_type, date_from=date_from,
               date_to=date_to, q=q)
    with db() as conn:
        _, items = _audit_query(conn, limit, **flt)
        desc = "; ".join(f"{k}={v}" for k, v in flt.items() if v) or "none"
        service.log_access(conn, who, "export", "export", "audit_trail.csv", f"{len(items)} rows; filters: {desc}")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=AUDIT_COLS)
    w.writeheader()
    w.writerows(items)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="audit_trail.csv"'})


# ------------------------------------------------------------------------------------------------ export
def _flat(data: list[dict]) -> list[dict]:
    rows = []
    for r in data:
        for t in r["targets"] or [{}]:
            rows.append({
                "id": r["id"], "title": r["title"], "category": r["category"], "status": r["status"], "version": r["version"],
                "target": t.get("target"), "realization": t.get("realization"), "score": t.get("score"),
                "ai_proposed_priority": t.get("ai_proposed_priority"), "pm_priority": t.get("pm_priority"),
                "evidence_level_target": t.get("evidence_level"), "evidence_level": r["evidence_level"],
                "horizon": r["horizon"], "kano_class": r["kano_class"], "kano_drift": r["kano_drift"],
                "must_not_lose": r["must_not_lose"], "effort": r["effort"], "description": r["description"],
                "target_metric": r["target_metric"], "acceptance_criteria": r["acceptance_criteria"],
                "prioritization_rationale": t.get("rationale"), "market_note": t.get("market_note"),
                "assumptions": r["assumptions"], "uncertainties": r["uncertainties"],
                "conflicting_evidence": r["conflicting_evidence"],
                "findings": "; ".join(f"F{f['id']} ({f['source_kind']}, {f['relation']}, {f['n_sources']} src)" for f in r["findings"]),
                "n_sources": sum(f["n_sources"] for f in r["findings"]),
            })
    return rows


def markdown_report(items: list[dict]) -> str:
    out = ["# Customer requirements — successor BMW vehicles", "",
           "AI-derived, PM-reviewed. Evidence and assumptions are listed separately. Scores are per derivative × market.", ""]
    for r in items:
        out += [f"## {r['id']} · {r['title']}", "",
                f"- **Status:** {r['status']} (v{r['version']}) · **Evidence level:** {r['evidence_level'] or '–'} · "
                f"**Horizon:** {r['horizon']} · **Kano:** {r['kano_class']} ({r['kano_drift'] or 'stable'}) · "
                f"**Effort:** {r['effort'] or '–'}" + (" · **Must-not-lose**" if r["must_not_lose"] else ""),
                f"- **Category:** {r['category']}", "", r["description"] or "", "",
                f"**Target metric:** {r['target_metric'] or '–'}  ", f"**Acceptance criteria:** {r['acceptance_criteria'] or '–'}", "",
                "| Target | Realization | Score | AI priority | PM priority | Evidence |", "|---|---|---|---|---|---|"]
        for t in r["targets"]:
            sc = f"{t['score']:.0f}" if t.get("score") is not None else "–"
            out.append(f"| {t['target']} | {t['realization'] or '–'} | {sc} | {t['ai_proposed_priority'] or '–'} | "
                       f"{t['pm_priority'] or 'not set'} | {t['evidence_level'] or '–'} |")
        out.append("")
        for t in r["targets"]:
            if t.get("rationale"):
                out.append(f"- *{t['target']}:* {t['rationale']}")
        out += ["", "**Evidence (linked findings)**", ""]
        for f in r["findings"]:
            out.append(f"- F{f['id']} [{f['source_kind']}, {f['relation']}] {f['title']} — {f['n_sources']} source(s)")
            for s in f["sources_sample"][:3]:
                ref = s.get("external_id") or s.get("url") or s.get("ref")
                q = (s.get("quote") or "").replace("\n", " ")
                out.append(f"  - {ref}" + (f": “{q[:200]}”" if q else ""))
        out += ["", "**Assumptions (forward-looking)**", "", r["assumptions"] or "–", "",
                "**Uncertainties**", "", r["uncertainties"] or "–", "",
                "**Conflicting evidence**", "", r["conflicting_evidence"] or "–", "", "---", ""]
    return "\n".join(out)


@router.get("/export")
def export(status: str | None = Query(None, description="comma-separated; default all but rejected"),
           format: Literal["json", "csv", "md"] = "json", actor: str = Depends(get_actor)) -> Response:
    with db() as conn:
        data = service.export_requirements(conn)
        want = {s.strip() for s in status.split(",") if s.strip()} if status else None
        data = [r for r in data if (r["status"] in want if want else r["status"] != "rejected")]
        if format == "json":
            body, mime, name = json.dumps(data, ensure_ascii=False, indent=1, default=str), "application/json", "requirements.json"
            detail = f"{len(data)} requirements"
        elif format == "csv":
            rows = _flat(data)
            buf = io.StringIO()
            if rows:
                w = csv.DictWriter(buf, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            body, mime, name, detail = buf.getvalue(), "text/csv; charset=utf-8", "requirements.csv", f"{len(rows)} rows"
        else:
            body, mime, name = markdown_report(data), "text/markdown; charset=utf-8", "requirements.md"
            detail = f"{len(data)} requirements"
        service.log_access(conn, actor, "export", "export", name, f"{detail}; status filter: {status or 'all but rejected'}")
    return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------------------------------------------ budget & stats
@router.get("/budget")
def budget_view() -> dict:
    with db() as conn:
        spent = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE status != 'reserved'").fetchone()[0]
        committed = conn.execute("""SELECT COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END), 0)
                                    FROM llm_usage""").fetchone()[0]
        calls = conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0]
        cache = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        by_job = [dict(r) for r in conn.execute(
            """SELECT job, COUNT(*) calls, COALESCE(SUM(cost_usd), 0) usd, COALESCE(SUM(reserved_usd), 0) reserved
               FROM llm_usage GROUP BY job ORDER BY usd DESC""")]
        by_group = [dict(r) for r in conn.execute(
            """SELECT substr(job, 1, instr(job || ':', ':') - 1) job_group, COUNT(*) calls, COALESCE(SUM(cost_usd), 0) usd
               FROM llm_usage GROUP BY 1 ORDER BY usd DESC""")]
        by_model = [dict(r) for r in conn.execute(
            """SELECT model, kind, COUNT(*) calls, COALESCE(SUM(cost_usd), 0) usd, SUM(input_tokens) input_tokens,
                      SUM(cached_tokens) cached_tokens, SUM(output_tokens) output_tokens, SUM(search_calls) searches
               FROM llm_usage GROUP BY 1, 2 ORDER BY usd DESC""")]
        by_status = [dict(r) for r in conn.execute(
            "SELECT status, COUNT(*) calls, COALESCE(SUM(cost_usd), 0) usd FROM llm_usage GROUP BY 1")]
    return {"spent": round(spent, 4), "committed": round(committed, 4), "total": 100.0,
            "thresholds": {"warn": budget.WARN_USD, "block_non_demo": budget.BLOCK_NON_DEMO_USD,
                           "hard_stop": budget.HARD_STOP_USD},
            "calls": calls, "cache_entries": cache, "by_job": by_job, "by_group": by_group, "by_model": by_model,
            "by_status": by_status}


@router.get("/budget/usage")
def budget_usage(job_group: str | None = None, limit: int = Query(500, ge=1, le=5000)) -> list[dict]:
    with db() as conn:
        if job_group:
            rows = conn.execute("""SELECT * FROM llm_usage WHERE substr(job, 1, instr(job || ':', ':') - 1) = ?
                                   ORDER BY id DESC LIMIT ?""", (job_group, limit))
        else:
            rows = conn.execute("SELECT * FROM llm_usage ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


@router.get("/pipeline/stats")
def pipeline_stats() -> dict:
    with db() as conn:
        ver = latest_extractor(conn)

        def one(sql, params=()):
            return conn.execute(sql, params).fetchone()[0]

        return {
            "sources_by_kind": dict(conn.execute("SELECT kind, COUNT(*) FROM source_item GROUP BY kind").fetchall()),
            "extractor_version": ver,
            "extracted": one("SELECT COUNT(*) FROM verbatim_extraction WHERE extractor_version = ?", (ver,)),
            "in_scope": one("SELECT COALESCE(SUM(in_scope), 0) FROM verbatim_extraction WHERE extractor_version = ?", (ver,)),
            "signals": one("SELECT COUNT(*) FROM signal WHERE extractor_version = ?", (ver,)),
            "unverified_quotes": one("SELECT COUNT(*) FROM signal WHERE extractor_version = ? AND quote_verified = 0", (ver,)),
            "findings_by_kind": dict(conn.execute("SELECT COALESCE(source_kind, 'other'), COUNT(*) FROM finding GROUP BY 1").fetchall()),
            "requirements_by_status": dict(conn.execute("SELECT status, COUNT(*) FROM requirement GROUP BY 1").fetchall()),
            "reqs_with_fit": one("SELECT COUNT(DISTINCT requirement_id) FROM fit_check"),
            "runs": one("SELECT COUNT(*) FROM prioritization_run"),
            "open_proposals": one("SELECT COUNT(*) FROM change_proposal WHERE status = 'open'"),
            "audit_events": one("SELECT COUNT(*) FROM audit_event"),
            "match_existing_events": one("SELECT COUNT(*) FROM audit_event WHERE action = 'match_existing'"),
            "fit_matrix": [{"check_type": r[0], "result": r[1], "n": r[2]} for r in
                           conn.execute("SELECT check_type, result, COUNT(*) FROM fit_check GROUP BY 1, 2")],
            "trust_tiers": [{"kind": r[0], "tier": r[1], "n": r[2]} for r in conn.execute(
                """SELECT kind, COALESCE(trust_tier, 'untiered'), COUNT(*) FROM source_item
                   WHERE kind IN ('web', 'reference') GROUP BY 1, 2""")],
            "spend_by_prefix": spend_by_prefix(conn),
        }


# ------------------------------------------------------------------------------------------------ demo snapshots
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _demo_state():
    """Load scripts/demo_state.py (not a package) so restore runs exactly the CLI's logic."""
    spec = importlib.util.spec_from_file_location("_demo_state", ROOT / "scripts" / "demo_state.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snapshots() -> list[str]:
    d = get_settings().data_dir / "snapshots"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.db") if _NAME.match(p.stem))


@router.get("/demo/snapshots")
def snapshots() -> list[str]:
    return _snapshots()


class RestoreBody(BaseModel):
    snapshot: str
    rationale: str


@router.post("/demo/restore")
def restore(body: RestoreBody, actor: str = Depends(get_actor)) -> dict:
    why = need_rationale(body.rationale)
    if not _NAME.match(body.snapshot) or body.snapshot not in _snapshots():
        raise not_found(f"No snapshot {body.snapshot!r}; available: {', '.join(_snapshots()) or 'none'}")
    if jobs.running():
        raise conflict("A pipeline job is running — restore when it has finished.")
    mod = _demo_state()
    with LOCK:   # nobody touches the DB while the file is swapped
        if jobs.running():
            raise conflict("A pipeline job is running — restore when it has finished.")
        DB.close()
        try:
            mod.restore(body.snapshot)
        finally:
            conn = DB.conn()   # reopen (also after a failed restore)
        conn.execute("BEGIN IMMEDIATE")
        try:
            audit(conn, actor_type="human", actor_id=actor, action="restore_snapshot", entity_type="database",
                  entity_id=body.snapshot, rationale=why)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        wave = current_wave(conn)
    return {"restored": body.snapshot, "current_wave": wave}
