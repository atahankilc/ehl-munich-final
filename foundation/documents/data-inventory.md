# Data Inventory

All raw files: `challange information document/BMW-Data/` (read-only, git-ignored). Profiled 2026-10-10; re-verified 2026-10-10 (pandas 3 in a `uv` Python 3.12 env + openpyxl/pdftotext).

**Counting rule:** the feedback files have one row per (verbatim × classification). All verbatim counts below are **unique `ID`s** unless a column says "rows".

## 1. Customer feedback (verbatims) — `{F70,G60,G70}_feedback_hackathon.xlsx`

Sheet `Feedback_Explorer`, 12 columns:

| Column | Meaning |
|---|---|
| `ID` | Verbatim ID, e.g. `G60-0001`. **Not unique per row** — one row per (verbatim × classification). An ID never spans two sources. |
| `Source` | Anonymized channel `Source A`–`D` (interpretation open, Q-005) |
| `Brand`, `Sales Description` | `[BMW]`, `[BMW 5 Series]` |
| `Country` | ISO-2 (US, GB, JP, KR, …) |
| `Derivate (e-code)` | F70 / G60 / G70 |
| `Engine Type` | `ICE`, `PHEV`, `BEVE` (= BEV; the raw value is `BEVE`) |
| `Feedback Type` | `Likes`, `Difficult to Use`, `Defect`, `Wants`, or empty (unclassified) |
| `Customer Feedback` | Free text, mean ~215–225 chars per verbatim (Source D ~125) |
| `Vfc level2 3 Name` | Combined "Component : Issue" label |
| `Vfc level2 Name` | Component / topic (e.g. `Seats`, `Touch screen, operation`, `Electric Range`) |
| `Vfc level3 Name` | Issue type (e.g. `Not user-friendly`, `Like: function`, `Customer request: function`) |

| File | Rows | Verbatims (unique IDs) | Sources (verbatims) | Countries (verbatims) | Engines (verbatims) |
|---|---|---|---|---|---|
| F70 | 4,076 | 2,128 | A 2,128 | GB 1,293, **JP 672**, SE 71, FR 53, AU 16, FI 8, DK 8, KR 4 | ICE 2,128 |
| G60 | 5,005 | 4,000 | B 2,626, A 854, C 384, D 136 | **US 3,610 (90%)**, KR 205, JP 53, GB 36, SE 28, DK 20, CA 18, … | ICE 2,259, BEV 1,363, PHEV 378 |
| G70 | 4,690 | 4,000 | B 2,853, A 695, C 314, D 138 | **US 3,792 (95%)**, KR 137, JP 40, CA 8, GB 8, … | ICE 2,568, BEV 1,129, PHEV 303 |

European verbatims: F70 ~1,430 (67%), G60 ~110, **G70 ~19**. Row counts overstate Source A, which carries the most multi-label rows: G60 Source A has 1,858 rows but only 854 verbatims.

Quirks:
- **Dedupe by `ID`** when counting verbatims; keep all rows as classification labels.
- **Unclassified verbatims:**
  - Source A: `Feedback Type` empty ⇔ `Vfc level2 = no_class_found`. That is 300 of F70's 2,128 verbatims (14%; 27% of rows).
  - Source D: no BMW classification at all.
  - Source C: ~70 verbatims per file have an empty type *and* an empty topic.
  - → Our own LLM classification is needed; the BMW taxonomy is a hint.
- 120 (F70) / 221 (G60) / 211 (G70) distinct `Vfc level2` values incl. `no_class_found`. Top topics: Drivetrain, Handling/Riding, Body equipment, Exterior design, Seats, Touch screen, Electric Range.
- Observed text patterns per source. These are **observations, not channel identities** (Q-005):
  - **A:** all derivatives, many countries (incl. JP/KR), lower-case normalized text ("the car…", "i really…"), so possibly translated.
  - **B:** US only; most verbatims start "Customer stated / mentioned / reported / commented…" (third-person notes).
  - **C:** US only; ~30–40% start "I had a minor/serious problem with…", others "What is…" / "If there…" (structured survey prompts); mostly Difficult-to-Use/Defect.
  - **D:** US only; short, ~80% positive wording ("love the…"), unclassified. It looks like answers to a "what do you like" question, **not** "what could be improved".
- **No China verbatims** for any derivative. There is **no date column** — no time series possible.

## 2. Customer studies — `F70_G60_G68_G70_customer_studies.xlsx`

### Sheet `CN_EU_2025` (76 content rows; openpyxl reports 84 incl. trailing empty rows)
- Columns: China → `BMW 5 Series G68`, `BMW 7 Series G70`; EU → `BMW 1 Series F70`, `BMW 5 Series G60`, `BMW 7 Series G70`.
- 37 categories, each a label row followed by a `Mean` row. Values are **numeric cells** (format `#,##0.00`), range ~6.5–9.9. Scale unconfirmed (0–10 or 1–10?; Q-006).
- **No sample sizes.**
- Categories: overall satisfaction, exterior/interior styling, interior quality, equipment level, safety, squeaks/rattles, value for money, reliability, visibility, controls/displays, smartphone integration, infotainment features + ease of use, navigation, seating comfort, small-item storage, acceleration, roadholding, efficiency, braking, sportiness, prestige, manoeuvrability, ride quality, front/rear roominess, luggage loading + capacity, ingress/egress, environmental friendliness, HVAC, build quality, quietness, driving position, connected services, interior versatility.

