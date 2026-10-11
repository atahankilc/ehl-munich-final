# Tech Stack

## Decided

| Topic | Decision | Ref |
|---|---|---|
| LLM provider | **OpenAI** for models, embeddings and web search | D-006 |
| Models | `gpt-6-luna` (bulk) · `gpt-6.1-sol` (reasoning) · `text-embedding-3-small` | D-010 |
| Budget | $100 total. Plan, prices, thresholds and cost rules live in **D-014 only** (not repeated here); running spend in `STATE.md` → Budget | D-010, D-014 |
| Config | Model names via env (`OPENAI_MODEL_FAST/SMART/EMBED`), never hardcoded | AGENTS rule 12 |
| All LLM calls | Go through one budget-guarded wrapper that logs usage | D-014 |
| Language / runtime | Python 3.12 via `uv`; packages `backend/src/bmw_req/` (pipeline) + `backend/src/api/` (API); `uv run …` from `backend/` | D-020, D-052 |
| Orchestration | **LangGraph**. No LangChain; graph nodes call OpenAI through the wrapper | D-015 |
| Storage | **SQLite**, one file `data/app.db` | D-016 |
| Graph | **No graph DB**; relational link tables + graph view in the UI | D-017 |
| Vector store / RAG | **sqlite-vec** in the same SQLite file; every vector row carries its source ID | D-018 |
| UI | **React + TypeScript (Vite) + three.js/react-three-fiber** (`frontend/`) over a **FastAPI** JSON layer (`backend/src/api/`, 127.0.0.1:8600); Streamlit app removed | D-039 (supersedes D-019), D-052 |
| OpenAI call path | OpenAI Python SDK, Responses API, inside `bmw_req.llm` (incl. `web_search`) | D-020 |
| Structured output | Pydantic models → `responses.parse` | D-020 |
| Profiles / deployment | `APP_ENV=development` (API reload + Vite) or `production` (API serves `frontend/dist`); natively via `make`, or Docker (`Dockerfile` targets dev/prod, `compose.yaml` profiles dev/prod, ports on 127.0.0.1, `data/` mounted, allowlist `.dockerignore`) | D-053 |
| Tests | `pytest`, no paid calls | D-020 |
| Data model | Demo table set in `backend/src/bmw_req/db.py` | D-021 |
| Excel parsing | `openpyxl` (no pandas in the app) | D-021 |
| Ingest | `uv run python -m bmw_req.ingest G60` — seeds brand/markets/models, one `source_item` per verbatim ID | D-021 |

## Still open

| Topic | Ref |
|---|---|
| Simulated ingest waves | decided, D-027 |
| — (clustering: scikit-learn agglomerative on `text-embedding-3-small`, D-025; PDFs: `pdftotext`; export: JSON/CSV/Markdown, D-032) | decided |

## Requirements any chosen stack must meet
- **Precompute:** run pipeline and research offline, cache results with retrieval timestamps, demo against the cache, and re-run only changed steps. Live web search in the demo is optional, with a cached fallback.
- **Raw data path:** read from `RAW_DATA_DIR` (default `./challange information document/BMW-Data`). Derived data goes to git-ignored `data/`.
- **Budget guard:** behaviour as in D-014 (reservation before Flex/Batch jobs, `max_output_tokens`, capped search calls, pilot first).

## Env & secrets

`.env` (git-ignored) holds `OPENAI_API_KEY` (provided by Atahan), `OPENAI_MODEL_FAST/SMART/EMBED`, `RAW_DATA_DIR` and `DATA_DIR`; template in `.env.example`. Budget thresholds are constants in `bmw_req/llm/budget.py` (D-014), not env vars.

## Budget guard (as built)

- `bmw_req.llm.LLM.generate()` / `.embed()` are the only way to call OpenAI.
- Each call reserves its worst case in `llm_usage` first (input ≈ UTF-8 bytes ÷ 2, + `max_output_tokens`, + `max_tool_calls` × ($0.01 + 20k content tokens)), at list price. Thresholds apply to settled cost + open reservations.
- After the call, the row is settled with actual tokens (cached, cache-write, reasoning), search calls and cost. Flex is discounted only if the response confirms `service_tier == "flex"`.
- API/connection errors settle at $0; any other failure after the request (e.g. parse error) keeps the worst case.
- A crashed process leaves a `reserved` row that keeps counting — settle or delete it by hand.
- Identical requests (same model, prompt, schema, params) are served from `llm_cache` at $0; pass `use_cache=False` to force a new call.
- The Process → System screen (and `GET /api/budget`) shows spend, committed and the usage log.

## Local machine notes

System anaconda Python 3.9 has a broken pandas/numpy ABI → use `uv venv --python 3.12`. `openpyxl`, `pdftotext` and `pdftoppm` (homebrew) work.
