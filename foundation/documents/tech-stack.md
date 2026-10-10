# Tech Stack

## Decided

| Topic | Decision | Ref |
|---|---|---|
| LLM provider | **OpenAI** for models, embeddings and web search | D-006 |
| Models | `gpt-6-luna` (bulk) · `gpt-6.1-sol` (reasoning) · `text-embedding-3-small` | D-010 |
| Budget | $100 total. Plan, prices, thresholds and cost rules live in **D-014 only** (not repeated here); running spend in `STATE.md` → Budget | D-010, D-014 |
| Config | Model names via env (`OPENAI_MODEL_FAST/SMART/EMBED`), never hardcoded | AGENTS rule 12 |
| All LLM calls | Go through one budget-guarded wrapper that logs usage | D-014 |

## Open — candidates for the architecture discussion (Q-014)

**Nothing in this section is decided.** Every item here is to be discussed with the team first, explicitly including LangChain, LangGraph, a vector DB, a graph, RAG and storage. The list only records what has been mentioned so far, so the discussion has a starting point.

| Layer | Candidates mentioned so far | Notes for the discussion |
|---|---|---|
| Language / runtime | Python 3.12 via `uv` (used so far only for data profiling) | Excel/PDF parsing: `openpyxl`/`pandas`, `pdftotext`/`pdfplumber` |
| Orchestration | OpenAI Agents SDK · LangChain · LangGraph · plain SDK + own pipeline | PM gates and the re-prioritization loop need human-in-the-loop pauses + history |
| Retrieval / RAG | RAG over verbatims + web evidence — or none | Citations must stay traceable to `source_item` |
| Vector store | Chroma · LanceDB · pgvector · Qdrant · sqlite-vec — or none | Only needed if retrieval/semantic search is chosen |
| Graph | Graph DB (Neo4j, Kùzu) · relational tables + graph view | Evidence chain source → finding → requirement → target |
| Storage | e.g. SQLite · Postgres · DuckDB | Must support an append-only audit trail and run snapshots |
| Structured output | e.g. Pydantic → OpenAI Structured Outputs | Requirement: every AI output schema-validated before storage |
| Web search tooling | OpenAI `web_search` via Responses API or an agent framework | Provider is decided (D-006); the call path isn't |
| Clustering | e.g. HDBSCAN / k-means on embeddings + LLM labels | Dedupe ~10.1k verbatims |
| Backend / frontend | e.g. FastAPI · Next.js + Tailwind + shadcn/ui · Recharts — or a simpler UI (e.g. Streamlit) | BMW values reasoning over architecture (challenge-brief) |
| Export | JSON + XLSX of requirement list + audit trail | Deliverable format, not a tech choice |

Also on the agenda: the logical data model in `architecture.md` (~25 entities) may be more than a hackathon demo needs (AGENTS rule 18).

## Requirements any chosen stack must meet
- **Precompute:** run pipeline and research offline, cache results with retrieval timestamps, demo against the cache, and re-run only changed steps. Live web search in the demo is optional, with a cached fallback.
- **Raw data path:** read from `RAW_DATA_DIR` (default `./challange information document/BMW-Data`). Derived data goes to git-ignored `data/`.
- **Budget guard:** behaviour as in D-014 (reservation before Flex/Batch jobs, `max_output_tokens`, capped search calls, pilot first).

## Env & secrets

`.env` (git-ignored) will hold `OPENAI_API_KEY` (provided by Atahan), `OPENAI_MODEL_FAST/SMART/EMBED`, `LLM_BUDGET_USD=100` and `RAW_DATA_DIR`. Only `.env.example` is committed; it doesn't exist yet and gets created at scaffolding.

## Local machine notes

System anaconda Python 3.9 has a broken pandas/numpy ABI → use `uv venv --python 3.12`. `openpyxl`, `pdftotext` and `pdftoppm` (homebrew) work.
