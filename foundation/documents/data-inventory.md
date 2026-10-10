# Data Inventory

All raw files: `challange information document/BMW-Data/` (read-only, git-ignored). Profiled 2026-10-10.

## 1. Customer feedback (verbatims) — `{F70,G60,G70}_feedback_hackathon.xlsx`

Sheet `Feedback_Explorer`, 12 columns:

| Column | Meaning |
|---|---|
| `ID` | Verbatim ID, e.g. `G60-0001`. **Not unique per row** — one row per (verbatim × classification). |
| `Source` | Anonymized channel `Source A`–`D` (see Q-005) |
| `Brand`, `Sales Description` | `[BMW]`, `[BMW 5 Series]` |
| `Country` | ISO-2 (US, GB, JP, KR, …) |
| `Derivate (e-code)` | F70 / G60 / G70 |
| `Engine Type` | `ICE`, `PHEV`, `BEVE` (= BEV) |
| `Feedback Type` | `Likes`, `Difficult to Use`, `Defect`, `Wants`, or empty (unclassified) |
| `Customer Feedback` | Free text (avg ~300 chars) |
| `Vfc level2 3 Name` | Combined "Component : Issue" label |
| `Vfc level2 Name` | Component / topic (e.g. `Seats`, `Touch screen, operation`, `Electric Range`) |
| `Vfc level3 Name` | Issue type (e.g. `Not user-friendly`, `Like: function`, `Customer request: function`) |

| File | Rows | Unique IDs | Sources | Countries (top) | Engines |
|---|---|---|---|---|---|
| F70 | 4,076 | 2,128 | A only | GB 2790, JP 1026, SE, FR… | ICE only |
| G60 | 5,005 | 4,000 | B 2627, A 1858, C 384, D 136 | **US 4365**, KR 278, GB 89 | ICE 2768, BEV 1763, PHEV 474 |
| G70 | 4,690 | 4,000 | B 2855, A 1383, C 314, D 138 | **US 4418**, KR 157, JP 56 | ICE 2956, BEV 1347, PHEV 387 |

Quirks:
- **Dedupe by `ID`** when counting verbatims; keep all rows as classification labels.
- `Feedback Type` empty ⇔ `no_class_found` (~1/4 of F70) — and Source D + some Source C rows have no classification at all. → our own LLM classification is needed, the BMW taxonomy is a hint.
- ~120–220 distinct `Vfc level2` topics; top: Drivetrain, Handling/Riding, Body equipment, Exterior design, Seats, Touch screen, Electric Range.
- Tone per source: B = "Customer stated…" (dealer/agent notes), C = "I had a minor problem with X - DTU/…" (survey with structured prefix), A = first-person reviews, D = short answers to "what could be improved".
- **No China verbatims** for any derivative.

## 2. Customer studies — `F70_G60_G68_G70_customer_studies.xlsx`

### Sheet `CN_EU_2025` (84 rows)
- Columns: China → `BMW 5 Series G68`, `BMW 7 Series G70`; EU → `BMW 1 Series F70`, `BMW 5 Series G60`, `BMW 7 Series G70`.
- 37 categories, each a header row followed by a `Mean` row (values stored **as strings** → parse to float). Scale unconfirmed (likely 0–10; Q-006).
- Categories: overall satisfaction, exterior/interior styling, interior quality, equipment level, safety, squeaks/rattles, value for money, reliability, visibility, controls/displays, smartphone integration, infotainment features + ease of use, navigation, seating comfort, small-item storage, acceleration, roadholding, efficiency, braking, sportiness, prestige, manoeuvrability, ride quality, front/rear roominess, luggage loading + capacity, ingress/egress, environmental friendliness, HVAC, build quality, quietness, driving position, connected services, interior versatility.

### Sheet `US_2025` (934 rows)
- Columns: question, `% of column, sample base`, `BMW 5 Series G60`, `BMW 7 Series G70`.
- 103 questions, each block = `Sample total` + 7-point distribution: I Hate It / A Failure / Unsatisfactory / Satisfactory / Excellent / Delightful / I Love It (shares 0–1).
- Granular: exterior (proportions, wheels, door handles, lights, door sound), driving (ride, handling, power), interior (materials, seats per row, roominess, storage, cupholders, cargo), climate, audio, controls intuitiveness, NVH, …
- **No F70 in US.**
- Useful derived metrics: top-2-box (Delightful + I Love It), bottom-3-box, net score.

## 3. Sales volumes — `sales_volumes.xlsx`

Sheets `F70`, `G60_G68`, `G70`; columns `market, market_code, volume_2024, volume_2025, volume_2030` (2030 = forecast).

| Derivative | EU 25 | CN 25 | US 25 | RoW 25 | Total 25 → 2030 |
|---|---|---|---|---|---|
| F70 | 85k | 0 | 0 | 28k | 113k → 118k |
| G60/G68 | 115k | 75k | 78k | 28k | 296k → 316k |
| G70 | 13k | 10k | 12k | 7k | 42k → 52k |

No powertrain split (despite the briefing saying "by powertrain") — engine mix only inferable from feedback.

## 4. Equipment / option lists — `{F70,G60,G70}_OptionList.PDF`

- German-market price lists ("Preisliste", July 2026), **in German**, 23–28 pages, text-extractable (`pdftotext -layout` works).
- Sections: Fahrzeugpreise (models, power, consumption, price), Serienausstattungen (standard equipment per model), M Sportpaket / Pro / M Sport Design, Räder & Reifen, Farbwelt Exterieur/Interieur, **Sonderausstattungen (options)**, Technische Werte.
- Matrix tables use `■` = standard; options with price.
- Use: baseline "what the car offers today", package structure, gaps vs. competitors. For US/CN it's an **assumption** that equipment is comparable.

## 5. Briefing material
- `BMW_Hackathon_Briefing_Short.pdf` (2 pages), `mission.md`, `data_and_source.png` (dataset purpose table), `image_1.png` ("1 billion findings → 1,000 requirements → one car" + example verbatims/themes), `image_2.png` (reference process).

## Coverage matrix (what we can say where)

| | EU | US | CN |
|---|---|---|---|
| F70 | verbatims (GB-heavy), study, sales | — | — |
| G60/G68 | few verbatims, study, sales | **verbatims, detailed study, sales** | study (G68), sales |
| G70 | few verbatims, study, sales | **verbatims, detailed study, sales** | study, sales |

External/web data fills gaps: competitors (Mercedes E/S/A-Class, Audi A6/e-tron, Tesla, NIO, XPeng, Li Auto, BYD…), reviews, trends.
