"""The SQLite → PostgreSQL translation in bmw_req.db (D-059): placeholders, literals, upserts, NULL ordering."""

import pytest

from bmw_req.db import translate


@pytest.mark.parametrize("sql, params, want", [
    ("SELECT * FROM t WHERE a = ? AND b LIKE 'x%'", True, "SELECT * FROM t WHERE a = %s AND b LIKE 'x%%'"),
    ("SELECT '?' , ? FROM t", True, "SELECT '?' , %s FROM t"),
    ("SELECT * FROM t WHERE b LIKE 'x%'", False, "SELECT * FROM t WHERE b LIKE 'x%'"),
    ("INSERT OR IGNORE INTO t (a) VALUES (?)", True, "INSERT INTO t (a) VALUES (%s) ON CONFLICT DO NOTHING"),
    ("UPDATE t SET at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?", True, "UPDATE t SET at = statement_timestamp() WHERE id = %s"),
])
def test_translate(sql, params, want):
    assert translate(sql, params) == want


@pytest.mark.parametrize("sql, want", [
    ("SELECT a FROM t ORDER BY a", "SELECT a FROM t ORDER BY a NULLS FIRST"),
    ("SELECT a FROM t ORDER BY a DESC, b LIMIT 5", "SELECT a FROM t ORDER BY a DESC NULLS LAST, b NULLS FIRST LIMIT 5"),
    ("SELECT a FROM t ORDER BY COALESCE(a, b) DESC, id", "SELECT a FROM t ORDER BY COALESCE(a, b) DESC NULLS LAST, id NULLS FIRST"),
    ("SELECT a FROM t ORDER BY a NULLS LAST", "SELECT a FROM t ORDER BY a NULLS LAST"),
    ("SELECT * FROM (SELECT a FROM t ORDER BY a) x ORDER BY 1 DESC",
     "SELECT * FROM (SELECT a FROM t ORDER BY a NULLS FIRST) x ORDER BY 1 DESC NULLS LAST"),
    ("SELECT a FROM t ORDER BY id DESC LIMIT 1", "SELECT a FROM t ORDER BY id DESC NULLS LAST LIMIT 1"),
])
def test_order_by_sorts_nulls_like_sqlite(sql, want):
    assert translate(sql, False) == want
