# PostgreSQL migration plan (D-059)

**Status:** P0, P1, P2 done (2026-10-12) · P3 (operations, docs, drop sqlite-vec) next.

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

## P1 as built (2026-10-12)

- **`bmw_req.db`** is the compatibility layer (psycopg 3): `?` → `%s` outside literals, ints/bools bound untyped (SQLite's
  loose typing), rows by name and position, numeric → float, boolean → 0/1, `INSERT OR IGNORE` → `ON CONFLICT DO
  NOTHING`, the SQLite timestamp expression → `utc_now_text()`, `BEGIN IMMEDIATE` → `BEGIN` + one transaction-scoped
  advisory lock (the single writer SQLite had — budget guard and run creation keep their guarantees), vectors as numpy
  float32. `INSERT OR REPLACE`, `PRAGMA`, `rowid`, `executescript` are refused with an error. Unit tests:
  `tests/test_db_translate.py`.
- **Ported by hand**: 18 `lastrowid` → `RETURNING id`; 8 `INSERT OR REPLACE` → `ON CONFLICT … DO UPDATE` (`req_area` now
  keeps its id on a re-run instead of getting a new one); vector tables keyed by entity id; `json_extract` → `->>`;
  boolean sums and boolean arithmetic in `ORDER BY` → `CASE`; `ROUND` on numeric; `PRAGMA table_info` →
  `information_schema`; `total_changes` → `rowcount`. The `ensure()` functions are no-ops (schema = Alembic).
- **Data**: `scripts/sqlite_to_postgres.py` — 267,099 rows, 43 tables, counts and id sums verified, no foreign-key
  orphans, one audit event; `data/app.db` stays untouched as the pre-D-059 backup.
- **Proof**: `scripts/compare_api.py` captured 99 API answers from the SQLite app before the switch and from the
  Postgres app after: 96 identical; the 3 others explained (the migration's own audit event; two "changes since JAN"
  lists whose order was hash-random before and is now stable).

### What made answers differ, and the fix (keep in mind for new queries)

1. **Text collation**: the image's default `en_US.utf8` sorts `rq:a-b` / `RQ:z` / `rq_z` differently from SQLite (bytes).
   The cluster is initialised with the builtin `C.UTF-8` locale (`POSTGRES_INITDB_ARGS`) → code-point order = SQLite.
2. **NULL order**: SQLite sorts NULL first ascending / last descending, Postgres the reverse. The layer adds
   `NULLS FIRST` / `NULLS LAST` to every `ORDER BY` term that doesn't say.
3. **Ties and missing `ORDER BY`**: SQLite returned rows in the order of the index it happened to use; Postgres
   doesn't. Fixed with explicit orders that reproduce it (checked against SQLite's query plans): clusters / themes /
   areas by key, evidence edges by destination then id, research by date then ref, study items by z then id, audit
   rows by time then id, the comment → strongest-cluster tie by signal id. **Rule from now on: every query whose row
   order reaches the user or a tie-break needs a full `ORDER BY`.**
4. **Pre-existing bug found**: "changes since JAN" listed new / removed / moved requirements in Python set order (random
   per process). Now band → score → ID.

### Operations (until P3)

- `make backup` (`pg_dump -Fc` → `data/backups/`), `make testdata` (real-data copy the API tests clone).
- Containers: `DATABASE_URL` points at `db:5432` inside compose; the image runs `alembic upgrade head` before the API.
- Removed: `scripts/demo_state.py`, `scripts/drop_wave_tables.py` (SQLite-only). `sqlite-vec` stays until P3 for the
  copy script.

## P2 as built (2026-10-12)

- **Types (migration 0002):** the 25 system timestamps (`ts`, `created_at`, `settled_at`, `started_at`, `finished_at`,
  `decided_at`, `retrieved_at`) are `timestamptz` with `statement_timestamp()` defaults (per statement, like SQLite's
  'now' — `now()` would tie rows written in one transaction and change their order). Source dates (`published_at`,
  `cutoff`) stay TEXT: they can be partial. The session runs in UTC and `bmw_req.db` reads timestamptz back as the exact
  text the app always had (`2026-10-11T10:05:03.123Z`); all stored values had millisecond precision, so nothing changed.
  `weights_version.weights_json` is `jsonb` (the one JSON column queried in SQL); jsonb reads back as JSON text. Other
  `*_json` columns stay TEXT until a query needs them (some hold non-JSON strings, e.g. audit old/new values).
- **Vector search:** `contextualize.candidates` asks Postgres for the K nearest evidence nodes per type (`ORDER BY
  embedding <=> theme, node_id DESC`), exact. `scripts/check_retrieval.py` compared it with the numpy search it
  replaced: 178 of 178 themes (cp1 71, cp2 107) identical. **No HNSW index yet, on purpose:** 2,192 nodes take
  milliseconds exactly, and an approximate index could return other neighbours. Add `CREATE INDEX … USING hnsw
  (embedding vector_cosine_ops)` with `hnsw.iterative_scan` when the knowledge base grows past ~50k nodes (Q-027), and
  re-run the check. Clustering and the 3D layout need full matrices and stay in numpy.
- **Bug found:** pgvector returns `Vector` objects, not numpy arrays — every pipeline step reading embeddings would
  have failed on its next run since P1. `db.vec()` converts them; `tests/test_vectors.py` covers the round trip and the
  retrieval order.
- **App role (migration 0003):** the app and pipelines connect as `sharksight_app` (`DATABASE_URL`): read / write on
  ordinary tables, only SELECT + INSERT on `audit_event`, `def_choice`, `def_link_review`, `prio_decision`, no DDL,
  no `alembic_version`. Migrations, backups and admin scripts use the owner (`MIGRATION_DATABASE_URL`; the container
  runs `alembic upgrade head` with it before the API). The password comes from `APP_DB_PASSWORD`. Tests run as the app
  role, so a missing permission fails a test. A new append-only table must REVOKE UPDATE / DELETE in its migration.
- **Proof:** all 99 API answers identical to the P1 capture after each change; 134 tests green.
