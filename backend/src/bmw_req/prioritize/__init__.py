"""Prioritization layer (D-050, contract `foundation/documents/prioritization.md`): BMW step 4 on top of the
requirement definition layer (D-048).

Two checkpoint stages: `gate` (LLM brand / segment / market / feasibility checks, `gate.py`) and `prioritize`
(deterministic prio-v1 per requirement × car line × market, `score.py`). The AI writes scores (logged) and *proposed*
bands; confirmed priorities are PM decisions (`prio_decision`, append-only) and a band that moves against a confirmed
or earlier band becomes a `prio_proposal` with its factor-level cause (rule 5, D-013).

This module owns the schema of the prio_* tables.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS prio_score (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES checkpoint_run(id), req_key TEXT NOT NULL, req_version INTEGER,
    line TEXT NOT NULL, market TEXT NOT NULL, score REAL NOT NULL, base REAL, band TEXT NOT NULL, rank INTEGER,
    confidence_json TEXT, breakdown_json TEXT, modifiers_json TEXT, flags_json TEXT, bundle_id TEXT, rung TEXT, rationale TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')), UNIQUE (run_id, req_key, line, market)
);
CREATE TABLE IF NOT EXISTS prio_bundle (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES checkpoint_run(id), bundle_id TEXT NOT NULL,
    keys_json TEXT NOT NULL, relations_json TEXT, band_by_target_json TEXT
);
CREATE TABLE IF NOT EXISTS prio_fit (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES checkpoint_run(id), req_key TEXT NOT NULL, req_version INTEGER,
    line TEXT NOT NULL, market TEXT NOT NULL, check_type TEXT NOT NULL, result TEXT NOT NULL, rationale TEXT,
    checked_by TEXT, model TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS prio_decision (   -- append-only: the PM's confirmed priority per requirement × line × market
    id INTEGER PRIMARY KEY, req_key TEXT NOT NULL, line TEXT NOT NULL, market TEXT NOT NULL, priority TEXT NOT NULL,
    rationale TEXT NOT NULL, actor TEXT NOT NULL, checkpoint_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS prio_proposal (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES checkpoint_run(id), req_key TEXT NOT NULL, line TEXT NOT NULL,
    market TEXT NOT NULL, old_band TEXT, proposed_band TEXT NOT NULL, cause TEXT NOT NULL, factor_delta_json TEXT,
    status TEXT NOT NULL DEFAULT 'open',   -- open | accepted | rejected | superseded
    decided_by TEXT, decided_at TEXT, decision_rationale TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS prio_score_run ON prio_score(run_id, line, market);
CREATE INDEX IF NOT EXISTS prio_score_target ON prio_score(req_key, line, market);
CREATE INDEX IF NOT EXISTS prio_fit_run ON prio_fit(run_id, req_key);
CREATE INDEX IF NOT EXISTS prio_proposal_target ON prio_proposal(req_key, line, market, status);
CREATE TRIGGER IF NOT EXISTS prio_decision_no_update BEFORE UPDATE ON prio_decision BEGIN SELECT RAISE(ABORT, 'prio_decision is append-only'); END;
CREATE TRIGGER IF NOT EXISTS prio_decision_no_delete BEFORE DELETE ON prio_decision BEGIN SELECT RAISE(ABORT, 'prio_decision is append-only'); END;
"""

BANDS = ("Must", "Should", "Could")
BAND_RANK = {b: i for i, b in enumerate(BANDS)}   # lower = stronger


def ensure(conn) -> None:
    conn.executescript(SCHEMA)
