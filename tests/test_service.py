"""PM service actions on a tiny synthetic requirement (in-memory DB, no BMW data, no paid calls)."""

import json
import sqlite3

import pytest

from bmw_req import service
from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.service import ActionError

PM = "Test PM"


@pytest.fixture
def conn():
    c = connect(":memory:")
    reference.seed(c)
    c.execute("INSERT INTO requirement (id, title, description, status) VALUES ('REQ-0001', 'Seamless phone pairing', 'd', 'proposed')")
    for m in ("US", "EU"):
        c.execute("""INSERT INTO requirement_target (requirement_id, vehicle_model_id, market_code, realization, score,
                         proposed_priority) VALUES ('REQ-0001', 'G60', ?, 'platform_wide', 62.0, 'Must')""", (m,))
        for ct, res in (("brand", "pass"), ("segment", "pass"), ("market", "pass"), ("feasibility", "warn")):
            c.execute("""INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, checked_by)
                         VALUES ('REQ-0001', 'G60', ?, ?, ?, 'ai:test')""", (m, ct, res))
    src = c.execute("INSERT INTO source_item (kind, ref, external_id) VALUES ('feedback', 't#1', 'G60-0001')").lastrowid
    for fid in (1, 2):
        c.execute("INSERT INTO finding (id, title, created_by, source_kind) VALUES (?, ?, 'test', 'verbatim')", (fid, f"F{fid}"))
        c.execute("INSERT INTO finding_source (finding_id, source_item_id) VALUES (?, ?)", (fid, src))
    c.execute("INSERT INTO requirement_finding VALUES ('REQ-0001', 1, 'supports')")
    return c


def events(c, action=None):
    sql = "SELECT * FROM audit_event" + (" WHERE action = ?" if action else "") + " ORDER BY id"
    return [dict(r) for r in c.execute(sql, (action,) if action else ())]


def status(c):
    return c.execute("SELECT status FROM requirement WHERE id = 'REQ-0001'").fetchone()[0]


def test_status_change_needs_actor_and_rationale(conn):
    with pytest.raises(ActionError):
        service.set_status(conn, "REQ-0001", "approved", PM, "")
    with pytest.raises(ActionError):
        service.set_status(conn, "REQ-0001", "approved", " ", "good evidence")
    with pytest.raises(ActionError):
        service.set_status(conn, "REQ-0001", "shipped", PM, "good evidence")
    assert status(conn) == "proposed" and not events(conn, "set_status")
    service.set_status(conn, "REQ-0001", "deferred", PM, "Wait for the customer study")
    ev = events(conn, "set_status")
    assert status(conn) == "deferred"
    assert len(ev) == 1 and ev[0]["actor_type"] == "human" and ev[0]["actor_id"] == PM
    assert (ev[0]["old_value"], ev[0]["new_value"], ev[0]["rationale"]) == ("proposed", "deferred", "Wait for the customer study")


def test_brand_fail_blocks_approval_until_override(conn):
    conn.execute("""INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, rationale, checked_by)
                    VALUES ('REQ-0001', 'G60', 'US', 'brand', 'fail', 'paywalls hardware', 'ai:test')""")
    assert service.brand_blocked(conn, "REQ-0001") == ["G60×US"]
    with pytest.raises(ActionError, match="Brand-fit FAIL"):
        service.set_status(conn, "REQ-0001", "approved", PM, "Strong evidence")
    assert status(conn) == "proposed"
    with pytest.raises(ActionError):
        service.override_gate(conn, "REQ-0001", "G60×US", PM, "")
    service.override_gate(conn, "REQ-0001", "G60×US", PM, "Feature is included, not paywalled")
    assert service.brand_blocked(conn, "REQ-0001") == []
    service.set_status(conn, "REQ-0001", "approved", PM, "Strong evidence; gate overridden")
    assert status(conn) == "approved"
    assert [e["action"] for e in events(conn) if e["actor_type"] == "human"] == ["override_gate", "set_status"]


def test_latest_brand_check_wins(conn):
    conn.execute("""INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, checked_by)
                    VALUES ('REQ-0001', 'G60', 'EU', 'brand', 'fail', 'ai:test')""")
    conn.execute("""INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, checked_by)
                    VALUES ('REQ-0001', 'G60', 'EU', 'brand', 'pass', 'ai:test')""")
    assert service.brand_blocked(conn, "REQ-0001") == []


def test_priority_change_is_audited(conn):
    service.set_priority(conn, "REQ-0001", "G60", "US", "Should", PM, "US evidence weaker than the score suggests")
    row = conn.execute("SELECT priority, proposed_priority FROM requirement_target WHERE market_code = 'US'").fetchone()
    assert (row["priority"], row["proposed_priority"]) == ("Should", "Must")   # AI proposal untouched
    ev = events(conn, "set_priority")
    assert len(ev) == 1 and ev[0]["entity_id"] == "REQ-0001:G60×US" and ev[0]["new_value"] == "Should"
    assert ev[0]["old_value"] is None
    with pytest.raises(ActionError):
        service.set_priority(conn, "REQ-0001", "G60", "US", "Critical", PM, "not a priority band")
    with pytest.raises(ActionError):
        service.set_priority(conn, "REQ-0001", "G60", "CN", "Must", PM, "no such target")
    assert len(events(conn, "set_priority")) == 1


