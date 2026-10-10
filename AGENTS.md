# AGENTS.md

Hackathon project for the **BMW "AI for Product Decision Making"** challenge: an AI app that turns customer feedback, BMW product/sales data and web research into **prioritized, evidence-linked customer requirements** for successor BMW vehicles, with a **product manager (PM) in the loop** and a **full audit trail**.

**Portfolio-level by design:** multiple models, markets, shared platforms (CLAR, FAAR → Neue Klasse) and plants from day one. The 5 Series (G60 + China LWB G68) is the deepest example; F70 and G70 use the same pipeline. **LLM provider: OpenAI.** Orchestration framework, vector DB, graph, RAG and storage are **not decided yet** (Q-014).

## Session start — mandatory

Read, in order:
1. `foundation/STATE.md` — current phase, in-progress, next steps
2. `foundation/OPEN_QUESTIONS.md` — check for blockers
3. `foundation/DECISIONS.md` — don't re-open settled decisions without new info
4. Relevant docs in `foundation/documents/`:
   - `challenge-brief.md` — mission, scope, deliverables checklist
   - `data-inventory.md` — datasets, schemas, quirks
   - `tech-stack.md` — stack, repo layout, env setup
   - `architecture.md` — workflow, AI vs. human steps, data model, audit rules
   - `requirement-model.md` — requirement fields, evidence levels, gates, prioritization
   - `knowledge-base.md` — 3-layer knowledge base, research agents, trust tiers
   - `portfolio-reference.md` — platforms, plants, BMW sales (researched, cited)
   - `competitor-landscape.md` — competitors, demand trends, brand positioning (researched, cited)

## Session end — mandatory

- Update `foundation/STATE.md` (phase, in progress, next up, one-line session log entry with date).
- Log every decision as `D-xxx` in `foundation/DECISIONS.md`; new questions as `Q-xxx` in `foundation/OPEN_QUESTIONS.md`.
- If code changes the stack, schema, or workflow, update the matching doc in `foundation/documents/` in the same change.

## Core rules

1. **Raw data is read-only and confidential.** `challange information document/` (typo is the real folder name) is git-ignored — never modify, move or commit it; never send it anywhere except the agreed LLM provider. Derived data goes to git-ignored `data/`.
2. **Stay in scope.** Customer-facing requirements only (features, equipment, comfort, space, usability, infotainment/digital, design & quality perception, driving experience, range/charging as experienced, variants/packages). **Out:** regulatory/homologation, engineering/component specs, pricing/business cases (rough effort as a factor is OK).
3. **Traceability is non-negotiable.** Every finding links to ≥1 source item; every requirement links to ≥1 finding. Keep provenance (file, sheet, row/ID, URL + date for web).
4. **Evidence vs. assumption.** Always separate evidence-backed statements from forward-looking assumptions (3–5 yr horizon); surface conflicting evidence instead of hiding it.
5. **The PM decides, never the AI.** AI only creates/edits in `proposed` status; `approved`/`rejected`/`deferred` require a human actor + rationale.
6. **Audit everything, append-only.** Every change to requirement content, score, priority, evidence or status → an `audit_event` (actor human/ai/system, timestamp, before/after, rationale, model for AI).
7. **Portfolio, not one-offs.** Brands, models, markets, platforms and plants are data/config — never hardcode a derivative or market. Requirements can target several derivative × market combinations.
8. **Brand & segment fit.** Every requirement must fit the brand and the segment (no "cheap efficiency hatch" from BMW, no Bugatti family car). Brand-fit `fail` blocks approval unless a PM overrides with rationale.
9. **Plant & platform feasibility.** A recommendation must be buildable: the derivative's platform and a plant that builds it can serve that market in time (incl. Neue Klasse transition). Used as a feasibility filter only — never output engineering specs.
10. **Web evidence is cited evidence.** Competitor, sales, demand and expectation facts come from web research with URL, publish/retrieve date and trust tier (T1–T3). LLM opinions are never stored as sources; unverified user claims stay flagged until verified.
11. **Explainable prioritization.** Every score has a visible factor breakdown and plain-language rationale.
12. **OpenAI for all LLM work**; model names via env (`OPENAI_MODEL_*`). Secrets live in `.env` (git-ignored); commit `.env.example` only.
13. **Markets are different customers.** Climate, usage and culture differ — segment findings by market and score/prioritize each derivative × market separately; surface cross-market conflicts (D-011).
14. **Future, not just past.** Derive what customers will need at successor launch (3–5 yr) from predecessor feedback + competitors + trends; tag horizon, Kano class and assumptions (D-012).
15. **Living process, not a one-shot list.** ~2-year process: every prioritization run is snapshotted; AI only *proposes* priority/status changes with their cause; PM decides; history is always visible (D-013).
16. **$100 OpenAI budget, total.** Cheap model (`gpt-6-luna`) for bulk extraction/classification/summaries; `gpt-6.1-sol` only for reasoning-heavy steps; all calls through the budget-guarded wrapper; Batch API + caching; update the Budget section in `foundation/STATE.md` after paid runs (D-010).
17. **Don't decide architecture alone.** Framework, storage, vector DB, graph and RAG choices (LangChain, LangGraph, …) are discussed with the team first (Q-014). Don't start scaffolding or implementation until the team says so.
18. **Hackathon pace.** Ship a working demo path end-to-end before polishing; prefer simple, cached, deterministic pipelines over clever ones. Don't build what's not needed for the demo.

## Quick facts

- Datasets per vehicle: verbatims (xlsx), customer study (xlsx, CN/EU means + US 7-point distribution), sales volumes 2024/25/2030 (xlsx), German option price list (PDF).
- Feedback xlsx has **one row per classification** — dedupe by `ID` when counting verbatims.
- No China verbatims exist; US verbatims dominate G60/G70; F70 has no US data.
- Local anaconda Python is broken for pandas — use a `uv` venv (Python 3.12).

## Commits

Small, descriptive commits; don't commit unless asked. Never commit raw BMW data, `.env`, or local DBs.
