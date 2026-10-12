# BMW Requirements Studio

AI-assisted, evidence-linked **customer requirements for BMW successor vehicles** — built for the BMW
"AI for Product Decision Making" hackathon challenge. The AI ingests BMW customer feedback, customer studies,
sales and option lists, enriches them with cited web research, extracts signals, clusters findings, derives and
scores requirements per derivative × market — and the **product manager decides**, with every step in an
append-only audit trail.

Portfolio-level from day one: 1 Series (F70), 5 Series (G60 + China LWB G68), 7 Series (G70) × EU / US / CN / RoW.

## Quick start

```bash
cp .env.example .env      # add OPENAI_API_KEY and the two database passwords (LLM provider: OpenAI)
make db                   # PostgreSQL 17 + pgvector in Docker, 127.0.0.1:5433 (D-059)
make migrate              # build the schema (Alembic)
```

Two profiles (`APP_ENV`, D-053), natively or in containers. Run only one of them at a time — they share port 8600
and the database.

| | Native | Containers (Docker) |
|---|---|---|
| **development** — API auto-reloads on save, PM app with live reload on http://127.0.0.1:5173 | `make install`, then `make api` + `make dev` | `make up-dev` |
| **production** — the API serves the built app on http://127.0.0.1:8600 | `make serve` | `make up` (detached; `make down`, `make logs`) |

`make test` runs pytest + the frontend typecheck. Images never contain the raw BMW data, `data/` or `.env`
(`.dockerignore` is an allowlist); compose mounts `data/` and reads `.env`, and publishes ports on 127.0.0.1 only.

## Repository layout

```
backend/            Python 3.12 (uv) — run every `uv run …` from here
  src/bmw_req/      pipeline: ingest, research, structure, definition, prioritize, LLM budget guard
  src/api/          FastAPI JSON layer for the PM app
  tests/            pytest (no paid calls)
  scripts/          demo states, benchmarks, pilot, checkpoint research merge
frontend/           PM app: React + TypeScript (Vite) + three.js
Dockerfile, compose.yaml   images (targets dev / prod) and compose profiles dev / prod
research/           cited checkpoint research (JSON) + sales verification
docs/pitch/         pitch deck, script, pptx builder
foundation/         project memory: state, decisions, open questions, reference docs
data/               derived data, settings, 3D models, backups (git-ignored); the database lives in Docker
```

The raw BMW data (`challange information document/`) and `data/` are git-ignored; the database lives in the Docker volume
`pgdata`.
Back up the database with `make backup` (`pg_dump` → `data/backups/`). `make testdata` refreshes the real-data copy
the API tests clone.

## End-to-end workflow

Runs per **checkpoint** (D-040, D-041): JAN 26 (cut-off 31 Jan 2026), then JUL 26 building on it. Every stage is a
recorded run (`checkpoint_run`) at one checkpoint; all commands run from `backend/` with `uv run python -m …`.

| # | Step | Who | Where |
|---|---|---|---|
| 1 | Ingest feedback (10,128 verbatims), customer study, sales, option lists | system | `bmw_req.ingest` |
| 2 | Reference layer (platforms, plants, competitors, market profiles, brand guardrails) + cited checkpoint research | AI-researched, **PM signs off guardrails** | `bmw_req.reference_data`, `research/checkpoints/`, `bmw_req.research` |
| 3 | Classify comments into signals in one shared aspect space; map study, options and research onto it | AI | `bmw_req.structure.classify`, `.classify_context` |
| 4 | Cluster → contextualize (insights, themes, evidence links) → requirement areas | AI | `bmw_req.structure.run_all` |
| 5 | Define → specify (metric + target ladder) → couple (links) | AI **proposes** | `bmw_req.definition.run` |
| 6 | Fit gate (brand, segment, market; feasibility as context) → deterministic prio-v1 score per line × market | AI checks, score is rule-based | `bmw_req.prioritize.run` |
| 7 | PM picks target rungs, reviews links, confirms bands, accepts or rejects AI proposals, sets weights | **Human, mandatory** | PM app: Definition, Prioritize |
| 8 | Requirement document per line × market, export (logged); audit trail | system | PM app: Document, Audit |

The AI never sets a priority: a changed score against a PM-confirmed band becomes a **proposal** with its cause.
Which model each AI step uses, its effort and spend cap are set on the **AI agents** page (D-055).

## How the deliverables map

| BMW deliverable | Where |
|---|---|
| Concept + working prototype | this repo; PM app: Evidence → Structure → Definition → Prioritize → Document |
| Structured requirement list (ID, description, findings + sources, score, rationale, evidence level, assumptions / uncertainties, status) | Document page, Markdown / CSV export (`/api/document/export`) |
| Workflow definition: AI autonomous vs mandatory human review | table above; `foundation/documents/architecture.md` |
| Audit trail: sources → findings → consolidation → scoring → prioritization → human decision | Audit page (per checkpoint); `audit_event` (append-only via triggers) |

## Key design choices

- **Evidence vs assumption** kept apart in every requirement; conflicting evidence linked as `contradicts`.
- **Markets are different customers** — every derivative × market target has its own score, evidence level and
  priority; missing data (e.g. no China verbatims) is shown as an evidence gap, not silently scored as zero.
- **Brand fit** is an approval gate (PM override with rationale); **feasibility** is non-blocking context.
- **OpenAI budget** with limits you set (ask before spending, stop) enforced by a reserving wrapper; every call logged in `llm_usage`, identical calls cached.

Project memory, decisions (D-001 … ) and open questions live in `foundation/`.
