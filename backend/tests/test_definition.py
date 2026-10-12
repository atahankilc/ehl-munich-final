"""Requirement definition (D-048): the code checks that keep every number honest, candidate pairs, bundles, and an API
smoke test on a throwaway clone of the real data (no LLM)."""

from __future__ import annotations

import psycopg
import pytest

from bmw_req.db import connect
from bmw_req.definition import couple, define, specify
from bmw_req.definition.domains import domain_for, shared_resources, zones_for

CTX = {
    "title": "Long-distance range", "targets": [{"line": "5 Series", "market": "US", "own_evidence": True},
                                                 {"line": "5 Series", "market": "CN", "own_evidence": False}],
    "facts": [{"id": "fact:1", "value": 727.4, "raw_value": 452.0, "unit": "km", "cycle": "WLTP", "quote": "452 miles"},
              {"id": "fact:2", "value": 900.0, "unit": "km", "cycle": "CLTC", "quote": "900 km"},
              {"id": "fact:3", "value": 650.0, "unit": "km", "cycle": "WLTP", "quote": "650 km", "unverified": True}],
    "study": [{"id": "study:7", "mean": None, "top2": 0.498}],
    "evidence": [{"id": "research:5", "text": "Rivals now reach 600 km", "relation": "trend_for"}],
    "trend_ids": ["research:5"],
}


def lv(value, basis, ids, text="x"):
    return {"value": value, "text": text, "basis": basis, "source_ids": ids, "note": ""}


def test_cited_level_keeps_only_values_in_its_sources():
    notes, gaps = [], []
    ok = specify.check_level(lv(452, "cited", ["fact:1"]), CTX, notes, gaps, "5 Series US target", False)
    assert ok["basis"] == "cited"   # the number as written (miles) counts
    assert specify.check_level(lv(49.8, "cited", ["study:7"]), CTX, notes, gaps, "5 Series US baseline", False)["basis"] == "cited"
    bad = specify.check_level(lv(700, "cited", ["fact:1"]), CTX, notes, gaps, "5 Series US target", False)
    assert bad["basis"] == "assumption" and "not found" in bad["note"]
    ghost = specify.check_level(lv(452, "cited", ["fact:99"]), CTX, notes, gaps, "5 Series US target", False)
    assert ghost["basis"] == "assumption" and ghost["source_ids"] == []


def test_cycles_never_mix_and_unverified_needs_company():
    notes, gaps = [], []
    mixed = specify.check_level(lv(900, "cited", ["fact:1", "fact:2"]), CTX, notes, gaps, "5 Series CN target", False)
    assert mixed["basis"] == "assumption" and "cycles" in mixed["note"]
    weak = specify.check_level(lv(650, "cited", ["fact:3"]), CTX, notes, gaps, "5 Series US threshold", False)
    assert weak["basis"] == "assumption"


def test_projected_needs_a_trend_and_gaps_are_recorded():
    notes, gaps = [], []
    assert specify.check_level(lv(650, "projected", ["research:5"]), CTX, notes, gaps, "5 Series US target", False)["basis"] == "projected"
    assert specify.check_level(lv(650, "projected", []), CTX, notes, gaps, "5 Series US target", False)["basis"] == "assumption"
    g = specify.check_level(lv(123, "gap", [], "rival boot volume"), CTX, notes, gaps, "5 Series US threshold", False)
    assert g["value"] is None and any("5 Series" in x and "US" in x for x in gaps)


