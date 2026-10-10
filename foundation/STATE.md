# Project State

_Last updated: 2026-10-10_

## Current phase

**Phase 1 — Scaffolding (started 2026-10-10).**
- Core direction decided: portfolio-level architecture, OpenAI, web-enriched knowledge base, brand-fit and plant/platform feasibility gates, per-market scoring, future-need projection, continuous re-prioritization, $100 model budget.
- Stack decided (D-015–D-020): LangGraph, SQLite + sqlite-vec, no graph DB, Streamlit, Python 3.12/uv.
- Scaffold in place: `pyproject.toml`, `src/bmw_req/` (config, SQLite, budget-guarded OpenAI wrapper with `llm_usage`), Streamlit `app.py` (budget view), 12 guard tests (no paid calls).
- Demo slice + tables decided (D-021): full demo schema built, G60 feedback ingested (4,000 verbatims, counts match `data-inventory.md`).
- Pilot run 2026-10-10: $0.0201 total, all quality checks passed except 1 paraphrased quote (see Pilot results).
- **Next: Q-018 schema fixes, then the full G60 extraction (parallel Flex calls).**

## Team & logistics (fill in — Q-007, Q-008)

| Item | Value |
|---|---|
| Team members & roles | _TODO_ |
| Who plays the PM in the demo | _TODO_ |
| Submission deadline | _TODO_ |
| Demo format / length | _TODO_ |
| Judging criteria (beyond the brief) | _TODO_ |

## Minimal demo path (decided, D-021)

One thin slice end-to-end before anything else (AGENTS rule 18). It covers BMW's minimum of one derivative in one market (`challenge-brief.md`).
- **Scope:** 5 Series (D-005).
  - **G60 × US:** ~3.6k verbatims + detailed study + sales. Best-evidenced.
  - **G68 × CN:** study + sales, no verbatims, so web evidence and the market conflict carry it (D-011).
  - G60 × EU as an optional third target (~110 verbatims + study).
- **Flow:**
  1. Classify the G60 verbatims.
  2. Group them into findings with sources.
  3. Derive ~10–15 requirements with targets US/CN.
  4. Run fit checks.
  5. Score and explain.
  6. PM approves, rejects or challenges a few.
  7. Show the audit trail.
  8. Run wave 2 (Q-012) and show priority changes + change proposals.
- F70/G70 stay supported by the data model and run later through the same pipeline.

## Done

- Challenge analyzed; all BMW data profiled and re-verified (`documents/data-inventory.md`).
- Foundation, `AGENTS.md`, `CLAUDE.md` created.
- BMW mentor input recorded (D-011 markets differ, D-012 future needs, D-013 continuous re-prioritization). BMW support recommended the annual report → `documents/bmw-annual-report-2025.md`.
- Model tiering (D-010); budget re-baselined (D-014).
- Q-001/002/003 answered by Atahan → D-005 (portfolio-level, 5 Series deepest), D-006 (OpenAI), D-007 (web knowledge base), D-008 (brand fit gate), D-009 (plant/platform feasibility).
- Conceptual architecture, requirement model and knowledge-base design drafted. Tech stack decided 2026-10-10 (D-015–D-020).
- Web research seeds written and fact-checked:
  - `portfolio-reference.md`: platforms, 14 vehicle plants + 3 CKD sites, BMW sales 2024–H1 2026, primary-sourced from the annual report where possible.
  - `competitor-landscape.md`: competitors, trends, expectations, brand-fit guardrails.
- Foundation review (2026-10-10) fixed, except the confidentiality items, which Atahan dropped.

## In progress

- Nothing.

## Next up (suggested order)

0. Fill in Team & logistics.
1. Ask BMW mentors: Q-005 (sources), Q-006 (scales + sample sizes), Q-010 (feasibility framing), Q-015 (sales volumes real?), Q-016 (ADAS scope).
2. ~~Architecture discussion (Q-014)~~ → done, D-015–D-020.
3. ~~Q-017~~ → D-021: demo slice G60 × US + G68 × CN; schema built.
4. ~~Scaffold + budget-guarded wrapper~~ → done. `OPENAI_API_KEY` is in `.env` (Atahan). Atahan still to confirm the $95 OpenAI project limit + $45 alert. Next: the pilot (D-014: 50 verbatims + 5 requirements).
5. Reference layer: load brands, segments, platforms, plants, production and sales from the seed docs (with source IDs) into SQLite (D-016).
6. Ingest BMW data: G60 feedback done. Still to do: customer study, sales, option list; F70/G70 feedback; waves (Q-012).
7. Signal extraction, market-segmented → findings with sources (LangGraph pipeline, D-015).
8. Research agents (competitor, market, review, trend, market profile) → web evidence.
9. Requirement derivation + future-need projection → fit checks → per-market scoring → prioritization runs + change proposals.
10. PM review UI + audit trail + export.
11. Demo script (multi-wave, shows re-prioritization over time).

## Budget (OpenAI, $100 total — plan in D-014)

| Item | Value |
|---|---|
| Spent to date | **$0.0201** (D-014 pilot, 3 calls, 2026-10-10). Source of truth: `llm_usage` in `data/app.db` / Streamlit page |
| Planned build spend | ≈ $60 (≈ $48 + 25% contingency) |
| Warn / block non-demo / app hard stop | $45 / $70 / $90 |
| Demo-day reserve | $20 ($70 → $90) |
| OpenAI project hard limit | $95 (to set by Atahan, + $45 alert) |

## Pilot results (2026-10-10, `scripts/pilot.py`, outputs in `data/pilot/`)

