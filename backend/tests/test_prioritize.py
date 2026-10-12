"""Prioritization (D-050): deterministic prio-v1 parts on a synthetic context (factors, renormalisation, rung → effort,
bundle band, choose-jointly flag) and an end-to-end + API smoke test on a throwaway clone of the real data (no LLM)."""

from __future__ import annotations

import json
import psycopg
import pytest

from bmw_req.db import connect
from bmw_req.prioritize import factors as S
from bmw_req.prioritize import score as P


def req(key="rq:a:0", decision="raise_capability", kano="performance", horizon="today", aspects=("climate",), targets=None,
        evidence=(), trends=(), area="ar:a"):
    targets = targets or [{"line": "5 Series", "market": "US", "own_evidence": True, "comments": 40}]
    return {"key": key, "version": 1, "area_key": area, "decision_type": decision, "kano": kano, "horizon": horizon,
            "horizon_year": None, "aspects_json": json.dumps(list(aspects)), "targets_json": json.dumps(targets),
            "evidence_ids_json": json.dumps(list(evidence)), "trend_ids_json": json.dumps(list(trends))}


def lv(value, basis="cited"):
    return {"value": value, "text": str(value), "basis": basis, "source_ids": [], "note": ""}


def spec(key="rq:a:0", direction="higher", baseline=None, threshold=None, recommended="target"):
    return {"req_key": key, "metric_json": json.dumps({"name": "m", "unit": "km", "direction": direction}),
            "ladder_json": json.dumps([{"line": "5 Series", "market": "US", "baseline": baseline,
                                        "threshold": threshold or lv(None, "gap"), "target": lv(None, "gap"), "stretch": None,
                                        "recommended": recommended, "rationale": "r"}])}


def ctx(reqs, specs=None, by_line_market=None, base=None, edges=None, src=None, study=None, links=None, choices=None, fit=None):
    study = study or {}
    return {"cp": "cp1", "runs": {}, "reqs": reqs, "specs": {s["req_key"]: s for s in (specs or [])},
            "areas": {"ar:a": {"metrics": {"by_line_market": by_line_market or {"5 Series:US": 40}}, "themes": ["th:1"]}},
            "edges": {"th:1": edges or []}, "src": src or {}, "study": study,
            "by_item": {(s["item"], s["vehicle_model_id"], s["market_code"]): s for s in study.values()},
            "base": base or {"5 Series:US": 1000, "5 Series:CN": 10, "5 Series:EU": 100},
            "market": {"bmw_weight": {"5 Series:US": 0.2, "5 Series:CN": 0.1, "5 Series:EU": 0.25}, "public_trend": {}, "conflicts": []},
            "choices": choices or {}, "links": links or [], "fit": fit or {}, "spec_tracks": {}}


W = P.DEFAULT_WEIGHTS


def test_customer_voice_shrinks_borrows_and_caps_shape():
    r = req(targets=[{"line": "5 Series", "market": "US"}, {"line": "5 Series", "market": "CN"}])
    c = ctx([r], by_line_market={"5 Series:US": 40, "5 Series:CN": 0, "5 Series:EU": 5})
    v, expl, observed, n = P.customer_voice(c, r, "5 Series", "US")
    assert observed and n == 40 and "40 of 1000" in expl
    prior = 45 / 1110
    assert v == pytest.approx(S.voice_curve(100 * S.shrink(40, 1000, prior) * P.MEDIUM))
    cv, cexpl, cobs, _ = P.customer_voice(c, r, "5 Series", "CN")       # 10 comments < 30: borrowed at ×0.5
    assert not cobs and "borrowed" in cexpl and cv == pytest.approx(0.5 * S.voice_curve(100 * 45 / 1100 * P.MEDIUM))


def test_satisfaction_gap_improve_vs_keep_strength():
    study = {1: {"id": 1, "item": "Air conditioning", "vehicle_model_id": "G60", "market_code": "US", "z": -1.2},
             2: {"id": 2, "item": "Handling", "vehicle_model_id": "G60", "market_code": "US", "z": 1.6}}
    imp = req(evidence=["study:1"])
    assert P.satisfaction_gap(ctx([imp], study=study), imp, "5 Series", "US")[0] == pytest.approx(0.6)
    keep = req(decision="keep_strength", evidence=["study:2"])
    v, e = P.satisfaction_gap(ctx([keep], study=study), keep, "5 Series", "US")
    assert v == pytest.approx(0.8) and "must-not-lose" in e
    assert P.satisfaction_gap(ctx([imp], study=study), imp, "5 Series", "CN")[0] is None     # no CN column for that item
    assert P.satisfaction_gap(ctx([req()]), req(), "5 Series", "US")[0] is None


