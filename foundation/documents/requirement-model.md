# Requirement Model, Evidence Levels & Prioritization

**Status: v4 — as built** (scoring v1, D-029, resolves Q-004; evidence levels computed per target; feasibility non-blocking D-030). Code: `bmw_req/pipeline/scoring.py`.

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

## Gates

- **Brand fit = fail** → the requirement cannot be approved without a PM override + rationale (`service.override_gate`).
- **Feasibility** = realization context only (D-030): checked and shown, never blocking, not scored.
- Fit checks: luna first, every warn/fail re-checked by sol (final verdict). `market` fit feeds a score modifier.

## Evidence level (per target, deterministic)

| Level | Rule (verbatims = distinct verbatims of the target's derivative × market behind supporting findings) |
|---|---|
| E1 | ≥ 20 verbatims from ≥ 2 channels AND (study gap supports it OR a T1/T2 web finding) |
| E2 | ≥ 15 verbatims, OR ≥ 3 verbatims + study/T1–T2 web, OR study + T1–T2 web |
| E3 | any verbatim, study item or web finding |
| E4 | nothing but assumptions |

The requirement-level `evidence_level` = best target level.

## Prioritization (scoring v1, D-029)

`score = 100 × Σ wᵢ·vᵢ / Σ wᵢ (over factors WITH data for this target) × confidence + market-fit modifier + effort modifier`, clipped 0–100.

| Factor (vᵢ ∈ 0–1) | Default weight | How |
|---|---|---|
| Customer voice | 30 | severity-weighted share of the market's in-scope feedback behind the supporting verbatim findings (log-saturating); support questions ×0.5; **no data** if the market has < 30 in-scope verbatims (CN, G70 EU) |
| Satisfaction gap | 15 | linked study items for this model × market: −z/2 (pain) or +z/2 (must-not-lose); **no data** before wave 2 / without a linked item |
| Market volume | 15 | BMW sales file (relative only, Q-015): 0.75 × units / max units + 0.25 × 2030 momentum |
| Competitive pressure | 15 | tier-weighted sources of linked competitor-advantage / review-criticism web findings for the market (4 = saturated) |
| Future relevance | 15 | horizon (today 0.3 / successor 0.6) + Kano drift to basic (+0.2) + trend/expectation findings (+0.1 each, ≤ 0.4) |
| Portfolio leverage | 10 | targets / 4 (+0.2 platform-wide) |
| Confidence | multiplier | E1 1.0 · E2 0.92 · E3 0.8 · E4 0.65 |
| Market fit | modifier | pass +2 · warn −5 · fail −10 |
| Effort | modifier | S 0 · M −3 · L −6 |

- Missing factors are renormalized and listed as **evidence gaps** on screen — a market is not punished for missing data, but its evidence level and confidence stay honest (fixes the CN bias of v3).
- Proposed priority bands: **Must ≥ 60, Should ≥ 45, Could < 45**. The AI proposal is shown next to the PM-confirmed priority.
- Every target shows its factor breakdown, gaps, modifiers and a plain-language rationale; weights are PM-editable and versioned (`weights_version`, audited).

## Continuous re-prioritization (D-013)

- Every prioritization run snapshots score, breakdown, rank and priority per requirement-target.
- Scores may be recomputed automatically (logged); **priority and status changes are only proposed** (`change_proposal`) and need a PM decision.
- Each proposal states its cause: which new evidence, weight change, or market shift moved it, and by how much per factor.
- The PM sees a priority timeline per requirement and a "what changed since last run" view.
