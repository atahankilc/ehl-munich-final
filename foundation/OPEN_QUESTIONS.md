# Open Questions

Format: `Q-xxx` · owner · blocking? · context · options/recommendation. When resolved, move to "Resolved" with the answer + linked decision.

## Open

### Q-004 — Prioritization logic
- Owner: team / PM persona
- Context: Must be explainable. Draft in `documents/requirement-model.md`.
- Draft v2 includes market volume, portfolio leverage and brand fit factors plus brand/feasibility gates.
- Questions: final default weights? PM-adjustable in UI (proposed: yes)?
- Known issues in the draft (found in review 2026-10-10, to settle with the weights):
  - **"0–100" is not true as written:** the base weights sum to 100, plus a ±10 market modifier and a −0…10 effort penalty, then multipliers.
  - **Brand fit is counted twice:** as a gate and as a 10-point factor.
  - **"warn lowers the score via the confidence factor"** conflicts with confidence being defined by evidence level.
  - **Structural bias against CN (and against EU for G70):**
    - There are no CN verbatims (and ~19 EU verbatims for G70), so these targets score 0 on "customer pain" (25 pts).
    - They can never reach E1.
    - Options: renormalize per target over the factors with data, or show "no verbatim evidence" as an explicit gap.
  - **Satisfaction gap:** CN/EU means and US distributions aren't comparable, and neither has sample sizes (Q-006).

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

### Q-010 — Does BMW accept platform/plant feasibility as part of the solution?
- Owner: team (ask BMW mentors)
- Context:
  - The brief puts technical/engineering requirements out of scope and explicitly names "**architecture**", which arguably covers vehicle platforms.
  - D-009 (accepted) makes feasibility a blocking gate. Yet the platform mappings and plant volumes in `portfolio-reference.md` are mostly [Trade]/[Unverified].
- Options for the team (not decided):
  - (a) keep it as a blocking gate;
  - (b) non-blocking "realization context" (warn/info only);
  - (c) drop it.
- Ask the mentors which framing helps rather than hurts.
- New input (BMW support, 2026-10-10): BMW recommends tying concepts to R&D priorities and the NEUE KLASSE architecture strategy from the annual report. That suggests platform/strategy *context* is welcome. It doesn't settle whether a feasibility `fail` should block approval.

### Q-011 — How detailed can plant/platform reference data be?
- Owner: team
- Context: public sources give plant ↔ model/platform mapping and NK timing, rarely capacity or flexibility. Decide what granularity we claim, and mark the rest as assumptions.

### Q-012 — How do we demo a ~2-year continuous process in a hackathon?
- Owner: team
- Context: D-013. The feedback data has **no dates**, so real time series aren't available.
- Recommendation: simulate time with **ingest waves**, labelled clearly as a simulation:
  - **Don't split waves by source:** the channels differ systematically (Q-005), so an A/B → C/D split would show channel differences as "changes over time".
  - Instead: wave 1 = a stratified random half of the verbatims + 2024 sales; wave 2 = the other half + study + 2025 sales; wave 3 = an "event" from web research (e.g. a competitor launch or the China sales drop).
- Show the priority timeline and AI change proposals between waves.

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
- Until answered: use the file as BMW-internal relative weights, don't blend it with public figures, and show the conflict (`data-inventory.md` §3, `portfolio-reference.md` §4).

### Q-016 — Is driver assistance (ADAS) in scope?
- Owner: team (ask BMW mentors)
- Context:
  - BMW's process image (image_2) lists *Driver assistance* and *Powertrain* as requirement groups.
  - ADAS is a top purchase driver in China (`competitor-landscape.md` §2).
  - But "safety" is out of scope (regulatory).
- Working line (not decided): ADAS *experience* (usability, availability, comfort, trust) is in; safety/homologation performance is out.

### Q-019 — Out-of-scope verdict drops some usable verbatims
- Owner: agent (proposal), team to OK
- Context: full G60 run (extract-v2) marked 268/4,000 verbatims out of scope (B 158, A 103, C 5, D 2). Spot check of 14: most are right (dealer/service calls, charger etiquette, generic "going well"), but 2–3 contain a real product signal next to dealer content, e.g. "only fast charged to 80%, which i really hated" dropped because a salesperson is mentioned; "why is there an 80% charging limit" is arguably a range/usability signal. Rough guess from that sample: ~15–20% of the 268 (≈ 40–55 verbatims) lost.
- Options: (a) re-check only the 268 with sol, asking "is there any in-scope signal?" (≈ $0.05); (b) prompt tweak "extract in-scope parts even if the verbatim is mostly about dealer/service" → new extractor version, full re-run ≈ $0.14; (c) accept the loss. Recommendation: (a).

## Resolved

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