def test_competitive_gap_numeric_then_fallback():
    r = req()
    num = P.competitive_gap(ctx([r]), r, spec(baseline=lv(500), threshold=lv(550)), "5 Series", "US")
    assert num[2] == "numeric" and num[0] == pytest.approx(0.5)                  # 10 % behind / 20 % = 0.5
    low = P.competitive_gap(ctx([r]), r, spec(direction="lower", baseline=lv(30), threshold=lv(36)), "5 Series", "US")
    assert low[0] == 0.0 and "ahead" in low[1]                                   # lower is better and BMW is lower
    edges = [("research", "7", "competes_with"), ("research", "8", "competes_with")]
    src = {7: {"trust_tier": "T1", "market_code": "US"}, 8: {"trust_tier": "T3", "market_code": "CN"}}
    fb = P.competitive_gap(ctx([r], edges=edges, src=src), r, spec(), "5 Series", "US")
    assert fb[2] == "fallback" and fb[0] == pytest.approx(0.25) and fb[1].startswith("fallback")   # only the US source
    none = P.competitive_gap(ctx([r]), r, spec(), "5 Series", "US")
    assert none[2] == "none" and none[0] == 0.0


def test_renormalisation_drops_missing_factors():
    base, wsum = S.renormalised({"customer_voice": (0.5, ""), "satisfaction_gap": (None, ""), "future_relevance": (1.0, "")}, W)
    assert wsum == 50 and base == pytest.approx((30 * 0.5 + 20 * 1.0) / 50)
    r = req(targets=[{"line": "5 Series", "market": "US"}])
    b = P.score_target(ctx([r], specs=[spec()]), r, "5 Series", "US", W)
    assert "Satisfaction gap" in b["gaps"] and b["factors"]["satisfaction_gap"]["points"] is None
    assert sum(f["points"] or 0 for f in b["factors"].values()) == pytest.approx(100 * (b["base"] / 100) * b["confidence"], abs=0.3)


def test_rung_changes_effort_and_choice_wins():
    r = req(decision="change_design", aspects=("display_ui",))          # M; display_ui draws on 3 resources → L
    assert P.effort(r, "target")[0] == "L" and P.effort(r, "threshold")[0] == "M" and P.effort(r, "baseline")[0] == "S"
    assert P.effort(req(decision="keep_strength"), "stretch")[0] == "M"
    c = ctx([r], specs=[spec(recommended="target")],
            choices={("rq:a:0", "5 Series", "US"): {"level": "threshold", "rationale": "x", "actor": "PM", "created_at": "t"}})
    b = P.score_target(c, r, "5 Series", "US", W)
    assert b["rung"]["chosen"] == "threshold" and b["rung"]["by"] == "pm" and b["modifiers"]["effort"] == S.EFFORT_MOD["M"]
    w = P.score_target(c, r, "5 Series", "US", W, rung_override="stretch")
    assert w["rung"]["by"] == "what_if" and w["modifiers"]["effort"] == S.EFFORT_MOD["L"]


def _b(score, band, observed=True):
    return {"score": score, "priority": band, "voice_observed": observed, "modifiers": {}, "factors": {}, "gates": {}}


def test_bundle_shares_strongest_band_and_conflict_flags_two_musts():
    links = [{"a": "A", "b": "B", "relation": "synergy", "via": "energy", "strength": 2, "review": None},
             {"a": "B", "b": "C", "relation": "enables", "via": "compute", "strength": 1, "review": None},   # weak: not bundled
             {"a": "A", "b": "D", "relation": "conflicts", "via": "mass", "strength": 2, "review": None},
             {"a": "C", "b": "D", "relation": "competes_for", "via": "package", "strength": 1, "review": None}]
    res = {("A", "5 Series", "US"): _b(65, "Must"), ("B", "5 Series", "US"): _b(40, "Could"),
           ("C", "5 Series", "US"): _b(62, "Must"), ("D", "5 Series", "US"): _b(61, "Must"), ("B", "5 Series", "CN"): _b(30, "Could")}
    bundles, _ = P.apply_links(ctx([], links=links), res)
    assert len(bundles) == 1 and bundles[0]["keys"] == ["A", "B"]
    assert res[("B", "5 Series", "US")]["priority"] == "Must" and res[("B", "5 Series", "US")]["own_priority"] == "Could"
    assert res[("B", "5 Series", "US")]["score"] == 40                       # score untouched
    assert res[("B", "5 Series", "CN")]["priority"] == "Could"               # A has no CN target: own band
    assert bundles[0]["band_by_target"] == {"5 Series:CN": "Could", "5 Series:US": "Must"}
    assert [j["with"] for j in res[("A", "5 Series", "US")]["joint"]] == ["D"]   # strength-1 C–D: info only
    assert "joint" not in res[("C", "5 Series", "US")]


