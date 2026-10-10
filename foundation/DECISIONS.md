# Decision Log

Append-only. Never delete an entry; supersede it with a new one (`Superseded by D-xxx`).

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
- Status: **open — not decided.** Must be discussed with the team in the architecture session (Q-014). Nothing here is binding.
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

## D-010 — OpenAI model tiering & $100 budget plan
- Date: 2026-10-10
- Decided by: agent (delegated by Atahan: "picking models is your job"); budget fixed by Atahan at **$100 total**
- Status: accepted
- Prices: official OpenAI pricing page (developers.openai.com/api/docs/pricing), fetched 2026-10-10, standard tier, per 1M tokens (input / cached input / output). Reasoning tokens are billed as output.
- Model choice:

| Tier | Env var | Model | Price | Used for |
|---|---|---|---|---|
| Bulk | `OPENAI_MODEL_FAST` | `gpt-6-luna` | $0.10 / $0.01 / $0.50 | verbatim classification & extraction, web-result summarizing/extraction, cluster labels, finding summaries, first-pass fit checks |
| Reasoning | `OPENAI_MODEL_SMART` | `gpt-6.1-sol` | $2.00 / $0.10 / $10.00 | requirement derivation, future-need projection, conflict/market trade-off analysis, prioritization rationale, PM "challenge" answers, final brand/feasibility verdicts on `warn`/`fail` |
| Embeddings | `OPENAI_MODEL_EMBED` | `text-embedding-3-small` | $0.02 | clustering / dedupe / semantic search |
| Not used by default | — | `gpt-6-astra` ($10 / $50) | — | only with explicit team OK |
| Fallback (if luna underperforms on structured output) | — | `gpt-5-mini` ($0.25 / $2.00) | — | — |

- Cost levers: Batch API (~50% off) for all offline bulk jobs; stable system prompts first for cache hits; batch 20–30 verbatims per call; low reasoning effort on luna; cache every result in SQLite and never re-run unchanged inputs; web search capped by call count.
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
- Guardrails: code-level budget guard — every call logged to `llm_usage` (model, tokens in/cached/out, search calls, $ from `config/llm_pricing.yaml`); warn at $50, block non-demo jobs at **$75**, hard stop at **$90**; **$25 reserved for demo day**. Atahan should also set a $100 hard limit on the OpenAI project dashboard. Running spend is tracked in `STATE.md` → "Budget".

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
