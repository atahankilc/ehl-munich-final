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
| D-022 | Extraction v2 (Q-018 fixes) + `signal` / `verbatim_extraction` tables | accepted |
| D-023 | Q-019 re-check of out-of-scope verdicts with sol; signal provenance column | accepted |
| D-024 | Extraction v3: one scope rule, `support_question` flag (resolves Q-020) | accepted |
| D-025 | Verbatim findings: embeddings + agglomerative clustering (0.35), per-market/per-wave metrics | accepted |
| D-026 | Study, sales and option-list ingest; one study finding per item with z-score | accepted |
| D-027 | Simulated ingest waves 1–3, LangGraph wave orchestrator (resolves Q-012) | accepted |
| D-028 | Derivation v3 (sol), evidence linker, portfolio consolidation across lines | accepted |
| D-029 | Scoring v1: weights, renormalization over available factors, gates, bands (resolves Q-004) | accepted |
| D-030 | Feasibility is non-blocking realization context (resolves Q-010, option b) | accepted |
| D-031 | Reference layer + web research agents with citation-filtered URLs and quote verification | accepted |
| D-032 | PM app: Streamlit pages over one service layer; access events logged | accepted |
| D-033 | Wrapper falls back from Flex to standard when Flex is unavailable; per-job run caps | accepted |
| D-036 | PM app organised by the PM's job: Home, guided Review, Priorities by market, AI suggestions; plain labels; demo tour | accepted |
| D-035 | Later waves dedup new drafts against the whole backlog → `extend` proposals (resolves Q-022) | accepted |
| D-034 | Validation fixes: rejected new requirement → status rejected; stale priority proposals superseded; honest new-requirement cause; Streamlit on localhost | accepted |

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

## D-022 — Extraction v2 and signal storage (applies Q-018)
- Date: 2026-10-10
- Decided by: agent; Atahan said "apply the Q-018 fixes and run full G60"
- Status: accepted
- Context: pilot findings (Q-018); the full run needs its output stored.
- Decision:
  - `extract-v2` prompt: new feedback type `complaint` (works as designed, customer dissatisfied); category definitions (trunk/doors → Exterior, HVAC/noise → Comfort & Space, …); stricter quote instruction.
  - Quotes are checked deterministically (contiguous span, whitespace/case normalized); failures are stored with `quote_verified = 0`, not dropped.
  - `prompt_cache_options={"mode": "explicit"}` on extraction calls: the prefix is below the 1,024-token cache minimum, so implicit cache writes were pure +25% input cost.
  - Derivation prompt: explicit horizon and Kano criteria, `horizon_reason`, `kano_drift`, proposed numeric targets marked as assumptions. Not re-validated yet (no derivation run since).
  - New tables: `verbatim_extraction` (one row per verbatim × extractor version, incl. out-of-scope verdict) and `signal` (one row per extracted signal). Findings will be built from signals; `finding_source` still points at `source_item`, so provenance stays verbatim-level.
  - Runner `bmw_req.pipeline.run_extract`: 25 verbatims per call, parallel Flex calls (16 workers), retry with backoff on rate-limit/timeout/5xx, per-run spend cap (default $1), idempotent per extractor version; one `audit_event` per batch (actor ai, model, prompt_ref = extractor version).
- Alternatives considered: storing signals in `source_item.meta_json` — rejected, not queryable for clustering.
- Consequences: changing the prompt means a new `EXTRACTOR_VERSION`; old results stay for comparison.

## D-023 — Re-check out-of-scope verdicts with sol (Q-019 option a)
- Date: 2026-10-10
- Decided by: Atahan ("run the Q-019 re-check"); implementation by agent
- Status: accepted
- Decision:
  - `bmw_req.pipeline.recheck`: verbatims with `in_scope = 0` are re-examined by sol (low effort, Flex) with the first-pass reason and an instruction to extract in-scope parts of mixed verbatims.
  - A flip updates `verbatim_extraction` (in_scope, `recheck_llm_usage_id`), adds signals under the same extractor version, and writes an `audit_event` with before/after. Confirmed verdicts only get `recheck_llm_usage_id`.
  - New column `signal.llm_usage_id` (call/model that produced each signal), backfilled for existing signals; small column-migration helper in `db.py`.
- Consequences: first-pass and re-check signals are distinguishable via `llm_usage.job`. The re-check used a looser rule than the first pass for "customer asked how X works" verbatims → Q-020.


## D-024 — Extraction v3: one scope rule for all derivatives (resolves Q-020)
- Date: 2026-10-10
- Decided by: agent (Atahan delegated full authority over the challenge on 2026-10-10: "you are the sole competitor")
- Status: accepted
- Context: Q-020. v2 + sol re-check treated support-call questions differently depending on the pass; F70/G70 were not extracted yet, so the cheapest moment to make it consistent was before the full runs (Q-020 option c).
- Decision: `extract-v3` for all 10,128 verbatims: mixed verbatims → extract every in-scope part; support-call questions → `difficult_to_use`, severity low, `support_question = 1`; generic praise or unspecified "issues" → out of scope. Scoring weights support questions ×0.5 (option a). v2 rows stay for comparison; everything downstream uses v3.
- Validation: 50-verbatim check incl. 25 recheck flips; benchmark vs BMW labels (`scripts/benchmark_extraction.py`, aggregates only): G60 macro recall v2 0.707 / v3 0.693, lenient recall unchanged; v3 in-scope 91% vs 96% — the 213 newly excluded verbatims are mostly BMW "overall technology" likes and unclassified rows (generic praise), accepted.
- Cost: ≈ $0.31 for all three derivatives (luna Flex).