def test_enabler_credit_and_cap():
    links = [{"a": "A", "b": "B", "relation": "enables", "via": "compute", "strength": 3, "direction": "a_to_b", "review": None},
             {"a": "C", "b": "A", "relation": "enables", "via": "energy", "strength": 2, "direction": "b_to_a", "review": None}]
    cr = P.enabler_credit(ctx([], links=links), {("A", "5 Series", "US"): 60.0, ("B", "5 Series", "US"): 50.0, ("C", "5 Series", "US"): 80.0})
    assert cr[("A", "5 Series", "US")][0] == pytest.approx(min(0.5, 1 * 0.5 + 2 / 3 * 0.8))
    assert ("B", "5 Series", "US") not in cr


def test_no_comment_market_capped_by_commented_market():
    r = req(kano="performance")
    us, cn = _b(50, "Should"), _b(58, "Should", observed=False)
    for b in (us, cn):
        b["factors"] = {"satisfaction_gap": {"value": 0.2}, "competitive_gap": {"value": 0.9}}
    P.requirement_rules(r, [("5 Series", "US", us), ("5 Series", "CN", cn)])
    assert cn["score"] == 50 and cn["modifiers"]["no_comment_cap"] == -8.0


# ------------------------------------------------------------------------------------------------ DB + API


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


def test_run_proposal_and_api(client):
    from bmw_req.checkpoints import latest_run
    from bmw_req.db import connect

    conn = connect()
    if not latest_run(conn, "cp1", "define") or not latest_run(conn, "cp1", "specify"):
        pytest.skip("no definition runs in the demo DB yet")
    first = P.run(conn, "cp1")
    assert first["targets"] > 0 and sum(first["by_band"].values()) == first["targets"]
    d = client.get("/api/prioritize?cp=cp1").json()
    assert d["ready"] and d["runs"]["prioritize"]["id"] == first["run_id"]
    assert {"checkpoint", "weights", "labels", "lines", "markets", "targets", "bundles", "proposals", "summary"} <= set(d)
    t = d["targets"][0]
    assert {"key", "title", "line", "market", "score", "band", "confidence", "factors", "modifiers", "gates", "flags", "rung",
            "rationale", "confirmed", "prev"} <= set(t)
    assert {f["dimension"] for f in t["factors"]} == {"customer", "business", "future"}
    assert client.get("/api/prioritize?cp=cp9").status_code == 404
    one = client.get(f"/api/prioritize/target/{t['key']}", params={"line": t["line"], "market": t["market"], "cp": "cp1"}).json()
    assert one["history"] and "evidence" in one
    wi = client.get("/api/prioritize/what-if", params={"key": t["key"], "line": t["line"], "market": t["market"], "level": "baseline",
                                                       "cp": "cp1"}).json()
    assert wi["effort"] == "S" and {"score", "band", "delta", "modifiers", "confidence", "exposures"} <= set(wi)
    assert all({"key", "via", "relation"} <= set(e) for e in wi["exposures"])
    assert {"scheme", "version", "factors", "bands"} <= set(d["weights"]) and d["weights"]["bands"]["Must"] == 60
    assert all("|" not in f or f.split("|")[0] in ("choose_jointly", "bundle_band") for x in d["targets"] for f in x["flags"])
    other = next(b for b in ("Must", "Should", "Could") if b != t["band"])
    assert client.post("/api/prioritize/decision", json={"key": t["key"], "line": t["line"], "market": t["market"],
                                                         "priority": other, "rationale": "no"}).status_code == 409
    ok = client.post("/api/prioritize/decision", json={"key": t["key"], "line": t["line"], "market": t["market"], "priority": other,
                                                       "rationale": "PM sees a stronger case", "actor": "Test PM", "cp": "cp1",
                                                       "override_brand": True})
    assert ok.status_code == 200, ok.text
    second = P.run(conn, "cp1")                 # the AI band now differs from the PM-confirmed band → proposal
    assert second["proposals"] >= 1
    props = [p for p in client.get("/api/prioritize?cp=cp1").json()["proposals"] if p["key"] == t["key"] and p["status"] == "open"]
    assert props and props[0]["old_band"] == other and props[0]["proposed_band"] == t["band"] and props[0]["cause"]
    assert set(props[0]["factor_delta"]) == set(P.DEFAULT_WEIGHTS)
    r = client.post(f"/api/prioritize/proposal/{props[0]['id']}", json={"verdict": "accept", "rationale": "Agree with the AI", "actor": "Test PM"})
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert client.post(f"/api/prioritize/proposal/{props[0]['id']}", json={"verdict": "reject", "rationale": "again"}).status_code == 409
    again = client.get("/api/prioritize?cp=cp1").json()
    tt = next(x for x in again["targets"] if (x["key"], x["line"], x["market"]) == (t["key"], t["line"], t["market"]))
    assert tt["confirmed"]["priority"] == t["band"]

    with connect() as c:
        assert c.execute("SELECT COUNT(*) FROM audit_event WHERE actor_type = 'human' AND action IN ('confirm_priority', 'proposal_accepted')"
                         ).fetchone()[0] >= 3
        assert c.execute("SELECT COUNT(*) FROM audit_event WHERE actor_id = 'structure.prioritize' AND action = 'rescore'").fetchone()[0] > 0
        with pytest.raises(psycopg.Error):
            c.execute("DELETE FROM prio_decision")


