# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + TypeScript (Vite) frontend with three.js via react-three-fiber for real-time 3D; a small FastAPI JSON layer (`api/`) over the existing Python pipeline (`src/bmw_req`, SQLite). Chosen by Atahan on 2026-10-11 to replace the Streamlit UI (D-039). Runs locally only (confidential BMW data, AGENTS rule 1).

## Users

- **Primary: a BMW product manager (PM)** responsible for what the successor of a car line (1, 5, 7 Series) offers its customers in each market. Over a ~2-year process they review AI-drafted customer requirements, decide (approve / reject / defer / edit / challenge, always with a reason), set priorities per car × market, and hand the result to engineering — while new evidence keeps arriving.
- **Demo audience: BMW judges and mentors** of the "AI for Product Decision Making" hackathon, watching the PM (Atahan) work the tool live on a laptop or projector. The UI is tuned demo-first: the story must land in a few clicks, without breaking the real tool underneath.

## Product Purpose

Turn ~10k customer comments, a customer study, sales data, option lists and cited web research into prioritized, evidence-linked customer requirements for successor BMW cars, per car and market. The AI reads, groups, drafts, checks fit and scores; the PM decides; everything is traceable to the customer's words and audited. Success: a PM trusts and acts on the ranking because every number explains itself, and the judges see a living decision process, not a one-shot list.

## Positioning

Not a feedback dashboard and not a chatbot: a decision instrument. Every requirement is a product decision BMW could take or trade off, scored per market with a visible factor breakdown, traced down to individual comments, gated by brand fit, and re-proposed — never silently changed — as new evidence arrives in waves.

## Operating Context

- Simulated ~2-year process: three evidence waves (feedback has no dates), each re-scoring and producing AI change proposals the PM accepts or rejects.
- Portfolio: F70 (1 Series), G60 (5 Series), G68 (5 Series LWB, China), G70 (7 Series); markets USA, Europe, China, Rest of world.
- Hand-offs: defect-type pain goes to a Quality hand-over list, not into requirements; the approved list is exported.
- Today's car matters as a reference: the current car and its equipment (German price list; public BMW configurator) are the baseline the successor improves on.

## Capabilities and Constraints

- AI only proposes; approved/rejected/deferred need a named human and a rationale. Brand-fit FAIL blocks approval unless the PM overrides with a reason. Audit is append-only.
- Scope: customer-facing requirements only — no regulatory, engineering specs or pricing.
- Evidence and assumption are always shown apart; conflicting evidence is surfaced, not hidden; markets without own comments are labelled.
- OpenAI is the only LLM provider; $100 total budget; running a wave costs money and takes minutes.
- Terminology to keep (English): Must / Should / Could; "5 Series · USA"; Strong / Good / Limited evidence / Assumption only; Expected / Differentiator / Delighter; To review / Challenged / Approved / Deferred / Rejected; "AI suggests" for unconfirmed priorities.
- A parallel workstream (D-040+) adds requirement origins (competitors, trends, regulation, personas), a regulatory radar, customer & model groups, an offering matrix per market and market intelligence; the IA must have a home for these.

## Brand Commitments

- English UI, current domain terms.
- Dark theme only.
- A BMW-like blue accent is wanted.
- No BMW logo or trademark branding in the UI; neutral product name.

## Evidence on Hand

- Live demo database `data/app.db` (39 requirements, 151 car × market targets, 3 runs, ~1.6k audit events, findings, signals with verbatim quotes, study metrics, sales, option lists, 219 cited web items). Verbatims are BMW-confidential: localhost only.
- 3D models of today's cars: public CC BY Sketchfab models (attribution required), downloaded by Atahan into `data/models/` (Q-025). Fan-made approximations, not BMW CAD.
- No testimonials, user research or production usage exist — never fabricate them.

## Product Principles

1. The PM decides, the AI explains — every AI output is a proposal with its cause visible.
2. One number, fully opened — any score can be unfolded to its factors and down to the customer's words.
3. Markets are different customers — never average them away; show where they disagree.
4. The car is the canvas — requirements are about a physical product; show them on it.
5. A process, not a report — what changed since last time comes first.
