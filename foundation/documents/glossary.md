# Glossary

Short definitions of terms used across the foundation. Sources are in the linked docs.

## Vehicles & codes
| Term | Meaning |
|---|---|
| **F70** | BMW 1 Series, current generation (built only in Leipzig) |
| **G60 / G61** | BMW 5 Series sedan / Touring (Dingolfing); i5 = BEV variant |
| **G68** | China-only long-wheelbase 5 Series + i5 LWB (Shenyang Dadong) |
| **G70** | BMW 7 Series incl. i7 (Dingolfing); facelift (LCI) SOP Jul 2026 |
| **Derivative / "Derivate"** | A model variant identified by its e-code (F70, G60, …); unit of the BMW data files |
| **LWB** | Long wheelbase (China-specific variants) |
| **SOP / EOP** | Start / end of production |
| **LCI** | Life Cycle Impulse = BMW's term for a facelift |
| **CKD** | Completely knocked down: local assembly from kits (Chennai, Rayong, Araquari) |
| **BBA** | BMW Brilliance Automotive, BMW's Chinese JV (Shenyang plants Dadong + Tiexi) |

## Platforms
| Term | Meaning |
|---|---|
| **CLAR** | Rear/all-wheel-drive cluster architecture (3/4/5/7 Series, X3–X7) |
| **FAAR** | Front-wheel-drive architecture, successor of UKL2 (1/2 Series, X1/X2) |
| **NK / NEUE KLASSE** | BMW's new BEV-first model generation (iX3 2025, i3 2026). BMW's name for its base: **NCAR** ("new cluster architecture") |
| **Gen6 eDrive** | Sixth-generation BMW electric drivetrain/battery (cylindrical cells) used by NK |

## Powertrains & market terms
| Term | Meaning |
|---|---|
| **ICE / PHEV / BEV** | Combustion / plug-in hybrid / battery electric. BMW data writes BEV as `BEVE` |
| **EREV** | Extended-range EV (combustion engine only charges the battery). Common in China |
| **NEV** | China's "new energy vehicle" = BEV + PHEV + EREV |
| **xEV / electrified** | BEV + PHEV (BMW reporting) |
| **ADAS / L2+** | Advanced driver assistance; L2+ = hands-on assisted driving incl. navigation-based features |
| **DCAS (UN R171)** | UN regulation for driver control assistance systems; BMW's Highway/City Assistant approval |
| **OTA / RSU** | Over-the-air update; BMW calls it Remote Software Upgrade |
| **CPCA / ACEA / KBA** | China / EU / German car-market statistics bodies |
| **APEAL / IQS / TXI** | J.D. Power studies on appeal, initial quality, tech experience |

## BMW data terms
| Term | Meaning |
|---|---|
| **Verbatim** | One free-text customer feedback item (unique `ID`) |
| **Source A–D** | Anonymized feedback channels (meaning open, Q-005) |
| **VFC level2 / level3** | BMW's feedback taxonomy: component/topic and issue type |
| **DTU** | "Difficult to Use" feedback type |
| **Top-2-box** | Share of "Delightful" + "I Love It" in the US 7-point study |

## Our model
| Term | Meaning |
|---|---|
| **Source item → finding → requirement → target** | Evidence chain: raw evidence → clustered insight → customer requirement → derivative × market it applies to |
| **E1–E4** | Evidence levels: strong / moderate / weak / assumption (`requirement-model.md`) |
| **T1–T3** | Source trust tiers: official/internal · reputable press/analysts · forums/blogs (`knowledge-base.md`) |
| **Kano class** | basic / performance / delighter; **drift** = expected shift by successor launch (D-012) |
| **Horizon** | `today` vs. `at_successor_launch` (3–5 yr) |
| **Fit checks** | brand / segment / market / feasibility per target: pass / warn / fail |
| **Prioritization run / snapshot** | One scoring pass with stored scores and ranks (D-013) |
| **Change proposal** | AI-suggested priority/status change that only the PM can accept |
| **Ingest wave** | Simulated batch of new evidence used to demo the ~2-year process (Q-012) |
| **PM** | Product manager — the human decision-maker in the loop |

## Budget terms (D-014)
| Term | Meaning |
|---|---|
| **luna / sol** | `gpt-6-luna` (cheap bulk) / `gpt-6.1-sol` (reasoning) |
| **Standard / Flex / Batch** | OpenAI tiers: Flex and Batch are 50% cheaper. Flex returns same-day; Batch within 24 h |
| **Billed search call** | One web-search action; a single reasoning request can make several |
