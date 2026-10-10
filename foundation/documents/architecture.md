# Architecture & Workflow

**Status: DRAFT v3 — conceptual.** The workflow, entities and rules below are the agreed *concept* (D-005, D-008–D-013). The *technical* stack is decided (LangGraph, SQLite, sqlite-vec, no graph DB, Streamlit — D-015–D-020, see `tech-stack.md`). The data model below is still a logical model; which entities the demo builds is open (Q-017).

## Guiding principle

BMW decides at **portfolio level** — across shared platforms (CLAR, FAAR, Neue Klasse), plants and markets — not one car at a time. The data model is therefore **multi-brand, multi-derivative, multi-market, platform- and plant-aware from day one**. The 5 Series (G60 + China LWB G68) is the deepest worked example; F70 and G70 run through the same pipeline.

## End-to-end workflow

| # | Stage | Actor | Output |
|---|---|---|---|
| 1 | **Ingest** BMW data (feedback, study, sales, option lists) for all derivatives × markets | AI (autonomous) | `source_item` with provenance (file, sheet, row) and scope (derivative, market) |
| 2 | **Load reference data** — platforms, plants, brand positioning, segments, competitor models | AI-researched, **human-curated** | reference tables, each fact with source + date (`portfolio-reference.md`, `competitor-landscape.md` are the seeds) |
| 3 | **Enrich via web research agents** — competitors, sales, demand, reviews, trends, customer expectations (see `knowledge-base.md`) | AI (autonomous), PM can accept/reject sources | `source_item(kind=web)` with URL, date, publisher, trust tier, quote |
| 4 | **Extract signals** — classify, dedupe, cluster into findings: complaint / unmet need / must-not-lose delighter / competitor advantage / market trend / brand expectation | AI (autonomous) | `finding` with scope (derivative / platform / market / portfolio), linked sources, metrics |
| 5 | **Derive requirements** — customer-facing, actionable, measurable target + acceptance criteria; scoped to one or more derivatives × markets | AI proposes | `requirement` (status `proposed`) + `requirement_target` rows |
| 6 | **Fit & feasibility checks** per target (D-008, D-009): brand fit, segment fit, market fit, platform/plant feasibility | AI checks, flags explained | `fit_check` rows: pass / warn / fail + rationale + evidence |
| 7 | **Score & prioritize** — explainable factors incl. market volume and portfolio leverage (`requirement-model.md`) | AI computes, PM adjusts weights | score breakdown + rationale |
| 8 | **PM review** — approve / reject / edit / challenge / defer; override failed checks only with rationale | **Human (mandatory)** | status change + rationale |
| 9 | **Document & export** — requirement list, portfolio view, full audit trail | AI | JSON / XLSX export, audit timeline per requirement |

### It's a loop, not a one-shot (D-013)

The requirements process runs **~2 years**. Steps 1–9 repeat whenever something changes:

```
new ingest batch (feedback wave, study, sales update, competitor launch, web refresh)
  → re-extract / update findings (only affected ones)
  → future-need projection refresh
  → prioritization run (snapshot of all requirement-target scores & ranks)
  → change proposals (priority/status/content) → PM accepts/rejects
  → history: priority timeline per requirement with the "why" of each move
```

Triggers: `new_evidence`, `weight_change`, `pm_request`, `scheduled`. Evidence has a freshness decay; stale evidence loses weight unless re-confirmed.

### Markets are distinct customer groups (D-011)

Findings are segmented by market; every requirement-target (derivative × market) has its **own** score, priority and fit result. A `market_profile` (climate, usage, culture, infrastructure) feeds extraction, projection and fit checks. Cross-market conflicts are flagged with realization options (global / market variant / package).

### Future needs (D-012)

Step 5 includes **future-need projection**: predecessor findings + competitor trajectory + trends + market profile → need at successor SOP, with horizon (`today` / `at_successor_launch`) and Kano class + expected drift.

**Mandatory human gates:** final status of every requirement; overriding a failed brand-fit or feasibility check; accepting curated reference data (platform/plant facts). Optional gates: accepting web sources, merging/splitting findings, changing weights.

## Core data model (draft)

