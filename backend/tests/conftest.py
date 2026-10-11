"""Every test gets its own empty settings file (D-054), so the real API key and budget limits never apply."""

import pytest

from bmw_req.llm import budget


@pytest.fixture(autouse=True)
def isolated_app_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.delenv("BUDGET_CONFIRM", raising=False)
    monkeypatch.setattr(budget, "_confirmed", False)
