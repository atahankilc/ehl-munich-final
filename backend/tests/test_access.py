"""Shared access key (api/access.py, D-063): off without ACCESS_KEY; with it, reads stay open and every change needs the
key in X-Access-Key (else 403, nothing written)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api import deps
    from api.main import app

    data = tmp_path / "data"
    (data / "models").mkdir(parents=True)
    (data / "models" / "g60.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("APP_SETTINGS_FILE", str(data / "settings.json"))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def test_no_key_configured_means_open(client, monkeypatch):
    monkeypatch.delenv("ACCESS_KEY", raising=False)
    assert client.get("/api/access").json() == {"required": False, "valid": True}
    assert client.put("/api/settings/budget", json={"confirm_above_usd": 40, "stop_at_usd": 80}).status_code == 200


def test_reads_open_changes_need_the_key(client, monkeypatch):
    monkeypatch.setenv("ACCESS_KEY", "ankara-test")
    for path in ("/api/health", "/models/g60.glb", "/api/checkpoints", "/"):
        assert client.get(path).status_code == 200, path
    assert client.get("/api/access").json() == {"required": True, "valid": False}
    assert client.get("/api/access", headers={"X-Access-Key": "ankara-test"}).json() == {"required": True, "valid": True}

    body = {"confirm_above_usd": 40, "stop_at_usd": 80}
    for headers in ({}, {"X-Access-Key": "wrong"}):
        r = client.put("/api/settings/budget", json=body, headers=headers)
        assert r.status_code == 403 and "access key" in r.json()["detail"]
    assert client.delete("/api/settings/openai-key").status_code == 403
    assert client.put("/api/settings/budget", json=body, headers={"X-Access-Key": "ankara-test"}).status_code == 200
