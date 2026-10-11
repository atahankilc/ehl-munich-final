"""JSON API (api/): every read endpoint answers, PM writes are validated and audited, jobs run in the background,
static files can't escape their root, exports are logged.

Runs against a TEMP COPY of data/app.db (DATA_DIR points at a tmp dir) — the real DB is never written. Paid LLM work
(wave open, challenge) is monkeypatched; constructing the real OpenAI wrapper fails the test.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bmw_req.config import ROOT

REAL_DB = ROOT / "data" / "app.db"
pytestmark = pytest.mark.skipif(not REAL_DB.exists(), reason="needs the local demo DB (data/app.db)")


@pytest.fixture(scope="session")
def master_db(tmp_path_factory) -> Path:
    """One consistent copy of the demo DB (sqlite backup API reads WAL content too), opened read-only."""
    dst = tmp_path_factory.mktemp("master") / "app.db"
    src = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    src.backup(out)
    out.close()
    src.close()
    return dst


def _make_client(data_dir: Path, master: Path, mp: pytest.MonkeyPatch) -> TestClient:
    from api import deps
    from api.main import app
    from bmw_req.llm import client as llm_client

    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(master, data_dir / "app.db")
    (data_dir / "models").mkdir(exist_ok=True)
    mp.setenv("DATA_DIR", str(data_dir))

    def no_paid_calls(*a, **k):
        raise RuntimeError("tests must never construct the real OpenAI wrapper")

    mp.setattr(llm_client.LLM, "__init__", no_paid_calls)
    deps.DB.close()
    return TestClient(app)


@pytest.fixture(scope="module")
def ro(tmp_path_factory, master_db):
    """Shared client for read-only tests."""
    from api import deps

    mp = pytest.MonkeyPatch()
    c = _make_client(tmp_path_factory.mktemp("ro"), master_db, mp)
    yield c
    deps.DB.close()
    mp.undo()


@pytest.fixture
def rw(tmp_path, master_db, monkeypatch):
    """Fresh DB copy per write test."""
    from api import deps

    c = _make_client(tmp_path / "data", master_db, monkeypatch)
    yield c
    deps.DB.close()


def _db(client_dir_env=None) -> sqlite3.Connection:
    from bmw_req.config import get_settings

    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _audit_count(action: str, **eq) -> int:
    where = " AND ".join(f"{k} = ?" for k in eq)
    with _db() as c:
        return c.execute("SELECT COUNT(*) FROM audit_event WHERE action = ?" + (f" AND {where}" if where else ""),
                         (action, *eq.values())).fetchone()[0]


def _first(sql: str, params=()):
    with _db() as c:
        return c.execute(sql, params).fetchone()


# ------------------------------------------------------------------------------------------------ reads
def test_every_get_answers_with_key_fields(ro):
    meta = ro.get("/api/meta").json()
    assert {"vehicles", "markets", "targets", "labels", "priority_bands", "scoring", "enums", "waves", "zones"} <= set(meta)
    assert meta["priority_bands"] == {"Must": 60.0, "Should": 45.0}
    assert {"key", "label", "vehicle", "market"} <= set(meta["targets"][0])

    st = ro.get("/api/state").json()
    assert {"current_wave", "next_wave", "spend_usd", "budget", "running_job", "counts"} <= set(st)
    assert set(st["counts"]["open_by_kind"]) >= {"priority", "extend", "new_requirement"}

    b = ro.get("/api/briefing").json()
    assert {"wave", "run", "headline", "movers", "new_requirements", "feed", "pulse", "decisions_waiting"} <= set(b)
    assert len(b["pulse"]) == 10 and len(b["feed"]) <= 25 and len(b["movers"]) <= 8
    assert {"new_requirements", "priority_changes", "risers", "fallers", "merges_open", "conflicts"} == set(b["headline"])

    q = ro.get("/api/queue").json()
    assert q["items"] and {"uid", "type", "kind", "req_id", "title", "subtitle", "score", "priority", "target"} <= set(q["items"][0])
    uids = [i["uid"] for i in q["items"]]
    assert len(uids) == len(set(uids))
    # new_requirement proposals are folded into their requirement item, never listed twice
    folded = {i["req_id"] for i in q["items"] if i.get("is_new_in_wave")}
    assert not any(i["kind"] == "new_requirement" and i["req_id"] in folded for i in q["items"])
    assert q["counts"]["requirements"] == sum(i["type"] == "requirement" for i in q["items"])
    qt = ro.get("/api/queue", params={"target": "G60×US"}).json()
    assert all(i["target"] is None or i["target"]["key"] == "G60×US" for i in qt["items"] if i["type"] == "requirement")
    assert ro.get("/api/queue", params={"target": "nonsense"}).status_code == 422

    props = ro.get("/api/proposals", params={"status": "all"}).json()
    assert {"id", "kind", "status", "requirement_id", "target", "delta", "created_at"} <= set(props[0])

    reqs = ro.get("/api/requirements").json()
    assert reqs and all(r["status"] != "rejected" for r in reqs)
    r0 = reqs[0]
    assert {"id", "max_score", "best_target", "zone", "brand_blocked", "targets"} <= set(r0)
    assert {"target", "score", "ai_priority", "pm_priority", "priority", "ai_only", "brand_gate", "rank"} <= set(r0["targets"][0])
    assert ro.get("/api/requirements", params={"vehicle": "G68", "market": "CN"}).json()

    rid = r0["id"]
    d = ro.get(f"/api/requirements/{rid}").json()
    assert {"targets", "derivation", "assumptions_list", "quotes", "study", "web", "fit", "open_proposals",
            "challenges", "contradicting", "overridden"} <= set(d)
    t = d["targets"][0]
    assert {"breakdown", "voice"} <= set(t) and "voice_base" in (t["breakdown"] or {"voice_base": None})
    assert "derivation_json" not in d
    assert ro.get("/api/requirements/REQ-9999").status_code == 404

    for sub in ("history", "evidence", "audit", "trace"):
        assert ro.get(f"/api/requirements/{rid}/{sub}").status_code == 200, sub
    tr = ro.get(f"/api/requirements/{rid}/trace").json()
    assert set(tr["steps"]) == {"collect", "read", "group", "draft", "fit", "score", "decide", "repeat"}
    assert ro.get(f"/api/requirements/{rid}/audit", params={"human_only": True}).json() is not None

    cars = ro.get("/api/cars").json()
    assert [c["vehicle"] for c in cars] == ["F70", "G60", "G68", "G70"]
    car = ro.get("/api/cars/G60", params={"market": "US"}).json()
    assert {"markets", "model", "zones", "requirements", "comparison", "market_profile", "competitors", "equipment",
            "production"} <= set(car)
    assert car["requirements"] and all(r["zone"] in car["zones"] for r in car["requirements"])
    assert "price" not in json.dumps(car["equipment"])
    g68 = ro.get("/api/cars/G68").json()
    assert g68["market"] == "CN" and g68["model"]["shared_with"] == "G60"
    assert ro.get("/api/cars/X99").status_code == 404
    assert ro.get("/api/cars/G68", params={"market": "US"}).status_code == 404

    f = ro.get("/api/findings", params={"limit": 5}).json()
    assert {"total", "used", "uncovered", "metrics_wave", "items"} <= set(f) and len(f["items"]) <= 5
    fid = f["items"][0]["id"]
    assert "used_by" in ro.get(f"/api/findings/{fid}").json()
    srcs = ro.get(f"/api/findings/{fid}/sources").json()
    assert all("price_eur" not in s["meta"] for s in srcs)
    sigs = ro.get(f"/api/findings/{fid}/signals").json()
    assert all("source" in s for s in sigs)
    assert ro.get("/api/findings/99999999").status_code == 404
    assert {"n_issues", "items"} <= set(ro.get("/api/quality").json())

    waves = ro.get("/api/waves").json()
    assert [w["n"] for w in waves] == [1, 2, 3] and {"state", "brought", "run"} <= set(waves[0])
    assert isinstance(ro.get("/api/runs").json(), list)
    diff = ro.get("/api/runs/diff")
    assert diff.status_code in (200, 409)
    if diff.status_code == 200:
        assert {"weight_changes", "rows", "stats"} <= set(diff.json())
    assert {"current", "defaults", "labels"} <= set(ro.get("/api/weights").json())
    au = ro.get("/api/audit", params={"limit": 10, "actor_type": "human"}).json()
    assert len(au["items"]) <= 10 and all(e["actor_type"] == "human" for e in au["items"])
    assert {"spent", "thresholds", "by_job"} <= set(ro.get("/api/budget").json())
    assert "extractor_version" in ro.get("/api/pipeline/stats").json()
    assert isinstance(ro.get("/api/demo/snapshots").json(), list)
    assert ro.get("/api/nope").status_code == 404


def test_briefing_and_car_answer_fast(ro):
    import time

    for path in ("/api/briefing", "/api/cars/G60?market=US", "/api/queue"):
        ro.get(path)   # warm
        t = time.perf_counter()
        assert ro.get(path).status_code == 200
        assert time.perf_counter() - t < 0.5, path


# ------------------------------------------------------------------------------------------------ writes
def _proposed_req(client) -> dict:
    return next(r for r in client.get("/api/requirements", params={"status": "proposed"}).json() if r["targets"])


def test_status_change_needs_a_rationale(rw):
    rid = _proposed_req(rw)["id"]
    r = rw.post(f"/api/requirements/{rid}/status", json={"status": "approved", "rationale": "ok"})
    assert r.status_code == 409 and "rationale" in r.json()["detail"].lower()
    assert rw.post(f"/api/requirements/{rid}/status", json={"status": "bogus", "rationale": "long enough"}).status_code == 422
    assert rw.post("/api/requirements/REQ-9999/status", json={"status": "deferred", "rationale": "long enough"}).status_code == 404


def test_approve_flow_accepts_ai_priorities_and_audits(rw):
    req = _proposed_req(rw)
    rid = req["id"]
    unset = [t["target"]["key"] for t in req["targets"] if t["pm_priority"] is None and t["ai_priority"]]
    before = _audit_count("set_status", entity_id=rid)
    r = rw.post(f"/api/requirements/{rid}/status", headers={"X-Actor": "Test%20PM%20K%C4%B1l%C4%B1%C3%A7"},
                json={"status": "approved", "rationale": "Strong evidence in the focus markets", "accept_ai_priorities": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requirement"]["status"] == "approved" and set(body["priorities_set"]) == set(unset)
    assert all(t["pm_priority"] == t["ai_priority"] for t in body["requirement"]["targets"] if t["target"]["key"] in unset)
    assert _audit_count("set_status", entity_id=rid) == before + 1
    ev = _first("SELECT actor_type, actor_id, new_value FROM audit_event WHERE action = 'set_status' ORDER BY id DESC LIMIT 1")
    assert (ev["actor_type"], ev["actor_id"], ev["new_value"]) == ("human", "Test PM Kılıç", "approved")
    q = rw.get("/api/queue").json()
    assert f"req:{rid}" not in {i["uid"] for i in q["items"]}
    assert f"req:{rid}" in {i["uid"] for i in rw.get("/api/queue", params={"include_decided": True}).json()["items"]}


def test_brand_fail_blocks_approval_until_overridden(rw):
    req = _proposed_req(rw)
    rid, t = req["id"], req["targets"][0]["target"]
    with _db() as c:
        c.execute("""INSERT INTO fit_check (requirement_id, vehicle_model_id, market_code, check_type, result, rationale,
                     checked_by) VALUES (?, ?, ?, 'brand', 'fail', 'test fail', 'test')""", (rid, t["vehicle"], t["market"]))
    assert rw.get(f"/api/requirements/{rid}").json()["brand_blocked"] == [t["key"]]
    r = rw.post(f"/api/requirements/{rid}/status", json={"status": "approved", "rationale": "Looks right to me"})
    assert r.status_code == 409 and "Brand-fit FAIL" in r.json()["detail"]
    assert rw.post(f"/api/requirements/{rid}/override", json={"target": "Z99×US", "rationale": "PM override"}).status_code == 404
    o = rw.post(f"/api/requirements/{rid}/override", json={"target": t["key"], "rationale": "Fits the brand after all"})
    assert o.status_code == 200 and o.json()["brand_blocked"] == []
    assert rw.get(f"/api/requirements/{rid}").json()["overridden"] == [t["key"]]
    assert rw.post(f"/api/requirements/{rid}/status", json={"status": "approved", "rationale": "Override recorded"}).status_code == 200


def test_priorities_put(rw):
    req = _proposed_req(rw)
    rid = req["id"]
    keys = [t["target"]["key"] for t in req["targets"]]
    # an unknown target refuses the whole request, nothing is written
    before = _audit_count("set_priority")
    bad = rw.put(f"/api/requirements/{rid}/priorities", json={"priorities": {keys[0]: "Must", "Z99×US": "Could"},
                                                            "rationale": "Board decision"})
    assert bad.status_code == 409 and _audit_count("set_priority") == before
    assert rw.put(f"/api/requirements/{rid}/priorities",
                  json={"priorities": {keys[0]: "Maybe"}, "rationale": "Board decision"}).status_code == 422
    r = rw.put(f"/api/requirements/{rid}/priorities", json={"priorities": {keys[0]: "Must"}, "rationale": "Board decision"})
    assert r.status_code == 200 and r.json()["changed"] == [keys[0]]
    again = rw.put(f"/api/requirements/{rid}/priorities", json={"priorities": {keys[0]: "Must"}, "rationale": "Board decision"})
    assert again.json()["changed"] == []
    clear = rw.put(f"/api/requirements/{rid}/priorities", json={"priorities": {keys[0]: None}, "rationale": "Undo that"})
    assert clear.json()["changed"] == [keys[0]]
    tr = next(t for t in rw.get(f"/api/requirements/{rid}").json()["targets"] if t["target"]["key"] == keys[0])
    assert tr["pm_priority"] is None and tr["ai_only"] is True


def test_edit_validates_fields_and_enums(rw):
    rid = _proposed_req(rw)["id"]
    url = f"/api/requirements/{rid}"
    assert rw.patch(url, json={"changes": {"must_not_lose": "1"}, "rationale": "trying"}).status_code == 422
    assert rw.patch(url, json={"changes": {"horizon": "someday"}, "rationale": "trying"}).status_code == 422
    assert rw.patch(url, json={"changes": {"effort": "XL"}, "rationale": "trying"}).status_code == 422
    assert rw.patch(url, json={"changes": {"title": " "}, "rationale": "trying"}).status_code == 422
    assert rw.patch("/api/requirements/REQ-9999", json={"changes": {"effort": "S"}, "rationale": "trying"}).status_code == 404
    v = rw.get(url).json()["version"]
    r = rw.patch(url, json={"changes": {"effort": "S", "kano_class": "delighter"}, "rationale": "Re-assessed with engineering"})
    assert r.status_code == 200 and r.json()["version"] == v + 1
    d = rw.get(url).json()
    assert (d["effort"], d["kano_class"], d["status"]) == ("S", "delighter", "proposed")


def test_finding_link_requires_existing_finding(rw):
    rid = _proposed_req(rw)["id"]
    assert rw.put(f"/api/requirements/{rid}/findings/99999999",
                  json={"relation": "supports", "rationale": "Relevant evidence"}).status_code == 404
    assert rw.put(f"/api/requirements/{rid}/findings/1", json={"relation": "maybe", "rationale": "x" * 6}).status_code == 422
    linked = {r[0] for r in _db().execute("SELECT finding_id FROM requirement_finding WHERE requirement_id = ?", (rid,))}
    fid = next(r[0] for r in _db().execute("SELECT id FROM finding ORDER BY id") if r[0] not in linked)
    assert rw.put(f"/api/requirements/{rid}/findings/{fid}", json={"relation": None, "rationale": "Remove it"}).status_code == 409
    r = rw.put(f"/api/requirements/{rid}/findings/{fid}", json={"relation": "contradicts", "rationale": "Counter-evidence"})
    assert r.status_code == 200 and r.json()["changed"]
    ev = rw.get(f"/api/requirements/{rid}/evidence").json()["findings"]
    assert any(f["id"] == fid and f["relation"] == "contradicts" for f in ev)
    assert rw.put(f"/api/requirements/{rid}/findings/{fid}", json={"relation": None, "rationale": "Remove it"}).status_code == 200


def test_accept_proposal(rw):
    p = next((p for p in rw.get("/api/proposals").json() if p["kind"] == "priority"), None)
    if p is None:
        pytest.skip("no open priority proposal in the demo DB")
    assert rw.post(f"/api/proposals/{p['id']}/decision", json={"accept": True, "rationale": "no"}).status_code == 409
    r = rw.post(f"/api/proposals/{p['id']}/decision", json={"accept": True, "rationale": "Agree with the new evidence"})
    assert r.status_code == 200 and r.json()["proposal"]["status"] == "accepted"
    tr = next(t for t in rw.get(f"/api/requirements/{p['requirement_id']}").json()["targets"]
              if t["target"]["key"] == p["target"]["key"])
    assert tr["pm_priority"] == p["proposed_value"]
    assert _audit_count("accept_proposal", entity_id=str(p["id"])) == 1
    again = rw.post(f"/api/proposals/{p['id']}/decision", json={"accept": True, "rationale": "Agree again please"})
    assert again.status_code == 409
    assert rw.post("/api/proposals/99999/decision", json={"accept": True, "rationale": "long enough"}).status_code == 404


def test_bulk_decision(rw):
    open_ = rw.get("/api/proposals").json()
    new_req = next((p for p in open_ if p["kind"] == "new_requirement"), None)
    other = next((p for p in open_ if p["kind"] in ("priority", "extend")), None)
    if not new_req or not other:
        pytest.skip("demo DB lacks open proposals")
    ids = [other["id"], new_req["id"], 99999]
    assert rw.post("/api/proposals/bulk-decision", json={"ids": ids, "accept": False, "rationale": "x"}).status_code == 409
    r = rw.post("/api/proposals/bulk-decision", json={"ids": ids, "accept": False, "rationale": "Not convinced yet"})
    assert r.status_code == 200
    body = r.json()
    assert body["done"] == [other["id"], new_req["id"]] and [f["id"] for f in body["failed"]] == [99999]
    # rejecting a new AI requirement drops it from review
    assert rw.get(f"/api/requirements/{new_req['requirement_id']}").json()["status"] == "rejected"


def test_weights_validation_and_rerun(rw):
    cur = rw.get("/api/weights").json()["current"]["weights"]
    url = "/api/weights"
    assert rw.post(url, json={"weights": cur, "rationale": "abc"}).status_code == 409
    assert rw.post(url, json={"weights": {**cur, "bogus": 3}, "rationale": "Board request"}).status_code == 422
    assert rw.post(url, json={"weights": {**cur, "customer_voice": 99}, "rationale": "Board request"}).status_code == 422
    assert rw.post(url, json={"weights": cur, "rationale": "Board request"}).status_code == 409   # unchanged
    assert rw.post(url, json={"weights": {k: 0 for k in cur}, "rationale": "Board request"}).status_code == 409
    n_runs = len(rw.get("/api/runs").json())
    r = rw.post(url, json={"weights": {**cur, "competitive_pressure": cur["competitive_pressure"] + 10},
                           "rationale": "Board wants more weight on competitors"})
    assert r.status_code == 200, r.text
    body = r.json()
    runs = rw.get("/api/runs").json()
    assert len(runs) == n_runs + 1 and runs[0]["id"] == body["run_id"] and runs[0]["trigger"] == "weight_change"
    assert _audit_count("change_weights") >= 1
    diff = rw.get("/api/runs/diff").json()
    assert diff["newer"] == body["run_id"] and any(w["factor"] == "competitive_pressure" for w in diff["weight_changes"])


# ------------------------------------------------------------------------------------------------ jobs
def test_wave_job_runs_in_background(rw, monkeypatch):
    from api import jobs
    from bmw_req.pipeline import graph

    st = rw.get("/api/state").json()
    if st["next_wave"] is None:
        assert rw.post(f"/api/waves/{st['current_wave'] + 1}/open").status_code == 409
        with _db() as c:
            c.execute("UPDATE app_state SET value = '2' WHERE key = 'current_wave'")
    assert rw.post("/api/waves/1/open").status_code == 409   # only the next wave
    release, calls = threading.Event(), []

    def fake_advance(wave, initiated_by="system", lines=None):
        calls.append((wave, initiated_by))
        release.wait(5)
        return {"wave": wave, "new_requirements": ["REQ-0999"], "run_id": 42, "log": ["opened (fake)", "stored 1"]}

    monkeypatch.setattr(graph, "advance", fake_advance)
    r = rw.post("/api/waves/3/open", headers={"X-Actor": "Wave Tester"})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    assert rw.get("/api/state").json()["running_job"]["id"] == jid
    assert rw.post("/api/waves/3/open").status_code == 409   # one job at a time
    release.set()
    j = jobs.wait(jid)
    assert j["status"] == "done" and j["result"] == {"wave": 3, "new_requirements": ["REQ-0999"], "run_id": 42}
    assert "opened (fake)" in j["log"] and calls == [(3, "Wave Tester")]
    assert rw.get(f"/api/jobs/{jid}").json()["status"] == "done"
    assert rw.get("/api/jobs/nope").status_code == 404


def test_challenge_job_uses_own_connection_and_reports_errors(rw, monkeypatch):
    from api import jobs
    from bmw_req.pipeline import challenge

    rid = _proposed_req(rw)["id"]
    seen = {}

    def fake_challenge(conn, llm, req_id, question, actor):
        from api.deps import DB

        seen.update(conn_is_shared=conn is DB.conn(), llm=llm, req=req_id, q=question, actor=actor)
        return {"answer": {"verdict": "not_upheld", "answer": "fake"}, "cost": 0.0, "cached": True}

    monkeypatch.setattr(challenge, "challenge", fake_challenge)
    monkeypatch.setattr(jobs, "make_llm", lambda conn: "fake-llm")
    assert rw.post(f"/api/requirements/{rid}/challenge", json={"question": "why"}).status_code == 409
    assert rw.post("/api/requirements/REQ-9999/challenge", json={"question": "Is this real?"}).status_code == 404
    r = rw.post(f"/api/requirements/{rid}/challenge", json={"question": "Is this really a US-only need?"})
    assert r.status_code == 202
    j = jobs.wait(r.json()["job_id"])
    assert j["status"] == "done" and j["result"]["answer"]["verdict"] == "not_upheld"
    assert seen == {"conn_is_shared": False, "llm": "fake-llm", "req": rid, "q": "Is this really a US-only need?",
                    "actor": "Atahan (PM)"}

    def boom(*a, **k):
        raise RuntimeError("budget exceeded (fake)")

    monkeypatch.setattr(challenge, "challenge", boom)
    j = jobs.wait(rw.post(f"/api/requirements/{rid}/challenge", json={"question": "And now?"}).json()["job_id"])
    assert j["status"] == "error" and "budget exceeded" in j["error"]


# ------------------------------------------------------------------------------------------------ static, export, access
def test_models_are_served_and_traversal_is_blocked(rw):
    from bmw_req.config import get_settings

    models = get_settings().data_dir / "models"
    (models / "g60.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (models / "f70").mkdir()
    (models / "f70" / "scene.gltf").write_text("{}")
    (models / "f70" / "scene.bin").write_bytes(b"\x00")
    r = rw.get("/models/g60.glb")
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary"
    assert rw.get("/models/f70/scene.gltf").headers["content-type"].startswith("model/gltf+json")
    assert rw.get("/models/f70/scene.bin").status_code == 200
    assert rw.get("/api/cars/G60").json()["model"]["url"] == "/models/g60.glb"
    assert rw.get("/api/cars/G68").json()["model"]["url"] == "/models/g60.glb"
    assert rw.get("/api/cars/F70").json()["model"]["url"] == "/models/f70/scene.gltf"
    assert rw.get("/api/cars/G70").json()["model"]["url"] is None
    for bad in ("/models/%2e%2e/app.db", "/models/..%2fapp.db", "/models/f70/%2e%2e/%2e%2e/app.db",
                "/models/%2fetc%2fpasswd", "/models/missing.glb", "/models/"):
        assert rw.get(bad).status_code == 404, bad


def test_exports_are_logged(rw):
    before = _audit_count("export")
    for fmt, mime in (("json", "application/json"), ("csv", "text/csv"), ("md", "text/markdown")):
        r = rw.get("/api/export", params={"format": fmt})
        assert r.status_code == 200 and r.headers["content-type"].startswith(mime)
        assert f"requirements.{fmt}" in r.headers["content-disposition"]
    data = rw.get("/api/export", params={"format": "json", "status": "approved"}).json()
    assert data and all(r["status"] == "approved" for r in data)
    assert rw.get("/api/export", params={"format": "pdf"}).status_code == 422
    assert rw.get("/api/quality.csv").status_code == 200
    assert rw.get("/api/audit.csv", params={"actor_type": "human"}).status_code == 200
    assert _audit_count("export") == before + 6
    assert _audit_count("export", entity_id="quality_handover.csv") == 1


def test_access_event_and_actor_header(rw):
    r = rw.post("/api/access", headers={"X-Actor": "Jane%20Doe"},
                json={"action": "view", "entity_type": "requirement", "entity_id": "REQ-0001"})
    assert r.status_code == 200
    ev = _first("SELECT actor_type, actor_id, entity_id FROM audit_event WHERE action = 'view' ORDER BY id DESC LIMIT 1")
    assert tuple(ev) == ("human", "Jane Doe", "REQ-0001")
    assert rw.post("/api/access", json={"action": "delete", "entity_type": "x", "entity_id": "y"}).status_code == 422


def test_demo_restore_swaps_the_db_and_is_audited(rw, master_db):
    from bmw_req.config import get_settings

    snaps = get_settings().data_dir / "snapshots"
    snaps.mkdir()
    shutil.copyfile(master_db, snaps / "baseline.db")
    assert rw.get("/api/demo/snapshots").json() == ["baseline"]
    rid = _proposed_req(rw)["id"]
    assert rw.post(f"/api/requirements/{rid}/status", json={"status": "deferred", "rationale": "Later, maybe"}).status_code == 200
    assert rw.post("/api/demo/restore", json={"snapshot": "../app", "rationale": "Reset the demo"}).status_code == 404
    assert rw.post("/api/demo/restore", json={"snapshot": "baseline", "rationale": "no"}).status_code == 409
    r = rw.post("/api/demo/restore", json={"snapshot": "baseline", "rationale": "Reset the demo"})
    assert r.status_code == 200, r.text
    assert rw.get(f"/api/requirements/{rid}").json()["status"] == "proposed"
    assert _audit_count("restore_snapshot", actor_type="human", entity_id="baseline") == 1


def test_spa_fallback_never_shadows_api_or_models(rw, tmp_path, monkeypatch):
    from api.routers import static

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(static, "WEB_DIST", dist)
    assert "<title>app</title>" in rw.get("/").text
    assert "<title>app</title>" in rw.get("/requirements/REQ-0001").text   # client-side route
    assert rw.get("/assets/app.js").text == "console.log(1)"
    assert rw.get("/assets/missing.js").status_code == 404
    assert rw.get("/api/does-not-exist").status_code == 404
    assert rw.get("/models/nothing.glb").status_code == 404
    assert rw.get("/%2e%2e/%2e%2e/etc/passwd").status_code in (404, 200) and "root:" not in rw.get("/%2e%2e/etc/passwd").text


def test_markets(ro):
    ms = ro.get("/api/markets").json()
    assert [m["code"] for m in ms] == ["US", "EU", "CN", "RoW"]
    assert {"code", "name", "label", "targets", "n_requirements", "must", "voice_base", "gaps"} <= set(ms[0])
    cn = next(m for m in ms if m["code"] == "CN")
    assert {t["key"] for t in cn["targets"]} == {"G68×CN", "G70×CN"}
    for code in ("US", "CN"):
        d = ro.get(f"/api/markets/{code}").json()
        assert {"profile", "targets", "distinctive", "competitors", "web_signals", "study_highlights"} <= set(d)
        assert {"climate", "sources", "profile_valid_from"} <= set(d["profile"])
        assert all(len(t["top"]) <= 6 for t in d["targets"])
        scores = [x["score"] or 0 for x in d["targets"][0]["top"]]
        assert scores == sorted(scores, reverse=True)
        assert len(d["distinctive"]) <= 10 and len(d["web_signals"]) <= 10 and len(d["study_highlights"]) <= 8
        rank = {"Must": 0, "Should": 1, "Could": 2}
        for x in d["distinctive"]:
            assert x["this_market"]["priority"] != x["elsewhere"]["priority"] and x["elsewhere"]["market"] != code
        gaps = [abs(rank[x["this_market"]["priority"]] - rank[x["elsewhere"]["priority"]]) for x in d["distinctive"]]
        assert gaps == sorted(gaps, reverse=True)
        n = [w["n_sources"] for w in d["web_signals"]]
        assert n == sorted(n, reverse=True)
        assert all(w["finding_id"] for w in d["web_signals"])
    assert ro.get("/api/markets/XX").status_code == 404
