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


@pytest.fixture
def pg_url(monkeypatch):
    """A fresh, empty, migrated PostgreSQL database for this test; DATABASE_URL points at it (D-059)."""
    from api import deps
    from tests import pg

    with pg.fresh_db() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        deps.DB.close()
        yield url
        deps.DB.close()


@pytest.fixture
def real_db_url(monkeypatch):
    """A throwaway clone of the real data (`make testdata` creates the template); skips without it."""
    from api import deps
    from tests import pg

    pg.server_url()
    if not pg.has_db(pg.REAL_DATA):
        pytest.skip(f"needs the real-data template database {pg.REAL_DATA} (`make testdata`)")
    with pg.fresh_db(pg.REAL_DATA) as url:
        monkeypatch.setenv("DATABASE_URL", url)
        deps.DB.close()
        yield url
        deps.DB.close()
