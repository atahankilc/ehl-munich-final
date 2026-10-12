"""Shared access key (api/access.py, D-063): off without ACCESS_KEY; with it, everything but the health check needs the
key as the Basic-auth password."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient


def _basic(user: str, password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api import deps
    from api.main import app

    data = tmp_path / "data"
    (data / "models").mkdir(parents=True)
    (data / "models" / "g60.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    monkeypatch.setenv("DATA_DIR", str(data))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def test_no_key_configured_means_open(client, monkeypatch):
    monkeypatch.delenv("ACCESS_KEY", raising=False)
    assert client.get("/models/g60.glb").status_code == 200


def test_key_required_everywhere_but_health(client, monkeypatch):
    monkeypatch.setenv("ACCESS_KEY", "s3cret-key")
    assert client.get("/api/health").status_code == 200
    for path in ("/models/g60.glb", "/api/checkpoints", "/"):
        r = client.get(path)
        assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    assert client.get("/models/g60.glb", headers=_basic("pm", "wrong")).status_code == 401
    assert client.get("/models/g60.glb", headers={"Authorization": "Basic !!notbase64"}).status_code == 401
    assert client.get("/models/g60.glb", headers={"Authorization": "Bearer s3cret-key"}).status_code == 401
    assert client.get("/models/g60.glb", headers=_basic("anyone", "s3cret-key")).status_code == 200
