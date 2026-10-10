# Challenge Brief — BMW "AI for Product Decision Making"

Source: `challange information document/BMW_Hackathon_Briefing_Short.pdf`, `mission.md`, `image_1.png`, `image_2.png`, `data_and_source.png`.

## The question

> What should the next generation of a BMW vehicle offer its customers?

Build an AI-powered app that helps **product managers (PMs)** derive, justify and prioritize **customer requirements** for a **successor vehicle**, grounded in customer feedback, BMW product + sales data, and web research — with the **PM firmly in control of every decision**.

- Vehicles: BMW **1 Series (F70)**, **5 Series (G60, China LWB = G68)**, **7 Series (G70)** — any one or a combination.
- Markets: **Europe, China, US** — any subset.
- Horizon: **3–5 years ahead** (needs at successor launch, not just today).
- Definition: **Customer Requirement = Customer-relevant attribute of a car.**
- Must make clear **what is evidence vs. forward-looking assumption**.

## The app must be able to

1. **Ingest** provided data and **enrich** with structured web knowledge.
2. **Extract signals** — recurring complaints, unmet needs, competitor advantages, market trends — **each linked to sources**.
3. **Derive requirements** — clear, actionable, customer-facing, realistic.
4. **Prioritize** — with a logic we define and can explain.
5. **Involve the PM** — approve, reject, edit, or challenge requirements, rationale and evidence.
6. **Audit trail** — complete chronological record of all actions, changes, access events.

## Scope

**In:** features, equipment, comfort, space, usability, infotainment & digital services, design & quality perception, driving experience, range & charging *as experienced by the customer*, variant & package offering.

**Out:** regulatory/homologation (safety, emissions, type approval); technical/engineering (component specs, architecture, suppliers); pricing / business case / cost calculation (rough cost/effort as a prioritization factor is OK).

## Expected deliverables (checklist)

- [ ] **Concept + demonstrable prototype** — heterogeneous inputs → derived requirements → prioritization → human review.
- [ ] **Structured sample requirement list**. Each requirement has:
  - [ ] unique ID
  - [ ] clear, actionable description
  - [ ] linked findings and sources
  - [ ] priority / score
  - [ ] applied prioritization rationale
  - [ ] evidence level
  - [ ] key future-facing assumptions & uncertainties
  - [ ] current decision status
- [ ] **End-to-end workflow definition** — what AI does autonomously, where human review is mandatory.
- [ ] **Demonstrable audit trail** — requirement traceable from sources → findings → consolidation → scoring → prioritization → human decision; records changes to content, scores, priorities, evidence, status, with **who/what**, **when**, **rationale**.

## BMW's reference process (image_2.png)

1. **Situation analysis** — baseline (previous BMW model, BMW portfolio, sales volume) + competition, customer/public feedback, product & global trends. (AI + human)
2. **Structure & context** — AI standardizes findings, identifies duplicates, groups themes, connects insights → list of all potential requirements (0/1: implement?).
3. **Requirements definition** — specification & quantification: measurable targets + acceptance criteria (e.g. "Range: 600 or 700 mi?", "Cooler for how many bottles?"), grouped by Exterior / Interior / Powertrain / Driver assistance / … (AI + human)
4. **Prioritization** — Customer, Business, … dimensions. (AI + human)
5. **Documentation** — requirements tracking. (AI)

## Judging signals (what BMW says it values)

- Trustworthy sources, transparent reasoning.
- Thoughtful prioritization.
- Clear handling of **uncertainty and conflicting evidence**.
- Customer value over engineering specs / regulation / business case.
- **Scalability** across vehicle lines, markets, future decisions → **don't build a one-off**.
- Focus is free: go deep where we're strongest, but show how it connects to the full path evidence → PM decision.

## BMW mentor clarifications (Discord, 2026-10-10)

Common PM pain points, straight from BMW:

1. **Balancing customer requirements across markets/regions.** Preferences differ by **climate, real-world usage and culture** — what works in one market can fail in another. → Never treat "the customer" as one group (D-011).
2. **Getting early customer feedback and extracting *future* requirements**, e.g. from feedback on predecessor vehicles. → Project what customers will want at successor launch, not just what they complained about (D-012).
3. **The requirements process is ongoing (~2 years), not a one-time list.** The most relevant requirements are re-prioritized again and again. → Continuous re-prioritization with history, so the PM sees how and why priorities changed (D-013).
