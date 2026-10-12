# Prioritization layer (D-050)

BMW reference process step 4: *Prioritization — Customer, Business, … dimensions (AI + human)*. It sits on top of the requirement definition layer (D-048, `requirement-definition.md`) and is page 4 of the app: **Prioritize** (`/prioritize`).

## Principles

- **Unit = requirement × car line × market target** (D-011): markets are different customers, so the 5 Series in the US and in China get separate priorities. Targets come from `def_requirement` (latest `define` run) × the lines/markets on its ladder (`def_spec`).
- **Deterministic scoring, free.** No LLM in `prioritize`; only the brand/segment/market `gate` uses the LLM. Rationale text is templated from the factor breakdown (rule 11: every score has a visible factor breakdown + plain-language rationale).
- **The AI proposes, the PM decides** (rule 5, D-013). The AI writes scores (logged) and *proposed* bands; confirmed priorities are PM decisions (`prio_decision`, append-only, audited). A band that would change at a later checkpoint becomes a `prio_proposal` with its factor-level cause.
- **Links feed in, but never penalise** (D-048): synergy/enables bundles share one band; conflicts between two Musts raise a "choose jointly" flag; enablers earn credit.
- **The PM's ladder rung matters** (`def_choice`, else the AI's recommended rung): it changes effort and confidence in the stored score.

## Score `prio-v1`

Reuses the score-v3 machinery (`pipeline/scoring.py`): weighted factors 0–1 → points, renormalised over the available factors (missing ones shown as evidence gaps), × confidence multiplier, + modifiers, bands **Must ≥ 60 · Should ≥ 45 · Could** (default thresholds). Weights and thresholds are PM-editable and versioned (`weights_version`, scheme `prio-v1`).

| Dimension | Factor | Weight | Computed from |
|---|---|---|---|
| Customer | `customer_voice` | 30 | area `metrics.by_line_market["<line>:<market>"]` vs. the in-scope comment base of that line × market (shrinkage + log curve as score-v3); markets without own comments borrow ×0.5 and are capped (D-038) |
| Customer | `satisfaction_gap` | 15 | `study:` evidence → `study_metric.z_within_column` for the line's derivatives × market: −z/2 (improve); +z/2 for `keep_strength` (must-not-lose) |
| Business | `competitive_gap` | 15 | numeric baseline vs. cited threshold in the metric direction, clip(gap / 20 %); fallback: tier-weighted `competes_with` evidence on the requirement's themes |
| Business | `market_weight` | 10 | 0.75 × BMW volume share (labelled *stylized, Q-015*) + 0.25 × public trend (D-046); BMW-vs-public conflicts flagged, never corrected |
| Business | `portfolio_leverage` | 10 | spread over lines × markets + enabler credit (Σ enables strength/3 × enabled base score/100, cap 0.5) |
| Future | `future_relevance` | 20 | horizon (launch 0.5 / today 0.2) + dated trend evidence (≤ 0.3) + Kano-drift proxy (0.2) |

- **Confidence multiplier** (E1 1.0 / E2 .92 / E3 .75 / E4 .5) from the ladder's basis mix (cited 1, projected .7, assumption .5, gap .3), own-market evidence and comment volume.
- **Effort** S 0 / M −3 / L −6 from `decision_type` and the number of resources the aspects draw on; the chosen rung shifts it (threshold −1 step, stretch +1, baseline = S).
- **Market fit** from the gate: pass +2 / warn −5 / fail −10.

## Links

- **Bundles:** connected components over non-removed `synergy` / `enables` links with strength ≥ 2. Members keep their own score; within a line × market the bundle gets **one proposed band = its strongest member's** (`bundle_note`).
- **Conflict flag:** `conflicts` or `competes_for` with strength ≥ 2 where both ends are Must in the same line × market → `choose_jointly {via}`. Strength 1 = info only. No score penalty.
- **What-if:** `GET /api/prioritize/what-if` recomputes one target for another rung without storing; lists linked partners exposed ("+1 exposure via mass").

## Gate (`gate` stage)

Brand / segment fit per requirement, market / feasibility per target — reuses the `pipeline/fit.py` prompts and luna → sol re-check flow, adapted to `def_requirement`. Brand `fail` blocks a PM approve unless overridden with a rationale (D-008); feasibility is non-blocking context (D-030). cp2 re-checks only new or re-versioned requirements. ≈ $0.40 at cp1, ≈ $0.10 at cp2.

## Checkpoints

`prioritize` is a `checkpoint_run` (cp2 builds on cp1). Tracks `prio:<key>|<line>|<market>` (weight = score). At cp2 a band that differs from the PM-confirmed band (or the cp1 proposal) → `prio_proposal` with factor deltas and a cause category: `new_fact` (spec track moved), `area_strengthened`, `market_trend`, `link_changed`, `pm_rung`.

