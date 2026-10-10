# Project State

_Last updated: 2026-10-10_

## Current phase

**Phase 0 — Foundation & alignment (finishing).** Core direction decided: portfolio-level architecture, OpenAI, web-enriched knowledge base, brand-fit and plant/platform feasibility gates, per-market scoring, future-need projection, continuous re-prioritization, $100 model budget. No application code yet. **Next: architecture discussion with the team (Q-014) — scaffolding comes later, only when Atahan says so.**

## Done

- Challenge analyzed, all BMW data profiled (`documents/data-inventory.md`).
- Foundation, `AGENTS.md`, `CLAUDE.md` created.
- BMW mentor input recorded (D-011 markets differ, D-012 future needs, D-013 continuous re-prioritization).
- Model tiering + $100 budget plan decided (D-010).
- Q-001/002/003 answered by Atahan → D-005 (portfolio-level, 5 Series deepest), D-006 (OpenAI), D-007 (web knowledge base), D-008 (brand fit gate), D-009 (plant/platform feasibility).
- Architecture v2, requirement model v2, knowledge-base design, tech stack updated.
- Web research seeds written (cited, reliability-tagged): `documents/portfolio-reference.md` (platforms, 16 plants, BMW sales 2024–H1 2026) and `documents/competitor-landscape.md` (competitors per segment × market, demand trends, expectations, brand-fit guardrails). User sales claims checked: China −14.2% → official −12.5% (BMW+MINI); Europe +7.3% / 1.02M confirmed (BMW+MINI).

## In progress

- Nothing.

## Next up (suggested order)

0. Review the foundation with a fresh session (review prompt was handed to Atahan).
1. **Architecture discussion (Q-014)**: LangChain, LangGraph, vector DB, graph, RAG, storage, backend/frontend — team decides, then log decisions.
2. *(Later, only on Atahan's go)* Scaffold repo — LLM wrapper with budget guard + `llm_usage` logging first, before any paid call.
3. Reference layer: load brands, segments, platforms, plants, production, sales into SQLite from the seed docs (with source IDs).
4. Ingest BMW data for all three derivatives, organized into ingest waves (Q-012).
5. Signal extraction, market-segmented (embeddings + clustering + LLM labels) → findings with sources.
6. Research agents (competitor, market, review, trend, market profile) → web evidence.
7. Requirement derivation + future-need projection → fit checks (brand, segment, market, feasibility) → per-market scoring → prioritization runs + change proposals.
8. PM review UI (portfolio matrix, per-market backlog, requirement detail, priority history, change inbox) + audit trail + export.
9. Demo script (multi-wave, shows re-prioritization over time).

## Budget (OpenAI, $100 total — D-010)

| Item | Value |
|---|---|
| Spent to date | **$0.00** (no app LLM calls yet) |
| Planned total | ≈ $40 |
| Warn / block non-demo / hard stop | $50 / $75 / $90 |
| Demo-day reserve | $25 |

Update this table after every paid run (source of truth: `llm_usage` table once the app exists).

## Risks / watch-outs

- Local anaconda Python 3.9 has a broken pandas/numpy → use `uv venv --python 3.12`.
- Option lists are German-market only — US/CN equipment baseline is an assumption.
- Plant capacity/flexibility is rarely public → feasibility checks need explicit assumptions (Q-011).
- BMW says engineering is out of scope → keep feasibility framed as a filter (Q-010).
- BMW data must never be committed or sent anywhere except OpenAI.
- Public sales are only in model pairs (1/2, 5/6 Series); no regional per-model figures → model-level market volume relies on BMW's `sales_volumes.xlsx`.
- Feedback data has no dates → the 2-year process must be demoed as simulated ingest waves (Q-012).
- `gpt-6-luna` structured-output quality untested → validate on 50 verbatims first; fallback `gpt-5-mini`.
- China-built i5 (G68 BEV) reportedly ended Jul 2026 (unconfirmed by BMW) — affects 5 Series China powertrain assumptions.

## Session log

- 2026-10-10 — Foundation created: challenge analysis, data inventory, proposed stack/architecture, agent rules.
- 2026-10-10 — Atahan's answers incorporated: portfolio-level model, OpenAI, web research, brand fit, plant/platform feasibility; research seeds for portfolio + competitors written and reviewed.
- 2026-10-10 — $100 budget → model tiering (D-010); BMW mentor pain points → D-011/012/013; architecture v3 (continuity layer, per-market scoring, future needs).
- 2026-10-10 — Framework/storage/RAG/graph choices marked open (Q-014, discuss with team); foundation committed.