# ------------------------------------------------------------------------------------------------ weights, preview, auto re-score
def test_bands_from_weights_and_validation():
    assert P.band_for(59.9) == "Should" and P.band_for(60) == "Must" and P.band_for(44) == "Could"
    assert P.band_for(50, {"Must": 50, "Should": 30}) == "Must" and P.band_for(29, {"Must": 50, "Should": 30}) == "Could"
    r = req(targets=[{"line": "5 Series", "market": "US"}])
    c = ctx([r], specs=[spec()])
    b = P.score_target(c, r, "5 Series", "US", W)
    lo = P.score_target(c, r, "5 Series", "US", W, bands={"Must": max(1.0, b["score"] - 1), "Should": max(0.5, b["score"] - 2)})
    assert lo["priority"] == "Must" and lo["score"] == b["score"] and lo["bands"]["Must"] == max(1.0, b["score"] - 1)
    for bad_w, bad_b in [({**W, "customer_voice": -1}, None), ({k: 0 for k in W}, None), ({"customer_voice": 1}, None),
                         (W, {"Must": 40, "Should": 45}), (W, {"Must": 101, "Should": 45}), (W, {"Must": 60, "Should": 0})]:
        with pytest.raises(ValueError):
            P.validate(bad_w, bad_b)


def _counts():
    with connect() as c:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("prio_score", "prio_proposal", "prio_decision", "weights_version", "audit_event", "checkpoint_run")}


def _need_runs(conn, *cps):
    from bmw_req.checkpoints import latest_run

    for cp in cps:
        if not latest_run(conn, cp, "prioritize"):
            pytest.skip(f"no prioritize run at {cp} in the demo DB")


def test_preview_changes_bands_without_writes(client):
    from bmw_req.db import connect

    _need_runs(connect(), "cp1")
    before = _counts()
    cur = client.get("/api/prioritize?cp=cp1").json()["weights"]
    same = client.post("/api/prioritize/preview", json={"factors": cur["factors"], "bands": cur["bands"], "cp": "cp1"}).json()
    assert same["summary"]["changes"] == 0 and same["summary"]["targets"] > 0     # same weights reproduce the stored run
    low = client.post("/api/prioritize/preview", json={"factors": cur["factors"], "bands": {"Must": 30, "Should": 10}, "cp": "cp1"}).json()
    assert low["summary"]["by_band"].get("Must", 0) > same["summary"]["by_band"].get("Must", 0) and low["changes"]
    assert all(c["prev_band"] != c["band"] for c in low["changes"]) and sum(low["summary"]["moves"].values()) == low["summary"]["changes"]
    one = client.post("/api/prioritize/preview", json={"factors": cur["factors"], "bands": cur["bands"], "cp": "cp1",
                                                       "line": same["targets"][0]["line"], "market": same["targets"][0]["market"]}).json()
    assert one["targets"] and {(t["line"], t["market"]) for t in one["targets"]} == {(same["targets"][0]["line"], same["targets"][0]["market"])}
    assert client.post("/api/prioritize/preview", json={"factors": cur["factors"], "bands": {"Must": 40, "Should": 50},
                                                        "cp": "cp1"}).status_code == 409
    assert _counts() == before