## D-025 — Verbatim findings by clustering
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: signals embedded (`text-embedding-3-small`, `signal_embedding` vec table, rowid = signal.id); agglomerative clustering (cosine, average linkage, distance threshold 0.35) within derivative × polarity (improve vs like) × category; clusters with ≥ 3 distinct verbatims become findings (`finding_signal`, `finding_source` with the best quote per verbatim); luna labels title/summary/type/coherence. Findings span the derivative's markets; `metrics_json.by_wave[w].markets[m]` holds verbatims, share of that market's in-scope base, severity-weighted count, types, channels, engines.
- Threshold sweep on G60 (0.30–0.50): 0.35 → 243 findings, 93% signal coverage, mean centroid cohesion 0.88. Result: G60 243, F70 166, G70 see STATE.
- Consequence: findings are never rebuilt in place once requirements link to them (the CLI refuses).

## D-026 — Study, sales, option-list ingest; study findings
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: deterministic ingest (`bmw_req.ingest.study/sales/options`); study → `study_metric` with z-score/rank within each model × market column (CN/EU means, US net top2−bottom3); one `finding` per study item (`satisfaction_gap` z ≤ −0.8, `satisfaction_strength` z ≥ 0.8, else `satisfaction_level`) — only notable ones are shown to derivation, all can be linked by the evidence linker. Option lists: luna turns DE price-list pages into 458 equipment items, every source line verified against the page text ($0.02). US/CN equipment = DE is an assumption. F70 China 2024 sales cell is a formula with value 0 (noted).

## D-027 — Simulated ingest waves and wave orchestrator (resolves Q-012)
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: `source_item.wave`: feedback split 50/50 per derivative × channel × market stratum (seed 2026); wave 1 = first half + 2024 sales + option lists + reference + baseline web; wave 2 = second half + customer study + 2025/2030 sales; wave 3 = "market event" web research (2026 launches). Labelled as a simulation everywhere. `bmw_req.pipeline.graph` (LangGraph): open_wave → derive → link_evidence → fit_checks → prioritize. Clusters are computed on all data; a finding is visible from its first wave with wave-specific metrics (documented leak of cluster structure, not of counts).

## D-028 — Derivation v3, evidence linker, portfolio consolidation
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: sol (high effort, Flex) per vehicle line gets top-110 pain/want + top-30 strength findings with per-market metrics, notable study findings, web findings, market profiles, brand guardrails, sales and existing requirements; proposes NEW requirements only (incremental). Every cited finding/target validated; drafts without valid evidence dropped. derive-v3 prompt fixes after the dry run: incremental effort scale and evidence-based market targeting (v2 put nearly every requirement on every market and rated most effort L). Wave 1 drafts of all lines are consolidated by sol into portfolio requirements where the same need appears in several lines. After derivation the luna evidence linker attaches study items (relation from z: supports/contradicts/context) and web findings per target market.

## D-029 — Scoring v1 (resolves Q-004)
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: per target score = 100 × (Σ wᵢ·vᵢ / Σ wᵢ over factors WITH data) × confidence(E1 1.0 / E2 0.92 / E3 0.8 / E4 0.65) + market-fit modifier (+2/−5/−10) + effort (S 0 / M −3 / L −6), clipped 0–100. Default weights: customer voice 30, satisfaction gap 15, market volume 15, competitive pressure 15, future relevance 15, portfolio leverage 10 (PM-editable, versioned). Missing factors are renormalized and shown as explicit evidence gaps (fixes the CN bias); the evidence level keeps confidence honest. Brand fit is a gate only (no double counting). Bands Must ≥ 60, Should ≥ 45, else Could. Evidence level per target is deterministic (verbatim count/channels, study support, T1/T2 web). AI proposes priorities; a PM-confirmed priority that a later run would change becomes a `change_proposal` with the factor-level cause.

## D-030 — Feasibility is non-blocking realization context (resolves Q-010)
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: option (b). BMW lists "architecture" as out of scope and the platform/plant data is partly trade-press; feasibility is checked and shown ("realization context") but never blocks approval and is not a score factor. Brand fit `fail` still blocks approval unless a PM overrides with a rationale.

## D-031 — Reference layer and web research agents
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: curated reference data (`bmw_req/reference_data.py`) loaded with one `source_item(kind=reference)` per cited original source (96; 21 flagged unverified); platforms, plants, production, 21 competitor models, market profiles, BMW guardrails (status "proposed — PM sign-off needed"). Research agents (competitor scout, review miner, trend scout, market profile, market analyst; luna + web_search, ≤ 4 calls/task) return structured evidence; an item is kept only if its URL is among the response's citations (10 dropped), quotes verified by fetching the page where possible (131 verified). 41 tasks (6 tagged wave 3). Web findings grouped per derivative × market by luna (152). Spend $1.69.

