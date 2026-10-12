"""Copy the SQLite database into PostgreSQL (D-059 P1). One-off; the SQLite file is only read.

`uv run python scripts/sqlite_to_postgres.py [--sqlite data/app.db] [--target URL]`   (target default: DATABASE_URL)

1. The target must be migrated (`make migrate`) and empty — the script refuses otherwise.
2. Every table is copied with COPY in the baseline's creation order, columns matched by name. Vectors: sqlite-vec
   `source_embedding` / `signal_embedding` (keyed by rowid) → `source_item_id` / `signal_id`; float32 BLOBs → vector.
   Foreign-key triggers are off during the load (a few self-references point forward), then every foreign key is
   checked for orphans.
3. Identity sequences continue after the copied ids. Row counts and id sums are compared table by table.
4. One audit event (system) records the copy. Stop the API first: the SQLite file must not change during the copy.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import psycopg
import sqlite_vec

from bmw_req.config import get_settings

BASELINE = Path(__file__).resolve().parents[1] / "migrations" / "sql" / "0001_baseline.sql"
VEC0 = {"source_embedding": "source_item_id", "signal_embedding": "signal_id"}   # sqlite rowid → postgres key column


def table_order() -> list[str]:
    return re.findall(r"^CREATE TABLE (\w+)", BASELINE.read_text(), re.M)


def pg_columns(pg, table: str) -> dict[str, str]:
    return {r[0]: r[1] for r in pg.execute(
        "SELECT column_name, udt_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY ordinal_position", (table,))}


def vector_text(blob) -> str | None:
    if blob is None:
        return None
    v = np.frombuffer(bytes(blob), dtype=np.float32)
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def orphans(pg) -> list[str]:
    """Every foreign key, checked: rows whose non-null reference has no parent."""
    out = []
    fks = pg.execute("""
        SELECT c.conrelid::regclass::text, c.confrelid::regclass::text,
               array_agg(a.attname ORDER BY k.n), array_agg(af.attname ORDER BY k.n)
        FROM pg_constraint c
        CROSS JOIN LATERAL unnest(c.conkey, c.confkey) WITH ORDINALITY AS k(col, fcol, n)
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.col
        JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = k.fcol
        WHERE c.contype = 'f' GROUP BY c.oid, c.conrelid, c.confrelid""").fetchall()
    for child, parent, cols, pcols in fks:
        on = " AND ".join(f"p.{pc} = c.{cc}" for cc, pc in zip(cols, pcols))
        notnull = " AND ".join(f"c.{cc} IS NOT NULL" for cc in cols)
        n = pg.execute(f"SELECT COUNT(*) FROM {child} c WHERE {notnull} AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {on})").fetchone()[0]
        if n:
            out.append(f"{child}({', '.join(cols)}) → {parent}: {n} orphan rows")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", default=str(get_settings().db_path))
    ap.add_argument("--target", default=get_settings().database_url)
    args = ap.parse_args()

    lite = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)
    lite.enable_load_extension(True)
    sqlite_vec.load(lite)
    lite.execute("BEGIN")   # one consistent snapshot for the whole copy
    pg = psycopg.connect(args.target, autocommit=True)

    tables = table_order()   # includes the two vector tables (VEC0)
    busy = [t for t in tables if pg.execute(f"SELECT EXISTS (SELECT 1 FROM {t})").fetchone()[0]]
    if busy:
        print(f"target is not empty ({', '.join(busy[:5])}…): migrate a fresh database first", file=sys.stderr)
        return 1

    in_sqlite = {r[0] for r in lite.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    skipped = [t for t in tables if t not in in_sqlite]   # created by a stage that never ran (e.g. candidate)
    tables = [t for t in tables if t in in_sqlite]
    report = {}
    with pg.transaction():
        pg.execute("SET LOCAL session_replication_role = replica")   # FK triggers off during the load
        for t in tables:
            cols = pg_columns(pg, t)
            if t in VEC0:
                select, names = f"SELECT rowid, embedding FROM {t}", [VEC0[t], "embedding"]
            else:
                lite_cols = [r[1] for r in lite.execute(f"PRAGMA table_info({t})")]
                names = [c for c in cols if c in lite_cols]
                missing = [c for c in lite_cols if c not in cols]
                if missing:
                    raise SystemExit(f"{t}: columns {missing} have no place in PostgreSQL — migrate the schema first")
                select = f"SELECT {', '.join(names)} FROM {t}"
            vec_idx = [i for i, c in enumerate(names) if cols.get(c) == "vector"]
            n = 0
            with pg.cursor().copy(f"COPY {t} ({', '.join(names)}) FROM STDIN") as cp:
                for row in lite.execute(select):
                    row = list(row)
                    for i in vec_idx:
                        row[i] = vector_text(row[i])
                    cp.write_row(row)
                    n += 1
            report[t] = n
        bad = orphans(pg)
        if bad:
            raise SystemExit("foreign-key orphans, nothing committed:\n  " + "\n  ".join(bad))
        for t in tables:   # identity sequences continue after the copied ids
            if "id" in pg_columns(pg, t) and pg.execute("SELECT pg_get_serial_sequence(%s, 'id')", (t,)).fetchone()[0]:
                pg.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE(MAX(id), 0) + 1, false) FROM {t}")

    # verify: counts (and id sums where there is an id)
    diffs = []
    for t, n in report.items():
        key = VEC0.get(t) if t in VEC0 else ("id" if pg_columns(pg, t).get("id") in ("int4", "int8") else None)
        lsum = lite.execute(f"SELECT COALESCE(SUM({'rowid' if t in VEC0 else key}), 0) FROM {t}").fetchone()[0] if key else 0
        pn, psum = pg.execute(f"SELECT COUNT(*), {f'COALESCE(SUM({key}), 0)' if key else '0'} FROM {t}").fetchone()
        ln = lite.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        if (pn, int(psum)) != (ln, int(lsum)):
            diffs.append(f"{t}: sqlite {ln} rows / id sum {lsum} vs postgres {pn} / {psum}")
    if diffs:
        print("VERIFY FAILED:\n  " + "\n  ".join(diffs), file=sys.stderr)
        return 1

    pg.execute("""INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, new_value, rationale)
                  VALUES ('system', 'scripts.sqlite_to_postgres', 'migrate_database', 'database', 'sqlite_to_postgres', %s, %s)""",
               (json.dumps(report), f"SQLite → PostgreSQL (D-059 P1) from {Path(args.sqlite).name}; counts and id sums verified"))
    total = sum(report.values())
    print(f"copied {total:,} rows in {len(report)} tables; counts and id sums match; no foreign-key orphans"
          + (f"; not in SQLite (left empty): {', '.join(skipped)}" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
