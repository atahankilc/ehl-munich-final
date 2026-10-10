# Tech Stack

**Status:** Only two things are decided: **OpenAI as LLM provider** (D-006) and the **model tiering + $100 budget** (D-010). Everything else on this page — orchestration framework, storage, vector DB, graph, RAG, backend/frontend — is a **proposal for the architecture discussion (Q-014)**, not a decision. LangChain, LangGraph, vector DB, graph and RAG are to be discussed with the team first.

| Layer | Choice | Why |
|---|---|---|
| Ingestion & pipeline | **Python 3.12**, `uv`, `openpyxl` / `pandas`, `pdfplumber` or `pdftotext` | Excel/PDF parsing |
| LLM provider | **OpenAI** (decided, D-006) | — |
| Orchestration | **Open (Q-014):** OpenAI Agents SDK vs. LangChain / LangGraph vs. plain SDK | To be discussed |
| Retrieval / RAG, vector DB, graph | **Open (Q-014)** | To be discussed |
| Structured output | Pydantic models → OpenAI Structured Outputs | Every AI output is schema-validated before storage |
| Web search | OpenAI built-in **`web_search`** tool (Responses API / Agents SDK `WebSearchTool`) | Citations with URLs out of the box; fallback search API only if needed |
| Embeddings / clustering | OpenAI embeddings (e.g. `text-embedding-3-small`) + clustering (HDBSCAN / k-means), LLM labels clusters | Dedupe & group ~13k verbatim rows |
| Backend API | **FastAPI** + Pydantic | Shares models with pipeline |
| Storage | **SQLite** (SQLModel/SQLAlchemy), append-only `audit_event` | Zero-ops; easy reset/seed. Upgrade to Postgres only if needed |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** | Fast PM review UI |
| Charts | Recharts | Portfolio matrix, score breakdowns |
| Export | JSON + XLSX of requirement list + audit trail | Deliverable |

Model names are **env config, not code**. Chosen tiering (D-010, prices fetched 2026-10-10):

| Env var | Model | $/1M in · cached · out | Use |
|---|---|---|---|
| `OPENAI_MODEL_FAST` | `gpt-6-luna` | 0.10 · 0.01 · 0.50 | bulk classification/extraction, web-result summaries, labels |
| `OPENAI_MODEL_SMART` | `gpt-6.1-sol` | 2.00 · 0.10 · 10.00 | requirement derivation, future-need projection, trade-offs, PM challenges |
| `OPENAI_MODEL_EMBED` | `text-embedding-3-small` | 0.02 | clustering, dedupe, search |

Web search: $10 per 1k calls + content tokens → capped call count.

## Budget guard ($100 total, D-010)

- One LLM wrapper for **all** OpenAI calls → logs to `llm_usage` with cost from `config/llm_pricing.yaml`.
- Thresholds (`config/llm_budget.yaml`): warn $50 · block non-demo jobs $75 · hard stop $90; $25 reserved for demo day.
- Batch API for offline bulk jobs; cache every result; never re-run unchanged inputs.
- CLI `budget` command prints spend by job/model; update `foundation/STATE.md` → "Budget" after every paid run.

## Repo layout (planned)

```
backend/
  app/
    ingest/         BMW data loaders (config-driven)
    reference/      platforms, plants, brands, segments, competitor catalog
    research/       OpenAI agents: competitor, market, review, trend, brand-fit, feasibility
    signals/        classification, clustering → findings
    requirements/   derivation, fit checks, scoring
    audit/          audit event writer
    api/
  tests/
config/             vehicles.yaml, markets.yaml, scoring.yaml, brands.yaml
frontend/           Next.js PM review app
data/               derived/cached data, SQLite db (git-ignored)
foundation/         project memory
```

## Env & secrets

`.env` (git-ignored): `OPENAI_API_KEY` (provided by Atahan), `OPENAI_MODEL_FAST/SMART/EMBED`, `LLM_BUDGET_USD=100`, `RAW_DATA_DIR` (default `./challange information document/BMW-Data`). Commit `.env.example` only.

## Local machine notes

System anaconda Python 3.9 has a broken pandas/numpy ABI → use `uv venv --python 3.12`. `openpyxl` and `pdftotext` (homebrew) work.

## Precompute strategy

Run the pipeline and research agents offline, cache in SQLite (with retrieval timestamps), demo against the cache; re-run only the changed step. Live web search during the demo is optional and should have a cached fallback.
