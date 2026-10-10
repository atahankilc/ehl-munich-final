# Requirement Model, Evidence Levels & Prioritization

**Status: DRAFT v3** (adds per-market scoring D-011, future needs D-012, continuous re-prioritization D-013) — prioritization weights still open (Q-004).

## Requirement fields (all required by BMW deliverable + our additions)

| Field | Notes |
|---|---|
| `id` | Global `REQ-0001`, stable forever |
| `targets` | One or more (derivative × market) with realization type: `carry_over`, `platform_wide`, `derivative_specific`, `market_variant`, `package`. **Each target has its own score, priority and fit result** (D-011) |
| `horizon` | `today` (fix/keep) or `at_successor_launch` (projected 3–5 yr need) (D-012) |
| `kano_class` / `kano_drift` | basic / performance / delighter, and expected drift by SOP (e.g. delighter → basic) |
| `title` / `description` | Customer-facing, actionable, solution-neutral where possible |
| `category` | Exterior · Interior · Comfort & Space · Infotainment & Digital · Driving Experience · Powertrain (as experienced) · Range & Charging · Driver Assistance (as experienced, scope Q-016) · Variants & Packages · Design & Quality Perception. Powertrain and Driver Assistance follow BMW's process image (image_2) |
| `target_metric` / `acceptance_criteria` | Measurable where possible |
| `linked_findings` → sources | Every requirement ≥ 1 finding; every finding ≥ 1 source |
| `fit_checks` | brand / segment / market / feasibility per target — pass / warn / fail + rationale |
| `score`, `score_breakdown`, `priority` | Per target; Must / Should / Could from score + PM decision; full history via `score_snapshot` |
| `rationale` | Plain-language explanation of score |
| `evidence_level` | See below |
| `assumptions` / `uncertainties` | Forward-looking (3–5 yr) beliefs and what could make them wrong |
| `conflicting_evidence` | Contradicting sources — shown, not hidden |
| `status` | `proposed` → `in_review` → `approved` / `rejected` / `deferred`; `challenged` loops back to `proposed`. AI may only create in `proposed` and set nothing else; every other transition is human (PM) with rationale (AGENTS rule 5) |

## Evidence levels

| Level | Meaning |
|---|---|
| **E1 Strong** | Multiple independent T1 sources agree (verbatims across sources + study gap and/or sales signal) |
| **E2 Moderate** | One strong T1 source, or T1 + T2 |
| **E3 Weak** | Few verbatims or external-only (T2/T3) |
| **E4 Assumption** | Forward-looking trend/expectation without current customer evidence |

## Gates (before scoring counts)

- **Brand fit = fail** → requirement cannot be approved for that target without a PM override + rationale.
- **Feasibility = fail** (no platform/plant can deliver it for that market in time) → same.
- `warn` results lower the score via the confidence factor and are shown prominently.

## Prioritization (draft, explainable weighted score; base weights sum to 100 — final range and the known issues are open in Q-004)

| Factor | Signal | Default weight |
|---|---|---|
| Customer pain / desire | dedup'd verbatim frequency, share of segment, severity (Defect/DTU > Want) | 25 |
| Satisfaction gap | low study score / bottom-box vs. other models & categories | 15 |
| Market volume & momentum | sales volume of this derivative × market, 2030 growth, share under pressure (e.g. China) | 15 |
| Market-profile fit | how strongly climate, usage and culture of this market amplify the need (e.g. rear-seat comfort in CN chauffeur use, seat ventilation in hot climates) | modifier ±10 |
| Competitive pressure | competitors in segment × market offer it / reviews cite it | 15 |
| Portfolio leverage | number of derivatives/markets benefiting on same platform (carry-over) | 10 |
| Future relevance | trend strength 3–5 yr, Kano drift, NK timing | 10 |
| Evidence freshness | decay on old evidence unless re-confirmed (D-013) | multiplier 0.7–1.0 |
| Brand & segment fit | strength of fit (pass strong / pass / warn) | 10 |
| Evidence confidence | multiplier by evidence level | ×(1.0 / 0.85 / 0.7 / 0.5) |
| Rough effort (optional) | S/M/L penalty (carry-over cheaper than derivative-specific) | −0…10 |

Plus **"must not lose" flag** for strong delighters (Likes).

PM can change weights in the UI; each change creates a new `weights_version`, an audit event and a prioritization run with a visible diff.

## Continuous re-prioritization (D-013)

- Every prioritization run snapshots score, breakdown, rank and priority per requirement-target.
- Scores may be recomputed automatically (logged); **priority and status changes are only proposed** (`change_proposal`) and need a PM decision.
- Each proposal states its cause: which new evidence, weight change, or market shift moved it, and by how much per factor.
- The PM sees a priority timeline per requirement and a "what changed since last run" view.
