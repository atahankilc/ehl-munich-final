"""Drop the tables only the retired wave pipeline used (D-057, D-058). Backup first, verified, then one transaction.

`uv run python scripts/drop_wave_tables.py [--dry-run]`   — stop the API first (it holds the DB).

1. Backs up the whole DB with SQLite's online backup API to data/backups/app-before-D058-<timestamp>.db and checks that
   every table to drop has the same row count in the backup.
2. Drops the tables (children before parents) in one transaction and writes one `audit_event` (system) with the row
   counts. Audit rows about the old pipeline stay: the trail is append-only.
3. VACUUM to give the space back.
Idempotent: tables already gone are skipped.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

from bmw_req.audit import audit
from bmw_req.config import get_settings
from bmw_req.db import connect

# children first, so no foreign key ever points at a dropped table
TABLES = ["finding_signal", "finding_source", "requirement_finding", "fit_check", "score_snapshot", "change_proposal",
          "requirement_target", "prioritization_run", "requirement", "finding", "app_state"]


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES if t in have}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="show what would be dropped, change nothing")
    args = ap.parse_args()

    db = get_settings().db_path
    conn = connect(db)
    before = counts(conn)
    if not before:
        print("nothing to drop: the wave tables are already gone")
        return 0
    print("to drop:", ", ".join(f"{t} ({n:,})" for t, n in before.items()))
    if args.dry_run:
        return 0

    # 1) verified backup
    backups = get_settings().data_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    dest = backups / f"app-before-D058-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.db"
    out = sqlite3.connect(dest)
    conn.backup(out)
    out.close()
    check = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and counts(check) == before
    check.close()
    if not ok:
        print(f"backup check FAILED ({dest}); nothing dropped", file=sys.stderr)
        return 1
    print("backup:", dest)

    # 2) drop in one transaction
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for t in TABLES:
            if t in before:
                conn.execute(f"DROP TABLE {t}")
        audit(conn, actor_type="system", actor_id="scripts.drop_wave_tables", action="drop_tables", entity_type="database",
              entity_id="wave_pipeline", old=before, new=None,
              rationale=f"Wave pipeline retired (D-057, D-058); backup {dest.name}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("PRAGMA foreign_keys=ON")
    bad = conn.execute("PRAGMA foreign_key_check").fetchall()
    print("dropped", len(before), "tables;", f"foreign-key problems: {len(bad)}")

    # 3) give the space back
    size = db.stat().st_size
    conn.execute("VACUUM")
    conn.close()
    print(f"size {size / 1e6:.0f} MB → {db.stat().st_size / 1e6:.0f} MB")
    print(json.dumps(before))
    return 0


if __name__ == "__main__":
    sys.exit(main())
