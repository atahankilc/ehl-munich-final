# Sales-volume verification (BMW `sales_volumes.xlsx` vs. DB vs. public data)

Checked 2026-10-11. Scope: F70 (1 Series), G60/G68 (5 Series, incl. China LWB), G70 (7 Series), markets EU / US / CN / RoW, years 2024 / 2025 / 2030 (forecast).
How it was checked:
- The raw xlsx was read locally with openpyxl, both formulas and cached values.
- The DB was opened read-only (`sqlite3 -readonly data/app.db`).
- Public figures were searched by model, market and year only. No BMW file value was sent to any external service (AGENTS rule 1).
- Nothing was paid for, and no OpenAI calls were made.

## Verdicts

| # | Question | Verdict |
|---|---|---|
| 1 | Ingest correctness (DB vs. file) | **Correct.** All 36 cells match. No drops, no duplicates, no unit scaling, and the G60/G68 split is right. One semantic caveat about F70 2024 (below). |
| 2 | Plausibility vs. public data | **Issues found.** Some cells are plausible: F70 EU, G70 US, the 5 Series *global total* for 2025, and 2024→25 growth for the 5 Series and 1 Series. Others are not: **G60 US is ~3× too high**, **G68 CN is 21–39% too low**, RoW is too low for G60 and G70, and G70 grows while public 7/8 Series deliveries fell. The 2030 growth for every cell conflicts with 2026 actuals. |
| 3 | Our own research items | **Mostly correct.** 21 sales items were spot-checked and none is clearly wrong. Issues: 2 items cite a secondary source that disagrees with BMW's official table, ~9 items are duplicated, 2 China H1 2026 figures use different measures without labels, 1 rationale is not in its source, and 3 Yiche items could not be verified. |

## 1. Ingest correctness

- **File structure.** The file `challange information document/BMW-Data/sales_volumes.xlsx` has 3 visible sheets: `F70`, `G60_G68` and `G70`. Each sheet is `A1:E5`, with columns `market, market_code, volume_2024, volume_2025, volume_2030`. There are no hidden sheets and no defined names.
- **Number format.** All number formats are `General`, and every value is a whole unit count (e.g. 80000). Nothing is in thousands, and the ingest code applies no scaling.
- **DB contents.** The `sales` table has 36 rows, which is 3 sheets × 4 markets × 3 years. There are 36 distinct (model, market, year) keys, so no row is duplicated. The rows are backed by 24 `source_item` rows (kind `sales`, one per row and wave), and `is_forecast=1` is set only on the 2030 rows.
- **Cell-by-cell check.** Every DB value equals the file's cached value. This includes the zero rows: F70 CN and F70 US are 0 in all years.
- **Market mapping.** The file codes `EU/CN/US/RoW` map 1:1 to our market codes. The EU market in our `market` table covers EU-27 plus GB, NO, CH, IS and LI, which is close to the Dataforce "Europe" scope.
- **G60 vs G68.** `SHEET_MODELS` assigns `G60_G68`/CN to G68 and the other markets to G60. This is right: the G68 LWB is China-only, and China does not get the G60 ([BMW press 8 Aug 2023 / 25 Jan 2024], `portfolio-reference.md` §2). The sheet probably also includes the i5 and the G61 Touring under "G60" (not stated in the file).
- **Formula quirk (already known and handled).** F70!C3 (China 2024) is `=-D3-C10`. C10 is empty, so the formula evaluates to −0 = 0. The DB stores 0, and the formula is kept in `meta_json.formulas`.
- **Semantic caveat, not a bug.** The F70 2024 value (EU 80k, RoW 25k) cannot be F70-only. The F70 launched on 5 Oct 2024, so 2024 is mostly the predecessor F40. Treat 2024 as "1 Series line".
- **Latent code risks (not triggered by this file).**
  - `read_sales` silently skips rows with an empty `market_code`.
  - It silently truncates float values via `int()`.
  - A non-numeric cell becomes `units = NULL` with no warning.

  None of these occurs in the current file.

## 2. Plausibility vs. public data

Divergence = (BMW − public) / public. "n/v" = not verified (no public figure found).

