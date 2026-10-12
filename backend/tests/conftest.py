"""Every test gets its own empty settings file (D-054), so the real API key and budget limits never apply."""

import pytest

from bmw_req.llm import budget


@pytest.fixture(autouse=True)
def isolated_app_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.delenv("BUDGET_CONFIRM", raising=False)
    monkeypatch.setattr(budget, "_confirmed", False)


@pytest.fixture(scope="session", autouse=True)
def _drop_pg_template():
    """The migrated template database (tests/pg.py) lives for the session only."""
    yield
    from tests import pg

    pg.drop_template()
