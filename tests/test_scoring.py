"""Scoring, evidence levels, renormalization and change proposals on synthetic data (no paid calls)."""

import json

import pytest

from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.pipeline import scoring
from bmw_req.service import set_priority


def _feedback(conn, n, market, wave=1, channel="Source B", prefix="G60"):
    ids = []
    for i in range(n):
        sid = conn.execute(
            """INSERT INTO source_item (kind, ref, external_id, trust_tier, vehicle_model_id, market_code, country, text,
                                        meta_json, wave) VALUES ('feedback', ?, ?, 'T1', 'G60', ?, ?, 'x', ?, ?)""",
            (f"f#{prefix}-{market}-{wave}-{channel}-{i}", f"{prefix}-{market}-{i}", market, market,
             json.dumps({"channel": channel, "engine": "ICE"}), wave)).lastrowid
        conn.execute("INSERT INTO verbatim_extraction (source_item_id, extractor_version, in_scope) VALUES (?, 'extract-v3', 1)", (sid,))
        ids.append(sid)
    return ids


@pytest.fixture
def conn():
    c = connect(":memory:")
    reference.seed(c)
    # 100 in-scope US verbatims per wave, 0 CN verbatims
    us1 = _feedback(c, 100, "US", wave=1)
    _feedback(c, 100, "US", wave=2, channel="Source A")
    fid = c.execute("""INSERT INTO finding (type, title, scope_level, vehicle_model_id, created_by, source_kind, first_wave)
                       VALUES ('defect', 'CarPlay drops', 'derivative', 'G60', 'test', 'verbatim', 1)""").lastrowid
    for sid in us1[:12]:
        gid = c.execute("""INSERT INTO signal (source_item_id, extractor_version, category, feedback_type, severity, quote,
                                               quote_verified, support_question)
                           VALUES (?, 'extract-v3', 'Infotainment & Digital', 'defect', 'high', 'q', 1, 0)""", (sid,)).lastrowid
        c.execute("INSERT INTO finding_signal VALUES (?, ?)", (fid, gid))
    c.execute("""INSERT INTO requirement (id, title, category, horizon, kano_class, kano_drift, effort, status)
                 VALUES ('REQ-0001', 'Phone link always works', 'Infotainment & Digital', 'today', 'basic', 'stable', 'S', 'proposed')""")
    c.execute("INSERT INTO requirement_finding VALUES ('REQ-0001', ?, 'supports')", (fid,))
    for d, m in [("G60", "US"), ("G68", "CN")]:
        c.execute("INSERT INTO requirement_target (requirement_id, vehicle_model_id, market_code, realization) VALUES ('REQ-0001', ?, ?, 'platform_wide')", (d, m))
    return c


def test_missing_factors_renormalized_and_flagged(conn):
    run = scoring.run_prioritization(conn, wave=1, trigger="new_evidence", initiated_by="system")
    rows = {r["market_code"]: json.loads(r["breakdown_json"]) for r in conn.execute(
        "SELECT * FROM score_snapshot WHERE run_id = ?", (run,))}
    us, cn = rows["US"], rows["CN"]
    assert us["factors"]["customer_voice"]["available"] and us["verbatims"]["verbatims"] == 12
    assert not cn["factors"]["customer_voice"]["available"]
    assert "Customer voice" in cn["gaps"] and "Satisfaction gap" in cn["gaps"]
    assert cn["evidence_level"] == "E4" and us["evidence_level"] == "E3"
    assert 0 <= cn["score"] <= 100 and 0 <= us["score"] <= 100
    assert "evidence level" in us["rationale"]


def test_wave_changes_base_and_proposals_need_confirmed_priority(conn):
    r1 = scoring.run_prioritization(conn, wave=1, trigger="new_evidence", initiated_by="system")
    assert conn.execute("SELECT COUNT(*) FROM change_proposal").fetchone()[0] == 0
    # PM confirms a priority that differs from what the next run will propose → proposal
    set_priority(conn, "REQ-0001", "G60", "US", "Must", "pm", "confirmed in review")
    prop = conn.execute("SELECT proposed_priority FROM requirement_target WHERE market_code = 'US'").fetchone()[0]
    r2 = scoring.run_prioritization(conn, wave=2, trigger="new_evidence", initiated_by="system")
    b1 = json.loads(conn.execute("SELECT breakdown_json FROM score_snapshot WHERE run_id = ? AND market_code = 'US'", (r1,)).fetchone()[0])
    b2 = json.loads(conn.execute("SELECT breakdown_json FROM score_snapshot WHERE run_id = ? AND market_code = 'US'", (r2,)).fetchone()[0])
    # wave 2 doubles the US base without new matching verbatims → customer voice drops
    assert b2["factors"]["customer_voice"]["value"] < b1["factors"]["customer_voice"]["value"]
    new_prio = conn.execute("SELECT proposed_priority FROM requirement_target WHERE market_code = 'US'").fetchone()[0]
    n_props = conn.execute("SELECT COUNT(*) FROM change_proposal WHERE run_id = ?", (r2,)).fetchone()[0]
    assert n_props == (1 if new_prio != "Must" else 0)
    assert prop in {"Must", "Should", "Could"}


def test_weight_change_is_audited(conn):
    scoring.current_weights(conn)
    w = dict(scoring.DEFAULT_WEIGHTS, customer_voice=50)
    scoring.set_weights(conn, w, "pm", "customer voice matters more")
    ev = conn.execute("SELECT * FROM audit_event WHERE action = 'change_weights'").fetchone()
    assert ev["actor_type"] == "human" and json.loads(ev["new_value"])["customer_voice"] == 50


def test_stale_priority_proposal_superseded_when_run_agrees(conn):
    scoring.run_prioritization(conn, wave=1, trigger="new_evidence", initiated_by="system")
    ai = conn.execute("SELECT proposed_priority FROM requirement_target WHERE market_code = 'US'").fetchone()[0]
    set_priority(conn, "REQ-0001", "G60", "US", ai, "pm", "confirmed in review")
    conn.execute("""INSERT INTO change_proposal (requirement_id, vehicle_model_id, market_code, field, old_value,
                        proposed_value, kind) VALUES ('REQ-0001', 'G60', 'US', 'priority', ?, 'Must', 'priority')""", (ai,))
    scoring.run_prioritization(conn, wave=1, trigger="pm_request", initiated_by="system")   # same evidence → agrees with PM
    assert conn.execute("SELECT COUNT(*) FROM change_proposal WHERE status = 'open'").fetchone()[0] == 0
