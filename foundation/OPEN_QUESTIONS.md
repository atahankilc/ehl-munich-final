# Open Questions

Format: `Q-xxx` · owner · blocking? · context · options/recommendation. When resolved, move to "Resolved" with the answer + linked decision.

## Open

### Q-004 — Prioritization logic
- Owner: team / PM persona
- Context: Must be explainable. Draft in `documents/requirement-model.md`.
- Draft v2 includes market volume, portfolio leverage and brand fit factors plus brand/feasibility gates.
- Questions: final default weights? PM-adjustable in UI (proposed: yes)?

### Q-005 — How are the "Source A–D" feedback channels interpreted?
- Owner: team (ask BMW mentors)
- Context: Sources are anonymized. B looks like dealer/service reports ("Customer stated..."), C like survey responses ("I had a minor problem with..."), A like online reviews, D like short free-text survey answers. Affects source-trust weighting.

### Q-006 — Customer study scales
- Owner: team (ask BMW mentors)
- Context: CN_EU sheet has means (likely 0–10?). US sheet is 7-point distribution ("I Hate It" … "I Love It"). Need confirmation to compare/normalize.

### Q-007 — Team roles & who is the "PM" in the demo?
- Owner: team

### Q-008 — Hackathon logistics
- Owner: team
- Questions: submission deadline, demo length, required format (video/live/slides), judging criteria.

### Q-010 — Does BMW accept platform/plant feasibility as part of the solution?
- Owner: team (ask BMW mentors)
- Context: brief says technical/engineering requirements are out of scope. We frame plant/platform only as a feasibility filter (D-009). Confirm this framing helps rather than hurts.

### Q-011 — How detailed can plant/platform reference data be?
- Owner: team
- Context: public sources give plant ↔ model/platform mapping and NK timing, rarely capacity or flexibility. Decide what granularity we claim, and mark the rest as assumptions.

### Q-014 — Architecture & framework choices (BLOCKING for scaffolding — discuss with team, do NOT decide alone)
- Owner: Atahan + team, in a dedicated architecture session
- Context: Atahan wants these discussed before any decision: **LangChain, LangGraph, a vector DB, a graph (knowledge graph / graph DB), and RAG**. Everything in `documents/tech-stack.md` and the storage/orchestration parts of `documents/architecture.md` is a proposal only.
- Points to prepare for the discussion (not decisions):
  - Orchestration: LangGraph (stateful graphs, human-in-the-loop interrupts, checkpoints — fits PM gates & re-prioritization loop) vs. OpenAI Agents SDK vs. plain SDK + own pipeline.
  - Retrieval: RAG over verbatims + web evidence for derivation and PM "challenge" answers; which vector store (Chroma, LanceDB, pgvector, Qdrant, sqlite-vec) and how citations stay traceable.
  - Graph: knowledge graph of source → finding → requirement → target (derivative/market/platform/plant) — graph DB (Neo4j, Kùzu) vs. relational tables + graph view.
  - Fit with constraints: $100 budget (D-010), audit trail (D-003), traceability, hackathon time.

### Q-012 — How do we demo a ~2-year continuous process in a hackathon?
- Owner: team
- Context: D-013. The feedback data has **no dates**, so real time series aren't available.
- Recommendation: simulate time with **ingest waves**: wave 1 = Source A/B feedback + 2024 sales; wave 2 = Source C/D + study + 2025 sales; wave 3 = "event" (e.g. a competitor launch or China sales drop from web research). Show the priority timeline and AI change proposals between waves. Label clearly as a simulation.

### Q-013 — Market profile sources
- Owner: team
- Context: D-011 needs climate/usage/culture per market. Use research agents + cited sources (mobility studies, climate data, J.D. Power China/US). How deep do we go — EU as one market or split (DE vs. GB vs. Nordics)? Recommendation: EU / US / CN for the demo; data model already supports countries.

## Resolved

### Q-009 — OpenAI models & budget → **luna for bulk, 6.1-sol for reasoning, $100 cap with guard** (D-010)
- Answered 2026-10-10: Atahan set $100 total and delegated model choice to the agent.

### Q-001 — Demo derivative/market → **portfolio-level, 5 Series deepest** (D-005)
- Answered by Atahan 2026-10-10: no single-car demo. Multi-model, multi-market architecture from the start; 5 Series (G60/G68) is the deepest example.

### Q-002 — Tech stack → **OpenAI for LLM/agents** (D-006); rest stays proposed default (D-004)
- Answered by Atahan 2026-10-10. API key provided by Atahan.

### Q-003 — Focus area → **web-enriched knowledge base + brand fit + platform/plant feasibility** (D-007, D-008, D-009)
- Answered by Atahan 2026-10-10: research competitors (offers, sales, in-demand models) and general customer expectations on the web; factor in brand image/segment and plants/platforms.