def test_validate_orders_rungs_fills_missing_targets_and_labels_assumptions():
    s = specify.Spec(req_key="rq:x:0", keep_previous=False,
                     metric=specify.Metric(name="Real-world highway range", unit="km", direction="higher", method="m", conditions="c"),
                     acceptance=[specify.Acceptance(criterion="c", condition="d", pass_threshold="p")] * 6,
                     ladder=[specify.Rung(line="5 Series", market="US", baseline=None,
                                          threshold=specify.Level(**lv(727.4, "cited", ["fact:1"])),
                                          target=specify.Level(**lv(650, "projected", ["research:5"])), stretch=None,
                                          recommended="target", rationale="r"),
                             specify.Rung(line="7 Series", market="US", baseline=None, threshold=specify.Level(**lv(1, "gap", [])),
                                          target=specify.Level(**lv(1, "gap", [])), stretch=None, recommended="target", rationale="r")],
                     gaps=[], assumptions=[], change_note=None)
    v = specify.validate(s, CTX)
    assert len(v["acceptance"]) == 4 and set(v["acceptance"][0]) == {"criterion", "condition", "pass"}
    us = next(r for r in v["ladder"] if r["market"] == "US")
    assert us["target"]["value"] >= us["threshold"]["value"]          # swapped back into the metric direction
    assert [r["line"] for r in v["ladder"]].count("7 Series") == 0      # not a target of this requirement
    cn = next(r for r in v["ladder"] if r["market"] == "CN")            # missing target → all-gap rung
    assert cn["target"]["basis"] == "gap" and cn["rationale"].startswith("[assumption")
    assert v["fact_ids"] == ["fact:1"]


def test_define_validate_market_evidence_and_horizon():
    ctx = {"kind": "improve", "aspect_hint": ["range"], "comments_by_line_market": {"5 Series:US": 12, "5 Series:EU": 1},
           "findings": [{"id": "insight:a", "comments": 12}],
           "evidence": [{"id": "research:5", "relation": "trend_for", "published": "2026-01-02", "market": "CN"},
                        {"id": "study:3", "relation": "supports", "line": "7 Series", "market": "CN"}]}
    d = define.ReqDraft(replaces=None, title="t", statement="s", aspects=["range", "bogus", "charging_speed"],
                        decision_type="raise_capability", today_status="standard",
                        targets=[define.Target(line="5 Series", market="US", note="n"), define.Target(line="5 Series", market="EU", note="n"),
                                 define.Target(line="1 Series", market="US", note="invalid"), define.Target(line="7 Series", market="CN", note="n")],
                        horizon="at_successor_launch", horizon_year=2030, kano="performance", evidence_ids=["insight:a", "study:3", "x:1"],
                        trend_ids=[], assumptions=[], change_note=None)
    row, notes = define.validate(d, ctx)
    assert row["aspects"] == ["range", "charging_speed"] and row["domain"] == "powertrain" and row["zones"] == ["underfloor", "charging"]
    assert row["horizon"] == "today" and row["horizon_year"] is None    # no dated trend id cited
    assert row["today_status"] == "unknown"                             # no option evidence in the area
    t = {(x["line"], x["market"]): x for x in row["targets"]}
    assert ("1 Series", "US") not in t                                  # not sold there
    assert t[("5 Series", "US")]["own_evidence"] and t[("7 Series", "CN")]["own_evidence"]   # comments / study
    assert not t[("5 Series", "EU")]["own_evidence"] and t[("5 Series", "EU")]["note"].startswith("[assumption")
    assert row["evidence_ids"] == ["insight:a", "study:3"]


def test_domains_and_candidate_pairs():
    assert domain_for(["other", "range"]) == "powertrain" and zones_for([]) == ["cabin"]
    assert shared_resources(["range"], ["handling_steering"]) == ["mass"]
    reqs = [{"key": f"rq:{i}", "aspects": a, "zones": zones_for(a), "lines": l} for i, (a, l) in enumerate([
        (["range"], ["5 Series"]), (["handling_steering"], ["5 Series"]), (["paint_body"], ["5 Series"]),
        (["range"], ["1 Series"]), (["efficiency"], ["5 Series", "7 Series"])])]
    pairs = {(a, b) for a, b, _ in couple.candidates(reqs)}
    assert ("rq:0", "rq:1") in pairs and ("rq:0", "rq:4") in pairs
    assert not any("rq:2" in p for p in pairs)                          # draws on no resource
    assert ("rq:0", "rq:3") not in pairs                                # no shared line
    many = [{"key": f"rq:{i:02d}", "aspects": ["range"], "zones": ["underfloor"], "lines": ["5 Series"]} for i in range(30)]
    deg = {}
    for a, b, _ in couple.candidates(many, max_n=5):
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    assert max(deg.values()) <= 5


