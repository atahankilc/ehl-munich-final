"""Document page (page 5): the deliverable payload, checkpoint visibility and the logged export, on a temp copy of
the demo DB (no LLM)."""

from __future__ import annotations

import sqlite3

import pytest

from bmw_req.config import ROOT

REAL_DB = ROOT / "data" / "app.db"


@pytest.fixture
def client(tmp_path, monkeypatch):
    if not REAL_DB.exists():
        pytest.skip("needs the local demo DB (data/app.db)")
    from fastapi.testclient import TestClient

    from api import deps
    from api.main import app
    from bmw_req.llm import client as llm_client

    data = tmp_path / "data"
    data.mkdir()
    src, out = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True), sqlite3.connect(data / "app.db")
    src.backup(out)
    out.close(), src.close()
    (data / "models").mkdir()
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setattr(llm_client.LLM, "__init__", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no paid calls in tests")))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def _need(client, cp):
    d = client.get("/api/document", params={"cp": cp, "line": "5 Series", "market": "US"}).json()
    if not d["ready"] or not d["items"]:
        pytest.skip(f"no prioritize run at {cp}")
    return d


def test_payload_has_deliverable_fields(client):
    d = _need(client, "cp2")
    h = d["header"]
    for k in ("checkpoint", "label", "cutoff", "by_band", "confirmed", "open_proposals", "generated_at", "weights_version", "count"):
        assert k in h
    assert h["count"] == len(d["items"])
    order = {"Must": 0, "Should": 1, "Could": 2}
    assert [order[i["priority"]["band"]] for i in d["items"]] == sorted(order[i["priority"]["band"]] for i in d["items"])
    for i in d["items"]:
        for k in ("id", "key", "title", "statement", "domain", "metric", "acceptance", "rung", "priority", "rationale", "factors",
                  "evidence", "assumptions", "gaps", "uncertainties", "links", "gates", "status", "history", "proposals"):
            assert k in i, k
        assert i["id"].startswith("REQ-5US-")
        assert i["status"] in ("confirmed", "ai_proposal", "open_proposal", "open_proposal_against_pm")
        assert i["evidence"]["count"] >= 1          # traceability: every requirement links to a source
    ids = [i["id"] for i in d["items"]]
    assert len(ids) == len(set(ids))


def test_cp1_shows_nothing_from_cp2(client):
    cp2 = _need(client, "cp2")
    t = next(i for i in cp2["items"] if not i["priority"]["confirmed"])
    other = next(b for b in ("Must", "Should", "Could") if b != t["priority"]["band"])
    r = client.post("/api/prioritize/decision", json={"key": t["key"], "line": "5 Series", "market": "US", "priority": other,
                                                      "rationale": "PM decision at JUL", "actor": "Test PM", "cp": "cp2",
                                                      "override_brand": True})
    assert r.status_code == 200
    at2 = client.get("/api/document", params={"cp": "cp2", "line": "5 Series", "market": "US"}).json()
    assert next(i for i in at2["items"] if i["key"] == t["key"])["priority"]["confirmed"]["priority"] == other
    at1 = _need(client, "cp1")
    for i in at1["items"]:
        assert all(h["checkpoint"] == "cp1" for h in i["history"])
        assert all(p["checkpoint"] == "cp1" for p in i["proposals"])
        assert all(x["checkpoint"] in (None, "cp1") for x in i["decisions"])
    hit = next((i for i in at1["items"] if i["key"] == t["key"]), None)
    assert hit is None or (hit["priority"]["confirmed"] or {}).get("rationale") != "PM decision at JUL"
    ch = client.get("/api/document/changes", params={"line": "5 Series", "market": "US"}).json()
    assert any(x["key"] == t["key"] and x["priority"] == other for x in ch["decisions"])


def test_export_is_logged(client):
    _need(client, "cp2")
    from bmw_req.db import connect

    conn = connect()
    before = conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'export'").fetchone()[0]
    md = client.get("/api/document/export", params={"cp": "cp2", "line": "5 Series", "market": "US", "format": "md"},
                    headers={"X-Actor": "Export PM"})
    assert md.status_code == 200 and md.text.startswith("# Customer requirements") and "REQ-5US-" in md.text
    assert "attachment" in md.headers["content-disposition"]
    cs = client.get("/api/document/export", params={"cp": "cp1", "line": "5 Series", "market": "US", "format": "csv"})
    assert cs.status_code == 200 and cs.text.splitlines()[0].startswith("id,key,title")
    rows = conn.execute("SELECT actor_id, entity_id FROM audit_event WHERE action = 'export' ORDER BY id DESC LIMIT 2").fetchall()
    assert conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'export'").fetchone()[0] == before + 2
    assert rows[1]["actor_id"] == "Export PM" and rows[1]["entity_id"].endswith(".md")
