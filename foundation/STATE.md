# Project State

_Last updated: 2026-10-10_

## Current phase

**Phase 2 — End-to-end demo built (2026-10-10).** Atahan delegated the whole challenge to the agent ("full power, sole competitor").
- Evidence layer complete: 10,128 verbatims (extract-v3, D-024), customer study (391 items), sales, option lists (458 items), reference layer (96 cited sources), web research (219 cited items, 152 web findings).
- Findings: verbatim clusters G60 243 · F70 166 · G70 242 (D-025), 391 study findings (D-026).
- Requirements pipeline: derivation (sol, derive-v5) → portfolio consolidation → evidence linker → fit checks → scoring v2 → change proposals, orchestrated per simulated wave (LangGraph, D-027–D-029).
- PM app (Streamlit, 11 pages, D-032) with approve/reject/defer/edit/challenge/override/priority/inbox, audit trail, export.
- Demo states via `scripts/demo_state.py` + `scripts/demo_build.py` (snapshots `evidence`, `wave1`, `demo`).

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

## Demo (how to run)

- `uv run streamlit run app.py`. DB holds the full `demo` state; `uv run python scripts/demo_state.py restore wave1` for a live PM review from scratch (stop the app first). Rebuild: `scripts/demo_build.py`.
- Story: Overview (workflow, funnel) → Portfolio → Backlog G60×US / G68×CN / G60×EU → Requirement REQ-0001 (evidence vs assumption, score breakdown, evidence chain, fit, decision, audit) → Change inbox (wave 2/3 proposals) → Market conflicts → Weights & runs (re-rank live, free) → Audit trail → Export.

## Next up (suggested order)

0. Fill in Team & logistics (Q-007, Q-008); rehearse the demo path above.
1. Ask BMW mentors: Q-005, Q-006, Q-015, Q-016 (Q-010 is now decided as non-blocking, D-030 — confirm).
2. PM sign-off of the proposed brand guardrails (D-031) — they gate approval.
3. Quality levers (benchmarks in `data/eval/`): judge "measurable" (3.5) and "evidence-grounded" (3.6) are the weakest dimensions; top-20 pain coverage 65–75% after wave 1 (rest picked up in waves 2/3).
4. Optional: async/background wave runs in the UI (currently blocking), wave-3 derivation cap (it still adds ~11 requirements).

## Budget (OpenAI, $100 total — plan in D-014)

| Item | Value |
|---|---|
| Spent to date | **$6.86** (2026-10-10): derivation $2.38 (incl. prompt iterations v2–v6, 4 wave-1 runs, waves 2–3 ×2), web research $1.69, fit checks $0.55, extraction $0.52, linker $0.23, recheck $0.13, benchmarks $0.09, challenge $0.08, consolidation $0.08, other $0.12, **plus a $1.00 reconciliation row** (usage rows lost in a failed demo restore, upper-bound estimate; bug fixed). Source of truth: `llm_usage` / Budget page |
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

## G60 extraction results (2026-10-10, extract-v2, `bmw_req.pipeline.run_extract`)

- 160 luna Flex calls (2 validation + 158 full), 16 workers, 12 min; **$0.1348** ($0.00084/call); 421k in / 455k out (58k reasoning); 0 cache writes; 0 failed, 0 missing, 0 invented IDs; no retries needed.
- 4,000 verbatims → 3,732 in scope → **5,400 signals** (US 4,607 · RoW 485 · EU 308).
- Feedback types: like 2,777 · complaint 851 · want 699 · defect 580 · difficult_to_use 493.
- Top categories: Infotainment & Digital 1,023 · Driving Experience 901 · Comfort & Space 781 · Interior 572 · Exterior 550.
- 33 signals (0.6%) have unverified quotes — mostly stitched with "…" or a changed word form ("enjoy" vs "enjoys"); flagged, not dropped.
- Out-of-scope verdicts drop some usable content → Q-019 → re-check below.

## Q-019 re-check results (2026-10-10, `bmw_req.pipeline.recheck`, sol low, Flex)

- 11 calls, **$0.1342** (agent had estimated ≈ $0.05 — off by 2.7×: sol output 1.2–2k tokens/call at $5/M Flex). Avg 3.4k in / 1.6k out per call.
- First attempt: 7 of 11 batches refused by the run's own $0.30 cap, because the cap counts open reservations and each sol call reserves ≈ $0.13 worst case (4 in flight ≈ $0.53). No API calls were made for them; re-run with a $1 cap finished them. Lesson: size run caps to workers × worst-case reservation.
- **111 of 268 flipped to in scope, 157 confirmed out of scope; 118 new signals**, 0 unverified quotes, 0 missing IDs.
- New signals: difficult_to_use 80 (66 of them hotline questions like "customer asked which regen setting to use"), like 17, defect 12, complaint 5, want 4. Real recoveries include "only fast charged to 80%, which i really hated", a flat-tire defect, oil-dipstick want, removed gesture control. The question-type ones are a looser rule than the first pass applied → Q-020.
- G60 now: 3,843 in-scope verbatims, **5,518 signals**.
- Re-estimate: extraction for all 10.1k verbatims ≈ $0.34/run, below D-014's $0.47/run.

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
- 2026-10-10 — Committed e7cabd9 (pilot). Q-018 → D-022 (extract-v2: `complaint` type, category definitions, quote check, no implicit cache writes; `signal`/`verbatim_extraction` tables; parallel runner). Full G60 extraction: 5,400 signals, $0.1348, 0 failures. Total spent $0.1549. Q-019 opened (out-of-scope over-exclusion). Not committed.
- 2026-10-10 — Committed ed747bf. Q-019 re-check (D-023): signal provenance column + migration, recheck module; 111/268 flipped, +118 signals, $0.1342 (est. was $0.05); first attempt tripped own run cap (no calls made), re-run OK. Total spent $0.2891. Q-020 opened (support-call questions as evidence). Not committed.
- 2026-10-10 — Full delegation from Atahan ("sole competitor"). Built the end-to-end demo: extract-v3 for all 10,128 verbatims (D-024, resolves Q-020); study/sales/option-list ingest (D-026); reference layer + web research agents (D-031, subagent); clustering findings (D-025); simulated waves + LangGraph orchestrator (D-027, Q-012); derivation v6 + consolidation + evidence linker (D-028); scoring v2 with shrinkage (D-029, Q-004); feasibility non-blocking (D-030, Q-010); Streamlit PM app, 11 pages (D-032, subagent); Flex fallback (D-033). Benchmarks: extraction vs BMW labels, requirement judge 3.83 → 4.26 → 4.02 (coverage 0.48 → 0.70), scoring robustness tau 0.93–0.96. Demo: 53 requirements, 165 targets, 3 runs, 1,632 audit events. Spent $6.86 total. 44 tests pass.
