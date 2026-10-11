"""Save / restore named demo states of data/app.db (e.g. 'evidence', 'wave1', 'demo').

`uv run python scripts/demo_state.py save wave1`
`uv run python scripts/demo_state.py restore wave1`
`uv run python scripts/demo_state.py list`

Restore keeps the CURRENT llm_usage and llm_cache rows (the budget log must never lose spend, D-014, and cached
answers keep replays free). Snapshots live in data/snapshots/ (git-ignored). Stop the Streamlit app first.
"""

import shutil
import sqlite3
import sys

from bmw_req.config import get_settings
from bmw_req.db import connect

KEEP = ["llm_usage", "llm_cache"]


def snap_dir():
    d = get_settings().data_dir / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(name: str) -> None:
    src = connect()
    dst = sqlite3.connect(snap_dir() / f"{name}.db")
    src.backup(dst)
    dst.close()
    print("saved", snap_dir() / f"{name}.db")


def restore(name: str) -> None:
    path = snap_dir() / f"{name}.db"
    if not path.exists():
        raise SystemExit(f"no snapshot {name}")
    db = get_settings().db_path
    # 1) back up the tables we must keep to a file BEFORE touching the live DB (crash-safe)
    keep_file = snap_dir() / "_keep_llm.db"
    if keep_file.exists():
        keep_file.unlink()
    cur = connect()
    cur.execute(f"ATTACH DATABASE '{keep_file}' AS keep")
    for t in KEEP:
        cur.execute(f"CREATE TABLE keep.{t} AS SELECT * FROM main.{t}")
    cur.execute("DETACH DATABASE keep")
    cur.close()
    # 2) swap in the snapshot
    for suffix in ("-wal", "-shm"):
        p = db.with_name(db.name + suffix)
        if p.exists():
            p.unlink()
    shutil.copyfile(path, db)
    # 3) put the kept rows back (FKs off: signals etc. reference llm_usage ids that are re-inserted unchanged)
    conn = connect()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(f"ATTACH DATABASE '{keep_file}' AS keep")
    conn.execute("BEGIN IMMEDIATE")
    for t in KEEP:
        conn.execute(f"DELETE FROM main.{t}")
        conn.execute(f"INSERT INTO main.{t} SELECT * FROM keep.{t}")
    conn.execute("""INSERT INTO audit_event (actor_type, actor_id, action, entity_type, entity_id, rationale)
                    VALUES ('system', 'demo_state', 'restore_snapshot', 'database', ?, 'Demo reset; LLM usage log kept')""",
                 (name,))
    conn.execute("COMMIT")
    conn.execute("DETACH DATABASE keep")
    conn.execute("PRAGMA foreign_keys=ON")
    print("restored", name, "(llm_usage / llm_cache kept; backup in", keep_file, ")")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "save":
        save(sys.argv[2])
    elif cmd == "restore":
        restore(sys.argv[2])
    else:
        for p in sorted(snap_dir().glob("*.db")):
            print(p.stem, f"{p.stat().st_size / 1e6:.1f} MB")