## D-032 — PM app
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: Streamlit app (`app.py`, `ui/`), 11 pages (overview, portfolio, backlog, requirement detail, change inbox, market conflicts, findings explorer, weights & runs, audit trail, export, budget). All writes go through `bmw_req.service` (rationale + named actor mandatory, append-only audit). View and export are logged as access events. Challenge = sol answer over linked evidence + semantic search; its edits become change proposals.

## D-033 — Flex fallback and per-job run caps
- Date: 2026-10-10 · Decided by: agent · Status: accepted
- Decision: on `429 flex_unavailable` the wrapper settles the reservation at $0 and retries once on standard processing (same cache key). Run caps in `run_extract` count only the run's own job, so parallel jobs can't trip them (a G60 run aborted for that reason).

## D-034 — Validation fixes (judge/QA pass)
- Date: 2026-10-10 · Decided by: agent (validation session, clear bugs only) · Status: accepted
- Context: end-to-end validation (`documents/validation-report.md`) found bugs that would show in a live demo.
- Decision:
  - `service.decide_proposal`: rejecting a `new_requirement` proposal sets the requirement to `rejected` (human action, rationale, audited). Before, it stayed `proposed`, in the backlog and in every scoring run, although the inbox says "reject to drop it".
  - `scoring.run_prioritization`: every re-score supersedes open priority proposals for that target; before, a stale proposal stayed open when a later run agreed with the PM again.
  - `graph.node_derive`: the cause of a wave ≥ 2 `new_requirement` proposal says whether it cites a finding new in that wave; before, it always claimed "new evidence" (false for 5 of 25 in the demo).
  - `.streamlit/config.toml`: `server.address = "localhost"` — the app served confidential BMW data on all interfaces (AGENTS rule 1). For a demo on another device, change it deliberately.
- Consequences: 2 regression tests (46 total). The `demo` snapshot is unaffected (no rejected new requirements, no stale proposals in it).

## D-035 — Dedup later-wave drafts against the whole backlog (resolves Q-022)
- Date: 2026-10-10 · Decided by: Atahan ("fix the duplicates and rebuild the demo"), implemented by agent · Status: accepted
- Context: wave ≥ 2 derivation saw only its own line's requirements and consolidation only merged one run's drafts → ~9 cross-line near-duplicates in the demo.
- Decision: after per-run consolidation, one sol call (`requirements.match_existing`, job `match_existing:wN`) maps every new draft to an existing non-rejected requirement of ANY line with the same need, or none. A match becomes an `extend` change proposal on the existing requirement (its new targets + new evidence links; audit `match_existing` by AI). Only unmatched drafts are stored as new requirements. Accepting (`service.extend_requirement`) adds the targets/links as human-attributed audit events; new targets are scored by the next run and fit-checked in the next wave (`fit.run` now checks every target without a brand check). Derivation prompts are unchanged, so earlier waves replay from cache.
- Alternatives: show other lines' requirements to derivation (prompt change, re-derivation of all waves); AI extends `proposed` requirements directly (allowed by rule 5, but less visible to the PM).
- Consequences: demo rebuilt ($0.45): 39 requirements (was 53), 151 targets, 14 duplicate drafts → 7 accepted merges (wave 2, scripted) + 7 open merge proposals in the wave-3 inbox. Top-20 pain coverage F70 0.95 · G60 0.95 · G70 0.75. Borderline pairs left by the matcher: REQ-0015/0033 (luggage), REQ-0012/0014/0018 (assistance, wave-1). Wave-1 drafts are still only consolidated among themselves.

## D-036 — PM app organised by the PM's job, in plain language
- Date: 2026-10-10 · Decided by: Atahan ("build it"), implemented by agent · Status: accepted (amends D-032's page set)
- Context: the 11 pages mirrored the data model (pipeline funnel, 20-column backlog, 6-tab requirement page, codes like G60×US / E1 / Kano); Atahan couldn't follow the flow — a judge won't either.
- Decision: sidebar groups *Start here* (Home, Review requirements, Priorities by market, AI suggestions), *Explore & trace* (Requirement details, Market conflicts, Findings explorer, Audit trail), *Under the hood* (Pipeline & data, All requirements table, Portfolio coverage, Weights & runs, Export, Budget). Home leads with the question, a 6-step "how it works", the wave stepper (moved from Overview), what needs a decision and top priorities for `portfolio.FOCUS_TARGETS`. Review = one requirement at a time: the need, customer comments (counts, quotes, small samples and markets without comments flagged), study, cited web evidence, conflicts, AI suggestion per car · market, decision form (reason required; optional "accept the AI priorities" per unset market) and "Ask the AI". Plain labels in `ui/common.py` (car/market names, evidence levels, Kano, horizon, status); AI suggestions are always marked as such. Optional 7-step demo tour. All writes still go through `service.py`.
- Consequences: no pipeline/schema change; existing detail pages unchanged apart from titles. The tour flag lives in plain session state (widget state didn't survive `st.switch_page`).

