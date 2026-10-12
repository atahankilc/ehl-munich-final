"""Settings API (D-054): API key and budget limits. No real OpenAI calls — the key check is patched."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

KEY = "sk-test-1234567890abcdefWXYZ"


@pytest.fixture
def client(tmp_path, monkeypatch, pg_url):
    from api import deps
    from api.main import app
    from api.routers import settings

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "verify_key", lambda key: None)
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def audit_rows(c):
    from api import deps

    with deps.db() as conn:
        return [dict(r) for r in conn.execute("SELECT action, entity_id, old_value, new_value FROM audit_event "
                                              "WHERE entity_type = 'setting' ORDER BY id")]


def test_key_is_saved_masked_and_audited(client):
    assert client.get("/api/settings").json()["openai"] == {"configured": False, "source": None, "masked": None}
    r = client.put("/api/settings/openai-key", json={"key": KEY}, headers={"X-Actor": "Tester"})
    assert r.status_code == 200
    assert r.json()["openai"] == {"configured": True, "source": "app", "masked": "sk-…WXYZ"}
    assert KEY not in client.get("/api/settings").text
    rows = audit_rows(client)
    assert rows[-1]["action"] == "set_api_key" and rows[-1]["new_value"] == "sk-…WXYZ"
    assert all(KEY not in str(v) for row in rows for v in row.values())
    assert client.delete("/api/settings/openai-key").json()["openai"]["configured"] is False
    assert audit_rows(client)[-1]["action"] == "remove_api_key"


def test_rejected_or_malformed_key_is_not_saved(client, monkeypatch):
    from api.routers import settings

    assert client.put("/api/settings/openai-key", json={"key": "short"}).status_code == 400

    def reject(key):
        raise HTTPException(400, "OpenAI rejected this key.")

    monkeypatch.setattr(settings, "verify_key", reject)
    assert client.put("/api/settings/openai-key", json={"key": KEY}).status_code == 400
    assert client.get("/api/settings").json()["openai"]["configured"] is False


def test_budget_limits_validated_and_audited(client):
    r = client.put("/api/settings/budget", json={"confirm_above_usd": 120, "stop_at_usd": 150})
    assert r.status_code == 200 and r.json()["budget"]["stop_at_usd"] == 150
    assert client.get("/api/usage").json()["budget"]["stop_at"] == 150
    assert client.put("/api/settings/budget", json={"confirm_above_usd": 200, "stop_at_usd": 150}).status_code == 400
    row = audit_rows(client)[-1]
    assert row["action"] == "set_budget" and '"stop_at_usd": 150' in row["new_value"]