def test_weights_save_rescore_proposes_against_confirmed_band(client, monkeypatch):
    from api import rescore
    from bmw_req.checkpoints import latest_run
    from bmw_req.db import connect

    conn = connect()
    _need_runs(conn, "cp1")
    monkeypatch.setattr(rescore, "MODE", "sync")
    d = client.get("/api/prioritize?cp=cp1").json()
    t = next(x for x in d["targets"] if x["band"] == "Should" and not x["confirmed"])
    ok = client.post("/api/prioritize/decision", json={"key": t["key"], "line": t["line"], "market": t["market"], "priority": "Should",
                                                       "rationale": "PM agrees with Should", "actor": "Test PM", "cp": "cp1"})
    assert ok.status_code == 200 and ok.json()["rescore"] in ("sync", "none")
    bands = {"Must": 99.0, "Should": min(98.0, t["score"] + 1)}       # the target drops to Could under these thresholds
    pv = client.post("/api/prioritize/preview", json={"factors": d["weights"]["factors"], "bands": bands, "cp": "cp1"}).json()
    assert any((a["key"], a["line"], a["market"]) == (t["key"], t["line"], t["market"]) for a in pv["decisions_affected"])
    assert client.post("/api/prioritize/weights", json={"factors": d["weights"]["factors"], "bands": bands,
                                                        "rationale": " "}).status_code >= 400   # rationale required
    old_run = latest_run(conn, "cp1", "prioritize")["id"]
    r = client.post("/api/prioritize/weights", json={"factors": d["weights"]["factors"], "bands": bands, "rationale": "Stricter Should bar",
                                                     "actor": "Test PM"})
    assert r.status_code == 200, r.text
    assert r.json()["rescore"] == "sync" and r.json()["bands"] == bands
    assert r.json()["weights_version"] == d["weights"]["version"] + 1          # numbered within prio-v1, not the shared row id
    new_run = latest_run(conn, "cp1", "prioritize")
    assert new_run["id"] > old_run and json.loads(new_run["stats_json"])["trigger"] == "auto:weights_changed"
    after = client.get("/api/prioritize?cp=cp1").json()
    assert after["weights"]["version"] == r.json()["weights_version"] and after["weights"]["bands"] == bands
    tt = next(x for x in after["targets"] if (x["key"], x["line"], x["market"]) == (t["key"], t["line"], t["market"]))
    assert tt["band"] == "Could" and tt["confirmed"]["priority"] == "Should"          # PM decision untouched
    props = [p for p in after["proposals"] if (p["key"], p["line"], p["market"]) == (t["key"], t["line"], t["market"]) and p["status"] == "open"]
    assert len(props) == 1 and props[0]["cause"] == "weights_changed" and props[0]["old_band"] == "Should" and props[0]["against"] == "pm"
    hist = client.get("/api/prioritize/weights/history").json()
    assert hist["history"][0]["version"] == r.json()["weights_version"] and hist["history"][0]["rationale"] == "Stricter Should bar"
    with connect() as c:
        old, new = c.execute("SELECT old_value, new_value FROM audit_event WHERE action = 'change_weights' AND actor_type = 'human' "
                             "ORDER BY id DESC LIMIT 1").fetchone()
        assert json.loads(new)["bands"] == bands and json.loads(old)["bands"] == d["weights"]["bands"]
        assert c.execute("SELECT COUNT(*) FROM audit_event WHERE actor_id = 'structure.prioritize' AND action = 'auto_rescore'").fetchone()[0] >= 1
    assert client.post("/api/prioritize/weights", json={"factors": d["weights"]["factors"], "bands": {"Must": 10, "Should": 20},
                                                        "rationale": "bad"}).status_code == 409


