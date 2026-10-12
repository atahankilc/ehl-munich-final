# Challenge Brief — BMW "AI for Product Decision Making"

Source: `challange information document/BMW_Hackathon_Briefing_Short.pdf`, `mission.md`, `image_1.png`, `image_2.png`, `data_and_source.png`.

## The question

> What should the next generation of a BMW vehicle offer its customers?

Build an AI-powered app that helps **product managers (PMs)** derive, justify and prioritize **customer requirements** for a **successor vehicle**, grounded in customer feedback, BMW product + sales data, and web research — with the **PM firmly in control of every decision**.

Why (PDF): turning large volumes of feedback, market signals, competitor info and product data into requirements is today "largely manual, time-consuming, and difficult to trace consistently".

- Vehicles: BMW **1 Series (F70)**, **5 Series (G60, China LWB = G68)**, **7 Series (G70)** — any one or a combination. (The PDF says only "1/5/7 Series"; the e-codes come from the data files.)
- Markets: **Europe, China, US** — any subset.
- **Minimum:** demonstrate at least **one derivative in one market**, but don't design a one-off; it must be adaptable to other vehicles/markets. The remaining datasets/scenarios are *optional* testing material (mission.md).
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

### Scope tensions (unresolved — don't paper over them)

- **Platform/plant feasibility vs. "architecture" out of scope.** BMW's out-of-scope list names "architecture". Vehicle platforms (CLAR, FAAR, NK) arguably *are* that. D-009 uses platform/plant data as a feasibility gate, which is our addition and not asked for by BMW. It also rests mostly on trade-press reference data. Open with BMW mentors: Q-010.
- **Driver assistance vs. "safety" out of scope.** BMW's own process image lists *Driver assistance* (and *Powertrain*) as requirement groups, and ADAS-as-experienced is a top purchase driver in China. But safety requirements are out of scope. Our working line: ADAS *experience* (usability, availability, comfort) is in; safety/homologation performance is out. Open: Q-016.
- **"Business" prioritization dimension vs. no business case.** image_2 shows *Customer* and *Business* dimensions. We use market volume and rough effort only — no pricing or business-case math.

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

Where each deliverable lives in SharkSight (moved here from the README, 2026-10-13):

| Deliverable | Where |
|---|---|
| Concept + working prototype | PM app: Evidence → Structure → Definition → Prioritize → Document |
| Structured requirement list | Document page; Markdown / CSV export (`/api/document/export`) |
| Workflow: AI autonomous vs mandatory human review | `architecture.md` (workflow table) |
| Audit trail: sources → findings → consolidation → scoring → prioritization → human decision | Audit page (per checkpoint); `audit_event`, append-only by triggers and role permissions (D-059) |

The PDF ("What to demonstrate") phrases the same as three items:
1. **Concept and working prototype**: AI supports identification, formulation and prioritization of customer-facing requirements from the provided data and, where relevant, external sources.
2. **Representative set of requirements with clear evidence and reasoning**: show how feedback, product data, market signals or competitor insights become requirements, and explain what drives their priority.
3. **Transparent decision-support experience**: PMs can **review, challenge, modify, approve or reject** AI proposals. Evidence, assumptions, uncertainties and key decisions stay visible and traceable.

Freedom of approach:
- Teams choose the technical approach, architecture, prioritization logic and UX.
- Deliverables may be one integrated solution or connected concepts, prototypes, models and visualizations (mission.md).
- BMW is interested in how the solution turns information into insight and makes reasoning transparent, "**not in a specific workflow or technical architecture**" (PDF). → Don't over-invest in architecture at the expense of the demo.

## BMW's reference process (image_2.png)

1. **Situation analysis** — baseline (previous BMW model, BMW portfolio, sales volume; AI + human) + competition, customer/public feedback, product & global trends (AI).
2. **Structure & context** — classify, cluster, contextualize: AI standardizes findings, identifies duplicates, groups themes, connects insights → list of all potential requirements (0/1: implement?), e.g. BEV powertrain, cooler, seat ventilation. (AI)
3. **Requirements definition** — specification & quantification: measurable targets + acceptance criteria (e.g. "Range: 600 or 700 mi?", "Cooler for how many bottles?", "Seat ventilation: fast enough?"), grouped by Exterior / Interior / Powertrain / Driver assistance / … (AI + human)
4. **Prioritization** — Customer, Business, … dimensions. (AI + human)
5. **Documentation** — requirements tracking (shown as a cycle). (AI)

## Provided data, promised vs. delivered (`data_and_source.png`)

| Dataset | BMW says | Reality (see `data-inventory.md`) |
|---|---|---|
| Customer verbatims | free text on the current vehicle → pain points, unmet needs, must-not-lose | ✓; no China verbatims, no dates |
| Equipment list | standard/optional equipment "by trim and market" | German price lists only |
| Sales volumes | units "by powertrain and region" | region only, no powertrain; values look stylized (Q-015) |
| Customer study | ratings in various categories | ✓; CN/EU means vs. US 7-point distributions, no sample sizes |

## Judging signals (what BMW says it values)

- Trustworthy sources, transparent reasoning.
- Thoughtful prioritization.
- Clear handling of **uncertainty and conflicting evidence**.
- Customer value over engineering specs / regulation / business case.
- **Scalability** across vehicle lines, markets, future decisions → **don't build a one-off**.
- Focus is free: go deep where we're strongest, but show how it connects to the full path evidence → PM decision.

## BMW mentor clarifications (Discord, 2026-10-10)

Common PM pain points from BMW. **This is a paraphrase** — TODO: paste the verbatim Discord message (author, timestamp) here so the source is traceable.

1. **Balancing customer requirements across markets/regions.** Preferences differ by **climate, real-world usage and culture** — what works in one market can fail in another. → Never treat "the customer" as one group (D-011).
2. **Getting early customer feedback and extracting *future* requirements**, e.g. from feedback on predecessor vehicles. → Project what customers will want at successor launch, not just what they complained about (D-012).
3. **The requirements process is ongoing (~2 years), not a one-time list.** The most relevant requirements are re-prioritized again and again. → Continuous re-prioritization with history, so the PM sees how and why priorities changed (D-013).
4. *(BMW support, 2026-10-10)* **Use the BMW Group Report 2025** to ground ideas: (a) market & sales data (regional growth, deliveries by model series, EV adoption) for personas, demand and impact; (b) product strategy & R&D (R&D priorities, ConnectedDrive/My BMW App, NEUE KLASSE) to show alignment with BMW's investments and future architecture. → Extract in `bmw-annual-report-2025.md`. Note: alignment with BMW strategy is context for prioritization, not engineering output (scope).