## Tables

```sql
prio_score(id PK, run_id, req_key, req_version, line, market, score, base, band, rank, confidence_json,
           breakdown_json, modifiers_json, flags_json, bundle_id, rung, rationale, created_at,
           UNIQUE(run_id, req_key, line, market))
prio_bundle(id PK, run_id, bundle_id, keys_json, relations_json, band_by_target_json)
prio_fit(id PK, run_id, req_key, req_version, line, market, check_type, result, rationale, checked_by, model, created_at)
prio_decision(id PK, req_key, line, market, priority, rationale, actor, checkpoint_id, created_at)        -- append-only, PM
prio_proposal(id PK, run_id, req_key, line, market, old_band, proposed_band, cause, factor_delta_json,
              status, decided_by, decided_at, decision_rationale, created_at)
```

## API (`backend/src/api/routers/prioritize.py`)

```
GET  /api/prioritize?cp=   → { checkpoint, ready, runs: {prioritize, gate}, weights, labels: {market_weight: "stylized (Q-015)"},
       lines, markets, targets: [Target], bundles: [{id, keys, band_by_target}], proposals: [Proposal], summary: {by_band, by_market} }
Target = { key, title, domain, zones, area_key, line, market, score, base, band, confirmed: {priority, actor, at, rationale}|null,
           rank, state, confidence: {level, mult, basis_mix}, factors: [{key, dimension, value, weight, points, explanation, available}],
           modifiers: [{key, points, why}], gates: {brand, segment, market, feasibility}, bundle_id, flags: [str], rung: {chosen, recommended},
           rationale, prev: {score, band}|null }
GET  /api/prioritize/target/{key}?line=&market=&cp=   → Target + history across checkpoints + evidence summary
GET  /api/prioritize/what-if?key=&line=&market=&level=&cp=
POST /api/prioritize/decision  {key, line, market, priority, rationale, actor}
POST /api/prioritize/proposal/{id}  {verdict: accept|reject, rationale, actor}
```

## Page 4 (`/prioritize`)

Continues page 3's object story in the same canvas: the requirement pins on the car become the priority view (see DESIGN.md "Prioritize (page 4)"). Market switcher, factor waterfall per target (grouped Customer / Business / Future → confidence → modifiers), bundle halos, "choose jointly" flags, JAN → JUL proposals with causes, PM confirm flow.

## As built (additive to the contract above)

Code: `backend/src/bmw_req/prioritize/` (`__init__.py` schema, `score.py` stage `prioritize`, `gate.py` stage `gate`, `run.py` CLI),
`backend/src/api/routers/prioritize.py`, tests `backend/tests/test_prioritize.py`. Shared helpers factored out of score-v3 without changing it:
`scoring.voice_curve / shrink / renormalised / cap_unobserved / align_basic`, `fit.luna_then_sol`.

```
uv run python -m bmw_req.prioritize.run --checkpoint cp1                     gate, then prioritize
uv run python -m bmw_req.prioritize.run --checkpoint cp1 --stage prioritize  re-score only (free)
uv run python -m bmw_req.prioritize.run --checkpoint cp1 --stage gate --pilot 5 [--only rq:… …]   print, store nothing
uv run python -m bmw_req.prioritize.run --checkpoint cp1 --report            bands per market + top-5 with factors
```

- **Weights and bands** live in `weights_version` as `{"scheme": "prio-v1", "weights": {six factors}, "bands": {Must,
  Should}}` (rows without `bands` = 60 / 45); score-v3's `current_weights` and process.py's `_current_weights` skip rows with
  a `scheme`. `score.py` reads both from the current version (`current_config` / read-only `stored_config`; `band_for`
  replaces the hard-coded 60 / 45 in the prio-v1 path, `score_all(…, bands=)`). Validation: exactly the six factors, each
  ≥ 0, sum > 0; 0 < Should < Must ≤ 100. Versions are numbered WITHIN the scheme (v1 = the system default row;
  `weights_version.id` is shared with score-v3 and is returned as `id`).
  - `POST /api/prioritize/weights {factors, bands, rationale, actor?}` (legacy `weights` = `factors`; `bands` omitted =
    keep) → new version + human audit `change_weights` (old / new factors + bands, rationale) → automatic re-score of
    every checkpoint cp1 → cp2. Returns `{weights_version (scheme number), id, factors, bands, rescore}`.
  - `GET /api/prioritize/weights/history?limit=` → `{current, defaults, history: [{version, id, factors, bands, actor, at,
    rationale, default}]}`. Revert = load an earlier version and save it again (a new version).
  - `POST /api/prioritize/preview {factors, bands, cp, line?, market?}` → every target re-scored IN MEMORY through the same
    `score_all` path (no writes): `targets[] {key, line, market, score, band, prev_score, prev_band (stored latest run),
    confirmed}`, `summary {targets, by_band, changes, moves {"Must→Should": n}, decisions_affected}`, `changes[]`,
    `decisions_affected[]` (PM decisions whose band the new AI band would contradict → would get a proposal).
  - GET `/api/prioritize` `weights` adds `id, actor, at, rationale, default, defaults {factors, bands}` and a `rescore`
    status (`{state: idle | running, seq, done, last, error}`; also `GET /api/prioritize/rescore`).
  - Page 4: "Weights vN" pill in the HUD controls opens a panel on the far left under the HUD (where the matrix goes; one
    of the two at a time): grouped sliders Customer / Business (market weight "stylized (Q-015)") / Future with each
    factor's and group's share, Must / Should threshold sliders (the skyline planes follow), debounced (250 ms) preview →
    the skyline columns morph to the previewed scores / AI bands (PM bands stay), "n band changes", moves, "PM decisions
    → proposal"; Save needs a rationale; Reset; last 6 versions (click = load). HUD micro line: "Scoring formula prio-v1 ·
    weights vN (default, D-050 | by <actor>, <date>)".