### Sheet `US_2025` (929 content rows; openpyxl reports 934)
- Columns: question, `% of column, sample base`, `BMW 5 Series G60`, `BMW 7 Series G70`.
- 103 questions, each block = `Sample total` + 7-point distribution: I Hate It / A Failure / Unsatisfactory / Satisfactory / Excellent / Delightful / I Love It. Shares 0–1; every block sums to 1.0.
- **`Sample total` = 1 is the share base, not a respondent count → no sample sizes.** No significance testing or n-weighting is possible.
- Granular: exterior (proportions, wheels, door handles, lights, door sound), driving (ride, handling, power), interior (materials, seats per row, roominess, storage, cupholders, cargo), climate, audio, controls intuitiveness, NVH, …
- **No F70 in US.**
- Useful derived metrics: top-2-box (Delightful + I Love It), bottom-3-box, net score. CN/EU means and US distributions are **not directly comparable** (Q-006).

## 3. Sales volumes — `sales_volumes.xlsx`

Sheets `F70`, `G60_G68`, `G70`; columns `market, market_code, volume_2024, volume_2025, volume_2030` (2030 = forecast).

| Derivative | EU 25 | CN 25 | US 25 | RoW 25 | Total 24 → 25 → 2030 |
|---|---|---|---|---|---|
| F70 | 85k | 0 | 0 | 28k | 105k → 113k → 118k |
| G60/G68 | 115k | 75k | 78k | 28k | 278.6k → 296k → 316k |
| G70 | 13k | 10k | 12k | 7k | 34k → 42k → 52k |

- **No powertrain split**, although `data_and_source.png` says "units by powertrain and region". Engine mix can only be inferred from feedback.
- `G60_G68` is one combined sheet, with no G60/G68 split. CN is presumably the G68 LWB.
- **Values look stylized and conflict with public data** (Q-015):
  - All values except one are round thousands.
  - G60/G68 CN is 68k → 75k (+10%) for 2024 → 2025. Public figures point the other way: 5 Series China (China-built) Jan–Nov 2025 was 107,348 per CPCA via Gasgoo, and BMW+MINI China fell 12.5% in 2025 (`competitor-landscape.md`, `portfolio-reference.md`).
  - F70 EU 85k vs. 1 Series Europe 91,931 (Dataforce; "Europe" definitions differ).
  - Until clarified, treat the file as **BMW-internal relative weights**, and surface the conflict instead of mixing both sources.

## 4. Equipment / option lists — `{F70,G60,G70}_OptionList.PDF`

- German-market price lists, **in German**, text-extractable (`pdftotext -layout` works):

  | File | PDF title | Edition | Pages |
  |---|---|---|---|
  | F70 | "BMW 1er Katalog Juli 2026" | Ausgabe 1, 28.05.2026 | 23 |
  | G60 | "BMW 5er **Limousine** Katalog Juli 2026" | Ausgabe 2, 22.06.2026 | 28 |
  | G70 | "BMW 7er Katalog Juli 2026" | Ausgabe 1, 28.05.2026 | 27 |

  The G60 list covers the sedan incl. i5 — **no Touring (G61)**.
- Sections: Fahrzeugpreise (models, power, consumption, price), Serienausstattung(en) (standard equipment per model), M Sportpaket / Pro, Räder & Reifen, Farbwelt, **Sonderausstattungen (options)**, Technische Werte.
- Matrix tables use `■` = standard; options with price.
- Use: baseline "what the car offers today", package structure, gaps vs. competitors.
- The briefing promises equipment "by trim and **market**", but only DE was provided. For US/CN it's an **assumption** that equipment is comparable.

## 5. Briefing material
- `BMW_Hackathon_Briefing_Short.pdf` (2 pages). **Image-only (no text layer):** `pdftotext` returns nothing, so render it (`pdftoppm`) to read it.
- `mission.md`.
- `data_and_source.png`: dataset purpose table.
- `image_1.png`: "1 billion findings → 1,000 requirements → one car" + example verbatims/themes.
- `image_2.png`: reference process.

## Coverage matrix (what we can say where)

| | EU | US | CN | RoW |
|---|---|---|---|---|
| F70 | ~1.4k verbatims (GB-heavy), study, sales | — | — | **~690 verbatims (JP 672)**, sales |
| G60/G68 | ~110 verbatims, study, sales | **~3.6k verbatims, detailed study, sales** | study (G68), sales | ~280 verbatims (KR 205, JP, CA), sales |
| G70 | ~19 verbatims (≈ none), study, sales | **~3.8k verbatims, detailed study, sales** | study, sales | ~190 verbatims (KR 137, JP), sales |

- RoW verbatims (JP/KR/CA/AU) are separate customer groups under D-011 — don't fold them into EU.
- External/web data fills gaps: competitors (Mercedes E/S/A-Class, Audi A6/e-tron, Tesla, NIO, XPeng, Li Auto, BYD…), reviews, trends.
