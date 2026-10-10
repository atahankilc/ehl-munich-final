# Decision Log

Append-only. Never delete an entry; supersede it with a new one (`Superseded by D-xxx`).

## Index (read this first; open an entry only when relevant)

| ID | Decision | Status |
|---|---|---|
| D-001 | `foundation/` is the single source of project truth | accepted |
| D-002 | Raw BMW data is read-only and stays out of git | accepted |
| D-003 | Only humans approve/reject/defer requirements | accepted |
| D-004 | Non-LLM tech stack | superseded by D-015–D-020 |
| D-005 | Portfolio-level (multi-model/market/platform/plant); 5 Series deepest | accepted |
| D-006 | OpenAI for all LLM work (framework open, Q-014) | accepted |
| D-007 | Web-enriched 3-layer knowledge base | accepted |
| D-008 | Brand & segment fit gate | accepted |
| D-009 | Platform/plant feasibility gate (blocking? reopened in Q-010) | accepted |
| D-010 | Model tiering luna / sol / embed-3-small | accepted; estimate & thresholds → D-014 |
| D-011 | Markets are distinct customer groups; per-market scores | accepted |
| D-012 | Future-need projection (horizon, Kano) | accepted |
| D-013 | Continuous re-prioritization with snapshots & change proposals | accepted |
| D-014 | Budget plan ≈$60, thresholds $45/$70/$90, $20 demo reserve | accepted |
| D-015 | Orchestration: LangGraph | accepted |
| D-016 | Storage: SQLite, relational tables | accepted |
| D-017 | No graph DB; relational links + graph view in the UI | accepted |
| D-018 | Vector search / RAG: sqlite-vec in the same SQLite file | accepted |
| D-019 | UI: Streamlit | accepted |
| D-020 | Scaffold conventions (Python 3.12/uv, OpenAI SDK direct, Pydantic, pytest) | accepted |
| D-021 | Demo slice G60 × US + G68 × CN; demo table set (Q-017) | accepted |

Keep this index in sync when adding a decision.

Template:

```
## D-xxx — <title>
- Date: YYYY-MM-DD
- Decided by: <person / team / agent (proposed)>
- Status: accepted | proposed | superseded by D-yyy
- Context: why this came up
- Decision: what we do
- Alternatives considered: ...
- Consequences: what this implies / constrains
```

---

## D-001 — Foundation folder is the single source of project truth
- Date: 2026-10-10
- Decided by: team (requested by Atahan)
- Status: accepted
- Context: Multiple agents (Claude Code, Codex) and humans work in parallel sessions during a short hackathon.
- Decision: `foundation/` holds state, decisions, open questions and reference docs. `AGENTS.md` / `CLAUDE.md` point to it and contain only the core rules.
- Alternatives considered: wiki / Notion — rejected, agents can't reliably read it.
- Consequences: every session must read and update the foundation.

## D-002 — Raw challenge data is read-only and stays out of git
- Date: 2026-10-10
- Decided by: team (already in `.gitignore`)
- Status: accepted
- Context: BMW-provided data is confidential.
- Decision: never modify files in `challange information document/`; derived data goes to a separate, git-ignored `data/` folder.
- Consequences: setup instructions must say where to place the raw data on a fresh clone.

## D-003 — Requirements are never approved by AI
- Date: 2026-10-10
- Decided by: derived from challenge brief ("PM firmly in control of every decision")
- Status: accepted
- Decision: AI may only create requirements in `proposed` status and suggest edits/scores. Transitions to `approved` / `rejected` / `deferred` require a human actor and a rationale, both written to the audit trail.

## D-004 — Tech stack (non-LLM parts)
- Date: 2026-10-10
- Decided by: agent (proposed); LLM part superseded by D-006
- Status: superseded by D-015–D-020 (Q-014 resolved 2026-10-10).
- Proposal on the table: Python/FastAPI/SQLite backend, Next.js frontend — see `documents/tech-stack.md`.

