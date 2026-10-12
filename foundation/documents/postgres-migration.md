# PostgreSQL migration plan (D-059)

**Status:** P0 done (2026-10-12) · P1 next.

Move the app from SQLite + sqlite-vec to **PostgreSQL 17 + pgvector**, one database for relational data, vectors,
full-text search and (later) the job queue. Uploaded files stay outside the database (disk volume now, S3-compatible
storage later). No graph database (D-017 stands; Apache AGE inside Postgres is the first step if one is ever needed).
OpenAI cost: $0 — the LLM cache moves with the data.

## Why now (future needs → what covers them)

| Need | SQLite today | PostgreSQL |
|---|---|---|
| Background agents writing while the PM works (Q-027) | one writer at a time | MVCC, concurrent writers |
| Scheduled / queued agent jobs | in-process threads | a job table with `FOR UPDATE SKIP LOCKED` |
| Semantic search over the knowledge base (RAG) | numpy brute force over BLOBs | `pgvector` + HNSW index, hybrid with full-text search |
| Uploads to the knowledge base | files would bloat the DB file | files on disk / object storage; provenance, chunks, embeddings in Postgres |
| Evidence graph | edge tables | edge tables + `WITH RECURSIVE` (graph queries in SQL) |
| Tamper-proof audit trail | triggers | triggers + the app role has no UPDATE / DELETE on audit tables |
| Several users, login, remote access | a local file | roles, network access, managed hosting possible (only with BMW's OK, rule 1) |
| Schema evolution | hand-rolled `MIGRATIONS` list + `ensure()` per module | versioned Alembic migrations, one place |

## Starting point (measured 2026-10-12)

- ~514 SQL call sites in 15 files; ~250k rows, 366 MB (mostly `track`, `signal`, `verbatim_extraction`, vectors).
- Schema spread over `db.py` (22 objects) and 8 module `ensure()` functions (checkpoints, structure, definition,
  prioritize).
- SQLite-only features in use: `?` placeholders (~100), `BEGIN IMMEDIATE` (51), `lastrowid` (18), `rowid` (27),
  `INSERT OR REPLACE / IGNORE` (14), `strftime` (21), `PRAGMA` (11), `json_extract` (2), `LIKE` (22, case-insensitive in
  SQLite, case-sensitive in Postgres), lax `GROUP BY` (11 queries to check), vec0 virtual tables (`source_embedding`,
  `signal_embedding`) and float32 BLOBs (`node_embedding`).
- One shared API connection behind an `RLock` (`api/deps.py`); pipeline workers and the re-score worker open their own.
- Tests open `connect(":memory:")` or copy the real `data/app.db`.

## Target setup

- **Compose service `db`**: image `pgvector/pgvector:0.8.0-pg17`, volume `pgdata`, port published on
  `127.0.0.1:5433` only (rule 1; 5432 is often taken by another local Postgres, `POSTGRES_PORT` overrides),
  healthcheck `pg_isready`. The app containers get `depends_on: db (healthy)` in P1.
- **Native development**: `make db` starts only the database container; `make api` / pipeline commands connect to it.
- **Connection**: `DATABASE_URL` in `.env` (e.g. `postgresql://sharksight:…@127.0.0.1:5432/sharksight`); a separate
  server connection `TEST_DATABASE_URL` through which tests create and drop throwaway databases. Credentials in `.env` only; `.env.example` gets a placeholder.
- **Driver**: psycopg 3 (binary). **Migrations**: Alembic (raw SQL migrations, no ORM).
- **Two roles**: `sharksight_owner` runs migrations; `sharksight_app` is what the app uses — no UPDATE/DELETE on
  `audit_event`, `def_choice`, `def_link_review`, `prio_decision` (append-only by permission, not only by trigger).

## Code strategy: lift and shift first, improve second

Keep every query's behaviour identical in the switch; use Postgres features only after the app runs on it.

1. **`bmw_req.db.connect()` returns a thin wrapper** over psycopg with the same surface the code uses today:
   `.execute(sql, params)` (translates `?` → `%s`, never inside string literals), `.executemany`, rows that work as
   `row["col"]` and `row[0]`, autocommit with explicit `BEGIN`. Most of the 514 call sites stay unchanged.
2. **Port the SQLite-only spots by hand**: `lastrowid` → `RETURNING id`; `INSERT OR …` → `ON CONFLICT`; `strftime` →
   `to_char(now() AT TIME ZONE 'UTC', …)` with the same text format; `json_extract` → `->>`; `PRAGMA` removed;
   `LIKE` checked case by case (`ILIKE` where the old behaviour relied on case-insensitivity); `GROUP BY` made strict;
   `rowid` → explicit keys.
3. **`BEGIN IMMEDIATE` → `BEGIN`**, plus an explicit lock where the old code relied on SQLite's single writer. Must
   not regress: the **budget guard** (`llm.budget.reserve`) takes `pg_advisory_xact_lock` so two workers can't both
   pass a limit; the same check for run creation in `checkpoints.py`.
4. **All DDL moves into Alembic** (one baseline migration reproducing today's schema, including the `ensure()` tables);
   `ensure()` functions become no-ops and are removed.
5. **Types in phase 1**: keep timestamps and JSON as TEXT in the same formats (API output and string comparisons stay
   identical), booleans as INTEGER. Vectors become `vector(1536)` columns right away (`source_embedding`,
   `signal_embedding`, `node_embedding` → tables keyed by their entity id).

## Phases (each tested, committed separately)

| Phase | Scope | Done when |
|---|---|---|
| **P0 — infrastructure** | `db` compose service, `make db`, `DATABASE_URL`, Alembic baseline, test fixtures (a fresh schema per test, cloned from a template database — replaces `:memory:`; a session copy of the real data replaces the `data/app.db` copies). App still on SQLite. | `alembic upgrade head` builds the full schema on an empty Postgres; fixtures work. |
| **P1 — switch** | db wrapper, dialect ports, budget-guard lock, `scripts/sqlite_to_postgres.py` (schema via Alembic, copy every table in FK order with `COPY`, vectors converted, sequences reset, row counts + checksums verified, one audit event), app and pipelines on Postgres. `data/app.db` kept read-only as backup. | Full test suite green on Postgres; every screen loads with the same numbers as before (spot-checked page by page); a cached pipeline stage re-run spends $0. |
| **P2 — use Postgres properly** | HNSW indexes + SQL nearest-neighbour search instead of numpy brute force (contextualize retrieval); JSONB for queried JSON columns; `timestamptz` (API keeps its ISO-Z output); app role without UPDATE/DELETE on audit tables. | Same results as P1 on the evidence-link step (top-k overlap check), tests green. |
| **P3 — operations & docs** | `make backup` / `make restore` (`pg_dump` / `pg_restore`) replace `demo_state.py` and `drop_wave_tables.py`; drop `sqlite-vec`; docs (tech-stack, architecture, README, AGENTS), D-016 / D-018 superseded. | Backup → restore round trip verified; no SQLite left in the code. |

## Risks and how they're handled

- **Silent behaviour changes** (NULL ordering, case-sensitive `LIKE`, strict typing — e.g. comparing TEXT ids to
  integers, lax `GROUP BY`): caught by the test suite plus a before/after comparison of every API endpoint's JSON on
  the real data (script, run in P1).
- **Budget guard race**: advisory lock (above) plus a concurrency test.
- **Timestamp / JSON formats** in API output: unchanged in P1 by keeping TEXT; P2 converts with tests on the output.
- **Docker becomes required** for the app and the tests (`make db` / `make test` start it).
- **Confidential data** (rule 1): the database runs locally in Docker, port bound to 127.0.0.1, the copy never
  leaves the machine. A hosted database only after BMW's OK.

## Out of scope here

Continuous intake, the job queue and uploads (Q-027) — this migration only makes them possible. Login / roles for
people (needed before any shared deployment).

## P0 as built (2026-10-12)

- `compose.yaml` service `db` (no profile), `make db` / `make db-stop` / `make migrate`; `make test` starts the DB.
- `.env`: `POSTGRES_PASSWORD`, `DATABASE_URL`, `TEST_DATABASE_URL` (placeholders in `.env.example`).
- Alembic in `backend/` (`alembic.ini`, `migrations/`): raw SQL files in `migrations/sql/`, run through the psycopg
  connection without parameter parsing (`migrations/helpers.py`). Baseline `0001`: all 42 tables (incl. the ones the
  stage modules create and the not-yet-run `candidate`), `utc_now_text()` producing SQLite's timestamp text,
  `forbid_change()` triggers on the 4 append-only tables, `vector(1536)` for every embedding, `source_embedding` /
  `signal_embedding` keyed by entity id instead of `rowid`. Column order follows the real DB.
- Tests: `tests/pg.py` (one migrated template DB per session, cloned per test, dropped afterwards; skips without a
  server); `tests/test_postgres_schema.py` checks table and column parity with today's SQLite schema (exact order for
  the positionally written `source_aspect`, `node_embedding`), append-only triggers, vector columns, timestamp format.
- Deferred to P2 as planned: the separate owner / app roles (one `sharksight` role for now).
