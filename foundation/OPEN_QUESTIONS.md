# Open Questions

Format: `Q-xxx` · owner · blocking? · context · options/recommendation. When resolved, move to "Resolved" with the answer + linked decision.

## Open

### Q-005 — How are the "Source A–D" feedback channels interpreted?
- Owner: team (ask BMW mentors)
- Context: Sources are anonymized. Observed patterns (`documents/data-inventory.md` §1) are hypotheses only:
  - **A:** multi-country (incl. JP/KR), lower-case normalized, possibly translated.
  - **B:** US only, third-person "Customer stated…" notes.
  - **C:** US only, structured survey prompts ("I had a minor/serious problem…", "What is…"), mostly Difficult-to-Use/Defect.
  - **D:** US only; short; unclassified. Two prompt templates in G60 (checked 2026-10-10): 34 of 136 end with "That is the one thing could be most improved about the <area> of my vehicle" (improvement answers, e.g. "the head rests are too short"); the rest are mostly "love the…" answers. So D mixes "what do you like" and "what could be most improved" — the earlier note that D is **not** improvement feedback was wrong.
- This affects source-trust weighting. Don't weight sources differently until confirmed.

### Q-006 — Customer study scales
- Owner: team (ask BMW mentors)
- Context:
  - The CN_EU sheet has numeric means in the range ~6.5–9.9 (0–10 or 1–10?).
  - The US sheet is a 7-point distribution ("I Hate It" … "I Love It").
  - **Neither sheet has sample sizes** — ask for n per model/market.
- Needed to compare/normalize, and to judge whether differences are meaningful.

### Q-007 — Team roles & who is the "PM" in the demo?
- Owner: team

### Q-008 — Hackathon logistics
- Owner: team
- Questions: submission deadline, demo length, required format (video/live/slides), judging criteria.

### Q-011 — How detailed can plant/platform reference data be?
- Owner: team
- Context: public sources give plant ↔ model/platform mapping and NK timing, rarely capacity or flexibility. Decide what granularity we claim, and mark the rest as assumptions.

### Q-013 — Market profile sources
- Owner: team
- Context: D-011 needs climate/usage/culture per market. Use research agents + cited sources (mobility studies, climate data, J.D. Power China/US).
- How deep do we go? EU as one market or split (DE vs. GB vs. Nordics)? Note that F70 feedback is 32% Japan and G60/G70 have KR/JP feedback (RoW).
- Recommendation: EU / US / CN (+ RoW where data exists) for the demo; the data model already supports countries.

### Q-015 — Are the BMW sales volumes real or illustrative?
- Owner: team (ask BMW mentors)
- Context: `sales_volumes.xlsx` conflicts with public data:
  - Its values are round thousands (all but one).
  - G60/G68 China is 68k → 75k (+10%) for 2024 → 2025, while public figures say 5 Series China (China-built, CPCA) Jan–Nov 2025 = 107,348 and BMW+MINI China fell 12.5%.
  - F70 EU 85k vs. 1 Series Europe 91,931 (Dataforce).
  - There is no powertrain split, although the briefing promised one.
- Also: F70 China 2024 is a formula cell (`=-D3-C10`, value 0) — another sign the file was constructed (2026-10-10).
- Until answered: use the file as BMW-internal relative weights, don't blend it with public figures, and show the conflict (`data-inventory.md` §3, `portfolio-reference.md` §4).

### Q-016 — Is driver assistance (ADAS) in scope?
- Owner: team (ask BMW mentors)
- Context:
  - BMW's process image (image_2) lists *Driver assistance* and *Powertrain* as requirement groups.
  - ADAS is a top purchase driver in China (`competitor-landscape.md` §2).
  - But "safety" is out of scope (regulatory).
- Working line (not decided): ADAS *experience* (usability, availability, comfort, trust) is in; safety/homologation performance is out.

## Resolved

### Q-020 — Support-call questions → **kept as weak usability evidence, one consistent rule** (D-024)
- Agent 2026-10-10 under Atahan's full delegation: extract-v3 re-extracted all derivatives with one rule; `signal.support_question` flags them and scoring weights them ×0.5.

### Q-012 — Demoing a ~2-year process → **three simulated ingest waves** (D-027)
- Stratified 50/50 verbatim split per derivative × channel × market; study + 2025 sales in wave 2; web "market event" in wave 3. Labelled SIMULATION in the UI.

### Q-010 — Feasibility framing → **option (b), non-blocking realization context** (D-030)
- Agent decision under full delegation; revisit if BMW mentors want it blocking.

### Q-004 — Prioritization logic → **scoring v1** (D-029)
- Renormalize over factors with data + explicit evidence gaps; brand fit gate only; PM-editable versioned weights; bands Must ≥ 60 / Should ≥ 45.

### Q-019 — Out-of-scope verdict drops usable verbatims → **re-checked with sol** (D-023)
- Atahan 2026-10-10: "run the Q-019 re-check". 111 of 268 flipped back in scope (118 signals). Agent's 15–20% guess was far too low; but 66 of the new signals are support-call questions → Q-020.

### Q-018 — Extraction schema fixes after the pilot → **applied in extract-v2** (D-022)
- Atahan 2026-10-10: "apply the Q-018 fixes". Verified on the 50 pilot verbatims, then full G60 run.

### Q-017 — Demo slice & data-model scope → **G60 × US + G68 × CN; logical model minus 3 folded tables** (D-021)
- Delegated by Atahan 2026-10-10 ("do whatever you want"); agent decided.

### Q-014 — Architecture & framework choices → **LangGraph, SQLite, no graph DB, sqlite-vec, Streamlit** (D-015–D-020)
- Answered by Atahan 2026-10-10: approved the agent's recommendation table and said to start scaffolding. Data-model scope and demo slice moved to Q-017.

### Q-009 — OpenAI models & budget → **luna for bulk, 6.1-sol for reasoning, $100 cap with guard** (D-010)
- Answered 2026-10-10: Atahan set $100 total and delegated model choice to the agent.

### Q-001 — Demo derivative/market → **portfolio-level, 5 Series deepest** (D-005)
- Answered by Atahan 2026-10-10: no single-car demo. Multi-model, multi-market architecture from the start; 5 Series (G60/G68) is the deepest example.

### Q-002 — Tech stack → **OpenAI for LLM/agents** (D-006); everything else is open in Q-014 (D-004 is only a proposal)
- Answered by Atahan 2026-10-10. API key provided by Atahan.

### Q-003 — Focus area → **web-enriched knowledge base + brand fit + platform/plant feasibility** (D-007, D-008, D-009)
- Answered by Atahan 2026-10-10: research competitors (offers, sales, in-demand models) and general customer expectations on the web; factor in brand image/segment and plants/platforms.