| Step | Calls | Tokens in / out (reasoning) | Cost | Latency (Flex) |
|---|---|---|---|---|
| Extract 50 G60 US verbatims (B 20, A/C/D 10 each, seed 42), luna low | 2 × 25 | 3.0k / 3.2k (452); 2.3k / 2.6k (142) | $0.0018 | 84 s, 66 s |
| Derive 5 requirements from 73 signals, sol medium | 1 | 6.1k / 2.1k (279) | $0.0183 | 35 s |

- **Extraction:** every ID returned, none invented, none duplicated; 73 signals; 1 verbatim correctly out of scope ("Nothng."). 1 of 73 quotes not an exact substring (model inserted "he"). Feedback type overlaps BMW's label on 28/39 labelled verbatims; most of the 11 mismatches are BMW "Difficult to Use" on things that are actually faults (CarPlay drops, trunk opening by itself), where our label looks more accurate. Real errors: "seats less comfortable than expected" → `defect`, trunk opening → category Interior. BMW's own label was wrong on G60-0877 (says trunk light, text is about vanity mirror).
- **Derivation:** 5 requirements, every cited ID exists, all have evidence (2–9 verbatims each); spot-checked citations support the claims. Weak points: all 5 tagged `at_successor_launch`, 4/5 Kano `basic`; metrics have no numeric targets (model says so in assumptions); 2 requirements rest on 2–3 verbatims, expected at n=50.
- **Re-estimate (D-014):** extraction ≈ $0.0009 per 25-verbatim call → ≈ $0.36 per full 10.1k run, ≈ $1.1 for 3 runs (plan $1.4). Derivation output was ~420 tokens/requirement vs 6k planned, but real input depends on the findings step (not built), so the derivation estimate stays as is. Plan total unchanged at ≈ $60.
- Prompt caching wrote almost the whole prompt on every call (+25% input, ~8% of pilot cost) with no reuse → Q-018.
- Follow-ups → Q-018. Source D finding → Q-005, `data-inventory.md`.

Update the budget table after every paid run. Once the app exists, the source of truth is the wrapper's usage log.

## Risks / watch-outs

- Local anaconda Python 3.9 has a broken pandas/numpy → use `uv venv --python 3.12`.
- Option lists are German-market only — the US/CN equipment baseline is an assumption.
- Plant capacity/flexibility is rarely public → feasibility checks need explicit assumptions (Q-011).
- BMW says engineering is out of scope → keep feasibility framed as a filter (Q-010).
- BMW data must never be committed or sent anywhere except OpenAI (AGENTS rule 1).
- Public sales are only in model-series pairs, with no regional per-model figures. Model-level market volume relies on BMW's `sales_volumes.xlsx`, which looks stylized and conflicts with public China data (Q-015).
- Scoring as drafted penalizes CN (no verbatims) and G70 EU (~19 verbatims) — see Q-004.
- Feedback data has no dates → the 2-year process must be demoed as simulated ingest waves (Q-012).
- `gpt-6-luna` structured-output quality is untested → pilot first (D-014); fallback `gpt-5-mini`.
- China-built i5 (G68 BEV) reportedly ended Jul 2026 (insider rumour, unconfirmed by BMW as of 2026-10-10) — affects 5 Series China powertrain assumptions.
- X5/7 Series successors: BMW calls them NK models, trade press says the platform is CLAR-derived (`bmw-annual-report-2025.md` §4). This matters for the G70 successor.

## Session log

- 2026-10-10 — Foundation created: challenge analysis, data inventory, proposed stack/architecture, agent rules.
- 2026-10-10 — Atahan's answers incorporated: portfolio-level model, OpenAI, web research, brand fit, plant/platform feasibility; research seeds for portfolio + competitors written and reviewed.
- 2026-10-10 — $100 budget → model tiering (D-010); BMW mentor pain points → D-011/012/013; architecture v3 (continuity layer, per-market scoring, future needs).
- 2026-10-10 — Framework/storage/RAG/graph choices marked open (Q-014, discuss with team); foundation committed.
- 2026-10-10 — Foundation review (fresh session): data inventory re-verified (unique-ID counts, Source D/A reinterpretation, no study sample sizes, sales file conflict); brief gaps added; 23 web facts spot-checked and corrected; Q-004/005/006/010/012/013 updated, Q-015/016 added; consistency fixes. No code, no commit.
- 2026-10-10 — Budget re-baselined (D-014). BMW Group Report 2025 extracted (`documents/bmw-annual-report-2025.md`, page-cited); `portfolio-reference.md` upgraded to primary sources. No code, no commit.
- 2026-10-10 — Decision hygiene: undecided stack items reworded as Q-014 candidates (tech-stack, D-010 note, STATE, Q-002, README, knowledge-base). Usability: decision index, lighter session-start read list, glossary, fresh-clone setup, team/logistics placeholders, proposed demo path, duplicates removed. No code, no commit.
- 2026-10-10 — Atahan approved the stack table → D-015–D-020, Q-014 resolved, Q-017 opened. Scaffold: pyproject/uv, `src/bmw_req` (config, SQLite + sqlite-vec, budget-guarded OpenAI wrapper per D-014), Streamlit budget page, 12 tests passing. No paid calls, no commit.
- 2026-10-10 — Scaffold committed (65d3952). Q-017 delegated → D-021: demo slice G60 × US + G68 × CN, demo schema (audit append-only via triggers, sqlite-vec, llm_cache), G60 feedback ingest (4,000 verbatims, verified vs. inventory). 16 tests passing. No paid calls.
- 2026-10-10 — Committed db695bd. Pilot (D-014) run: extraction (luna) + derivation (sol) modules, `scripts/pilot.py`; $0.0201 spent; results + re-estimate in STATE; Source D note corrected (Q-005, data-inventory); Q-018 opened for schema fixes. Pilot code not committed yet.
