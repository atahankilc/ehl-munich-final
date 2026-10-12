"""AI agents page (D-055): agent settings are applied on every call, caps and on/off are enforced, tiers and custom
models work, every change is audited, and the audit feed separates checkpoints. Fake OpenAI client — no paid calls."""

import pytest
from fastapi.testclient import TestClient

from bmw_req import app_settings
from bmw_req.db import connect
from bmw_req.llm import AgentBlocked, agents, budget, pricing
from tests.test_budget import make_llm, preload


@pytest.fixture
def conn():
    return connect(":memory:")


def test_every_agent_has_a_known_tier_and_unique_key():
    assert len({a.key for a in agents.AGENTS}) == len(agents.AGENTS)
    for a in agents.AGENTS:
        assert a.tier in ("fast", "smart", "embed") and (a.kind == "embeddings") == (a.tier == "embed")


@pytest.mark.parametrize("job, key", [
    ("classify:extract-v4:cp1", "classify"), ("classify:study-aspects", "context_mapper"), ("couple:cp2:recheck", "couple_recheck"),
    ("couple:cp2", "couple"), ("research:competitor_scout", "research_web"), ("research:benchmarks", "benchmark_research"),
    ("research:findings", None), ("gate:sol", "gate_recheck"), ("embed:themes", "embed_context"),
    ("derive:5 Series:w1", None), ("extract:G60:extract-v3", None),
])
def test_jobs_match_their_agent(job, key):
    a = agents.match(job)
    assert (a.key if a else None) == key


def test_model_and_effort_override_are_applied(conn):
    app_settings.set_agent_config("define", app_settings.AgentConfig(model="gpt-6-luna", reasoning_effort="high"))
    llm = make_llm(conn)
    llm.generate(job="define:cp1", tier="smart", input="x", max_output_tokens=10, reasoning_effort="medium")
    call = llm.client.responses.calls[-1]
    assert call["model"] == "gpt-6-luna" and call["reasoning"] == {"effort": "high"}
    llm.generate(job="specify:cp1", tier="smart", input="x", max_output_tokens=10, reasoning_effort="medium")
    assert llm.client.responses.calls[-1]["model"] == "gpt-6.1-sol"   # other agents keep their tier


def test_switched_off_agent_is_blocked(conn):
    app_settings.set_agent_config("classify", app_settings.AgentConfig(enabled=False))
    with pytest.raises(AgentBlocked, match="switched off"):
        make_llm(conn).generate(job="classify:extract-v4:cp1", tier="fast", input="x", max_output_tokens=10)
    make_llm(conn).generate(job="couple:cp1", tier="fast", input="x", max_output_tokens=10)   # others still run


def test_agent_cap_counts_only_its_own_spend(conn):
    preload(conn, 5.0)   # job 'seed' belongs to no agent
    conn.execute("INSERT INTO llm_usage (job, kind, model, status, reserved_usd, cost_usd) "
                 "VALUES ('specify:cp1', 'responses', 'gpt-6.1-sol', 'completed', 0.9, 0.9)")
    app_settings.set_agent_config("specify", app_settings.AgentConfig(cap_usd=1.0))
    with pytest.raises(AgentBlocked, match=r"\$1.00 cap"):
        make_llm(conn).generate(job="specify:cp2", tier="smart", input="x" * 2000, max_output_tokens=20_000)
    assert budget.agent_committed_usd(conn, agents.BY_KEY["specify"]) == pytest.approx(0.9)


def test_tier_and_custom_model(conn):
    app_settings.set_custom_model("gpt-6-nova", {"kind": "responses", "input": 0.2, "cached_input": 0.02, "output": 1.0})
    assert pricing.kind_of("gpt-6-nova") == "responses" and budget.price_for("gpt-6-nova").output == 1.0
    app_settings.set_tier_model("fast", "gpt-6-nova")
    llm = make_llm(conn)
    llm.generate(job="couple:cp1", tier="fast", input="x", max_output_tokens=10)
    assert llm.client.responses.calls[-1]["model"] == "gpt-6-nova"
    with pytest.raises(ValueError):
        app_settings.set_tier_model("embed", "gpt-6-nova")   # wrong kind for the tier


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api import deps
    from api.main import app

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def test_agents_api_configures_and_audits(client):
    s = client.get("/api/agents").json()
    names = {a["key"] for p in s["pipelines"] for a in p["agents"]}
    assert names == set(agents.BY_KEY)
    r = client.put("/api/agents/specify", json={"model": "gpt-6-luna", "enabled": True, "cap_usd": 2})
    spec = next(a for p in r.json()["pipelines"] for a in p["agents"] if a["key"] == "specify")
    assert spec["model"] == "gpt-6-luna" and spec["config"]["cap_usd"] == 2
    assert client.put("/api/agents/specify", json={"model": "text-embedding-3-small"}).status_code == 400
    assert client.put("/api/agents/nope", json={}).status_code == 404
    from api import deps
    with deps.db() as conn:
        row = conn.execute("SELECT action, entity_id FROM audit_event WHERE entity_type = 'setting' ORDER BY id DESC").fetchone()
    assert dict(row) == {"action": "set_agent", "entity_id": "agent:specify"}


def test_custom_model_in_use_cannot_be_removed(client):
    m = {"id": "gpt-6-nova", "kind": "responses", "input": 0.2, "cached_input": 0.02, "output": 1.0}
    assert client.post("/api/agents/models", json=m).status_code == 200
    assert client.post("/api/agents/models", json={**m, "id": "gpt-6-luna"}).status_code == 409   # built in
    client.put("/api/agents/couple", json={"model": "gpt-6-nova"})
    assert client.delete("/api/agents/models/gpt-6-nova").status_code == 409
    client.put("/api/agents/couple", json={})
    assert client.delete("/api/agents/models/gpt-6-nova").status_code == 200


def test_audit_feed_separates_checkpoints_and_tags_areas(client):
    from api import deps
    with deps.db() as conn:
        conn.execute("INSERT OR IGNORE INTO checkpoint (id, label, cutoff, position) VALUES ('cp1', 'JAN 26', '2026-01-31', 1)")
        conn.execute("INSERT INTO checkpoint_run (checkpoint_id, stage, status, actor, started_at, finished_at) "
                     "VALUES ('cp1', 'define', 'done', 'system', '2026-10-01T10:00:00Z', '2026-10-01T10:05:00Z')")
    client.put("/api/settings/budget", json={"confirm_above_usd": 10, "stop_at_usd": 20})
    cp1 = client.get("/api/audit/feed?scope=all&cp=cp1&only_cp=true").json()["items"]
    assert cp1 and all(i["checkpoint"] == "cp1" for i in cp1) and {i["area"] for i in cp1} == {"definition"}
    none = client.get("/api/audit/feed?scope=all&cp=none&only_cp=true").json()["items"]
    assert any(i["area"] == "settings" for i in none) and all(i["checkpoint"] is None for i in none)