- **Automatic re-score (`backend/src/bmw_req/prioritize/auto.py`, worker `backend/src/api/rescore.py`):** after `POST /decision` and
  `POST /proposal/{id}` (re-score the LATER checkpoints only: inputs at the decision's own checkpoint did not change),
  `POST /weights` (all checkpoints), `POST /api/definition/choice` (from the choice's checkpoint, or all) and
  `POST /api/definition/link-review` (all: link reviews apply everywhere). The POST commits, then queues and returns
  `rescore: "queued"` (`"none"` when nothing is later). One daemon worker thread on its own database connection; requests
  during a run coalesce into one follow-up pass from the earliest requested checkpoint; ~0.1 s per checkpoint. Only
  checkpoints that already have a prioritize run are re-run; each is a normal new `checkpoint_run` (stats `trigger:
  "auto:<trigger>"`) and logs `audit_event` actor `structure.prioritize`, action `auto_rescore {trigger, from, runs}`.
  `PRIO_AUTO_RESCORE=thread | sync | off` (default `off` under pytest; tests set `sync`). The page polls
  `/api/prioritize/rescore` until idle, then refetches page 4 (all checkpoints); HUD shows "re-scoring…".
- **Cause `weights_changed`:** when the weights version differs from the previous run at the same checkpoint, the run also
  scores with the old weights; a proposal whose band only the weights moved gets cause `weights_changed` (after `pm_rung`).
- **Checkpoint visibility (fix):** a run supersedes only open proposals of ITS checkpoint; a decision supersedes open
  proposals at checkpoints where it is visible (its own and later); `GET /api/prioritize?cp=` lists proposals of the current
  run plus still-open ones from runs at visible checkpoints (cp1 never shows cp2's), one open proposal per target (newest);
  target detail filters proposals and decisions the same way; "previous score" rows come from visible checkpoints only.
- **Rejected proposals don't nag:** a proposal the PM rejected (after their latest decision on the target) is not re-proposed
  with the same old → new band until the score has moved ≥ 5 points.
- **Rise / Fall (PM request 2026-10-11, frontend only):** a challenged decision is split by direction (proposed band above the
  PM's = up, green; below = down, big red) on the skyline, HUD, inspector banner, matrix, list and page 5; see DESIGN.md →
  Rise/Fall rule. It supersedes the white "!" marks below except in the weights preview. There is no sample mode: before the stage
  has run, page 4 says so and shows nothing (D-060).
- **Page 4 PM marks:** confirmed columns get a sweep-blue edge and a blue "M ✓" chip (base disc stays); a challenged
  decision (open proposal with `against: "pm"`) gets a white ring at the AI score and "! AI: Should ▼ · <cause>", pulsing
  once per checkpoint arrival; matrix cells ✓ / white "!" + proposed band; list rows "PM ✓" in blue, challenged first with
  "!". A compact HUD line "n of your decisions are challenged at JUL" lists them (requirement · line · market · your band →
  proposed · cause); a row opens the inspector. The inspector starts with "What you're deciding on" (statement, area,
  metric, the rung in use here with value and basis, ≤ 3 acceptance criteria, "View definition →"), shows bundle members as
  rows (target value, own score / band, "lifted to <band> by the bundle") and states the decision's scope (one requirement
  × line × market; bundle members keep their own decisions).
- **Customer voice:** area comments carry no severity, so each counts at score-v3's medium severity (share × 2/3 before
  the log curve). Comment base = in-scope extract-v4 comments visible at the checkpoint per line × market; < 30 → borrow.
- **Satisfaction gap:** study items = the requirement's `study:` ids ∪ its area themes' supporting / contradicting study
  edges, matched by item text to the line's derivatives × market.
- **Competitive gap:** numeric only when the rung has a numeric baseline AND a cited / projected threshold; otherwise the
  fallback (tier-weighted `competes_with` edges on the area's themes, sources in that market or global, /4). With no
  competitor evidence it counts 0 (not renormalised, as score-v3's competitive pressure). `factors[].method` =
  `numeric | fallback | none`; explanations start with "fallback (…)"; flags `competitive_fallback` / `competitive_none`.
- **Portfolio leverage:** spread = min(0.5, (targets − 1) / 6) + enabler credit (two passes: base without credit → credit).
- **Future relevance:** trends = requirement `trend_ids` ∪ theme `trend_for` edges in that market (0.1 each, ≤ 0.3); Kano
  drift 0.2 for performance / delighter requirements with competitor or trend evidence.
- **Confidence level:** E1 ≥ 20 own comments and (study or basis ≥ .7); E2 ≥ 10 comments, or ≥ 3 with study / basis ≥ .6,
  or study with basis ≥ .7; E3 ≥ 3 comments, study, basis ≥ .5 or define's `own_evidence`; else E4. Basis score =
  ½ chosen-rung basis + ½ mean over the rung's levels.
- **Effort:** keep_strength / package_variant S, change_design / add_feature / market_variant M, raise_capability L; +1 step
  when the aspects draw on ≥ 3 resources; then the rung shift.
- **Order of rules:** score → D-038 no-comment cap (own evidence = satisfaction gap AND competitive gap ≥ .5) → D-038 one
  band for Kano-basic needs → bundle band → choose-jointly flags → rationale. Rank within line × market = score order (a bundle-lifted band does not move a member up the ranking).
- **Flags** (page 4 parses `kind|arg|arg`): `brand_blocked` (brand fail, D-008), `brand_fail|warn`-style `brand_warn`,
  `segment_warn` / `segment_fail`, `gate_pending`, `borrowed_voice` (no comment base of its own, D-038), `no_comment_cap`,
  `basic_aligned`, `bundle_band|<band>`, `volume_conflict` (BMW file vs public), `competitive_fallback` / `competitive_none`,
  `choose_jointly|<via>|<partner key>`.
- **Payload shapes (match `frontend/src/lib/prioritize.ts`):** `weights = {scheme, version, factors, bands: {Must, Should}}`;
  `markets` = list; unavailable factors have `value: null, points: 0, available: false`; proposals' `factor_delta` =
  points per factor (`explain`, `against`, `score`, `prev_score` alongside; status may also be `superseded`); target detail
  `history[] = {checkpoint, label, run_id, score, band, rank, rung, rationale, confirmed}`, `evidence = {comments, study,
  research, options, insights, own_market, count, by_kind, trend_ids, factors}`; what-if = `{key, line, market, level,
  score, band, base, delta, modifiers, confidence, effort, rationale, before, exposures: [{key, title, via, relation,
  strength, band, note}], exposure_summary: ["+1 exposure via mass"]}`.
- **Agent-panel events** (`audit_event`, actor `structure.gate` / `structure.prioritize`): gate `start {requirements,
  to_check, carried}` → one `check {key, checked, to_check, brand, segments, markets, by, error}` per finished requirement
  → `finished {stats}`; prioritize `scored {targets, by_band, bundles, proposals, flags}`.
- **Gate:** `prio_fit` holds one brand / segment / market / feasibility row per target (brand is per requirement, segment
  per line, both repeated per target); `checked_by` = `luna | sol | carried:<…>`. Static instructions + portfolio reference
  first (prompt cache), then one requirement; sol re-checks brand / segment / market warn / fail at reasoning effort low.
- **Proposals:** reference band = the latest PM decision visible at the checkpoint, else the parent run's band; every
  re-score supersedes the target's open proposals at its checkpoint (status `open | accepted | rejected | superseded`). Accepting writes a
  `prio_decision` (audit `proposal_accepted` + `confirm_priority`); a direct decision supersedes open proposals.
- **Decision:** body adds optional `cp` and `override_brand`; a Must / Should on a brand-`fail` target needs
  `override_brand: true` (409 otherwise); actor falls back to `X-Actor`; rationale ≥ 5 chars.
- **Target** adds `version`, `own_band` (band before the bundle rule), `effort`, `gaps`, `confidence.{basis_score, comments,
  study}`, `factors[].{label, method}`; `gates` are objects `{result, rationale, checked_by}`. AI re-scores write
  `audit_event` rows (actor `structure.prioritize`, action `rescore`, entity `prio_target`, id `key|line|market`).