def test_bundles_skip_weak_and_removed_links():
    from api.routers.definition import bundles

    links = [{"a": "A", "b": "B", "relation": "conflicts", "via": "mass", "strength": 3, "review": None},
             {"a": "B", "b": "C", "relation": "synergy", "via": "energy", "strength": 2, "review": None},
             {"a": "C", "b": "D", "relation": "synergy", "via": "energy", "strength": 1, "review": None},
             {"a": "E", "b": "F", "relation": "enables", "via": "compute", "strength": 3, "review": {"verdict": "removed"}}]
    out = bundles(links)
    assert [b["keys"] for b in out] == [["A", "B", "C"]] and out[0]["conflict"]


# ------------------------------------------------------------------------------------------------ API smoke


@pytest.fixture
def client(tmp_path, monkeypatch, real_db_url):
    from fastapi.testclient import TestClient

    from api import deps
    from api.main import app
    from bmw_req.llm import client as llm_client

    data = tmp_path / "data"
    data.mkdir()
    (data / "models").mkdir()
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setattr(llm_client.LLM, "__init__", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no paid calls in tests")))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def test_api_smoke(client):
    r = client.get("/api/definition?cp=cp1")
    assert r.status_code == 200
    d = r.json()
    assert {"checkpoint", "ready", "runs", "domains", "resources", "zones", "models", "requirements", "links", "bundles"} <= set(d)
    assert set(d["models"]) == {"1 Series", "5 Series", "7 Series"}
    assert client.get("/api/definition?cp=cp9").status_code == 404
    if not d["requirements"]:
        pytest.skip("no definition run in the demo DB yet")
    q = d["requirements"][0]
    assert {"key", "version", "area_key", "title", "domain", "zones", "metric", "acceptance", "ladder", "gaps", "evidence_count"} <= set(q)
    one = client.get(f"/api/definition/requirement/{q['key']}?cp=cp1").json()
    assert {"evidence", "facts", "area", "history"} <= set(one)
    line, market = (q["ladder"][0]["line"], q["ladder"][0]["market"]) if q["ladder"] else (q["lines"][0], q["markets"][0])
    assert client.post("/api/definition/choice", json={"key": q["key"], "line": line, "market": market, "level": "target",
                                                       "rationale": "no"}).status_code == 409
    ok = client.post("/api/definition/choice", json={"key": q["key"], "line": line, "market": market, "level": "stretch",
                                                     "rationale": "Flagship needs the delighter", "actor": "Test PM"})
    assert ok.status_code == 200
    again = client.get("/api/definition?cp=cp1").json()
    rung = next(r for x in again["requirements"] if x["key"] == q["key"] for r in x["ladder"] if r["line"] == line and r["market"] == market) \
        if q["ladder"] else None
    if rung:
        assert rung["choice"]["level"] == "stretch" and rung["choice"]["actor"] == "Test PM"
    other = d["requirements"][1]["key"]
    lr = client.post("/api/definition/link-review", json={"a": other, "b": q["key"], "relation": "synergy", "verdict": "added",
                                                          "via": "energy", "strength": 2, "rationale": "Both use the same energy budget"})
    assert lr.status_code == 200 and lr.json()["review"]["a"] == min(other, q["key"])

    with connect() as c:
        assert c.execute("SELECT COUNT(*) FROM audit_event WHERE actor_type = 'human' AND action IN ('choose_level', 'link_added')").fetchone()[0] >= 2
        with pytest.raises(psycopg.Error):
            c.execute("DELETE FROM def_choice")


def test_metric_flag_wants_tangible_quantities():
    sat = {"name": "Share of target customers rating ride comfort at least 6 of 7", "unit": "%"}
    assert specify.metric_flag(sat, ["ride_comfort"])
    assert specify.metric_flag(sat, ["exterior_design"]) is None          # perception aspect: study share is fine
    task = {"name": "Share of first-time users who complete destination entry in ≤ 3 steps", "unit": "%"}
    assert specify.metric_flag(task, ["display_ui"]) is None and specify.metric_flag(task, ["parking_aids"])
    assert specify.metric_flag({"name": "Real-world highway range at 120 km/h", "unit": "km"}, ["range"]) is None
