# Knowledge Base & Web Enrichment

**Status: DRAFT (D-007).** BMW's own customer data is not enough. The knowledge base combines internal data, curated reference data and web evidence.

## Three layers

| Layer | Contents | How it gets in | Changes |
|---|---|---|---|
| **1. BMW internal** | Verbatims, customer studies, sales volumes, option lists (`data-inventory.md`) | Deterministic loaders | Read-only |
| **2. Curated reference** | Platforms, plants (location, platforms, powertrains, NK readiness), production allocation, brand positioning + guardrails, segments, competitor model catalog | Research agents propose → human accepts | Versioned; every fact has source + date |
| **3. Web evidence** | Competitor features & sales, market demand & powertrain trends, professional reviews, customer expectation studies, owner forums/social | Research agents, on demand or scheduled | Append-only, timestamped |

Seed docs: `portfolio-reference.md` (platforms, plants, BMW sales), `competitor-landscape.md` (competitors, trends, brand positioning), `bmw-annual-report-2025.md` (T1: BMW Group Report 2025 — market & sales data, R&D, NEUE KLASSE strategy, with page numbers; recommended by BMW support).

## Research agents (OpenAI web search; orchestration via LangGraph — D-015)

| Agent | Question it answers | Typical sources |
|---|---|---|
| **Competitor scout** | Who competes per segment × market, what they offer that BMW doesn't | OEM sites, press releases, reviews |
| **Market & sales analyst** | Volumes and growth by brand/model/powertrain/market; which models are in demand | ACEA, KBA, CPCA, Cox/Automotive News, OEM reports |
| **Review miner** | What professional reviewers and owners praise/criticize (BMW + competitors) | Car and Driver, Autocar, Auto Bild, Autohome/Dongchedi, forums |
| **Market profile scout** (D-011, Q-013) | Climate, real usage, culture, infrastructure and powertrain mix per market | Mobility/usage studies, climate data, J.D. Power CN/US, charging statistics |
| **Trend & expectation scout** | Customer expectations 3–5 years ahead (software, ADAS, charging, interior, personalization) | J.D. Power, McKinsey, Deloitte, S&P |
| **Brand-fit checker** | Does a requirement fit BMW brand + the derivative's segment? | Brand reference (layer 2) |
| **Feasibility checker** | Can the target platform/plant build it for that market at the planned time? | Platform/plant reference (layer 2) |

Each agent returns **schema-validated structured output** (Pydantic → Responses API structured output, D-020): claim, quote, URL, publisher, published date, retrieved date, market, model(s), trust tier. Free-text LLM opinions are **never** stored as sources.

## Trust tiers

| Tier | Examples | Default weight |
|---|---|---|
| **T1** | BMW internal data; official OEM press/annual reports; registration statistics (KBA, ACEA, CPCA) | 1.0 |
| **T2** | Reputable press & analysts (Reuters, Bloomberg, Automotive News, J.D. Power, McKinsey), professional reviews | 0.8 |
| **T3** | Forums, social media, blogs, aggregators | 0.5 |

Rules: prefer recent sources (flag > 24 months old); when sources disagree, store both and raise `conflicting_evidence`; facts the user supplied are stored as `T3/user-claim` until verified.

## Brand & segment fit (D-008)

Every requirement is checked against the brand profile (BMW: driving pleasure, sportiness, driver focus, premium quality, design, innovation) and the derivative's segment. Example: a "budget, efficiency-first family hatch" spec contradicts BMW positioning → `fail`, regardless of how loudly a generic market trend demands it. Guardrails live in `brand.guardrails_json`, seeded from `competitor-landscape.md`.

## Platform & plant feasibility (D-009)

For each `requirement_target`: is the derivative's platform (and its successor, e.g. NK) able to carry the requirement; does a plant that builds this platform + powertrain serve that market; is the timing compatible with NK rollout? Output `pass / warn / fail` + rationale. This is a **feasibility filter on customer requirements**, not an engineering spec (scope stays customer-facing).
