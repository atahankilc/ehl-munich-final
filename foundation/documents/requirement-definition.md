# Requirement definition layer (D-048)

BMW's reference process step 3: *specification & quantification — measurable targets + acceptance criteria ("Range: 600 or 700 mi?", "Cooler for how many bottles?", "Seat ventilation: fast enough?"), grouped by Exterior / Interior / Powertrain / Driver assistance / …* It sits between the structure layer (D-043: areas = BMW step 2, "potential requirements, 0/1 implement?") and prioritization (step 4).

Page 3 of the app: **Definition** (`/definition`).

## Principles

- **Customer-experienced metrics only.** "Real-world highway range at 120 km/h", "seat feels cool within N min at 35 °C", "fits N × 0.75 l bottles upright". Never component specs (battery kWh, compressor, supplier) — BMW scope (challenge brief).
- **One primary metric per requirement** (D-038). Different-but-coupled metrics become *links*, not merges.
- **A target ladder, not one number.** Per car line × market: `baseline` (today's BMW) → `threshold` (competitive parity, must not fall below) → `target` (projected need at successor launch, D-012) → `stretch` (delighter). The AI *recommends* a level; the **PM chooses** (rationale, audited). AI never sets status (rule 5).
- **Every number has a basis:** `cited` (source ids, quote-verified), `projected` (assumption, names the trend it rests on), `assumption` (no evidence, reasoning given), `gap` (no data → open question / research task). Never invent a number to fill a gap.
- **Conditions follow markets** (D-011): acceptance criteria name the conditions the market's customers live in (heat soak for US-South/CN, −7 °C for EU winter, chauffeured rear use for CN).
- **Links between requirements** — the "roof of the House of Quality", at customer level: `conflicts`, `competes_for`, `enables`, `synergy`, each with a `via` resource (energy, mass, thermal, package, attention, aero, acoustic, compute — `definition/domains.py`). Links are AI *proposals*; the PM confirms or removes them.
- **Grouped by domain** (config in `definition/domains.py`): Exterior · Interior & comfort · Powertrain & charging · Chassis & dynamics · Driver assistance · Infotainment & digital · Variants & packages · Design & quality perception. Domain and car zones are derived deterministically from aspects, never by the LLM.
- **Checkpoints** (D-040/041): every stage is a `checkpoint_run`; cp2 builds on cp1, re-works only what changed (area moved, new benchmark visible, linked requirement changed) and records why (`change_note`, `recalibrates` edges, tracks).

## Pipeline

| Stage | Input | Output | Model |
|---|---|---|---|
| `benchmarks` (per source, cached; facts visible by the source's checkpoint) | research / web / reference items with numbers (option-list rows hold equipment presence, no numbers: `specify` reads them directly) | `spec_fact` rows | rule + luna (fast) |
| `define` | latest `areas` run + theme evidence (latest `contextualize`) | `def_requirement` — 1–3 per non-quality area | sol (smart) |
| `specify` | `define` run + `spec_fact` (by aspect, visible at cp) + study + options | `def_spec` — metric, acceptance criteria, ladder per line × market | sol |
| `couple` | `specify` run; candidate pairs = shared resource (`domains.shared_resources`) + same line | `def_link` | luna judge, sol for strong/conflict |

`uv run python -m bmw_req.definition.run --checkpoint cp1` runs define → specify → couple (benchmarks first if missing).

## Tables

```sql
spec_fact(id PK, source_item_id → source_item, aspect, attribute, entity, brand, model_code, market,
          value REAL, value_max REAL, unit,              -- value in the attribute's CANONICAL unit (miles→km, mph→km/h,
          raw_value REAL, raw_unit,                      --   hp→kW, cu ft→l, s/h→min); raw_* = the number as written
          cycle, condition, quote, quote_field,          -- quote_field: 'quote' | 'text' (which item field holds the quote)
          method, model, created_at,                     -- method: rule | luna
          UNIQUE(source_item_id, attribute, entity, market, cycle))
  -- attribute: controlled slug list ATTRIBUTES in definition/benchmarks.py (34 slugs: range_km, dc_peak_kw,
  -- charge_10_80_min, km_added_10min, screen_in, boot_l, rear_legroom_mm, wheelbase_mm, accel_0_100_s, hands_off_kmh,
  -- seat_massage_programs, fridge_l, fitment_pct, wtp_pct, want_pct, concern_pct, pp100, …), each with aspect, canonical
  -- unit and direction (higher|lower = better). Generic shares/scores (fitment_pct, wtp_pct, want_pct, concern_pct,
  -- satisfaction_pts, pp100) take their aspect from extraction / source_aspect.
  -- cycle: WLTP | CLTC | EPA | NEDC | real_world | null. Visibility = source_item.checkpoint (joined, never stored).
spec_fact_scan(source_item_id PK, attributes_found, method, model, created_at)   -- processed marker (rule|luna|skip)

def_requirement(id PK, key, version, run_id → checkpoint_run, parent_id → def_requirement, area_key,
                status,            -- proposed
                title, statement, domain, aspects_json, zones_json, lines_json, markets_json,
                decision_type, today_status, horizon, horizon_year, kano,
                evidence_ids_json, trend_ids_json, assumptions_json, change_note, model, created_at,
                UNIQUE(run_id, key))
  -- key: 'rq:<area-slug>:<n>' stable across checkpoints

def_spec(id PK, run_id, req_key, version, parent_id → def_spec,
         metric_json,      -- {name, unit, direction: higher|lower|binary, method, conditions}
         acceptance_json,  -- [{criterion, condition, pass}]  (≤ 4)
         ladder_json,      -- [{line, market, baseline: Level|null, threshold: Level, target: Level, stretch: Level|null,
                           --   recommended: threshold|target|stretch, rationale}]
         gaps_json,        -- [str] open questions / research tasks for missing numbers
         assumptions_json, fact_ids_json, change_note, model, created_at, UNIQUE(run_id, req_key))
  -- Level = {value: number|null, text: str, basis: cited|projected|assumption|gap, source_ids: [str], note: str}

def_link(id PK, run_id, a_key, b_key, relation,  -- conflicts | competes_for | enables | synergy
         via,              -- resource key from domains.RESOURCES
         strength INTEGER, -- 1 (weak) … 3 (strong)
         direction,        -- a_to_b | b_to_a | mutual   (enables is directional)
         rationale, method, model, created_at, UNIQUE(run_id, a_key, b_key, relation))

def_choice(id PK, req_key, line, market, level, rationale, actor, checkpoint_id, created_at)   -- append-only, PM
def_link_review(id PK, a_key, b_key, relation, verdict,  -- confirmed | removed | added
                via, strength, rationale, actor, checkpoint_id, created_at)                    -- append-only, PM
```

Every write by a stage → `structure.events.log` (actor `structure.<stage>`, feeds Agent panel + audit). PM writes → `audit_event` with actor_type `human`, before/after, rationale.

Tracks: `rq:<key>` (define; weight = area share), `spec:<key>` (specify; payload = recommended target per line×market so a moved bar shows as changed), `link:<a>|<b>|<relation>` (couple).

## API (`api/routers/definition.py`)

```
GET  /api/definition?cp=cp2
  → { checkpoint, ready: bool, runs: {define, specify, couple: {id, finished_at, stats}|null},
      domains: [{key, label, aspects}], resources: {key: description}, zones: ZONES,
      models: {"1 Series"|"5 Series"|"7 Series": {url|null, orientation, attribution, stand_in}},
      requirements: [Requirement], links: [Link], bundles: [{id, keys: [str], reason}] }

Requirement = { key, version, area_key, area_title, title, statement, domain, aspects, zones, lines, markets,
                decision_type, today_status, horizon, horizon_year, kano, state (track state), change_note,
                metric, acceptance, ladder (each rung may carry `choice: {level, rationale, actor, at}`), gaps,
                assumptions, evidence_count }
Link = { id, a, b, relation, via, strength, direction, rationale, state, review: {verdict, actor, rationale, at}|null }
bundles = connected components over links with strength ≥ 2 that are not removed (computed in the API)

GET  /api/definition/requirement/{key}?cp=   → Requirement + evidence [{id, kind, text, url, tier, published, relation, quote}],
                                              facts [spec_fact rows used], area {key, title, need}, history [versions across cps]
POST /api/definition/choice      {key, line, market, level, rationale, actor}  → 200 + audit_event
POST /api/definition/link-review {a, b, relation, verdict, via?, strength?, rationale, actor} → 200 + audit_event
```

**As built (additive to the contract above):**
- `def_requirement.targets_json` = `[{line, market, own_evidence, note, comments}]` — the line × market targets (≤ 4,
  own evidence first; a target without ≥ 3 comments / a study item for that car and market / market research is
  labelled `[assumption: …]` in its note). `markets_json` is the list of market codes, `lines_json` the lines.
- `def_spec` also stores `req_version` (the define version it specifies) and `input_ids_json` (the fact ids it was
  shown); `fact_ids_json` = the facts actually cited by a level. Metric direction `binary` allows text-only levels.
- Requirement payload adds `targets`, `status`, `spec_state`, `spec_moved` (up | down | mixed | text | null),
  `spec_change_note`, `trend_ids`; the detail adds `choices` (all PM choices for the key). GET adds `lost` (keys
  whose track was lost at this checkpoint); bundles add `conflict: bool`; links add `method` and `source` (ai | pm —
  PM-added links appear as links with state `added`).
- POST bodies accept optional `cp` (stored as `checkpoint_id`); `actor` falls back to the `X-Actor` header. `level`
  may be `baseline` (keep today's level). Link reviews store `a`/`b` sorted (the AI's pair order). Rationale ≥ 5
  chars (409 otherwise). Audit actions: `choose_level` (entity `def_requirement`, field `ladder:<line>:<market>`) and
  `link_confirmed` / `link_removed` / `link_added` (entity `def_link`, id `a|b|relation`).
- Spec tracks: state `strengthened` / `weakened` when the recommended bar moved up / down in the metric direction,
  `held` otherwise; `payload.moved` carries mixed / text-only moves. Track weight = number of cited levels.
- Code checks in specify also enforce: cited facts never mix test cycles; an unverified fact alone cannot make a
  level `cited`; values may match a fact's canonical or as-written number (miles) or a study mean / top-2 share (%).
- specify is benchmark-aware: the model sees `benchmarks.ATTRIBUTES` for the requirement's aspects with fact counts
  and the area's competitor/trend evidence; a non-survey attribute with facts MUST be the metric. Code checks add:
  the recommended rung must carry a value (else falls back to target/threshold), a threshold equal to the baseline
  without a citation becomes `gap`, cited facts must be in the metric's unit. `metric_flag` rejects rating shares on
  non-perception aspects and task shares on non-usability aspects → one repair re-ask per run.
- `--redo all|flagged` (specify): a new run at the same checkpoint on top of the latest one (lineage via parent_id +
  `recalibrates`), e.g. after a prompt change. cp1 history: run 22 (first), 23 (flagged repair), 25 (benchmark-aware redo).
- cp2 dirty rules (carry-forward first): define re-drafts only areas that are new / strengthened / weakened (held
  areas carry, even with new relink edges); specify re-asks new or changed requirements and those with new verified
  facts in the metric's own tangible unit (`moved_facts`); couple re-judges pairs touching changed requirements.
- couple candidates rank physical resources (mass, energy, thermal, aero, acoustic) first, cap attention/package-only
  pairs at 4 per requirement, and always add classic trade-offs from `domains.TENSIONS` (range × handling via mass …).
  `seat_comfort` draws on package + thermal only (was also mass/energy, which flooded range neighbours).
- LLM calls wait for Flex capacity (30 / 60 / 120 s) before the wrapper's standard-price fallback
  (`define.generate`); a failing batch is logged (`batch_failed`) and does not abort the run.

## How prioritization uses it (next layer)

- **Bundles:** strongly linked requirements are prioritized together; two Must requirements in `conflicts` get a "choose ladder levels jointly" flag.
- **Enabler credit:** a requirement that `enables` others earns portfolio leverage from what it unlocks.
- **What-if:** moving one rung highlights linked requirements with the `via` — a warning, never an automatic re-score.

## Page 3 (`/definition`)

Same canvas as Evidence/Structure (one mounted scene). Area diamonds split into requirement pins and fly onto the car, which rises at the centre; the scan volume sinks. Pins sit at their zone, coloured by domain (categorical hues, never blue — One Blue Rule). Selecting a requirement flies the camera to its zone (x-ray for interior zones), opens the inspector with the ladder (baseline / rival markers / threshold / target / stretch on one scale) and acceptance criteria, and draws its links as arcs through the car between zones — solid = synergy / enables, dashed = conflicts / competes_for — labelled with the `via`. Car line switcher (1 / 5 / 7 Series); domain filter. JAN → JUL: moved bars and new links pulse.