| Car | Mkt | Year | BMW file | Public value(s) | Source (published) | Divergence |
|---|---|---|---|---|---|---|
| F70 | EU | 2024 | 80,000 | ≈83,960 (derived: 91,931 / 1.095). This is 1 Series incl. F40 runout. DE alone 19,705 (KBA). | Dataforce via [bmwblog](https://www.bmwblog.com/2026/01/20/bmw-x1-best-selling-bmw-europe-2025/) (2026-01-20); [KBA FZ10 12/2024](https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ10/fz10_2024_12.xlsx?__blob=publicationFile) | −5% |
| F70 | EU | 2025 | 85,000 | 91,931 (+9.5%). DE 26,293 (+33%), UK 20,538. | Dataforce via bmwblog (2026-01-20); [KBA FZ10 12/2025](https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ10/fz10_2025_12.xlsx?__blob=publicationFile) (2026-01); [BMW UK](https://www.press.bmwgroup.com/united-kingdom/article/detail/T0454784EN_GB/bmw-group-uk-leads-the-premium-segment-in-2025) (2026-01-06) | −7.5% |
| F70 | CN | all | 0 | Correct: China sells a locally built 1 Series sedan (Tiexi), not the F70. | `portfolio-reference.md` §2 | ok |
| F70 | US | all | 0 | Correct: the 1 Series is not sold in the US. | BMW NA table (below) has no 1 Series row | ok |
| F70 | RoW | 24/25 | 25k / 28k | n/v. The 1/2 Series pair globally is 198,226 → 214,175 and cannot be split. The 1 Series is not in Japan's 2025 import top 10. | BMW Group Report 2025 p. 79; JAIA | n/v |
| G60 | US | 2024 | 75,600 | **25,315** (5 Series incl. i5; the i5 alone was 8,763) | [BMW NA Q4/FY2025 table](https://www.press.bmwgroup.com/usa/article/attachment/T0454803EN_US/642259) (2026-01-05) | **+199%** |
| G60 | US | 2025 | 78,000 | **27,107** (+7.1%) | same | **+188%** |
| G60 | EU | 2024 | 110,000 | n/v (Europe). DE 26,669 (KBA). Derived Europe Jan–Apr 2024 ≈ 18.8k (5 Series + i5). | KBA; [Carscoops/Dataforce](https://www.carscoops.com/?p=3224228) (2025-06-04) | n/v |
| G60 | EU | 2025 | 115,000 | n/v (full year). DE 37,643 (+41%, incl. 11,485 BEV). Europe Jan–Apr: 5 Series 20,402 (+56%) + i5 8,843 (+55%) = 29,245. Full-year run rate ≈ 85–90k is **our estimate, unverified**. | KBA 12/2025; Dataforce via Carscoops (2025-06-04) | ≈ +30% if run rate holds (unverified) |
| G68 | CN | 2024 | 68,000 | **86,174** (CPCA, 5 Series excl. i5) | Gasgoo "December 2024 sales ranking of C sedans… Germany's brands" (`autonews.gasgoo.com/sales/article/75729.html`). Seen via search snippet only; the page returned 403. | **−21%** |
| G68 | CN | 2025 | 75,000 | **107,348** Jan–Nov (CPCA, Nov +14.4% YoY). **116,173** FY retail (PCauto). i5 China 7,461 (Yiche, unverified). | Gasgoo Nov 2025 ranking (2025-12, snippet); [PCauto](https://price.pcauto.com.cn/salescar/sg441/) (fetched 2026-10-11) | **−30% to −39%** |
| G60+G68 | all | 2024 | 278,600 | 250,674 (5/6 Series, BMW brand) | BMW Group Report 2025 p. 79 (2026-03) | +11% |
| G60+G68 | all | 2025 | 296,000 | 299,582 (+19.5%) | same | −1% |
| G60 | RoW | 2025 | 28,000 | Korea alone 23,876. The rest of RoW (JP, CA, AU, Middle East, India/Thailand CKD) is not counted. | [Hankyung](https://www.hankyung.com/article/202606232417g) (2026-06-24) | KR alone = 85% of the BMW RoW figure, so the file is implausibly low |
| G70 | US | 2024 | 10,000 | **10,714** (incl. i7; i7 alone 3,431) | BMW NA FY2025 table (2026-01-05) | −7% |
| G70 | US | 2025 | 12,000 | **11,393** (+6.3%; i7 2,905, −15.3%) | same + [BMW NA release](https://www.press.bmwgroup.com/usa/article/detail/T0454803EN_US/bmw-of-north-america-reports-full-year-2025-u-s-sales-results) | +5% |
| G70 | CN | 2024 | 8,000 | n/v | — | n/v |
| G70 | CN | 2025 | 10,000 | 9,525 registrations. Dec 2025: 1,429 (ECC). | Yiche (research item 12313, T3, page is JS-only so not re-verified); [CarNewsChina](https://carnewschina.com/2026/01/12/huaweis-maextro-s800-outsold-rivals-from-porsche-bmw-and-maybach-in-china/) (2026-01-12) | +5% (unverified base) |
| G70 | EU | 24/25 | 11k / 13k (+18%) | n/v (Europe). **DE 2,917 → 2,586 (−11%)**. UK 2025: 7 Series 794 + i7 959. | KBA 12/2024, 12/2025; BMW UK (2026-01-06) | Direction conflicts with DE |
| G70 | RoW | 2025 | 7,000 | Korea alone 5,834 (+17%) | Korea Times via KAIDA (repo source 10742) | KR = 83% of the BMW RoW figure, so the file is too low |
| G70 | all | 24→25 | 34k → 42k (**+24%**) | 7/8 Series 56,542 → 53,399 (**−5.6%**). 8 Series US alone was 5,345 / 4,029. | BMW Group Report 2025 p. 79 | Level too low by ~10–15k (8 Series share n/v). **Direction wrong.** |

### Is "everything grows, 2024 → 2025 → 2030" plausible?

- **2024 → 2025: partly yes.** 2024 was a changeover year for the 5 Series (G60 SOP Oct 2023, G68 SOP Jan 2024) and the 1 Series (F70 launch Oct 2024), so growth in 2025 is real. Public figures for these cells:
  - 5 Series US: +7.1%.
  - 5 Series China: 86k → ≥107k (Jan–Nov).
  - 5 Series Europe: Jan–Apr +56%; Germany +41%.
  - 1 Series Europe: +9.5%.
  - **Correction to Q-015:** Q-015 says the China 5 Series public figures "point the other way". That is wrong for the 5 Series itself. The 5 Series grew in China in 2025, even though BMW+MINI China fell 12.5%. The conflict is the **level** (file 75k vs public 107–116k), not the direction.
- **7 Series 2024 → 2025: mixed.** US +6.3% and Korea +17%, but Germany −11% and global 7/8 Series −5.6%. The file's +24% total is not supported.
- **2025 → 2030: not supported by current actuals.**
  - BMW Group H1 2026: −4.2%; China −20.4%.
  - 5 Series US H1 2026: −7.1% ([BMW NA Q2 2026 table](https://www.press.bmwgroup.com/usa/article/attachment/T0459010EN_US/651660), 2026-07-02).
  - 5 Series China H1 2026: −19% (Yiche retail) or 42,588 YTD with June −59% (CPCA via [Gasgoo June 2026](https://autonews.gasgoo.com/autosales/june-2026-sales-ranking-of-c-sedanscars-from-germanys-brands-80934.html)).
  - 7 Series US H1 2026: −9.2%.
  - 7 Series China H1 2026: 3,671, which annualises to about −23% vs 2025. The i7 was reportedly dropped in China in June 2026 (CnEVPost, 2026-06-17).
  - By 2030, the G60 and G70 will be at or past end of cycle. BMW lists the 7 Series successor among its Neue Klasse developments (BMW Group Report 2025 p. 70/81). So a 2030 "G60/G70" volume is in effect a successor volume.
- **What the pattern suggests.** The 5 Series total matches BMW's published global figure almost exactly (−1%). The market split does not:
  - US is about 51k too high.
  - China is about 32–48k too low.
  - RoW is too low.

  This fits a file built top-down from a total, with a stylized market split (Q-015). This is an inference, not verified.

## 3. Research-item spot check (DB `source_item`, kind `research`)

| id(s) | Claim | Check | Result |
|---|---|---|---|
| 12090 / 11358 | 5 Series US 2025 27,107 (+7.1%) | BMW NA table: 27,107 vs 25,315 = +7.1% | ok |
| 12092 / 11360 | 7 Series US 2025 11,393 (+6.3%) | BMW NA table: 11,393 vs 10,714 | ok |
| 12094, 12096 | Q4 2025 5 Series 6,097 (−25.2%); 7 Series 2,862 (−24.8%) | BMW NA table: Q4 2024 was 8,147 / 3,806 | ok |
| 12098/11380, 12099/11381 | i5 6,877 (−21.5%); i7 2,905 (−15.3%) | BMW NA release: 8,763 / 3,431 in 2024 | ok |
| 12091, 12093, 12095, 12097 | H1 2026 5 Series 12,473 (−7.1%), 7 Series 5,181 (−9.2%); Q2 6,984 (+17.3%), 2,921 (−7.3%) | BMW NA Q2 2026 table | ok |
| 12036, 12060, 12066 | KBA DE 2025: 1 Series 26,293; 5 Series 37,643; 7 Series 2,586 | KBA FZ10 12/2025 (downloaded, parsed locally) | ok |
| 11388 / 12134 | 7/8 Series global 53,399 (−5.6%) | Group Report p. 79: 56,542 → 53,399 | ok |
| 11382 / 12133 | 5/6 Series 299,582 (+19.5%); rationale "2024 was changeover year" | The figures are in bmwblog (2026-03-12). The changeover rationale is **not in the bmwblog article**; it is our inference (correct per `portfolio-reference.md` S41). | Value ok; **rationale misattributed to this URL** |
| **11437** | "G60 US 26,861 (2025)", GoodCarBadCar | GCBC does show 26,861 and says the i5 is "tracked separately". But BMW's official table gives **27,107**, and its passenger-car rows sum to the total with no separate i5 row, so the 5 Series row includes the i5. | **Conflicts with T1. Use 27,107.** |
| **11443** | "G70 US 11,303 (2025)", GCBC | BMW official: **11,393** | **Conflicts with T1. Use 11,393.** |
| 11433, 11442 | G30 US peak 43,937 (2018) → 20,857 (2022); G11 12,918 (2016) → 5,974 (2022) | GCBC table matches (the 2015 figure of 44,162 is F10, so "G30 peak" is fine) | ok (T2/T3) |
| 11390 / 12147 | 5 Series China Jan–Nov 2025 107,348, 3rd | Gasgoo Nov 2025 snippet: YTD 107,348. Ranked 3rd YTD behind A6L 147,845 and E-Class 117,633; ranked 2nd in November alone. | ok (page itself 403) |
| 12268 | 5 Series China FY2025 retail 116,173 | PCauto page shows "2025年累计 116,173" | ok |
| **11391 vs 12269** | H1 2026: 42,588 (CPCA) vs 48,041 (−19%, Yiche retail) | Both figures exist but measure different things (CPCA ranking vs Yiche retail). The −19% for 12269 could not be verified. | **Label the measure. Don't present both as "sales".** |
| 11728, 11729, 12334 | 7 Series China Apr 2026 436, Jan–Apr 2,976; Dec 2025 1,429 | CarNewsChina (2026-05-13, 2026-01-12), ECC data | ok |
| 12116 | 5 Series Korea 2025 23,876 | Hankyung (2026-06-24) states it. The article does not name which body the unit figures come from (KAIDA is cited only for rankings). | ok, provenance vague |
| 12313, 12281, 12269–12271 | Yiche 7 Series China FY2025 9,525; i5 7,461; monthly 5 Series | The Yiche pages render via JS, so no content could be fetched. A web search did not find 9,525. | **Unverified (T3)** |

- **Duplicates.** About 9 claim pairs appear twice from two ingest runs (11358/12090, 11360/12092, 11380/12098, 11381/12099, 11382/12133, 11386/12132, 11388/12134, 11390/12147, 11372/12088). Their rationale fields differ. Dedupe or link them via `pair_key`, so that evidence counts are not inflated.
- **Errors found.** No wrong model, market or year assignment was found in the checked items.

## Recommendation for the pipeline

1. **Use BMW's file only as a relative, BMW-internal weight**, with the label "BMW-provided, stylized (Q-015)". Never use it as an absolute volume, and never blend it with public figures.
2. **Prefer within-car shares over cross-car comparisons.** Two cases are safe enough: F70 EU vs RoW, and G70 US vs CN. The G60/G68 US-vs-CN split is not safe. If the file says the US is 2.9× bigger than in public data, a market-weighted score for the 5 Series will over-weight US customers. In that case, show both weightings and let the PM decide.
3. **Do not use the file's growth (2024→25→2030) as a growth signal.** For trend, use the cited public T1 figures:
   - BMW NA tables.
   - KBA FZ10.
   - The BMW Group Report p. 79.
   - CPCA via Gasgoo for China, labelled as wholesale or retail.

   Treat the 2030 column as a "successor-volume assumption" (horizon tag, D-012), not as a fact.
4. **Surface conflicts automatically.** When the file and a public figure for the same car × market × year differ by more than ±25%, emit a conflict flag on the finding or score. That threshold flags G60 US, G68 CN, G70 total and the RoW rows. Today it would fire for G60 US (+188–199%) and G68 CN (−21% to −39%).
5. **Fix the research corpus:**
   - Keep the T1 values over GCBC (11437, 11443).
   - Merge the duplicates.
   - Tag China figures as `measure: wholesale|retail|registrations`.
   - Keep the Yiche-only numbers flagged as unverified.
6. **Ask BMW (Q-015):** is the US row really US only, and does the CN row include the i5 LWB and imports? An answer either fixes the split or confirms that the file is purely illustrative.
