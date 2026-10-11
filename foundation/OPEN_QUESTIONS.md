# Open Questions

Format: `Q-xxx` · owner · blocking? · context · options/recommendation. When resolved, move to "Resolved" with the answer + linked decision.

## Open

### Q-026 — Gaps in the checkpoint research (D-040)
- The agents' web-search quota ran out mid-run. Missing: China model-level sales (5 Series LWB / E-Class L / A6L; Gasgoo/CPCA rankings blocked), Japan & Korea market totals, UK/EU-wide model rankings (Dataforce/JATO), Genesis/Lincoln H1 2026, BMW 1/7 Series volumes in EU/CN, Chinese vs foreign brand share in China, China subsidy pauses, Germany EV-subsidy uptake, UK ZEV mandate, charging-cost vs fuel, in-car AI adoption data, OTA/subscriptions. Full list: `gaps` in `research/checkpoints/checkpoints.json`.
- **China round 2 done (2026-10-11):** +207 items (china_models, china_market, china_context): FY2025/H1 2026 retail for A6L / E-Class / 5 Series, luxury registrations 7 Series / S-Class / S800 / Maybach S, domestic-brand share 64→69 %, luxury retail −30 % in H1, CPCA forecast cut, trade-in fund, L2/NOA standard, McKinsey 2026. Many China model figures are Yiche sums (T3, unverified). Still open: i7 China, BBA combined share, rear-screen/massage penetration, Roland Berger/Bain, Gasgoo (blocked).

### Q-025 — 3D models for the Cars screen (D-039)
- Owner: Atahan · not blocking (placeholder car renders without them)
- Context: the Cars screen renders public, fan-made CC BY Sketchfab models (attribution on screen): 1 Series "Bmw-1-series 2025" (teenlin3, AI-generated mesh, 500k tris), 5 Series "i5" (akyolefe319), 7 Series "2023 BMW I7 G70" (NazhDesign). Downloads need a Sketchfab login (the agent may not log in), so the files must be placed in `data/models/{f70,g60,g70}.glb` (or `<name>/scene.gltf`). Each model's axis orientation in `car_zones.MODELS_GLTF` is provisional until checked visually. For real use BMW would supply its own visualisation assets.
- Update 2026-10-11: Atahan downloaded the three GLBs; copied (not moved — raw folder is read-only) to `data/models/{f70,g60,g70}.glb`; orientations set in `car_zones.MODELS_GLTF` (files carry a Z-up→Y-up root matrix → F70/G70 front +z, G60 front −z) and checked by rendering all three plus the rear-cabin x-ray. Remaining: whether to keep these fan-made models for the pitch (the 1 Series mesh is AI-generated) and the originals in `challange information document/` can be deleted by Atahan.

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
- **Update 2026-10-11 (verification, `research/sales-verification.md`):**
  - **Ingest is correct.** All 36 DB cells match the file. There are no drops or duplicates, values are in units (no thousands), and CN→G68 is right.
  - **Correction to the context above.** The 5 Series in China *grew* in 2025. CPCA shows 86,174 (2024) → 107,348 (Jan–Nov 2025), and PCauto retail shows 116,173 for FY2025. So the conflict is the **level** (the file is 21–39% low), not the direction.
  - **New: G60 US is about 3× public.** BMW NA reports 25,315 (2024) and 27,107 (2025), incl. i5.
  - **The G60+G68 total matches public.** The BMW Group Report p. 79 gives 299,582 for the 5/6 Series in 2025, about 1% from the file. Only the market split is off.
  - **RoW is too low.** Korea alone is 23,876 for the 5 Series and 5,834 for the 7 Series in 2025, which is 83–85% of the file's RoW.
  - **G70 direction is wrong.** The file's G70 total grows +24%, while public 7/8 Series fell −5.6% and the 7 Series in Germany fell −11% (KBA).
  - **The 2030 growth for every cell contradicts H1 2026 actuals.**
  - New sub-question for BMW: is the US row US-only, and does CN include the i5 LWB and imports?

### Q-016 — Is driver assistance (ADAS) in scope?
- Owner: team (ask BMW mentors)
- Context:
  - BMW's process image (image_2) lists *Driver assistance* and *Powertrain* as requirement groups.
  - ADAS is a top purchase driver in China (`competitor-landscape.md` §2).
  - But "safety" is out of scope (regulatory).
- Working line (not decided): ADAS *experience* (usability, availability, comfort, trust) is in; safety/homologation performance is out.

### Q-024 — Leftovers from Q-021/Q-023 (evidence changes on decided requirements, web contradictions)
- Owner: team · not blocking
- Context: D-038 closed most of Q-021 and Q-023. Two parts are still open:
  - **Q-021 (b):** the linker still adds links to approved/deferred requirements directly in each wave. Rules 5/6 and the brief count evidence changes as decision-relevant, so they could become `link_finding` change proposals for the PM instead.
  - **Q-023, contradictions:** web findings with `contradicts=true` still don't affect the score; only `supports` count. Study items already work both ways through the z-score.
- Options: (a) leave both as they are and show them in the text only; (b) proposals for decided requirements plus a confidence cut when contradicting web evidence exists. Recommendation: (b), if there's time before the demo.

## Resolved

### Q-021 — Linker over-linking → **same need, not same theme (option c, prompt part)** (D-038)
- Atahan 2026-10-11: closed. The linker prompt now links only evidence about the same need and says that every web link raises the score. Still open: evidence on approved requirements becomes a proposal instead of a direct change (option b) → Q-024.

### Q-023 — Customer voice barely separates markets → **score-v3: borrowed rate ×0.5, capped at the best comment-backed market** (D-038)
- Atahan 2026-10-11: closed. A market without its own comment base borrows the line's rate at ×0.5, labelled "borrowed". It can't outrank the requirement's best comment-backed market unless it has its own study gap and competitor pressure. E3/E4 confidence cuts are stricter. Still open: contradicting web evidence lowering the score → Q-024.

### Q-022 — Cross-line duplicates from later waves → **dedup against the whole backlog, `extend` proposals** (D-035)
- Atahan 2026-10-10: "fix the duplicates and rebuild the demo". Demo 53 → 39 requirements.

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
