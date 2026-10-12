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
| D-015 | Orchestration: LangGraph | superseded by D-057 |
| D-016 | Storage: SQLite, relational tables | accepted |
| D-017 | No graph DB; relational links + graph view in the UI | accepted |
| D-018 | Vector search / RAG: sqlite-vec in the same SQLite file | accepted |
| D-019 | UI: Streamlit (superseded by D-039) | superseded |
| D-020 | Scaffold conventions (Python 3.12/uv, OpenAI SDK direct, Pydantic, pytest) | accepted |
| D-021 | Demo slice G60 × US + G68 × CN; demo table set (Q-017) | accepted |
| D-022 | Extraction v2 (Q-018 fixes) + `signal` / `verbatim_extraction` tables | accepted |
| D-023 | Q-019 re-check of out-of-scope verdicts with sol; signal provenance column | accepted |
| D-024 | Extraction v3: one scope rule, `support_question` flag (resolves Q-020) | accepted |
| D-025 | Verbatim findings: embeddings + agglomerative clustering (0.35), per-market/per-wave metrics | accepted |
| D-026 | Study, sales and option-list ingest; one study finding per item with z-score | accepted |
| D-027 | Simulated ingest waves 1–3, LangGraph wave orchestrator (resolves Q-012) | accepted |
| D-028 | Derivation v3 (sol), evidence linker, portfolio consolidation across lines | accepted |
| D-029 | Scoring v1: weights, renormalization over available factors, gates, bands (resolves Q-004) | accepted; customer-voice gap handling amended by D-038 |
| D-030 | Feasibility is non-blocking realization context (resolves Q-010, option b) | accepted |
| D-031 | Reference layer + web research agents with citation-filtered URLs and quote verification | accepted |
| D-032 | PM app: Streamlit pages over one service layer; access events logged | accepted |
| D-033 | Wrapper falls back from Flex to standard when Flex is unavailable; per-job run caps | accepted |
| D-036 | PM app organised by the PM's job: Home, guided Review, Priorities by market, AI suggestions; plain labels; demo tour | accepted |
| D-035 | Later waves dedup new drafts against the whole backlog → `extend` proposals (resolves Q-022) | accepted |
| D-037 | "How it works" page: one requirement traced through all 8 steps, rule beside concrete effect, score waterfall | accepted |
| D-038 | Requirements must be product decisions: defects → quality hand-over, strict merging, no-comment markets can't outrank evidenced ones, one priority for Expected needs (amends D-028, D-029) | accepted |
| D-039 | New PM frontend "Successor": React + three.js (`web/`) over a FastAPI JSON layer (`api/`), redesigned workflow (Briefing → Decide → Cars in 3D → Markets → Evidence → Process), replaces Streamlit (supersedes D-019) | accepted |
| D-040 | Two real-date checkpoints (31 Jan / 31 Jul 2026) replace simulated waves; cited checkpoint research in `research/checkpoints/` | accepted (research layer); pipeline/UI integration pending |
| D-041 | Checkpoint lineage in code (checkpoint, checkpoint_run, track; cp2 must build on cp1), research in the DB, comment galaxy, new black 3D frontend "track-while-scan" replacing the D-039 screens | accepted |
| D-042 | 5 Series = one car line (G68 = China long-wheelbase part of it); car-specific public research moves onto the car rings so every ring changes at JUL | accepted |
| D-043 | Structure & context pipeline rebuilt on checkpoints: extract-v4 (shared aspect space), portfolio-wide incremental clustering, contextualize (insights, themes, evidence graph via RAG), areas (potential requirement areas — drafting is the next step); page 2 "Structure" | accepted |
| D-044 | App name "SharkSight" + minimal shark-nose logo (replaces "Successor") | accepted |
| D-045 | Audit trail separated by checkpoint; pre-rebuild history hidden by default, not deleted (append-only kept) | accepted |
| D-046 | Sales in the AI pipeline: BMW's file only as a labelled relative market weight, trends only from cited public figures, BMW-vs-public conflicts (> 25 %) surfaced; areas carry `metrics.market` | accepted |
| D-047 | Web-agent findings and the reference layer join the evidence pool (as research nodes, K 10 → 14); `relink` re-runs only evidence linking as a NEW contextualize run (lineage kept) | accepted |
| D-048 | Requirement definition layer (page 3): define → specify → couple on checkpoints; customer-experienced metric + target ladder (baseline/threshold/target/stretch, PM picks the rung), every number cited/projected/assumption/gap; requirement links with a "via" resource; grouped by domain, shown on the 3D car | accepted |
| D-049 | Evidence page shows sources only; the AI's reading of an item ("What the AI found", "Used as evidence") moves to Structure, with a "View in Structure" link | accepted |
| D-034 | Validation fixes: rejected new requirement → status rejected; stale priority proposals superseded; honest new-requirement cause; Streamlit on localhost | accepted |
| D-050 | Prioritization layer (page 4): deterministic `prio-v1` per requirement × line × market (Customer 45 / Business 35 / Future 20), bundle band, choose-jointly flags, enabler credit, PM rung changes the stored score, new LLM gate | accepted |
| D-051 | Page 5 "Document" = BMW step 5 deliverable per line × market (all brief fields, JAN→JUL changes, MD/CSV export, logged); PM-editable weights + bands with preview; auto re-score after PM actions; challenged-decision alerts | accepted |
| D-052 | Repo cleanup + monorepo layout: Streamlit app removed (completes D-039); `backend/` (Python) + `frontend/` (was `web/`) + `docs/pitch/`; root Makefile | accepted |
| D-053 | Run profiles `APP_ENV` development/production; Docker image (targets dev/prod) + compose profiles, 127.0.0.1 only, no confidential data in images | accepted |
| D-054 | Adjustable budget + API key in the app: ask-before-spending and stop limits, terminal/app confirmation, key in `data/settings.json` (amends D-014, rule 12/16) | accepted |
| D-055 | AI agents page = source of truth for AI config (per-agent model / effort / on-off / spend cap, model tiers, priced models) + usage; Audit page (whole trail, one checkpoint at a time); audit panel slimmed | accepted |
| D-056 | Document, AI agents and Audit are full-screen 2D pages: no 3D rendered behind them, own checkpoint switch, timeline hidden (supersedes D-051's sheet-over-scene) | accepted |
| D-057 | Wave pipeline retired: old API routes, `pipeline/`, `service.py`, `research/findings.py`, their tests and scripts removed; shared helpers moved; LangGraph dropped (supersedes D-015); old-only DB tables kept for now | accepted |

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
- **Superseded by D-039 (2026-10-11): React + three.js frontend over a FastAPI layer.**
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

## D-037 — "How it works": follow one requirement step by step
- Date: 2026-10-11 · Decided by: Atahan ("improve the process and UI by showing how data is handled step by step and how decisions are made"), implemented by agent · Status: accepted (extends D-036)
- Context: the pipeline graph (Pipeline & data) shows counts, and Requirement details shows tabs per artefact, but nowhere does a reader see one piece of data travel end to end, nor the rule that decided each step.
- Decision: new page `ui/journey.py` in *Start here*, second after Home. Pick a requirement and a car · market; 8 step cards (collect → read/extract → group into themes → draft → fit checks → score → PM decides → new wave re-scores). Each card: who acts (AI with model / System / PM), the rule in plain words, live totals and AI spend for that step on the left; on the right the concrete example — one real verbatim with provenance, the signals the AI extracted (quote verified), the theme it landed in with per-market share, the draft (evidence vs assumption, horizon reason), the four fit verdicts with their effect (gate / modifier / shown / context), the score as a waterfall (factor points after renormalization → evidence-confidence cut → market-fit and effort modifiers → score, with Should 45 / Must 60 lines) plus the factor table, the PM's audited decisions, and the score per wave run with the AI's stated cause. Markets without comments (China) say so and borrow the example from another market of the same requirement. Linked from Home ("how it works" strip), Review ("Walk through it step by step") and the demo tour (step 2).
- Consequences: read-only; no pipeline, schema or scoring change; thresholds are imported from `pipeline/scoring.py` so the page can't drift from the formula (clustering 0.35 / ≥3 comments is restated in text).

## D-038 — Requirements must be product decisions; evidence-poor markets can't top the ranking
- Date: 2026-10-11 · Decided by: Atahan (PM review of the first queued requirement: "what kind of analysis is this?"), implemented by agent · Status: accepted (amends D-028 derivation/consolidation and D-029 scoring)
- Context: the top of the review queue was REQ-0006 "Reliable digital use without interruptions" — (1) a defect complaint restated as a requirement (nobody decides against working software; that is quality engineering), (2) a merge of three different needs (1 Series phone connectivity, 7 Series rear-entertainment start-up, Chinese rivals' rear entertainment) with per-line metrics measuring different things, (3) scored Must 72 in China with **zero** customer comments vs Should 51 in the US with 40 complaints. Cause of (3): D-029 dropped the missing customer-voice factor (30 %) and renormalized, so the remaining factors carried 100 % and the E2 confidence cut (×0.92) was too small. 7 of 39 requirements had a no-comment market on top. "Basic" needs were Must in one market and Could in another.
- Decision:
  1. **Defects → Quality hand-over.** Pain findings with ≥ 50 % defect signals are flagged `quality_issue` in the derivation context and listed on a new *Quality hand-over* page (with evidence, CSV). derive-v7: "X must work reliably" is not a requirement; every draft must state `product_decision` — something BMW could trade off. Coverage rule now targets the biggest pain findings that are *not* quality issues.
  2. **Strict merging.** Consolidation and backlog dedup group drafts only if one product decision satisfies all of them and the metrics measure the same thing; same theme/category is not enough. The linker links web/study evidence only for the same need, not the same theme (Q-021 option c, prompt part).
  3. **Scoring score-v3.** A market without its own usable comment base borrows the car line's comment rate at ×0.5 (labelled "borrowed") instead of dropping the factor; it is capped at the requirement's best comment-backed market unless it has its own study gap AND competitor pressure (both ≥ 0.5) — the cap is a visible modifier. Confidence E3 0.8 → 0.75, E4 0.65 → 0.5. Kano-basic requirements get one proposed priority in every market (the strongest market's band); per-market scores stay visible.
  4. Demo rebuilt from the `evidence` snapshot with these rules.
- Alternatives: hard-filter defect clusters out of derivation (rejected — mixed themes like voice recognition are real capability questions); cap without exception (rejected — China LWB rear-seat comfort is a genuine market difference backed by study + competitors).
- Consequences: China priorities now rest on China's own study + competitor evidence or stay below evidenced markets; the PM sees "borrowed" and "capped" in the score breakdown and the How-it-works waterfall.

## D-039 — New PM frontend: React + three.js over a FastAPI layer, redesigned around the PM's workflow
- Date: 2026-10-11 · Decided by: Atahan ("discard this python library and use something more suitable for 3D rendering"; "the pages seem out of workflow … looks like AI slop"; delegated: "be bold"; chose stack, direction "Cockpit", demo-first) · implemented by agent · Status: accepted · Supersedes D-019.
- Context: the Streamlit app had six overlapping "priority per car × market" views, two diverging decision screens, three pipeline explanations, a buried wave control and could not render real 3D. Atahan pinned Fey (web) as the visual inspiration.
- Decision:
  1. **Stack.** `api/` — FastAPI on 127.0.0.1:8600, one shared SQLite connection behind a lock, every write through `bmw_req.service` / `pipeline.scoring` with actor (X-Actor) + rationale, ActionError → 409, long AI work (wave, challenge) as background jobs. `web/` — Vite + React 19 + TypeScript, TanStack Query, react-router, react-three-fiber/drei (three.js) for the car stage, motion, cmdk. No CORS, localhost only (AGENTS rule 1). Built frontend is served by the API (`web/dist`).
  2. **Workflow / IA** (floating dock, ⌘K everywhere): **Briefing** (what the last wave changed, compiled from the run — no AI call; portfolio pulse car × market; movers; feed) → **Decide** (ONE queue: AI priority changes, merges, requirements to review, AI edits; J/K stepping, A/D/R, reason required, gate override inline, "Ask the AI") → **Cars** (today's car in a 3D studio, requirements pinned on zones, x-ray for interior zones, today's equipment per zone, same-car market comparison, market profile, competitors, plants) → **Markets** (market profile, what it asks of each car, where it disagrees, cited market signals, competitors, study stand-outs) → **Requirement** page (score arc per market, waterfall, history, evidence chain requirement → finding → signal → comment, fit, audit, challenges; "Trace step by step" overlay replaces "How it works") → **Evidence** (findings library, gaps = uncovered themes, quality hand-over) → **Process** (wave timeline + open next wave, runs & weights, audit, deliverable export, system/budget/demo snapshots). **Story mode** ("Present") walks the pitch over the live app.
  3. **Visual world "Cockpit"**: near-black cabin glass, one BMW-like blue for decisions, telltale colours for state, Mona Sans with wide light numerals as instrument readouts; PM-confirmed priority = filled, AI suggestion = dashed + "AI". No BMW logo; product name "Successor".
  4. **3D models**: public CC BY Sketchfab models (1 Series "Bmw-1-series 2025" by teenlin3, 5 Series "i5" by akyolefe319, 7 Series "2023 BMW I7 G70" by NazhDesign; G68 shown on the G60 model), files in git-ignored `data/models/` (downloads need a Sketchfab login), attribution on screen. Zones in a normalised car frame (`car_zones.ZONES`), requirements → zones by keyword rules (no LLM); per-model orientation in `car_zones.MODELS_GLTF`. Placeholder car when files are missing.
- Alternatives: keep Streamlit + embed Sketchfab viewer (rejected by Atahan: not real 3D, workflow problems remain); Next.js (no benefit for a local tool).
- Consequences: Streamlit `app.py`/`ui/` stay until the new UI is accepted, then are removed. Run: `uv run python -m api` + `cd web && npm run dev` (dev) or `npm run build` then the API alone at http://127.0.0.1:8600. API tests in `tests/test_api.py`. Q-025 (model sourcing/orientation calibration).

## D-040 — Two real-date checkpoints instead of simulated waves; checkpoint research layer
- Date: 2026-10-11 · Decided by: Atahan ("divide a year into 2 … randomly apply all the customer feedback into those two … if we know it for sure because it is posted on the internet, use realistic data … Jan 2026 and Jul 2026"; "forget everything we already implemented"), implemented by agent · Status: accepted for the research layer; how classification, clustering, contextualizing and requirement elicitation use it is left to Atahan's next steps · Supersedes D-027's wave definitions once integrated.
- Context: D-027 simulated time with a random 50/50 split plus an invented "market event" wave dated 2026-11 to 2027-11. Atahan questioned why waves exist at all and asked for real, dated public evidence so the effect of time on AI proposals is visible.
- Decision:
  1. **Two checkpoints** = what a PM could know on **31 Jan 2026** (FY2025 results) and **31 Jul 2026** (H1 2026 results). An item belongs to the earliest checkpoint whose cut-off is ≥ its source publication date; nothing published after 31 Jul 2026 is used. Month-only dates count as month end; undated history pages (predecessor background) count as known at Jan and are flagged `undated`.
  2. **Customer feedback** (no dates) keeps the stratified 50/50 split of D-027 (seed 2026): half visible at Jan, all at Jul.
  3. **Research layer** `research/checkpoints/`: `SCHEMA.md` (item schema, trust tiers, pairing rule), `raw/<topic>.json` from 8 research agents (markets, BMW portfolio + predecessors G30/G11/F40, premium competitors, EV challengers, segment sales, tech trends, policy & macro, consumer studies), merged and validated by `scripts/checkpoints_merge.py` → `checkpoints.json` (821 items, 778 quotes checked on the page, 299 metric pairs across both checkpoints; T1 369 / T2 323 / T3 129). Public web data only, so it is committed.
  4. **Comparisons use year-on-year change and shares**, never absolute volumes (full year vs half year). When a figure has no Jul update, the Jan value is shown as "old", not dropped.
  5. **Checkpoint Atlas** (`scripts/checkpoints_page.py` → `atlas.html`, a local page; not published) visualises the layer with a two-step Jan/Jul switch bottom-right; every mark opens its source.
- Consequences: research gaps tracked in Q-026. The pipeline still runs on the D-027 waves until Atahan leads the classification → clustering → contextualization → elicitation rebuild.

## D-041 — Checkpoint lineage, comment galaxy and a new 3D frontend
- Date: 2026-10-11 · Decided by: Atahan ("design a black bg app with minimal design philosophy … graphic and 3D … make sure the second checkpoint will work on the output of checkpoint 1 and recalibrate requirements with the newly added data"; chose: comment galaxy as the first view, all BMW-internal data known at Jan, replace the old app, direction "track-while-scan"), implemented by agent · Status: accepted · Implements D-040; supersedes D-027's wave definitions and the D-039 screens.
- Decision:
  1. **Schema:** `checkpoint`, `checkpoint_run` (stage, parent_run_id), `track` (new/held/strengthened/weakened/lost with weight and prev_weight), `source_layout`; `source_item.checkpoint`. Module `bmw_req/checkpoints.py`: visibility rules, research import (`research/checkpoints/checkpoints.json` → `source_item(kind=research)`, 1,028 items), `start_run` refuses a cp2 run without a completed cp1 run of the same stage, `write_tracks` computes states against the parent and writes `lost` rows explicitly. Stage `acquire` run at both checkpoints (cp2: 6,645 held, 5,610 new). Tests: `tests/test_checkpoints.py`.
  2. **Galaxy:** all 10,128 raw comments embedded with text-embedding-3-small ($0.009) and laid out once in 3D (`bmw_req/pipeline/galaxy.py`); no AI interpretation of the text.
  3. **Frontend:** the D-039 screens and components are deleted; new app = checkpoint provider + sweep control + Scan screen (React + react-three-fiber, same stack). Colour encodes track state (blue = acquired by this sweep, white = held), not categories; isolation by car/market/channel/label/engine via the key.
- Consequences: the old API endpoints stay until the new screens replace them; their tests assume the 3-wave demo DB (3 fail on the current wave-1 DB, unrelated to this change). The calibration lab (`web/lab.html`, `web/src/three`) is kept.

## D-042 — One 5 Series; car rings carry dated public data
- Date: 2026-10-11 · Decided by: Atahan ("merge them into one 5 Series sector"; chose "add public July data" for the static rings), implemented by agent · Status: accepted
- Context: G68 has no comments and no own sales row (BMW's sheet is one G60_G68 tab); as its own car it was a near-empty sector. Study, options and sales rings never changed at JUL because BMW's files exist once (all known at JAN, D-041).
- Decision:
  1. **The 5 Series is one car line.** Requirements belong to the line; the China target is realised on the G68 (`market_variant`), US/EU on the G60. The G68 stays a separate vehicle in the data. On the scan: three car sectors; the last ~28 % of the 5 Series sector is the "LWB · China" part (G68 study items and sales, China research).
  2. **Car-specific public research goes onto the car's rings** (`api/routers/scan.py: research_cars / research_ring`): sales metrics → sales ring (stem = public volume), studies/reviews/awards → study ring, product news → options ring. They are contacts like the comments (dot = held, ring = acquired at JUL, flare when the sweep passes), drawn beside BMW's own marks and never blended with them (Q-015). The date ring keeps the remaining research and moved inside, next to the comments.
- Consequences: at JUL every ring gains items (public H1 2026 sales, J.D. Power 2026 IQS/APEAL awards, ADAC 2026, the 7 Series facelift and i7-China news). Matching is a regex on entity/headline; items naming BMW as a whole are matched by headline.

## D-043 — Structure & context: classify → cluster → contextualize → elicit, per checkpoint
- Date: 2026-10-11 · Decided by: Atahan (fresh extraction; evidence graph in SQLite with RAG; page 2 "collapse into structure"; "spawn sub agents to find optimizations … I want to see improvements with the new data"), designed from three read-only reviews (classification, clustering, contextualize), implemented by agent · Status: accepted
- Decision (code in `src/bmw_req/structure/`, every stage a `checkpoint_run`; cp2 builds on cp1):
  1. **classify** (`classify.py`, extract-v4): fixed ~45-aspect taxonomy shared by all sources (`taxonomy.py`); intensity (1–3) separate from impact; nature/want_kind/occupant/context/benchmark/future_cue/explicit; one signal per (aspect, nature); hints for Source C self-reported severity and the Source D survey prompt (never quoted); quotes ≥ 4 words; ~2.6k-token cacheable prompt; 20 comments per luna Flex call. cp2 classifies only the delta. A/B on a fixed 400-comment sample (`scripts/benchmark_classify.py`, `data/eval/classify_ab.json`): BMW-label macro 0.609 → 0.615, likes 0.84 → 0.90, "serious" → high 0.17 → 0.37, "minor" → low 0.22 → 0.49, quotes < 4 words 13 % → 5 %, survey-prompt quotes 10 → 0, Korea in-scope 0.71 → 0.76, aspect coverage 0 → 99 %; wants 0.56 → 0.54 (≈). `classify_context.py`: study rows (|z| ≥ 0.8 → gap/like), research (luna: aspect + nature), options (aspect) into `source_aspect`.
  2. **cluster** (`cluster.py`): portfolio-wide within polarity × category, average linkage 0.35 + recursive split of oversized clusters; stable keys `cl:<pol>:<cat>:<anchor>`; cp2 assigns new signals to cp1 clusters (mean-member cosine ≤ 0.35), clusters only leftovers; track weight = comment share, strengthened/weakened only if ≥ 10 % relative AND |z| ≥ 1.96 (the random JAN/JUL split must not look like change).
  3. **contextualize** (`contextualize.py`): luna standardizes one insight per cluster (title, statement, need type, quality issue, product decision); duplicate judge on cosine ≥ 0.86 pairs; themes (average linkage 0.45 on statement embeddings, cp2 joins nearest cp1 theme ≥ 0.55); RAG: research/study/options embedded once (`node_embedding`), per theme top-k checkpoint-visible candidates verified by luna into typed `evidence_edge`s (supports, contradicts, competes_with, trend_for, available_as_option, context). cp2 re-runs only changed clusters/themes; clean ones carry their edges as held.
  4. **areas** (`areas.py`): this step structures, it does not draft requirements (Atahan: drafting proposals is the next step). sol groups the themes into 15–40 potential requirement areas (title, need, kind improve / keep / emerging, why now from the given evidence, ≤ 3 open questions for drafting); code adds comments, line × market coverage and evidence counts; quality-only themes form a separate quality list. cp2 keeps area keys, attaches new themes, records change notes; tracks significance-tested. `elicit.py` (candidate drafting with code checks: future horizon needs a dated trend edge, own-market evidence per target, cited ids from the theme's edges) is kept for the next step and not run here.
  5. **Page 2 "Structure"** (`/structure`, same canvas as the scan): comments morph into their clusters; cluster nodes (blue improve / white keep; dot held, ring new, double ring strengthened, amber weakened/lost), theme halos, requirement-area diamonds above their themes, evidence arcs to the exact ring items; stage funnel; live agent panel (stages, progress, feed of AI steps from the audit trail; comments flash as they are classified); inspectors for clusters (signals with quotes), themes (evidence by relation) and areas (need, why now, open questions, coverage); "What the AI found" on comments and research on page 1. API `api/routers/structure.py`.
- Consequences: the old pipeline (`pipeline/`, extract-v3, findings, requirements, linker) stays for history but the new screens read only D-043 tables. Q-021 (over-linking) and the D-038 defect rule are enforced in code here.

## D-044 — App name "SharkSight" and the shark-nose logo
- Date: 2026-10-11 · Decided by: Atahan ("SharkSight olsun, logoyu çizip uygulamaya ekle, minimal bir logo olsun"), implemented by agent · Status: accepted · Renames the D-039 app "Successor".
- Decision: the app is called **SharkSight**: BMW's forward-leaning "shark nose" (Haifischnase, back in the Neue Klasse concepts) + foresight, because the app projects successor requirements. Pitch line: "Smaller kidneys. Sharper foresight." The logo is a great white's head seen straight from the side, abstracted to a single geometric line (dome to the snout tip, a straight mouth cut, the lower jaw), traced from a reference photo Atahan supplied (`web/src/components/Logo.tsx`, `web/public/favicon.svg`). No BMW roundel or M logo, to avoid trademark issues and to avoid looking like an official BMW product.
- Consequences: the wordmark sits left of the page tabs at top centre; the top-bar pills (Evidence, Structure, Audit) grew from 28 to 32px, 13px text, to carry it. The localStorage key `successor.actor` is kept so the saved PM actor survives the rename.

## D-045 — Audit trail separated by checkpoint; pre-rebuild history hidden, not deleted
- Date: 2026-10-11 · Decided by: Atahan asked to separate the audit trail by checkpoint and allowed erasing the rows from before the app refactor; implemented by agent · Status: accepted.
- Decision: `/api/audit/feed` shows only the selected checkpoint's rows on the Evidence and Structure scopes. "Everything" shows both checkpoints, each tagged. The classifier's A/B test is tagged `ab` (shown in Everything only). A data load that fed both checkpoints is split into one row per checkpoint with its item count. Rows from before the first checkpoint run (the old wave-based app, 1,114 events) are **not deleted**: `audit_event` is append-only by rule 6 and DB triggers. Instead the feed leaves them out unless `history=true`, which is a toggle at the end of Everything ("Show history before the checkpoint rebuild").
- Consequences: no history is lost. A physical delete would mean dropping the append-only triggers and needs an explicit PM decision. A backup of the DB and a JSON export of the pre-rebuild rows were taken anyway (`data/backups/`, git-ignored).

## D-046 — Sales in the AI pipeline: BMW's file as a labelled weight, trends from public figures, conflicts surfaced
- Date: 2026-10-11 · Decided by: Atahan ("satış verisini de AI kullansın … ama verilerin yanlışlığını teyit et"), after the sales verification (`research/sales-verification.md`, Q-015 note); implemented by agent · Status: accepted.
- Context: the verification found the ingest correct (36/36 rows match the xlsx) but BMW's market split implausible (5 Series US ≈ 3× public, China LWB 21–39 % low, 7 Series grows +24 % vs −5.6 % public; the 5 Series global total matches), and every 2024 → 2030 growth contradicts H1 2026 public declines. Clustering stays comment-only (study/research enter via the evidence graph).
- Decision (`src/bmw_req/structure/market.py`, deterministic, no LLM):
  1. **BMW's sales file = relative weight only**: share of BMW's 2025 volume per car line × market (G60 + G68 summed), always labelled "internal and stylized (Q-015)". Its growth is never used as a trend.
  2. **Trends only from cited public research items** visible at the checkpoint: latest year-over-year change per line × market with source id, period, region and trust tier; longer periods beat single months; partial figures are skipped (combined lines, model families like "1/2 Series", single powertrains like i7 BEV). Germany stands in for Europe and is shown as DE.
  3. **Conflicts surfaced**: where BMW's file and a comparable public full-year figure (same line, market, year; global vs the line total) differ by more than 25 %, the market is flagged instead of either figure being silently preferred (today: 5 Series US +188 %, 5 Series China −35 %).
  4. **Areas**: the sol prompt gets a compact `market_context` (shares, trends, conflicts) with the rule that inferred causes are worded as assumptions and BMW figures are not relied on where they conflict; every area gets an additive `metrics.market` (markets its comments come from, BMW share, public trend, conflict flag). Existing areas get it by a no-LLM backfill (`python -m bmw_req.structure.market --backfill`); no re-run of areas.
  5. **UI**: the area inspector shows a Markets table (comments, BMW volume share, public trend with tier + source id, "≠ public" mark) with the label.
- Consequences: no new paid calls. Prioritisation/scoring (not rebuilt for the D-043 pipeline yet) can use the same weights later. Open for BMW (Q-015): is the US row US-only, and does China include the i5 LWB and imports?

## D-047 — Web and reference findings join the evidence pool; `relink` as a new contextualize run
- Date: 2026-10-11 · Decided by: Atahan ("evet yapalım") after an audit of what the AI never reads; run order agreed with the main session · Status: accepted.
- Context: contextualize's evidence linking (D-043 step 4) only considered `source_item.kind = 'research'`. The web-agent findings (`web`, 138 visible) and the reference layer (`reference`, 88 visible: competitor features, trends, market facts) were never candidates, although they are cited sources of exactly the competitor / trend kind the links need.
- Decision:
  1. `node_texts` / `visible_nodes` include kinds `research`, `web` and `reference` as node type "research" (one source_item id space; the item's kind stays on `source_item` for provenance, so the evidence counts, inspector and theme views work unchanged; 3D arcs skip items without a ring position). Nearest research candidates per theme 10 → 14 so they don't crowd out research. Undated web items stay invisible (D-041).
  2. `contextualize.relink(cp)` re-runs only step 4 as a **new** contextualize run: copies the latest completed run's insights, theme membership and non-evidence edges (belongs_to, duplicate_of, sub_need_of) and insight/theme tracks, links every theme against the current pool (one luna Flex call per theme), writes edge tracks against the parent and supersedes the old run. Never in place: a completed run's edges stay as they were (rule 6, D-041 lineage). Order: cp1, then cp2, so cp2's edge states compare against the new cp1 edges.
  3. Areas are not re-run: `market.backfill()` (D-046) recounts `metrics.evidence` per area from the latest contextualize run of its checkpoint, with no LLM.
- Consequences: a few cents of luna + embeddings; run after the cp2 chain finishes, pilot cp1 first, update the Budget section. Brand, market-profile, platform and plant reference tables stay for the requirement-drafting step (not run, per Atahan).

## D-048 — Requirement definition: measurable ladders, coupled requirements, shown on the car
- Date: 2026-10-11 · Decided by: Atahan ("go ahead, i agree" to the proposal: ladder with PM choosing, 1–3 requirements per area, links feed prioritization as bundles/flags/enabler credit without automatic penalties, ≤ $0.5 gap research); implemented by agents · Status: accepted · Builds on D-043 (areas), D-038 (one product decision, one metric), D-012 (future horizon), D-046 (market weights). Contract: `documents/requirement-definition.md`.
- Context: BMW's reference process step 3 asks for specification & quantification ("Range: 600 or 700 mi?", "Cooler for how many bottles?", "Seat ventilation: fast enough?"), grouped by Exterior / Interior / Powertrain / Driver assistance. `elicit.py` (never run) had metric names but no values, no acceptance criteria, no benchmarks and no links; cited numbers existed only as free text.
- Decision:
  1. **Areas are BMW's step 2** ("potential requirements, 0/1"); the new layer drafts **1–3 requirements per non-quality area** (`define`, sol), each one product decision.
  2. **`specify`**: one customer-experienced metric (no component specs — scope), ≤ 4 acceptance criteria with market conditions, and a **target ladder per line × market**: baseline (today's BMW) → threshold (competitive parity) → target (projected to launch) → stretch (delighter). Every level has a basis `cited | projected | assumption | gap`; code downgrades unverifiable citations and never fills a gap with an invented number. The AI recommends a rung; **the PM chooses** (append-only `def_choice` + audit).
  3. **`benchmarks`**: a `spec_fact` table of cited numeric facts (attribute, value, unit, cycle, entity, source) extracted with luna from research / web / reference items, plus one capped gap-research round (≤ $0.5). Visibility follows the source's checkpoint, so a competitor raising the bar between JAN and JUL moves the ladder at cp2.
  4. **`couple`**: requirement links `conflicts | competes_for | enables | synergy` with a **via** resource (energy, mass, thermal, package, attention, aero, acoustic, compute). Candidates come deterministically from shared resources (`definition/domains.py`), luna judges, sol re-checks strong/conflict links. Links are proposals; the PM confirms/removes/adds (`def_link_review`). Relational table, no graph DB (D-017).
  5. **Domains and car zones are config** derived from aspects (`definition/domains.py`), never chosen by the LLM; zone `underfloor` (battery & energy) added to `car_zones.ZONES`.
  6. **Prioritization (next layer)** uses links as bundles (strong components prioritized together), conflict flags between Musts ("choose ladder levels jointly") and enabler credit — no automatic score penalties from conflicts.
  7. **Page 3 "Definition"**: requirement pins on the 3D car by zone, coloured by domain; selecting one flies to its zone and shows the ladder; links are drawn as arcs through the car labelled with the via.
- Consequences: planned spend ≈ $3–4 for both checkpoints (pilot first). The old `requirement` tables stay for history. Open: scoring rebuild on `def_requirement` (prioritization layer).

## D-049 — Evidence shows sources only; the AI's reading lives on Structure
- Date: 2026-10-11 · Decided by: Atahan ("we dont need to show what the ai found and used as evidence in evidence page … show them … on the structure page"; chose: with a link across), implemented by agent · Status: accepted · Sharpens D-041/D-043 (page 1 raw evidence, page 2 AI structure); AGENTS rule 4 (evidence vs. interpretation).
- Decision: on Evidence the inspector shows only the source (quote/figure, facts, provenance, link). "What the AI found" (signals) and "Used as evidence" (theme links) render only on Structure. Evidence instead shows one line, e.g. "Used in 3 themes at JUL 26" / "Grouped into a cluster at JUL 26", with **View in Structure** that switches page and keeps the item selected; a comment opens its cluster (comments are not selectable on Structure). No link when the AI did not use the item.
- Consequences: frontend only (`web/src/screens/scan/Scan.tsx`, `Guide.tsx`, `scan.css`); no API or pipeline change.

## D-050 — Prioritization on the definition layer: prio-v1, bundles, rung-aware, new gate
- Date: 2026-10-11 · Decided by: Atahan ("go ahead with your own guts") on the four open questions of the prioritization proposal; the agent's recommended defaults were taken · Status: accepted · Builds on D-029/D-038 (scoring machinery), D-046 (market weights), D-048 (definition layer). Contract: `documents/prioritization.md`.
- Decision:
  1. Unit = requirement × car line × market target; a new deterministic stage `prioritize` (no LLM) writes `prio_score` with a factor breakdown and templated rationale.
  2. Weights prio-v1: Customer 45 (voice 30, satisfaction gap 15) · Business 35 (competitive gap from the ladder 15, market weight 10 — cut from 15 because BMW's sales file is stylized, portfolio leverage incl. enabler credit 10) · Future 20. Editable, versioned.
  3. **One band per synergy/enables bundle** (strongest member's); individual scores stay visible. Conflicts/competes-for between two Musts → "choose jointly" flag, no penalty.
  4. **The PM's chosen ladder rung changes the stored score** (effort + confidence); without a choice the AI's recommended rung is used; a what-if endpoint shows other rungs.
  5. **New LLM gate** (brand / segment / market / feasibility) on the new requirements (≈ $0.40 cp1, ≈ $0.10 cp2); brand fail blocks approval unless overridden (D-008), feasibility non-blocking (D-030). Old fit verdicts are not reused (different requirements).
  6. cp2 band changes → `prio_proposal` with factor deltas and cause; PM decisions append-only (`prio_decision`).
- Consequences: new tables (old `fit_check` / `change_proposal` FK to the legacy `requirement` table); page 4 "Prioritize".

## D-051 — Document page, editable weights/bands, auto re-score, challenged decisions
- Date: 2026-10-11 · Decided by: Atahan ("olur ekle", "aç beşinci sayfayı"; asked for visible decisions and warnings when a decision is later contradicted) · Status: accepted · Builds on D-050. Docs: `documents/prioritization.md` (As built), `documents/document.md`.
- Decision:
  1. **Weights and Must/Should thresholds are PM-editable** on page 4 (preview without writes; save needs a rationale → new prio-v1 weights version, numbered within the scheme; audited). Bands that move because of weights become proposals with cause `weights_changed`; PM decisions are never changed silently.
  2. **Auto re-score:** after a PM decision, proposal verdict, weights save, ladder-rung choice or link review, `prioritize` re-runs (deterministic, ~0.1 s per checkpoint) for that and every later checkpoint in a background worker, so a JAN decision contradicted at JUL shows up at once. A rejected proposal is not re-proposed unless the score moves ≥ 5 points.
  3. **Challenged decisions are prominent:** PM-confirmed targets carry the PM's blue mark ("M ✓", One Blue Rule); open proposals against a PM band show a white "!" with the AI's proposed band and cause on the column, in the matrix, the list, and a "N of your decisions are challenged" notice.
  4. **Checkpoint visibility fix:** proposals/decisions only show at checkpoints where they are visible (JAN leaked 38 JUL proposals).
  5. **Page 5 "Document"** (BMW step 5): per line × market the final, traceable requirement list with every deliverable field from the brief (ID, description, sources, priority/score, rationale, evidence level, assumptions/uncertainties, decision status) plus metric/ladder/acceptance, gates, links, history; JAN → JUL changes; Markdown/CSV export, each export audited.

## D-052 — Repo cleanup and monorepo layout
- Date: 2026-10-11
- Decided by: Atahan (asked for cleanup + standard structure; chose "full monorepo split" over a Python-only tidy)
- Status: accepted
- Context: D-039 replaced the Streamlit app but it was still in the repo (`app.py`, `ui/`, `.streamlit/`, `streamlit` dependency pulling pandas/altair); Python packages, tests, scripts and the frontend sat side by side at the root.
- Decision:
  1. Remove the Streamlit app and dependency; remove unused npm deps `cmdk`, `motion`; untrack `web/tsconfig.tsbuildinfo` (`*.tsbuildinfo` ignored). Declare directly imported `httpx`, `numpy`; `pitch` dependency group (`python-pptx`, `pillow`) for the pptx builder.
  2. Layout: `backend/` = `src/bmw_req/`, `src/api/` (was root `api/`), `tests/`, `scripts/`, `pyproject.toml`, `uv.lock`, `.venv`; `frontend/` = the PM app (was `web/`); `docs/pitch/` (was `pitch/`). Unchanged at the root: `foundation/` (D-001), `research/`, `data/`, `.env`, raw data folder (rule 1), AGENTS/CLAUDE/DESIGN/PRODUCT/README. Root `Makefile` (`install`, `api`, `dev`, `build`, `test`).
  3. `bmw_req.config.ROOT` stays the repo root (`parents[3]`), so `data/`, `research/` and `.env` paths are unchanged; the API serves `frontend/dist`; `demo_state.py` is loaded from `backend/scripts/`.
- Alternatives considered: Python-only tidy (`api/` into `src/`, keep `web/`); cleanup only.
- Consequences: all `uv run …` commands run from `backend/` (or via `make`). Older entries and the session log keep their original paths (`web/`, `api/`, `scripts/`, `src/bmw_req`) — read them as `frontend/`, `backend/src/api/`, `backend/scripts/`, `backend/src/bmw_req`. New `reference` ingest batches record `backend/src/bmw_req/reference_data.py` as file.

## D-053 — Run profiles and containers
- Date: 2026-10-11
- Decided by: Atahan (asked for development/deployment profiles, "on containers maybe"); details by the agent
- Status: accepted
- Context: host, port and mode were hardcoded (`127.0.0.1:8600`, no reload); dev (API + Vite) and demo (API serving the build) were only told apart in docs.
- Decision:
  1. `APP_ENV=development|production` (default development; anything else fails at start). development: uvicorn reload on `backend/src`; production: no reload, warns if `frontend/dist` is missing. `API_HOST`/`API_PORT`/`API_RELOAD` env overrides; Vite reads `API_URL`/`VITE_HOST`. Defaults unchanged (127.0.0.1).
  2. Containers: one multi-stage `Dockerfile` (node build → python 3.12-slim + uv; targets `dev`, `prod`), layout mirrors the repo so `ROOT=/app`. `compose.yaml` profiles `prod` (one container) and `dev` (API with bind-mounted source + Vite container). Ports published on 127.0.0.1 only; inside the container the server listens on 0.0.0.0 (needed for port publishing).
  3. Confidentiality (AGENTS rule 1): `.dockerignore` is an allowlist; raw BMW data, `data/` and `.env` never enter an image — `data/` is mounted, `.env` passed as env_file. Raw data is not mounted (pipeline CLIs run natively).
  4. Makefile: `api`/`dev` (native dev), `serve` (native prod), `up`/`up-dev`/`down`/`logs` (containers).
- Alternatives considered: native only; separate frontend server (nginx) in prod — unnecessary, the API already serves the build from the same origin.
- Consequences: native and container runs must not overlap (same port, same SQLite file). In development a code save restarts the API and ends any job running in it. Images are local only — nothing is pushed to a registry.

## D-054 — Adjustable budget limits and API key in the app
- Date: 2026-10-11
- Decided by: Atahan (post-hackathon: "make it adjustable … a setting to put the API key and then determine when it stops or gives a prompt to the user so the user is more careful"); details by the agent
- Status: accepted (amends D-014 thresholds; AGENTS rules 12 and 16 updated)
- Context: the hackathon's fixed $100 plan (warn $45 / block non-demo $70 / hard stop $90, constants in code) no longer fits; Atahan continues solo and wants to control the budget directly.
- Decision:
  1. `bmw_req.app_settings`: API key + two limits in `$DATA_DIR/settings.json` (0600, outside `app.db` so snapshot restores never touch it; `APP_SETTINGS_FILE` overrides the path). A key saved in the app wins over `.env`; removing it falls back to `.env`.
  2. Guard (`llm.budget.reserve`): **stop at** (default $90) — no call crosses it; **ask before spending above** (default $45) — a run must be confirmed once: terminal `[y/N]`, `BUDGET_CONFIRM=1`, or `budget.approved()` for an API job the user confirmed in the app; else `BudgetNeedsConfirmation`. Stop is checked before asking; the prompt never holds the DB write lock. The API never prompts on its terminal. The hackathon "block non-demo" threshold is dropped.
  3. API `/api/settings` (GET; PUT `/openai-key` checks the key with a free `models.list` call first; DELETE `/openai-key`; PUT `/budget`). The key is never returned (masked `sk-…abcd`); every change is an `audit_event` (entity `setting`) with the masked key only.
  4. UI: Audit → Usage gets "OpenAI API key" and "Spend limits" above the figures; the budget bar is scaled to the stop with a mark at ask-before-spending.
- Alternatives considered: key in `.env` written by the app (not persistent in containers, where `.env` is only an env_file); settings in `app.db` (snapshot restore would roll them back); a per-run estimate gate (no reliable per-run estimates yet).
- Consequences: the app has no login (D-053 note) — anyone who can reach 127.0.0.1:8600 can change the key and limits; fine on localhost, must change before any shared deployment. Agents must not confirm spend or raise limits on their own (rule 16). The old wave/challenge API jobs don't take a confirm flag — they are unused by the frontend and slated for removal.

## D-055 — AI agents page and Audit page
- Date: 2026-10-11
- Decided by: Atahan ("take the agents page out of the audit panel … configure which agents are used where and how much, with the usage data … a real source of truth"; "for auditing … its own page with all the audit logs together, checkpoints separated"); details by the agent
- Status: accepted
- Decision:
  1. **Agent registry** `bmw_req.llm.agents`: 22 agents of the checkpoint pipeline (sources, structure, definition, prioritization), each matched to its `llm_usage.job` names, with the code's defaults (tier, reasoning effort, web search). Jobs of the earlier wave pipeline match no agent — history only, not configurable.
  2. **Per-agent settings** in `data/settings.json` (`app_settings`, beside D-054's key and limits): model (else the tier's), reasoning effort (else the code's), on/off, spend cap (total committed spend of the agent). `LLM.generate()` / `.embed()` apply them on every call; the guard refuses an agent that is off or would pass its cap (`AgentBlocked`, a `BudgetExceeded`, so pipelines stop as on a budget stop). A changed model/effort is a new cache key.
  3. **Model tiers** (fast / smart / embed) settable in the app (else `OPENAI_MODEL_*`), and **priced models**: built-in prices stay in code (D-014); new OpenAI models can be added with their list prices (`pricing.all_prices()`), removable only when unused.
  4. API `/api/agents` (GET; PUT `/{key}`, PUT `/tiers`, POST/DELETE `/models`), every change an `audit_event` (entity `setting`).
  5. **Pages**: "AI agents" (`/agents`) — key + limits, tiers, one table per pipeline (model, effort, cap with fill bar, on/off, spend, calls, last run), models & prices, usage details (the former Usage tab). "Audit" (`/audit`) — the whole trail for ONE checkpoint at a time (JAN 26 / JUL 26 follow the app's checkpoint; "No checkpoint" for settings, exports, checkpoint-agnostic steps), filter by area (evidence / structure / definition / prioritize / settings / other, new `area` on every feed row) and by who acted, history before the rebuild on request. Both are full-height sheets over the dimmed scene like Document; reached from top-right pills "Agents" and "Audit".
  6. The top-right **Audit panel** stays as the quick look (current page, current checkpoint only — Prioritize no longer mixes both checkpoints) with a link to the Audit page; its "Everything" and "Usage" tabs are gone. Trail rendering shared in `components/auditTrail.tsx`.
- Alternatives considered: agent config in code or `.env` (not a source of truth the PM can change); separate routes outside the 3D scene (would remount the canvas on every switch).
- Consequences: agents must never change agent settings, tiers or prices on their own (rule 16). The bottom-left Agent activity box is unchanged. Continuous intake replacing checkpoints is future work (Q-027).

## D-056 — Full-screen 2D pages, nothing rendered behind them
- Date: 2026-10-11
- Decided by: Atahan ("make documents and other non-3D UIs full screen. Do not render them in front of the model")
- Status: accepted (replaces the sheet-over-dimmed-scene presentation of D-051 page 5 and D-055)
- Decision: Document, AI agents and Audit fill the screen under the top band on an opaque black page (content ≤ 1320px, centred). The 3D canvas stays mounted but is hidden and paused (`frameloop="never"`), so it costs no GPU time and going back is instant; the 3D-only HUD (nav pad, hover card, inspector, checkpoint timeline) is not shown. Document gets its own JAN 26 / JUL 26 switch in its head (the Audit page already has one; AI agents needs none).
- Alternatives considered: unmount the canvas (reload of the scene and 3D models on every return); keep the dimmed scene (Atahan: no).
- Consequences: DESIGN.md "Document (page 5)" and the new "Full-screen 2D pages" section updated.

## D-057 — Retire the wave pipeline
- Date: 2026-10-12
- Decided by: Atahan (code-health plan after the hackathon: "do the first one")
- Status: accepted (supersedes D-015; the wave model of D-027–D-038 survives only as history in the DB and audit trail)
- Context: the app ran on the checkpoint pipeline (D-040 ff.), but the simulated-wave pipeline was still in the code: 8 API routers no screen called, `bmw_req.pipeline` (waves, LangGraph orchestrator, derive, linker, fit, scoring, challenge, extraction v2/v3, findings), `service.py`, the old-only `research/findings.py`, and the tests behind 3 stale failures.
- Decision:
  1. Removed: API routers `meta_state`, `briefing`, `queue`, `requirements`, `cars`, `markets`, `evidence`, `process` and `api/{queries,jobs,labels}.py`; `bmw_req/pipeline/` (except galaxy), `bmw_req/service.py`, `bmw_req/research/findings.py`; tests `test_api` (static tests kept as `test_static.py` on an empty DB), `test_service`, `test_scoring`, `test_requirements`, the extraction/recheck tests in `test_store` and the findings test in `test_research`; scripts `demo_build.py`, `pilot.py`, `benchmark_scoring.py`, `benchmark_requirements.py`; the frontend's unused `logView`; the `langgraph` dependency.
  2. Moved unchanged (byte-identical prompts, so cached answers stay valid): `audit()` + `log_access()` → `bmw_req/audit.py`; score-v3 helpers used by prio-v1 → `prioritize/factors.py`; the fit-check instructions + luna→sol re-check → `prioritize/fitcheck.py`; `Category` + `quote_ok` → `structure/taxonomy.py`; `pipeline/galaxy.py` → `structure/galaxy.py`.
  3. `GET /api/health` replaces `/api/state` for the container healthcheck. The agent registry (D-055) drops the research summarizer; its past spend counts as earlier pipeline.
  4. **Not yet done:** dropping the tables only the old pipeline used (`requirement`, `requirement_target`, `requirement_finding`, `fit_check`, `prioritization_run`, `score_snapshot`, `change_proposal`, `app_state`, `finding_signal`, and `finding`/`finding_source`) — a DB migration, to be decided with Atahan. Audit rows stay (append-only).
- Consequences: tests 151 → 114, all green (the 3 stale failures are gone with the code they tested). Old snapshots in `data/snapshots/` (evidence, wave1, demo) predate the checkpoint data — restoring them now gives the old model; `demo_state.py` stays as a generic DB backup/restore.