def test_edit_bumps_version_one_event_per_field(conn):
    v = service.edit_requirement(conn, "REQ-0001", {"title": "Instant phone pairing", "effort": "S", "status": "approved"},
                                 PM, "Sharper wording")
    r = conn.execute("SELECT title, effort, version, status FROM requirement").fetchone()
    assert v == 2 and (r["title"], r["effort"], r["version"], r["status"]) == ("Instant phone pairing", "S", 2, "proposed")
    assert sorted(e["field"] for e in events(conn, "edit")) == ["effort", "title"]   # status is not editable here
    assert service.edit_requirement(conn, "REQ-0001", {"title": "Instant phone pairing"}, PM, "no-op") == 2


def test_finding_link_add_change_remove(conn):
    service.set_finding_link(conn, "REQ-0001", 2, "contradicts", PM, "EU owners praise the opposite")
    service.set_finding_link(conn, "REQ-0001", 1, None, PM, "Not about pairing")
    links = {r[0]: r[1] for r in conn.execute("SELECT finding_id, relation FROM requirement_finding")}
    assert links == {2: "contradicts"}
    ev = events(conn, "edit_evidence")
    assert [(e["field"], e["old_value"], e["new_value"]) for e in ev] == [("finding:2", None, "contradicts"),
                                                                         ("finding:1", "supports", None)]


def test_accepting_priority_proposal_applies_it(conn):
    service.set_priority(conn, "REQ-0001", "G60", "EU", "Must", PM, "Confirmed AI proposal")
    pid = conn.execute("""INSERT INTO change_proposal (requirement_id, vehicle_model_id, market_code, field, old_value,
                              proposed_value, reason, kind) VALUES ('REQ-0001', 'G60', 'EU', 'priority', 'Must', 'Could',
                              'customer voice -12 pts', 'priority')""").lastrowid
    with pytest.raises(ActionError):
        service.decide_proposal(conn, pid, True, PM, "")
    service.decide_proposal(conn, pid, True, PM, "New wave shows the issue is fixed")
    assert conn.execute("SELECT priority FROM requirement_target WHERE market_code = 'EU'").fetchone()[0] == "Could"
    p = conn.execute("SELECT status, decided_by, decision_rationale FROM change_proposal WHERE id = ?", (pid,)).fetchone()
    assert tuple(p) == ("accepted", PM, "New wave shows the issue is fixed")
    assert [e["action"] for e in events(conn) if e["actor_type"] == "human"][-2:] == ["set_priority", "accept_proposal"]
    with pytest.raises(ActionError):   # already decided
        service.decide_proposal(conn, pid, False, PM, "changed my mind")
    with pytest.raises(ActionError):
        service.decide_proposal(conn, 999, True, PM, "does not exist")


def test_accepting_content_and_link_proposals(conn):
    c1 = conn.execute("""INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                         VALUES ('REQ-0001', 'target_metric', NULL, 'Pairing < 5 s', 'PM challenge', 'content')""").lastrowid
    c2 = conn.execute("""INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                         VALUES ('REQ-0001', 'finding:2', NULL, 'supports', 'semantic search', 'link_finding')""").lastrowid
    service.decide_proposal(conn, c1, True, PM, "Measurable target")
    service.decide_proposal(conn, c2, True, PM, "Relevant evidence")
    r = conn.execute("SELECT target_metric, version FROM requirement").fetchone()
    assert (r["target_metric"], r["version"]) == ("Pairing < 5 s", 2)
    assert conn.execute("SELECT relation FROM requirement_finding WHERE finding_id = 2").fetchone()[0] == "supports"


def test_rejecting_proposal_changes_nothing(conn):
    pid = conn.execute("""INSERT INTO change_proposal (requirement_id, field, old_value, proposed_value, reason, kind)
                          VALUES ('REQ-0001', 'title', 'Seamless phone pairing', 'Other', 'x', 'content')""").lastrowid
    service.decide_proposal(conn, pid, False, PM, "Original wording is clearer")
    assert conn.execute("SELECT title, version FROM requirement").fetchone()[:] == ("Seamless phone pairing", 1)
    assert events(conn, "reject_proposal")[0]["rationale"] == "Original wording is clearer"


def test_audit_is_append_only_and_access_logged(conn):
    service.log_access(conn, PM, "view", "requirement", "REQ-0001")
    service.log_access(conn, PM, "export", "export", "requirements.json", "3 requirements")
    ev = events(conn)
    assert [(e["action"], e["actor_type"]) for e in ev] == [("view", "human"), ("export", "human")]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_event")
    service.set_status(conn, "REQ-0001", "rejected", PM, "Out of segment")
    assert len(events(conn)) == 3


def test_export_and_trail(conn):
    service.set_priority(conn, "REQ-0001", "G60", "US", "Must", PM, "Confirmed")
    conn.execute("UPDATE requirement_target SET score_breakdown_json = ? WHERE market_code = 'US'",
                 (json.dumps({"rationale": "driven by customer voice"}),))
    out = service.export_requirements(conn)
    assert out[0]["id"] == "REQ-0001" and len(out[0]["targets"]) == 2 and out[0]["findings"][0]["n_sources"] == 1
    us = next(t for t in out[0]["targets"] if t["target"] == "G60×US")
    assert (us["pm_priority"], us["ai_proposed_priority"], us["rationale"]) == ("Must", "Must", "driven by customer voice")
    trail = service.requirement_trail(conn, "REQ-0001")
    assert [e["action"] for e in trail] == ["set_priority"]
