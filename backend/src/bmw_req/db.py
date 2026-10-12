"""PostgreSQL store (D-059) behind the connection surface the code was written against (originally sqlite3).

The schema lives in Alembic migrations (`backend/migrations/`, `make migrate`), not here. `connect()` returns a thin
wrapper over a psycopg 3 connection that keeps the old behaviour, so ~500 query sites stay unchanged:

- `?` placeholders become `%s` (and a literal `%` becomes `%%`), parameters are bound the loose way SQLite did:
  ints and bools go out untyped, so `text_col = ?` with an int compares like before; bools are stored as 0/1.
- rows work as `row["col"]`, `row[0]`, `dict(row)`; `numeric` comes back as float and `boolean` as 0/1, like SQLite.
- `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`; the SQLite timestamp expression → `statement_timestamp()`.
- timestamps are `timestamptz` (P2) but read back as the ISO text the code always had (`2026-10-11T10:05:03.123Z`),
  in UTC; `jsonb` reads back as JSON text (callers `json.loads` it, as before).
- `ORDER BY` sorts NULLs like SQLite (first when ascending, last when descending) unless a term says NULLS itself.
- autocommit outside explicit transactions; `BEGIN IMMEDIATE` → `BEGIN` + one transaction-scoped advisory lock, which
  serializes exactly the writers that SQLite serialized (budget guard, run creation, …). Readers never wait.
- vectors (pgvector) are written from numpy arrays and read as pgvector `Vector` objects; `vec()` turns any of them
  into a float32 array.
Anything else SQLite-only (`INSERT OR REPLACE`, `lastrowid`, `PRAGMA`, `executescript`) is refused loudly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.adapt import Dumper, Loader

from bmw_req.config import get_settings

IntegrityError = psycopg.IntegrityError
WRITE_LOCK = 0x5348_4B53   # "SHKS": the one advisory lock that stands in for SQLite's single writer

_SQLITE_NOW = re.compile(r"strftime\('%Y-%m-%dT%H:%M:%fZ',\s*'now'\)")
_INSERT_OR_IGNORE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.I)
_REFUSED = re.compile(r"^\s*(INSERT\s+OR\s+REPLACE|PRAGMA)\b|\browid\b", re.I)


# ------------------------------------------------------------------------------------------------ type adaptation
class _UntypedDumper(Dumper):
    """Send ints/bools as untyped text so Postgres infers the type from context (SQLite's loose typing)."""

    oid = 0

    def dump(self, obj):
        return str(int(obj)).encode()


class _FloatFromNumeric(Loader):
    def load(self, data):
        return float(bytes(data).decode())


class _IntFromBool(Loader):
    def load(self, data):
        return 1 if bytes(data) == b"t" else 0


class _IsoZFromTimestamptz(Loader):
    """'2026-10-11 10:05:03.123456+00' (session in UTC) → '2026-10-11T10:05:03.123Z', the text SQLite stored."""

    def load(self, data):
        s = bytes(data).decode()
        day, clock = s.split(" ", 1)
        clock = clock.split("+", 1)[0].split("-", 1)[0]
        hms, _, frac = clock.partition(".")
        return f"{day}T{hms}.{(frac + '000')[:3]}Z"


class _TextFromJson(Loader):
    def load(self, data):
        return bytes(data).decode()


class Row(tuple):
    """A result row readable by position and by column name, like sqlite3.Row."""

    __slots__ = ()
    _cols: tuple[str, ...] = ()

    def __getitem__(self, k):
        if isinstance(k, str):
            try:
                return tuple.__getitem__(self, self._cols.index(k))
            except ValueError:
                raise IndexError(f"No column named {k!r}") from None
        return tuple.__getitem__(self, k)

    def keys(self) -> list[str]:
        return list(self._cols)


def _row_factory(cursor):
    cols = tuple(d.name for d in cursor.description or ())
    cls = type("Row", (Row,), {"_cols": cols, "__slots__": ()})
    return lambda values: cls(values)


# ------------------------------------------------------------------------------------------------ SQL translation
def translate(sql: str, has_params: bool) -> str:
    """SQLite dialect bits that map 1:1 → PostgreSQL. `?` outside quotes/comments → `%s`; `%` → `%%` when binding."""
    if _REFUSED.search(sql):
        raise NotImplementedError(f"SQLite-only SQL reached PostgreSQL (port it): {sql.strip()[:120]}")
    sql = _SQLITE_NOW.sub("statement_timestamp()", sql)
    if _ORDER_BY.search(sql):
        sql = _nulls_like_sqlite(sql)
    if _INSERT_OR_IGNORE.match(sql):
        sql = _INSERT_OR_IGNORE.sub("INSERT INTO", sql, count=1).rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    if not has_params:
        return sql
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c in ("'", '"'):                      # quoted literal / identifier ('' and "" escape themselves)
            j = i + 1
            while j < n and not (sql[j] == c and (j + 1 >= n or sql[j + 1] != c)):
                j += 2 if sql[j] == c else 1
            out.append(sql[i:j + 1].replace("%", "%%"))
            i = j + 1
        elif c == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            out.append(sql[i:j].replace("%", "%%"))
            i = j
        elif c == "?":
            out.append("%s")
            i += 1
        elif c == "%":
            out.append("%%")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


_ORDER_BY = re.compile(r"\bORDER\s+BY\b", re.I)
_ORDER_END = re.compile(r"\b(LIMIT|OFFSET|FETCH|FOR|UNION|EXCEPT|INTERSECT)\b", re.I)


def _nulls_like_sqlite(sql: str) -> str:
    """Add NULLS FIRST (ASC) / NULLS LAST (DESC) to every ORDER BY term that doesn't say: SQLite treats NULL as the
    smallest value, PostgreSQL as the largest. Paren-aware; string literals are left alone by construction (callers
    pass SQL text where ORDER BY terms are plain expressions)."""
    out, pos = [], 0
    for m in _ORDER_BY.finditer(sql):
        if m.start() < pos:
            continue
        out.append(sql[pos:m.end()])
        i, depth, start, terms = m.end(), 0, m.end(), []
        while i < len(sql):
            c = sql[i]
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    break
                depth -= 1
            elif c == "'":
                i = sql.index("'", i + 1)
            elif depth == 0 and (c in ",;" or _ORDER_END.match(sql, i) and not sql[i - 1].isalnum() and sql[i - 1] != "_"):
                if c == ",":
                    terms.append(sql[start:i]); start = i + 1
                else:
                    break
            i += 1
        terms.append(sql[start:i])
        fixed = []
        for t in terms:
            core = t.rstrip()
            tail = t[len(core):]
            if re.search(r"\bNULLS\s+(FIRST|LAST)\s*$", core, re.I) or not core.strip():
                fixed.append(t)
            elif re.search(r"\bDESC\s*$", core, re.I):
                fixed.append(core + " NULLS LAST" + tail)
            else:
                fixed.append(core + " NULLS FIRST" + tail)
        out.append(",".join(fixed))
        pos = i
    out.append(sql[pos:])
    return "".join(out)


def _params(p):
    if p is None:
        return None
    if isinstance(p, dict):
        return p
    return tuple(p)


# ------------------------------------------------------------------------------------------------ connection
class Connection:
    """The sqlite3-style surface the code uses, over one psycopg connection (autocommit)."""

    def __init__(self, raw: psycopg.Connection):
        self.raw = raw

    def execute(self, sql: str, params: Sequence | dict | None = None):
        p = _params(params)
        head = sql.lstrip()[:16].upper()
        if head.startswith("BEGIN"):
            cur = self.raw.execute("BEGIN")
            if head.startswith("BEGIN IMMEDIATE"):
                self.raw.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK,))
            return cur
        return self.raw.execute(translate(sql, bool(p)), p or None)

    def executemany(self, sql: str, seq: Iterable[Sequence]):
        rows = [_params(r) for r in seq]
        cur = self.raw.cursor()
        if rows:
            cur.executemany(translate(sql, True), rows)
        return cur

    def executescript(self, sql: str):
        raise NotImplementedError("The schema lives in Alembic migrations (D-059); executescript is SQLite-only.")

    def cursor(self):
        return self.raw.cursor()

    def close(self) -> None:
        self.raw.close()

    @property
    def in_transaction(self) -> bool:
        return self.raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def connect(url: str | None = None) -> Connection:
    """Open the app database (DATABASE_URL). Autocommit; explicit `BEGIN` opens a transaction."""
    url = url or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example); start the database with `make db`")
    raw = psycopg.connect(url, autocommit=True, row_factory=_row_factory, options="-c timezone=UTC")
    register_vector(raw)
    raw.adapters.register_dumper(int, _UntypedDumper)
    raw.adapters.register_dumper(bool, _UntypedDumper)
    raw.adapters.register_dumper(np.integer, _UntypedDumper)
    raw.adapters.register_loader("numeric", _FloatFromNumeric)
    raw.adapters.register_loader("bool", _IntFromBool)
    raw.adapters.register_loader("timestamptz", _IsoZFromTimestamptz)
    raw.adapters.register_loader("jsonb", _TextFromJson)
    return Connection(raw)


def vec(v) -> np.ndarray:
    """An embedding as the float32 array pgvector stores (lists, arrays, or legacy float32 bytes)."""
    if isinstance(v, (bytes, bytearray, memoryview)):
        return np.frombuffer(bytes(v), dtype=np.float32)
    if hasattr(v, "to_numpy"):   # pgvector.Vector, as the vector loader returns it
        return np.asarray(v.to_numpy(), dtype=np.float32)
    return np.asarray(v, dtype=np.float32)
