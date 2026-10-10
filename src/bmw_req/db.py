"""SQLite store (D-016) with sqlite-vec loaded (D-018). Tables per D-021."""

import sqlite3
from pathlib import Path

import sqlite_vec

from bmw_req.config import get_settings

NOW = "(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"

# Demo table set (D-021). JSON columns hold lists/objects; *_json columns are TEXT.
SCHEMA = f"""
-- Reference layer (portfolio) ------------------------------------------------
CREATE TABLE IF NOT EXISTS brand (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, brand_group TEXT, positioning TEXT,
    core_values_json TEXT, guardrails_json TEXT, source_ids_json TEXT
);
CREATE TABLE IF NOT EXISTS platform (
    id TEXT PRIMARY KEY, owner_brand_group TEXT, powertrains_json TEXT, introduced TEXT,
    phase_out TEXT, successor_platform_id TEXT REFERENCES platform(id), source_ids_json TEXT
);
CREATE TABLE IF NOT EXISTS vehicle_model (
    id TEXT PRIMARY KEY, brand_id TEXT NOT NULL REFERENCES brand(id), line TEXT, body TEXT,
    segment TEXT, platform_id TEXT REFERENCES platform(id), generation TEXT, sop TEXT,
    eop_planned TEXT, powertrains_json TEXT, is_bmw_group INTEGER NOT NULL DEFAULT 1,
    market_variants_json TEXT
);
CREATE TABLE IF NOT EXISTS market (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, countries_json TEXT NOT NULL,  -- ["*"] = catch-all
    climate TEXT, usage_patterns TEXT, cultural_expectations TEXT, infrastructure TEXT,
    powertrain_mix TEXT, profile_source_ids_json TEXT, profile_valid_from TEXT
);
CREATE TABLE IF NOT EXISTS plant (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT, country TEXT, platforms_json TEXT,
    powertrains_json TEXT, nk_ready_from TEXT, capacity_note TEXT, source_ids_json TEXT
);
CREATE TABLE IF NOT EXISTS production (
    vehicle_model_id TEXT NOT NULL REFERENCES vehicle_model(id), plant_id TEXT NOT NULL REFERENCES plant(id),
    market_variant TEXT, markets_served_json TEXT, since TEXT, until TEXT, source_ids_json TEXT
);
CREATE TABLE IF NOT EXISTS sales (
    vehicle_model_id TEXT NOT NULL REFERENCES vehicle_model(id), market_code TEXT NOT NULL REFERENCES market(code),
    year INTEGER NOT NULL, units INTEGER, is_forecast INTEGER NOT NULL DEFAULT 0,
    source_item_id INTEGER NOT NULL REFERENCES source_item(id)
);

-- Evidence layer ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_batch (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT {NOW},
    kind TEXT NOT NULL,           -- feedback_wave | study | sales | option_list | competitor_event | web_refresh | reference
    description TEXT, file TEXT
);
CREATE TABLE IF NOT EXISTS source_item (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,           -- feedback | study | sales | option_list | web | reference
    ref TEXT NOT NULL,            -- provenance: e.g. 'G60_feedback_hackathon.xlsx#Feedback_Explorer:G60-0001'
    external_id TEXT,             -- e.g. verbatim ID G60-0001
    trust_tier TEXT,              -- T1..T3
    vehicle_model_id TEXT REFERENCES vehicle_model(id), market_code TEXT REFERENCES market(code),
    country TEXT, platform_id TEXT REFERENCES platform(id),
    url TEXT, published_at TEXT, retrieved_at TEXT NOT NULL DEFAULT {NOW},
    text TEXT, quote TEXT, meta_json TEXT,
    ingest_batch_id INTEGER REFERENCES ingest_batch(id),
    UNIQUE (kind, ref)
);
CREATE INDEX IF NOT EXISTS ix_source_scope ON source_item(vehicle_model_id, market_code);
CREATE TABLE IF NOT EXISTS finding (
    id INTEGER PRIMARY KEY, type TEXT, title TEXT NOT NULL, summary TEXT,
    scope_level TEXT,             -- derivative | platform | market | portfolio
    vehicle_model_id TEXT REFERENCES vehicle_model(id), market_code TEXT REFERENCES market(code),
    platform_id TEXT REFERENCES platform(id),
    metrics_json TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT {NOW}
);
CREATE TABLE IF NOT EXISTS finding_source (
    finding_id INTEGER NOT NULL REFERENCES finding(id), source_item_id INTEGER NOT NULL REFERENCES source_item(id),
    quote TEXT, relation TEXT NOT NULL DEFAULT 'supports',   -- supports | contradicts
    PRIMARY KEY (finding_id, source_item_id)
);

CREATE TABLE IF NOT EXISTS verbatim_extraction (   -- one row per verbatim × extractor version (D-022)
    source_item_id INTEGER NOT NULL REFERENCES source_item(id), extractor_version TEXT NOT NULL,
    in_scope INTEGER NOT NULL, out_of_scope_reason TEXT, llm_usage_id INTEGER REFERENCES llm_usage(id),
    recheck_llm_usage_id INTEGER REFERENCES llm_usage(id),   -- second-pass check of an out-of-scope verdict (D-023)
    created_at TEXT NOT NULL DEFAULT {NOW},
    PRIMARY KEY (source_item_id, extractor_version)
);
CREATE TABLE IF NOT EXISTS signal (                -- AI-extracted customer signal; input to findings (D-022)
    id INTEGER PRIMARY KEY, source_item_id INTEGER NOT NULL REFERENCES source_item(id),
    extractor_version TEXT NOT NULL, category TEXT NOT NULL, topic TEXT, feedback_type TEXT NOT NULL,
    severity TEXT, need_statement TEXT, quote TEXT,
    quote_verified INTEGER NOT NULL,   -- quote is a contiguous span of the verbatim (whitespace/case normalized)
    llm_usage_id INTEGER REFERENCES llm_usage(id),   -- call (and so model) that produced it (D-023)
    FOREIGN KEY (source_item_id, extractor_version) REFERENCES verbatim_extraction(source_item_id, extractor_version)
);
CREATE INDEX IF NOT EXISTS ix_signal_source ON signal(source_item_id);

-- Decision layer ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requirement (
    id TEXT PRIMARY KEY,          -- REQ-0001
    title TEXT NOT NULL, description TEXT, category TEXT, target_metric TEXT, acceptance_criteria TEXT,
    horizon TEXT,                 -- today | at_successor_launch
    kano_class TEXT, kano_drift TEXT, evidence_level TEXT,   -- E1..E4
    assumptions TEXT, uncertainties TEXT, conflicting_evidence TEXT,
    status TEXT NOT NULL DEFAULT 'proposed', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT {NOW}
);
CREATE TABLE IF NOT EXISTS requirement_target (
    requirement_id TEXT NOT NULL REFERENCES requirement(id),
    vehicle_model_id TEXT NOT NULL REFERENCES vehicle_model(id), market_code TEXT NOT NULL REFERENCES market(code),
    realization TEXT,             -- carry_over | platform_wide | derivative_specific | market_variant | package
    score REAL, score_breakdown_json TEXT, priority TEXT, rationale TEXT,
    PRIMARY KEY (requirement_id, vehicle_model_id, market_code)
);
CREATE TABLE IF NOT EXISTS requirement_finding (
    requirement_id TEXT NOT NULL REFERENCES requirement(id), finding_id INTEGER NOT NULL REFERENCES finding(id),
    relation TEXT NOT NULL DEFAULT 'supports',
    PRIMARY KEY (requirement_id, finding_id)
);
CREATE TABLE IF NOT EXISTS fit_check (
    id INTEGER PRIMARY KEY, requirement_id TEXT NOT NULL REFERENCES requirement(id),
    vehicle_model_id TEXT REFERENCES vehicle_model(id), market_code TEXT REFERENCES market(code),
    check_type TEXT NOT NULL,     -- brand | segment | market | feasibility
    result TEXT NOT NULL,         -- pass | warn | fail
    rationale TEXT, evidence_source_ids_json TEXT, checked_by TEXT NOT NULL, checked_at TEXT NOT NULL DEFAULT {NOW}
);
CREATE TABLE IF NOT EXISTS audit_event (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT {NOW},
    actor_type TEXT NOT NULL CHECK (actor_type IN ('ai', 'human', 'system')), actor_id TEXT,
    action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
    field TEXT, old_value TEXT, new_value TEXT, rationale TEXT, model TEXT, prompt_ref TEXT
);
CREATE TRIGGER IF NOT EXISTS audit_event_no_update BEFORE UPDATE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_event_no_delete BEFORE DELETE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;

-- Continuity layer (D-013) -----------------------------------------------------
CREATE TABLE IF NOT EXISTS weights_version (
    id INTEGER PRIMARY KEY, weights_json TEXT NOT NULL, created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT {NOW}, rationale TEXT
);
CREATE TABLE IF NOT EXISTS prioritization_run (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT {NOW},
    trigger TEXT NOT NULL,        -- new_evidence | weight_change | pm_request | scheduled
    ingest_batch_id INTEGER REFERENCES ingest_batch(id), weights_version_id INTEGER REFERENCES weights_version(id),
    model TEXT, initiated_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS score_snapshot (
    run_id INTEGER NOT NULL REFERENCES prioritization_run(id), requirement_id TEXT NOT NULL REFERENCES requirement(id),
    vehicle_model_id TEXT NOT NULL, market_code TEXT NOT NULL,
    score REAL, breakdown_json TEXT, rank INTEGER, priority TEXT,
    PRIMARY KEY (run_id, requirement_id, vehicle_model_id, market_code)
);
CREATE TABLE IF NOT EXISTS change_proposal (
    id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES prioritization_run(id),
    requirement_id TEXT NOT NULL REFERENCES requirement(id), vehicle_model_id TEXT, market_code TEXT,
    field TEXT NOT NULL, old_value TEXT, proposed_value TEXT, reason TEXT, evidence_delta_json TEXT,
    status TEXT NOT NULL DEFAULT 'open',   -- open | accepted | rejected
    decided_by TEXT, decided_at TEXT, decision_rationale TEXT
);

-- LLM bookkeeping (D-014, D-010) ----------------------------------------------
CREATE TABLE IF NOT EXISTS llm_usage (
    id                 INTEGER PRIMARY KEY,
    created_at         TEXT NOT NULL DEFAULT {NOW},
    settled_at         TEXT,
    job                TEXT NOT NULL,
    demo               INTEGER NOT NULL DEFAULT 0,
    kind               TEXT NOT NULL,            -- responses | embeddings
    model              TEXT NOT NULL,
    service_tier       TEXT,
    status             TEXT NOT NULL,            -- reserved | completed | failed
    reserved_usd       REAL NOT NULL,
    cost_usd           REAL,
    input_tokens       INTEGER,
    cached_tokens      INTEGER,
    cache_write_tokens INTEGER,
    output_tokens      INTEGER,
    reasoning_tokens   INTEGER,
    search_calls       INTEGER,
    response_id        TEXT,
    error              TEXT
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY,         -- sha256 of model + request
    job TEXT, model TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT {NOW},
    output_text TEXT, llm_usage_id INTEGER REFERENCES llm_usage(id)
);

-- Vectors (D-018): rowid = source_item.id -------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS source_embedding USING vec0(embedding float[1536]);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the app DB (default `data/app.db`), load sqlite-vec and ensure the schema.

    Autocommit mode: callers open transactions explicitly (`BEGIN IMMEDIATE`).
    """
    if path is None:
        path = get_settings().db_path
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


# Columns added after a table was first created: (table, column, definition). CREATE IF NOT EXISTS
# doesn't add them to an existing DB.
MIGRATIONS = [
    ("signal", "llm_usage_id", "INTEGER REFERENCES llm_usage(id)"),
    ("verbatim_extraction", "recheck_llm_usage_id", "INTEGER REFERENCES llm_usage(id)"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, definition in MIGRATIONS:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            if (table, column) == ("signal", "llm_usage_id"):
                # Backfill: until D-023 every signal came from its verbatim's first-pass call.
                conn.execute(
                    """UPDATE signal SET llm_usage_id = (SELECT e.llm_usage_id FROM verbatim_extraction e
                       WHERE e.source_item_id = signal.source_item_id AND e.extractor_version = signal.extractor_version)"""
                )
