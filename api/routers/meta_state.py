"""GET /api/meta (labels, enums, portfolio config) and GET /api/state (wave, spend, counts, running job)."""

from fastapi import APIRouter

from api import jobs, labels as L
from api.deps import db
from api.queries import current_wave, target_obj, tkey
from bmw_req.car_zones import ZONES
from bmw_req.llm import budget
from bmw_req.pipeline import scoring
from bmw_req.pipeline.waves import WAVES
from bmw_req.portfolio import FOCUS_TARGETS, LINES, MIN_MARKET_VERBATIMS, SUCCESSOR_LAUNCH, all_targets
from bmw_req.service import EDITABLE

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def meta() -> dict:
    return {
        "actor_default": L.DEFAULT_PM,
        "vehicles": L.VEHICLE_NAMES, "markets": L.MARKET_SHORT, "market_names": L.MARKET_NAMES,
        "lines": LINES, "targets": [target_obj(d, m) for d, m in all_targets()],
        "focus_targets": [tkey(d, m) for d, m in FOCUS_TARGETS],
        "successor_launch": SUCCESSOR_LAUNCH, "min_market_verbatims": MIN_MARKET_VERBATIMS,
        "labels": {"evidence": L.EVIDENCE_LABELS, "evidence_help": L.EVIDENCE_HELP, "kano": L.KANO_LABELS,
                   "horizon": L.HORIZON_LABELS, "status": L.STATUS_LABELS, "proposal_kinds": L.PROPOSAL_KINDS,
                   "proposal_states": L.PROPOSAL_STATES, "verdicts": L.VERDICTS, "fit_types": L.FIT_TYPES,
                   "realization": L.REALIZATION, "actor_types": L.ACTOR_TYPES, "trust_tiers": L.TRUST_TIERS,
                   "factor_help": L.FACTOR_HELP},
        "priorities": L.PRIORITIES, "statuses": L.STATUSES,
        "priority_bands": {name: lo for name, lo in scoring.PRIORITY_BANDS if lo > 0},
        "scoring": {"version": scoring.SCORING_VERSION, "default_weights": scoring.DEFAULT_WEIGHTS,
                    "factor_labels": scoring.FACTOR_LABELS, "confidence": scoring.CONFIDENCE,
                    "effort_mod": scoring.EFFORT_MOD, "market_fit_mod": scoring.MARKET_FIT_MOD},
        "editable_fields": EDITABLE,
        "enums": L.ENUMS,
        "waves": {str(k): v for k, v in WAVES.items()},
        "zones": ZONES,
    }


@router.get("/state")
def state() -> dict:
    with db() as conn:
        w = current_wave(conn)
        opened = [{"wave": int(r["entity_id"]), "ts": r["ts"], "actor": r["actor_id"]} for r in conn.execute(
            "SELECT entity_id, ts, actor_id FROM audit_event WHERE action = 'open_wave' ORDER BY id")
            if str(r["entity_id"]).isdigit()]
        spend = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE status != 'reserved'").fetchone()[0]
        st = dict(conn.execute("SELECT status, COUNT(*) FROM requirement GROUP BY status").fetchall())
        by_kind = {k: 0 for k in L.PROPOSAL_KINDS}
        for k, n in conn.execute("""SELECT COALESCE(kind, 'priority'), COUNT(*) FROM change_proposal
                                    WHERE status = 'open' GROUP BY 1"""):
            by_kind[k] = n
        runs = conn.execute("SELECT COUNT(*) FROM prioritization_run").fetchone()[0]
    nxt = w + 1 if (w + 1) in WAVES else None
    return {
        "current_wave": w, "wave": WAVES.get(w), "next_wave": nxt, "waves_opened": opened,
        "spend_usd": round(float(spend), 4),
        "budget": {"warn": budget.WARN_USD, "block_non_demo": budget.BLOCK_NON_DEMO_USD,
                   "hard_stop": budget.HARD_STOP_USD, "total": 100.0},
        "running_job": jobs.running(),
        "counts": {"to_review": sum(st.get(s, 0) for s in L.REVIEW_STATUSES),
                   "open_proposals": sum(by_kind.values()), "open_by_kind": by_kind,
                   "decided": sum(st.get(s, 0) for s in L.DECIDED_STATUSES), "approved": st.get("approved", 0),
                   "requirements": sum(st.values()), "runs": runs},
    }