### Reference layer (portfolio)
```
brand(id, name, group, positioning, core_values[], guardrails_json, source_ids[])
segment(id, name, e.g. premium_compact | upper_mid | luxury, description)
platform(id e.g. CLAR | FAAR | NK, owner_brand_group, powertrains_supported[], introduced, phase_out, successor_platform_id, source_ids[])
vehicle_model(id e.g. G60, brand_id, line "5 Series", body, segment_id, platform_id, generation,
              sop, eop_planned, powertrains[], is_bmw_group, market_variants[])   -- BMW + competitors in one table
market(code EU | US | CN | RoW, countries[])
market_profile(market_code, climate, usage_patterns, cultural_expectations, infrastructure, powertrain_mix, source_ids[], valid_from)
plant(id, name, city, country, platforms_supported[], powertrains_supported[], nk_ready_from, capacity_note, source_ids[])
production(vehicle_model_id, plant_id, market_variant e.g. "G68 LWB", markets_served[], since, until)
sales(vehicle_model_id, market_code, year, units, is_forecast, source_id)
```

### Evidence layer
```
source_item(id, kind[feedback|study|sales|option_list|web|reference], trust_tier[T1..T3],
            vehicle_model_id?, market_code?, platform_id?, ref, url?, published_at?, retrieved_at,
            text, quote, meta_json)
finding(id, type, title, summary, scope_level[derivative|platform|market|portfolio],
        metrics_json, created_by, created_at)
finding_scope(finding_id, vehicle_model_id?, market_code?, platform_id?)
finding_source(finding_id, source_item_id, quote, relation[supports|contradicts])
```

### Decision layer
```
requirement(id "REQ-0001", title, description, category, target_metric, acceptance_criteria,
            horizon[today|at_successor_launch], kano_class[basic|performance|delighter], kano_drift,
            evidence_level, assumptions, uncertainties, conflicting_evidence,
            status, version)                                   -- content versioned; old versions kept
requirement_target(requirement_id, vehicle_model_id, market_code,
                   realization[carry_over|platform_wide|derivative_specific|market_variant|package],
                   score, score_breakdown_json, priority, rationale)   -- per-market priority (D-011)
requirement_finding(requirement_id, finding_id, relation[supports|contradicts])
fit_check(id, requirement_id, vehicle_model_id, market_code, check[brand|segment|market|feasibility],
          result[pass|warn|fail], rationale, evidence_source_ids[], checked_by, checked_at)
audit_event(id, ts, actor_type[ai|human|system], actor_id, action, entity_type, entity_id,
            field, old_value, new_value, rationale, model, prompt_ref)   -- append-only
```

### Continuity layer (D-013)
```
ingest_batch(id, ts, kind[feedback_wave|study|sales|competitor_event|web_refresh], description, source_ids[])
prioritization_run(id, ts, trigger[new_evidence|weight_change|pm_request|scheduled], ingest_batch_id?,
                   weights_version, model, initiated_by)
score_snapshot(run_id, requirement_id, vehicle_model_id, market_code, score, breakdown_json, rank, priority)
change_proposal(id, run_id, requirement_id, target?, field, old_value, proposed_value, reason,
                evidence_delta_json, status[open|accepted|rejected], decided_by, decided_at, decision_rationale)
weights_version(id, weights_json, created_by, created_at, rationale)
llm_usage(id, ts, job, model, input_tokens, cached_tokens, output_tokens, search_calls, cost_usd)   -- budget tracking (D-010)
```

Requirement IDs are global (`REQ-0001`); scope lives in `requirement_target`, so one requirement can apply to several derivatives/markets (e.g. an infotainment UX fix across all CLAR cars).

## Audit trail rules

- Append-only: no UPDATE/DELETE on `audit_event`.
- Every mutation of requirement content, targets, score, priority, evidence links, fit checks or status → one event (who/what, when, before/after, rationale).
- AI events record model name + prompt/agent version; web research events record queries and URLs.
- Access events (view/export) logged as well.

## Key UI views (planned)

- **Portfolio matrix** — derivatives × markets, with platform and plant, sales trend, top findings, requirement count.
- **Requirement detail** — evidence chain (sources → findings → requirement), fit checks, score breakdown, audit timeline, approve/reject/edit/challenge.
- **Competitor view** — per segment × market: who sells what, strengths, gaps vs. BMW.
- **Ranked backlog** — per market (EU / US / CN side by side), adjustable weights, visible re-ranking diff.
- **Priority history** — timeline per requirement across prioritization runs, each move annotated with its cause (new evidence, weight change, PM decision).
- **Change inbox** — open AI change proposals after a new ingest batch; PM accepts/rejects with rationale.
- **Market conflict view** — requirements whose priority diverges strongly between markets, with realization options.