def test_decision_at_cp1_auto_rescore_proposes_at_cp2(client, monkeypatch):
    from api import rescore
    from bmw_req.checkpoints import latest_run
    from bmw_req.db import connect

    conn = connect()
    _need_runs(conn, "cp1", "cp2")
    monkeypatch.setattr(rescore, "MODE", "sync")
    cp2 = {(x["key"], x["line"], x["market"]): x for x in client.get("/api/prioritize?cp=cp2").json()["targets"]}
    t = next(x for x in client.get("/api/prioritize?cp=cp1").json()["targets"]
             if (x["key"], x["line"], x["market"]) in cp2 and not x["confirmed"])
    tk = (t["key"], t["line"], t["market"])
    other = next(b for b in ("Must", "Should", "Could") if b != cp2[tk]["band"])
    old_cp2 = latest_run(conn, "cp2", "prioritize")["id"]
    ok = client.post("/api/prioritize/decision", json={"key": t["key"], "line": t["line"], "market": t["market"], "priority": other,
                                                       "rationale": "PM sees a different case", "actor": "Test PM", "cp": "cp1",
                                                       "override_brand": True})
    assert ok.status_code == 200 and ok.json()["rescore"] == "sync"
    new_cp2 = latest_run(conn, "cp2", "prioritize")
    assert new_cp2["id"] > old_cp2 and json.loads(new_cp2["stats_json"])["trigger"] == "auto:decision"

    def open_props():
        return [p for p in client.get("/api/prioritize?cp=cp2").json()["proposals"]
                if (p["key"], p["line"], p["market"]) == tk and p["status"] == "open"]

    props = open_props()
    assert len(props) == 1 and props[0]["old_band"] == other and props[0]["proposed_band"] == cp2[tk]["band"]
    assert props[0]["against"] == "pm" and props[0]["run_id"] == new_cp2["id"]
    from bmw_req.prioritize.auto import rescore as rescore_now

    rescore_now(conn, "cp1", "test", include_self=False)          # again: the old proposal is superseded, never duplicated
    assert len(open_props()) == 1
    rj = client.post(f"/api/prioritize/proposal/{open_props()[0]['id']}", json={"verdict": "reject", "rationale": "Keep my band",
                                                                                 "actor": "Test PM"})
    assert rj.status_code == 200 and rj.json()["rescore"] == "none"   # nothing after cp2
    rescore_now(conn, "cp2", "test")
    assert open_props() == []                                         # a rejected move isn't re-proposed until the score moves


def test_cp1_payload_never_shows_cp2_proposals(client, monkeypatch):
    from api import rescore
    from bmw_req.db import connect

    conn = connect()
    _need_runs(conn, "cp1", "cp2")
    monkeypatch.setattr(rescore, "MODE", "sync")
    cp2 = client.get("/api/prioritize?cp=cp2").json()
    t = next(x for x in cp2["targets"] if not x["confirmed"])
    other = next(b for b in ("Must", "Should", "Could") if b != t["band"])
    assert client.post("/api/prioritize/decision", json={"key": t["key"], "line": t["line"], "market": t["market"], "priority": other,
                                                         "rationale": "PM sees a different case", "actor": "Test PM", "cp": "cp1",
                                                         "override_brand": True}).status_code == 200
    run_cp = {r["id"]: r["checkpoint_id"] for r in conn.execute("SELECT id, checkpoint_id FROM checkpoint_run")}
    at2 = client.get("/api/prioritize?cp=cp2").json()["proposals"]
    assert any(run_cp[p["run_id"]] == "cp2" for p in at2)                       # the cp2 re-score proposed against the PM
    at1 = client.get("/api/prioritize?cp=cp1").json()["proposals"]
    assert [p for p in at1 if run_cp[p["run_id"]] != "cp1"] == []
    one = client.get(f"/api/prioritize/target/{t['key']}", params={"line": t["line"], "market": t["market"], "cp": "cp1"}).json()
    assert all(run_cp[p["run_id"]] == "cp1" for p in one["proposals"]) and all(h["checkpoint"] == "cp1" for h in one["history"])
    opens = {}
    for p in at2:
        if p["status"] == "open":
            k = (p["key"], p["line"], p["market"])
            assert k not in opens, "one open proposal per target"
            opens[k] = p
