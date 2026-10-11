"""Reference loader + research agents/storage/findings on synthetic data (no paid calls, no network)."""

import json
from types import SimpleNamespace as NS

import pytest

from bmw_req.db import connect
from bmw_req.ingest import reference
from bmw_req.llm import LLMResult
from bmw_req.research import findings as F
from bmw_req.research.agents import (
    AgentResult, EvidenceItem, Task, cited_urls, filter_cited, norm_url, quote_in_text, page_text,
)
from bmw_req.research.run import done_task_ids, store


@pytest.fixture
def conn():
    c = connect(":memory:")
    reference.load_reference(c)
    return c


def item(url, claim="Rival offers rear massage seats.", **kw):
    base = dict(claim=claim, quote="Rear seats offer massage.", url=url, publisher="Pub", published_date="2026-03-05",
                market_code="CN", vehicle_models=["X"], competitor="NIO ET7", evidence_type="competitor_feature",
                category="Comfort & Space", trust_tier="T2")
    return EvidenceItem(**{**base, **kw})


def fake_response(annotation_urls=(), source_urls=()):
    msg = NS(type="message", content=[NS(annotations=[NS(type="url_citation", url=u) for u in annotation_urls])])
    ws = NS(type="web_search_call", action=NS(query="q1", sources=[NS(url=u) for u in source_urls]))
    return NS(output=[ws, msg])


def test_reference_loader_is_idempotent_and_sourced(conn):
    again = reference.load_reference(conn)
    assert again["changed"] is False
    assert conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'load_reference'").fetchone()[0] == 1
    ref_ids = {r[0] for r in conn.execute("SELECT id FROM source_item WHERE kind = 'reference'")}
    for table, col in [("platform", "source_ids_json"), ("plant", "source_ids_json"), ("production", "source_ids_json"),
                       ("brand", "source_ids_json"), ("market", "profile_source_ids_json")]:
        for (v,) in conn.execute(f"SELECT {col} FROM {table}"):
            assert v and set(json.loads(v)) <= ref_ids, table
    g68 = conn.execute("SELECT plant_id, markets_served_json FROM production WHERE vehicle_model_id = 'G68'").fetchone()
    assert g68["plant_id"] == "SHE_DADONG" and json.loads(g68["markets_served_json"]) == ["CN"]
    guard = json.loads(conn.execute("SELECT guardrails_json FROM brand WHERE id = 'BMW'").fetchone()[0])
    assert guard["status"].startswith("proposed") and "fail" in guard["segments"]["luxury"]
    assert conn.execute("SELECT COUNT(*) FROM vehicle_model WHERE is_bmw_group = 0").fetchone()[0] >= 15
    # existing seed + country mapping still work
    assert reference.country_to_market(conn)("JP") == "RoW"


def test_url_citation_filter_drops_uncited_urls():
    resp = fake_response(["https://www.nio.com/et7?utm_source=openai"], ["https://example.org/a/"])
    cited = cited_urls(resp)
    kept, dropped = filter_cited(
        [item("https://nio.com/et7"), item("http://example.org/a"), item("https://made-up.example/x")], cited)
    assert [i.url for i in kept] == ["https://nio.com/et7", "http://example.org/a"]
    assert [i.url for i in dropped] == ["https://made-up.example/x"]
    assert norm_url("https://www.a.com/p/?utm_medium=x&id=3#frag") == "a.com/p?id=3"


def test_quote_matching():
    text = page_text("<html><script>x()</script><p>The rear seats offer “massage” and   heating.</p></html>")
    assert quote_in_text('The rear seats offer "massage" and heating', text)
    assert quote_in_text("The rear seats ... heating.", text)
    assert not quote_in_text("Front seats are cold.", text)


def _result(task, urls):
    items = [item(u, claim=f"claim {n}") for n, u in enumerate(urls)]
    return AgentResult(task, items, [item("https://x.invalid")], {}, ["q"], None, 0.01, "fake-model")


def test_store_is_idempotent_and_audited(conn):
    task = Task("cs:G68:CN", "competitor_scout", "5 Series", "G68", "CN", "focus", wave=3)
    res = _result(task, ["https://a.com/1", "https://b.com/2?utm_source=openai"])
    ids1 = store(conn, res, [1, None])
    ids2 = store(conn, res, [1, None])
    assert ids1 == ids2 and len(ids1) == 2
    rows = conn.execute("SELECT * FROM source_item WHERE kind = 'web' ORDER BY id").fetchall()
    assert len(rows) == 2 and rows[1]["url"] == "https://b.com/2" and rows[0]["wave"] == 3
    assert rows[0]["vehicle_model_id"] == "G68" and rows[0]["market_code"] == "CN" and rows[0]["published_at"] == "2026-03-05"
    meta = json.loads(rows[0]["meta_json"])
    assert meta["quote_verified"] == 1 and meta["task_id"] == "cs:G68:CN" and meta["evidence_type"] == "competitor_feature"
    assert "cs:G68:CN" in done_task_ids(conn)
    ev = json.loads(conn.execute("SELECT new_value FROM audit_event WHERE action = 'web_research'").fetchone()[0])
    assert ev["n_dropped_uncited"] == 1 and ev["queries"] == ["q"]


class FakeLLM:
    def __init__(self, out):
        self.out = out

    def model_for(self, tier):
        return "fake-model"

    def generate(self, **kw):
        return LLMResult(text="", parsed=self.out, usage_id=None, cost_usd=0.0, response=None)


def test_findings_validate_ids_and_store(conn):
    task = Task("cs:G68:CN", "competitor_scout", "5 Series", "G68", "CN", "focus")
    ids = store(conn, _result(task, ["https://a.com/1", "https://b.com/2", "https://c.com/3"]), [1, 1, 0])
    out = F.FindingsOut(findings=[
        F.WebFinding(type="competitor_advantage", title="Rivals offer rear massage", summary="s", category="Comfort & Space",
                     scope_level="derivative", supporting_ids=[ids[0], ids[1], 999999], contradicting_ids=[ids[2], ids[0]]),
        F.WebFinding(type="market_trend", title="Invented", summary="s", category=None, scope_level="market",
                     supporting_ids=[424242], contradicting_ids=[]),
    ])
    summary = F.build_all(conn, llm_factory=lambda: FakeLLM(out))
    s = summary[F.FINDINGS_VERSION + ":G68|CN|w1"]
    assert s["findings"] == 1 and s["dropped_findings"] == 1 and s["invalid_ids"] == 2
    f = conn.execute("SELECT * FROM finding").fetchone()
    assert f["source_kind"] == "web" and f["created_by"] == "ai:fake-model" and f["vehicle_model_id"] == "G68"
    assert f["first_wave"] == 1 and json.loads(f["metrics_json"])["n_sources"] == 3
    rel = dict(conn.execute("SELECT source_item_id, relation FROM finding_source").fetchall())
    assert rel == {ids[0]: "supports", ids[1]: "supports", ids[2]: "contradicts"}
    # idempotent per group
    assert F.build_all(conn, llm_factory=lambda: FakeLLM(out)) == {}
