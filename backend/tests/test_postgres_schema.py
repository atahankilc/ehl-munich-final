"""D-059 P0: the Alembic baseline reproduces today's schema on PostgreSQL — same tables and columns (in the same order
where the code inserts by position), append-only tables refuse UPDATE/DELETE, timestamps keep SQLite's text format.
Needs the local server (`make db`); skips otherwise."""

import re

import psycopg
import pytest

from tests import pg

# vec0 virtual tables (sqlite) ↔ plain vector tables (postgres) differ on purpose; bookkeeping tables are engine-specific
DIFFERENT_ON_PURPOSE = {"source_embedding", "signal_embedding", "sqlite_sequence", "alembic_version"}
# tables the code writes with `INSERT INTO t VALUES (…)` (no column list): their column order must match exactly.
# Elsewhere order may differ — the baseline follows the real DB, where some columns were added by later ALTERs.
POSITIONAL = {"source_aspect", "node_embedding"}


def sqlite_schema() -> dict[str, list[str]]:
    from bmw_req import checkpoints, prioritize
    from bmw_req.db import connect
    from bmw_req.definition import benchmarks, define
    from bmw_req.structure import areas, classify_context, cluster, contextualize, elicit

    c = connect(":memory:")
    for ensure in (checkpoints.ensure, cluster.ensure, contextualize.ensure, areas.ensure, elicit.ensure,
                   define.ensure, benchmarks.ensure, prioritize.ensure):
        ensure(c)
    c.executescript(classify_context.SCHEMA)   # created inline by its stage, not by an ensure()
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
             if not re.search(r"_(chunks|rowids|info|vector_chunks\d*)$", r[0])]
    return {t: [r["name"] for r in c.execute(f"PRAGMA table_info({t})")] for t in names if t not in DIFFERENT_ON_PURPOSE}


@pytest.fixture(scope="module")
def pg_conn():
    with pg.fresh_db() as url, psycopg.connect(url, autocommit=True) as conn:
        yield conn


def postgres_schema(conn) -> dict[str, list[str]]:
    rows = conn.execute("""SELECT table_name, column_name FROM information_schema.columns
                           WHERE table_schema = 'public' ORDER BY table_name, ordinal_position""").fetchall()
    out: dict[str, list[str]] = {}
    for t, col in rows:
        if t not in DIFFERENT_ON_PURPOSE:
            out.setdefault(t, []).append(col)
    return out


def test_same_tables_and_columns(pg_conn):
    lite, post = sqlite_schema(), postgres_schema(pg_conn)
    assert sorted(lite) == sorted(post)
    assert {t: cols for t, cols in lite.items() if sorted(post[t]) != sorted(cols)} == {}
    assert {t: lite[t] for t in POSITIONAL if post[t] != lite[t]} == {}


def test_vector_tables_and_extension(pg_conn):
    cols = dict(pg_conn.execute("""SELECT table_name || '.' || column_name, udt_name FROM information_schema.columns
                                   WHERE column_name = 'embedding'""").fetchall())
    assert cols == {f"{t}.embedding": "vector" for t in
                    ("source_embedding", "signal_embedding", "node_embedding", "insight", "theme")}


@pytest.mark.parametrize("table", ["audit_event", "def_choice", "def_link_review", "prio_decision"])
def test_append_only_tables_refuse_changes(pg_conn, table):
    row = {"audit_event": "(actor_type, action, entity_type, entity_id) VALUES ('system', 'test', 'x', '1')",
           "def_choice": "(req_key, line, market, level, rationale, actor) VALUES ('k', 'l', 'm', 'target', 'why', 'pm')",
           "def_link_review": "(a_key, b_key, relation, verdict, rationale, actor) VALUES ('a', 'b', 'r', 'ok', 'why', 'pm')",
           "prio_decision": "(req_key, line, market, priority, rationale, actor) VALUES ('k', 'l', 'm', 'Must', 'why', 'pm')"}
    pg_conn.execute(f"INSERT INTO {table} {row[table]}")
    for sql in (f"UPDATE {table} SET id = id", f"DELETE FROM {table}"):
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            pg_conn.execute(sql)


def test_timestamps_keep_sqlite_text_format(pg_conn):
    ts = pg_conn.execute("INSERT INTO ingest_batch (kind) VALUES ('test') RETURNING ts").fetchone()[0]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", ts)
