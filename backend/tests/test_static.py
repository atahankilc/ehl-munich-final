"""Static files and health (api/routers/static.py, api/main.py): 3D models are served with their media types and can't
escape their root; the built SPA never shadows /api or /models. Runs on a fresh empty DB in a temp DATA_DIR."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api import deps
    from api.main import app

    data = tmp_path / "data"
    (data / "models").mkdir(parents=True)
    monkeypatch.setenv("DATA_DIR", str(data))
    deps.DB.close()
    yield TestClient(app)
    deps.DB.close()


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_models_are_served_and_traversal_is_blocked(client):
    from bmw_req.config import get_settings

    models = get_settings().data_dir / "models"
    (models / "g60.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (models / "f70").mkdir()
    (models / "f70" / "scene.gltf").write_text("{}")
    (models / "f70" / "scene.bin").write_bytes(b"\x00")
    r = client.get("/models/g60.glb")
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary"
    assert client.get("/models/f70/scene.gltf").headers["content-type"].startswith("model/gltf+json")
    assert client.get("/models/f70/scene.bin").status_code == 200
    for bad in ("/models/%2e%2e/app.db", "/models/..%2fapp.db", "/models/f70/%2e%2e/%2e%2e/app.db",
                "/models/%2fetc%2fpasswd", "/models/missing.glb", "/models/"):
        assert client.get(bad).status_code == 404, bad


def test_spa_fallback_never_shadows_api_or_models(client, tmp_path, monkeypatch):
    from api.routers import static

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(static, "WEB_DIST", dist)
    assert "<title>app</title>" in client.get("/").text
    assert "<title>app</title>" in client.get("/prioritize").text   # client-side route
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/models/nothing.glb").status_code == 404
    assert "root:" not in client.get("/%2e%2e/etc/passwd").text