## D-005 — Portfolio-level architecture (multi-model, multi-market, platform- and plant-aware)
- Date: 2026-10-10
- Decided by: Atahan (answer to Q-001)
- Status: accepted
- Context: BMW decides across shared platforms (CLAR, FAAR → Neue Klasse), plants and markets, not one car at a time. Improving models within an existing platform beats new platforms on cost. Markets diverge strongly — verified (see `documents/portfolio-reference.md`): BMW+MINI China 2025 −12.5% to 625,527 (BMW official; the −14.2% figure is Inovev, unclear scope), H1 2026 China −20.4%; BMW+MINI Europe 2025 +7.3% to 1,016,360; US +5.0%. 5 Series is built in Dingolfing with a market-specific LWB variant (G68) at Shenyang Dadong.
- Decision: data model handles brands, segments, platforms, vehicle models, markets, plants, production allocation and sales from day one. Requirements are global and target one or more derivative × market combinations. **5 Series (G60/G68) is the deepest worked example**; F70 and G70 run through the same pipeline.
- Alternatives considered: single derivative/market demo (rejected — can't show platform/market trade-offs).
- Consequences: see `documents/architecture.md` v2; portfolio matrix becomes a core UI view.

## D-006 — OpenAI for all LLM/agent work
- Date: 2026-10-10
- Decided by: Atahan (answer to Q-002)
- Status: accepted
- Decision: **OpenAI is the LLM provider** (models, embeddings, web search). Atahan provides `OPENAI_API_KEY`. Model names are env config.
- Not decided here: the orchestration framework (OpenAI Agents SDK vs. LangChain/LangGraph vs. plain SDK), vector DB, graph, RAG design → Q-014.
- Consequences: no Anthropic SDK in the app. Exact models/budget → D-010.

## D-007 — Web-enriched knowledge base
- Date: 2026-10-10
- Decided by: Atahan (answer to Q-003)
- Status: accepted
- Context: BMW's customer data alone is insufficient.
- Decision: three-layer knowledge base (BMW internal · curated reference · web evidence) fed by research agents covering competitors (offers, sales, in-demand models), market demand, reviews, general customer expectations and trends. Every web fact carries URL, dates and trust tier. See `documents/knowledge-base.md`.

## D-008 — Brand & segment fit is a gate on every requirement
- Date: 2026-10-10
- Decided by: Atahan
- Status: accepted
- Decision: every requirement target gets a brand-fit and segment-fit check against a brand profile (what customers expect from BMW vs. Mercedes, Audi, Tesla, Chinese brands…). `fail` blocks approval unless a PM overrides with rationale.

## D-009 — Platform & plant feasibility check on go-to-market
- Date: 2026-10-10
- Decided by: Atahan
- Status: accepted
- Decision: model configurations, shared platforms and plants (location, platforms and powertrains each can build, NK readiness) are reference data. Each requirement target is checked for whether a plant that builds the right platform/powertrain can serve that market in time. `fail` blocks approval unless overridden.
- Note: BMW lists engineering requirements as out of scope. We use platform/plant data only as a **feasibility filter and context** on customer requirements — we never output component/engineering specs. (Confirm framing with BMW mentors, Q-010.)
- Known tension (review 2026-10-10): BMW's out-of-scope list explicitly names "architecture", and most platform/plant reference data is [Trade]/[Unverified]. Whether `fail` should *block* approval is reopened in Q-010 — not changed here.

## D-010 — OpenAI model tiering & $100 budget plan
- Date: 2026-10-10
- Decided by: agent (delegated by Atahan: "picking models is your job"); budget fixed by Atahan at **$100 total**
- Status: accepted — model choice stands; **estimate and guardrail thresholds superseded by D-014**
- Prices: official OpenAI pricing page (developers.openai.com/api/docs/pricing), fetched 2026-10-10, standard tier, per 1M tokens (input / cached input / output). Reasoning tokens are billed as output.
- Model choice:

| Tier | Env var | Model | Price | Used for |
|---|---|---|---|---|
| Bulk | `OPENAI_MODEL_FAST` | `gpt-6-luna` | $0.10 / $0.01 / $0.50 | verbatim classification & extraction, web-result summarizing/extraction, cluster labels, finding summaries, first-pass fit checks |
| Reasoning | `OPENAI_MODEL_SMART` | `gpt-6.1-sol` | $2.00 / $0.10 / $10.00 | requirement derivation, future-need projection, conflict/market trade-off analysis, prioritization rationale, PM "challenge" answers, final brand/feasibility verdicts on `warn`/`fail` |
| Embeddings | `OPENAI_MODEL_EMBED` | `text-embedding-3-small` | $0.02 | clustering / dedupe (semantic search only if retrieval is chosen, Q-014) |
| Not used by default | — | `gpt-6-astra` ($10 / $50) | — | only with explicit team OK |
| Fallback (if luna underperforms on structured output) | — | `gpt-5-mini` ($0.25 / $2.00) | — | — |

- Cost levers: Batch API (~50% off) for all offline bulk jobs; stable system prompts first for cache hits; batch 20–30 verbatims per call; low reasoning effort on luna; cache every result persistently (store open, Q-014) and never re-run unchanged inputs; web search capped by call count.
- Estimate (incl. ~3× re-runs during development):

| Workstream | Model | Estimate |
|---|---|---|
| Classify/extract ~10k unique verbatims (×3 runs, Batch) | luna | ~$1.5 |
| Embeddings (~1.5M tokens, ×3) | embed | ~$0.1 |
| Cluster labels / finding summaries (~300 clusters, top-50 re-labelled with sol) | luna + sol | ~$1 |
| Web research: ≤ 600 search calls ($10/1k) + content tokens | luna | ~$8 |
| Requirement derivation & future-need projection (~100 reqs, ×3) | sol | ~$12 |
| Fit checks (brand/segment/market/feasibility), sol only on warn/fail | luna + sol | ~$4 |
| Re-prioritization runs / rationale generation | sol | ~$4 |
| Interactive PM challenge/edit calls (dev + demo) | sol | ~$10 |
| **Total planned** | | **≈ $40** |

- Note: the model tiering is independent of the open framework question (Q-014); whichever framework is chosen must route calls through the budget guard.
- Guardrails: code-level budget guard — every call logged to `llm_usage` (model, tokens in/cached/out, search calls, $ from a pricing config); warn at $50, block non-demo jobs at **$75**, hard stop at **$90**; **$25 reserved for demo day**. Atahan should also set a $100 hard limit on the OpenAI project dashboard. Running spend is tracked in `STATE.md` → "Budget".

## D-011 — Markets are distinct customer groups (BMW mentor input)
- Date: 2026-10-10
- Decided by: BMW mentor (Discord) → team
- Status: accepted
- Context: PM pain point #1: balancing requirements across markets/regions; preferences differ by **climate, real usage, culture**. "The customer" is not one group.
- Decision: market is a first-class dimension everywhere. A `market_profile` reference (climate, usage patterns e.g. chauffeur/rear-seat use in China, long-distance Autobahn in DE, commuting/large-vehicle norms in US; cultural & brand expectations; charging infrastructure) informs extraction and fit checks. Findings are segmented by market; each `requirement_target` (derivative × market) carries **its own score, priority and fit result**, so one requirement can be Must in CN and Could in EU. Cross-market conflicts are surfaced explicitly (realization options: global, market variant e.g. G68, or package/option).

## D-012 — Extract future requirements, not just past complaints (BMW mentor input)
- Date: 2026-10-10
- Decided by: BMW mentor (Discord) → team
- Status: accepted
- Context: PM pain point #2: getting early feedback and extracting **future** requirements from predecessor feedback.
- Decision: a dedicated "future-need projection" step: predecessor findings + competitor trajectory + trends + market profile → projected need at successor SOP (3–5 yr). Each requirement carries a **horizon** (`today` vs. `at_successor_launch`) and a **Kano class** (basic / performance / delighter) with expected drift (today's delighter → tomorrow's basic, e.g. OTA, ADAS in China). Projections are always E4/assumption-tagged unless backed by current evidence.

## D-013 — Continuous re-prioritization over a ~2-year process (BMW mentor input)
- Date: 2026-10-10
- Decided by: BMW mentor (Discord) → team
- Status: accepted
- Context: Requirements work is an ongoing ~2-year process where priorities are re-evaluated repeatedly — not a one-shot list.
- Decision: requirements are living objects. New evidence arrives in **ingest batches**; each batch, weight change, or PM request triggers a **prioritization run** that snapshots every requirement-target's score, breakdown and rank. The AI may update scores (logged) but only **proposes** priority/status changes; the PM accepts or rejects them. The UI shows priority history over time with the "why" for every change (which evidence/weight/decision moved it). Evidence ages (freshness decay) so stale evidence loses weight unless re-confirmed.
- Consequences: the *conceptual* model gains `ingest_batch`, `prioritization_run`, `score_snapshot`, `change_proposal`, requirement versions (see `documents/architecture.md`). Demo must show at least two time steps (Q-012).

## D-014 — Budget plan re-baselined (supersedes D-010 estimate & thresholds)
- Date: 2026-10-10
- Decided by: agent (delegated by Atahan: model/budget planning; Atahan asked for the fix)
- Status: accepted
- Context: Review found D-010's ≈$40 too low. It ignored reasoning tokens (billed as output), per-target fan-out (requirements × targets × checks), and that reasoning models issue several billed search calls per request. Its thresholds were also inconsistent: a $90 hard stop left only $15 of the "$25 demo reserve".
- Prices: re-checked 2026-10-10 on developers.openai.com/api/docs/pricing, per 1M tokens (input / cached / output):

| Model | Standard | Flex = Batch (-50%) |
|---|---|---|
| `gpt-6-luna` | $0.10 / $0.01 / $0.50 | $0.05 / $0.005 / $0.25 |
| `gpt-6.1-sol` | $2.00 / $0.10 / $10.00 | $1.00 / $0.05 / $5.00 |
| `text-embedding-3-small` | $0.02 | $0.01 (Batch) |

  - Web search: $10 / 1k billed calls + content tokens at model input rates.
  - Cache writes cost 1.25× input (luna/sol). The minimum cacheable prefix is 1,024 tokens; the cache lives 30 min.

- Decision: the model choice from D-010 stays. The plan changes as follows:
  - **Flex** for same-day offline jobs; **Batch** only for overnight jobs (24 h window). Interactive and web-research calls run on Standard (Batch support for `web_search` is undocumented).
  - **Scoring is deterministic** (no LLM). LLMs only write rationale.
  - **Fit checks:** luna does the first pass on every target. sol runs only on `fail`, **once per requirement** (all its targets in one call), not per target.
  - **Web search capped in billed calls (1,000 total)**, not requests. Cap tool calls per request, and count calls from the response.
  - **Reasoning effort:** luna `none`/`low` for classification and extraction. sol `low` by default, `medium` only for derivation/projection; `high`+ needs a team OK.
  - **`max_output_tokens` on every call.**
  - **Pilot before full runs:** 50 verbatims + 5 requirements. Measure real tokens, then re-estimate this table in `STATE.md`.

- Estimate, with explicit assumptions (3 dev runs unless stated):

| Workstream | Assumptions | Tier | Est. |
|---|---|---|---|
| Classify/extract 10,128 verbatims | 25 per call (406 calls); 3.4k in (2k prompt + 25×55); 4k out (160/verbatim incl. reasoning); ×3 | luna Flex | $1.4 |
| Embeddings | 1.5 M tokens ×3 | embed | $0.1 |
| Cluster labels | 300 × (2.1k in / 0.5k out) luna + top-50 × (3k / 1.5k) sol; ×3 | Flex | $1.8 |
| Web research | 1,000 billed calls ($10) + 20k content tokens/call (luna) + 1.5k out/call | luna Std | $13 |
| Requirement derivation + future-need projection | 100 reqs × (15k in / 6k out incl. reasoning) × 3 | sol Flex | $13.5 |
| Fit checks | 1,600 luna checks (4k / 1.5k) per run + sol on ~20 failing reqs (8k / 4k); ×3 | Flex | $4.4 |
| Prioritization rationale | per run: luna 400 targets (3k / 0.8k) + sol top-20 changes (5k / 3k); 6 runs (3 dev + 3 demo waves) | Std | $6.5 |
| PM challenge / edit (dev + demo) | 150 calls × (20k in, ~50% cached / 3k out) | sol Std | $7.7 |
| **Subtotal** | | | **≈ $48** |
| Contingency +25% | prompt iteration, retries, parse failures, cache writes | | ≈ $12 |
| **Planned build spend** | | | **≈ $60** |

- Guardrails (supersede D-010):

| Threshold | Value | Effect |
|---|---|---|
| Warn | **$45** | Warning; re-estimate the plan |
| Block non-demo jobs | **$70** | Only demo-tagged jobs may run |
| Demo reserve | **$20** | From $70 to $90 |
| App hard stop | **$90** | No further calls |
| OpenAI project hard limit | **$95** | Covers enforcement lag and in-flight jobs; it resets monthly, so it backs up the app guard and doesn't replace it. Atahan sets it, plus a $45 alert |

  - Each Flex/Batch job **reserves its worst-case cost before submission**: input tokens + `max_output_tokens` + capped tool calls, at list price. A job that would cross a threshold is refused. After completion the reservation is replaced with actual usage.
  - Every call goes through the wrapper and is logged to `llm_usage`. Spend is tracked in `STATE.md` → Budget.

- Alternatives considered:
  - Keep ≈$40 with sol per target. Rejected: realistic cost is ~$55–150.
  - Use Batch for everything. Rejected: the 24 h window blocks same-day iteration; Flex has the same price.
  - Downgrade derivation to luna. Kept as a fallback lever only, because quality matters most there.
- Consequences:
  - **Levers if the warn threshold hits early:** cut dev runs from 3 to 2 (≈ −$7); luna for all rationale (≈ −$5); web-search cap 600 (≈ −$5).
  - The fallback `gpt-5-mini` costs 2.5–4× luna. Use it only if luna's structured-output quality fails the pilot.

## D-015 — Orchestration: LangGraph
- Date: 2026-10-10
- Decided by: Atahan (approved the agent's Q-014 recommendation table)
- Status: accepted
- Context: Q-014. PM gates and re-prioritization runs need human-in-the-loop pauses and checkpoints (D-003, D-013).
- Decision: multi-step pipelines run as LangGraph graphs. LangChain is **not** adopted: graph nodes call OpenAI through our own budget-guarded wrapper (D-014), never through LangChain model classes.
- Alternatives considered: OpenAI Agents SDK; LangChain; plain SDK + own pipeline.
- Consequences: no graph code until there is a step to orchestrate; the wrapper stays the only path to OpenAI.

## D-016 — Storage: SQLite, relational tables
- Date: 2026-10-10
- Decided by: Atahan (approved the agent's Q-014 table, which offered "SQLite or Postgres"; agent picked SQLite)
- Status: accepted
- Context: Q-014. Audit trail, run snapshots and provenance are naturally rows.
- Decision: one SQLite file at `data/app.db` (git-ignored). Postgres not used: SQLite needs no server and holds vectors too (D-018).
- Alternatives considered: Postgres (+pgvector); DuckDB.
- Consequences: append-only tables for audit/usage; concurrent writers serialized via `BEGIN IMMEDIATE`. The demo data model (which of the ~25 logical entities to build) is still open → Q-017.

## D-017 — No graph DB
- Date: 2026-10-10
- Decided by: Atahan (approved the agent's Q-014 table)
- Status: accepted
- Context: Q-014. The evidence chain is source → finding → requirement → target.
- Decision: model the chain as relational link tables in SQLite; render it as a graph in the UI. No Neo4j/Kùzu.
- Alternatives considered: Neo4j, Kùzu.
- Consequences: graph queries are SQL joins / recursive CTEs.

## D-018 — Vector search / RAG: sqlite-vec
- Date: 2026-10-10
- Decided by: Atahan (approved the agent's Q-014 table, which offered "sqlite-vec or LanceDB"; agent picked sqlite-vec)
- Status: accepted
- Context: Q-014. Retrieval must keep citations traceable to the source item.
- Decision: embeddings (`text-embedding-3-small`, D-010) stored with `sqlite-vec` in the same `data/app.db`; every vector row carries its source ID. LanceDB not used, to keep one store.
- Alternatives considered: LanceDB, Chroma, Qdrant, pgvector.
- Consequences: needs a Python build that allows SQLite extension loading (uv's Python 3.12 does).

## D-019 — UI: Streamlit
- Date: 2026-10-10
- Decided by: Atahan (approved the agent's Q-014 table, which offered "Streamlit or FastAPI + simple frontend"; agent picked Streamlit)
- Status: accepted
- Context: Q-014. BMW values reasoning over architecture; hackathon pace (AGENTS rule 18).
- Decision: one Python Streamlit app for the PM review UI. No separate backend/frontend; Next.js proposal from D-004 dropped.
- Alternatives considered: FastAPI + Next.js; FastAPI + simple frontend.
- Consequences: whole app is Python.

## D-020 — Scaffold conventions
- Date: 2026-10-10
- Decided by: agent, while scaffolding on Atahan's go (implementation details that follow from D-015–D-019, not new architecture)
- Status: accepted
- Decision:
  - Python 3.12 via `uv`, project in `pyproject.toml`, package `src/bmw_req/`.
  - OpenAI Python SDK, **Responses API** called directly inside the wrapper `bmw_req.llm` (also the call path for `web_search`). Structured output via Pydantic models (`responses.parse`).
  - Budget guard per D-014: model prices in `bmw_req/llm/pricing.py`; a model without a price entry is refused; every call needs `max_output_tokens`; worst-case cost is reserved in `llm_usage` before the call (input estimated as UTF-8 bytes ÷ 2, deliberately high) and replaced by actual usage after it.
  - Tests with `pytest`, no paid calls in tests.
- Consequences: logged cost includes the cache-write surcharge (1.25× input, D-014) from `usage.input_tokens_details.cache_write_tokens`. Flex is priced at −50% only when the response confirms `service_tier == "flex"`.

## D-021 — Demo slice and demo table set (resolves Q-017)
- Date: 2026-10-10
- Decided by: agent (delegated by Atahan: "do whatever you want" on Q-017)
- Status: accepted
- Context: Q-017. The logical model in `architecture.md` has ~25 entities; AGENTS rule 18 says build only what the demo needs, but the demo must show D-011 (per-market), D-013 (re-prioritization over time) and the audit trail.
- Decision:
  - **Demo slice** = the proposed path in `STATE.md`: **G60 × US** (verbatims + study + sales) and **G68 × CN** (study + sales + web evidence); G60 × EU optional. F70/G70 use the same code later.
  - **Tables built** (SQLite, `bmw_req/db.py`): all logical entities except three that are folded in:
    - `segment` → text column on `vehicle_model`.
    - `market_profile` → columns on `market` (one current profile per market; history via `audit_event`).
    - `finding_scope` → nullable `vehicle_model_id` / `market_code` / `platform_id` on `finding` (one scope per finding).
  - Added: `source_item.country` (feedback is per country; D-011 RoW groups stay visible), `source_embedding` (sqlite-vec, D-018), `llm_cache` (persist results, never re-run unchanged inputs — D-010 cost lever).
  - `audit_event` is enforced append-only by SQLite triggers.
  - Country → market mapping lives in the `market` rows (config, AGENTS rule 7). Europe incl. GB/NO → `EU`; US → `US`; CN → `CN`; everything else (JP, KR, CA, AU, ZA, …) → `RoW`.
  - Raw xlsx parsing with `openpyxl` (no pandas in the app).
- Alternatives considered: a minimal 8-table model without the continuity layer — rejected, D-013 must be demoed.
- Consequences: one `ingest_batch` per raw file for now; splitting feedback into simulated waves is still Q-012.

