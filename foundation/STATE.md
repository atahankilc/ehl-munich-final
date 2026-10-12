# Project State

_Last updated: 2026-10-13_

## Current phase

**Phase 3 — Post-hackathon (from 2026-10-11).** The hackathon is over; Atahan continues the project solo to improve it.
Demo-first shortcuts (AGENTS rule 18) are no longer the main constraint; rule 1 (confidential BMW data) still applies.

The app (SharkSight) as of 2026-10-12:
- **Pages:** Evidence → Structure → Definition → Prioritize → Document (the 3D workflow), plus AI agents and Audit (full-screen, D-055/D-056).
- **Pipeline:** checkpoint pipeline only (D-040 ff.); the wave pipeline is retired (D-057/D-058). Every stage has run at JAN 26 and JUL 26: acquire, classify, cluster, contextualize, areas, define, specify, couple, gate, prioritize.
- **Data:** 12,370 source items (10,128 verbatims, 1,369 research / web / reference items), 15,440 classified signals; 76 (JAN) / 80 (JUL) requirements; 252 / 259 prioritized line × market targets; 2,868 audit events; $11.69 OpenAI spend.
- **Stack:** PostgreSQL 17 + pgvector in Docker (D-059; P0–P3 done), FastAPI + React/three.js, Docker profiles (D-053), adjustable budget + per-agent settings (D-054/D-055), no sample data (D-060).

_Hackathon (Phase 2, 2026-10-10):_ the first demo (simulated waves, Streamlit) has since been fully replaced; its records were pruned 2026-10-13 (git history keeps them).

## Team & logistics (Q-007 resolved 2026-10-11)

| Item | Value |
|---|---|
| Team | Atahan, solo (post-hackathon) |
| PM in the app | Atahan |
| Deadline / judging | none — hackathon over |

## Done

Post-hackathon (2026-10-11 / 12):
- Repo cleanup + monorepo layout `backend/` / `frontend/` (D-052); run profiles + containers (D-053).
- Adjustable budget + API key in the app (D-054); AI agents page as the source of truth for models, efforts, caps (D-055); Audit page per checkpoint (D-055); full-screen 2D pages (D-056).
- Wave pipeline retired and its tables dropped (D-057, D-058); LangGraph removed.
- PostgreSQL 17 + pgvector (D-059): migrations, compatibility layer, data copied and verified (99 API answers identical), timestamptz, exact vector search in SQL, restricted app role, SQLite removed.
- No sample data anywhere in the app (D-060).

Hackathon:
- Challenge analyzed; all BMW data profiled and re-verified (`documents/data-inventory.md`).
- Foundation, `AGENTS.md`, `CLAUDE.md` created.
- BMW mentor input recorded (D-011 markets differ, D-012 future needs, D-013 continuous re-prioritization). BMW support recommended the annual report → `documents/bmw-annual-report-2025.md`.
- Q-001/002/003 answered by Atahan → D-005 (portfolio-level, 5 Series deepest), D-006 (OpenAI), D-007 (web knowledge base), D-008 (brand fit gate), D-009 (plant/platform feasibility).
- Web research seeds written and fact-checked:
  - `portfolio-reference.md`: platforms, 14 vehicle plants + 3 CKD sites, BMW sales 2024–H1 2026, primary-sourced from the annual report where possible.
  - `competitor-landscape.md`: competitors, trends, expectations, brand-fit guardrails.

## In progress

Nothing running.

## How to run

- **Database first:** `make db`, then `make migrate` (PostgreSQL in Docker, 127.0.0.1:5433, D-059). Back up with `make backup` (`pg_dump` → `data/backups/`); `make testdata` refreshes the real-data copy the API tests clone.
- **PM app:** production `make serve` or `make up` (container) → http://127.0.0.1:8600; development `make api` + `make dev` or `make up-dev` → http://127.0.0.1:5173. Only one at a time (same port, same database). All `uv run …` commands run from `backend/`.
- **Pipeline stages:** `uv run python -m bmw_req.structure.run_all`, `… -m bmw_req.definition.run --checkpoint cp1`, `… -m bmw_req.prioritize.run --checkpoint cp1` (then `cp2`); spend is guarded by the limits and agent settings on the AI agents page.
- **Cloud (Render + Neon, D-063):** `deploy/render/load-data.sh '<neon owner url>'` once, then Render → New → Blueprint → this repo (secrets: `ACCESS_KEY`, `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `OPENAI_API_KEY`); guide `deploy/README.md`.
- **3D models:** `data/models/{f70,g60,g70}.glb` (git-ignored, Q-025); without them a placeholder car renders.
- `data/backups/` holds the `pg_dump` backups (no SQLite files remain, 2026-10-12).

## Next up (suggested order)

1. **Automatic checks:** CI (GitHub workflow: pytest on a Postgres service + frontend typecheck) and a Python linter; fix the 3 lint findings that predate the cleanup (`run_all.py`, `prioritize/score.py`).
2. **AI output quality:** the weakest judged dimensions were "measurable" and "evidence-grounded"; terse audit text for the prioritize stage ("scored", "auto rescore").
3. **Login / roles for people** before anyone else uses the app.
4. **Open with BMW / Atahan:** Q-005, Q-006, Q-015, Q-016; sign-off of the brand guardrails (D-031), which gate approval.

## Budget (OpenAI — limits adjustable in the app, D-054; was $100 total, D-014)

| Item | Value |
|---|---|
| Spent to date | **$11.69** (2026-10-12, from `llm_usage`; includes the retired hackathon pipeline). Source of truth: `llm_usage` / AI agents page |
| Ask before spending / stop (app settings, D-054) | $45 / $90 (defaults; Atahan changes them on the AI agents page) |
| OpenAI project hard limit | $95 (to set by Atahan, + $45 alert) |

## Risks / watch-outs

- Local anaconda Python 3.9 has a broken pandas/numpy → use `uv venv --python 3.12`.
- Option lists are German-market only — the US/CN equipment baseline is an assumption.
- Plant capacity/flexibility is rarely public → feasibility checks need explicit assumptions (Q-011).
- BMW says engineering is out of scope → keep feasibility framed as a filter (Q-010).
- BMW data must never be committed or sent anywhere except OpenAI (AGENTS rule 1).
- Public sales are only in model-series pairs, with no regional per-model figures. Model-level market volume relies on BMW's `sales_volumes.xlsx`, which looks stylized and conflicts with public China data (Q-015).
- Markets without own comments (CN) or very few (G70 EU) score on borrowed customer voice at half weight (D-038, prio-v1).
- Feedback data has no dates → the process runs on two real-date checkpoints (D-040); continuous intake is future work (`documents/future-work.md`).
- China-built i5 (G68 BEV) reportedly ended Jul 2026 (insider rumour, unconfirmed by BMW as of 2026-10-10) — affects 5 Series China powertrain assumptions.
- X5/7 Series successors: BMW calls them NK models, trade press says the platform is CLAR-derived (`bmw-annual-report-2025.md` §4). This matters for the G70 successor.

## Session log

_Earlier entries (hackathon, retired wave pipeline and Streamlit) pruned 2026-10-13; see git history._

- 2026-10-11 — D-040: two real-date checkpoints (31 Jan / 31 Jul 2026) replace simulated waves. 8 research agents → `research/checkpoints/` (821 cited items, 299 Jan↔Jul pairs); Checkpoint Atlas as a local page (`research/checkpoints/atlas.html`; Atahan wants no published artifacts). Gaps → Q-026. Next: Atahan leads classification → clustering → contextualization → elicitation on the new periods.
- 2026-10-11 — D-041: checkpoint lineage (cp2 builds on cp1, tracks new/held/strengthened/weakened/lost), research imported (1,028 items after China round 2), 10,128 comments embedded ($0.009) into a fixed 3D galaxy, old screens deleted, new black "track-while-scan" frontend with the Scan screen and bottom-right sweep control.
- 2026-10-11 — D-042: one 5 Series sector (G68 = LWB China part), research ring moved inside, car-specific public research on study/options/sales rings so all rings change at JUL; per-type colours, inspectors on every ring element, no auto-rotation, arrival sweep. DESIGN.md rewritten for track-while-scan.
- 2026-10-11 — Raw data page (parallel session): layer focus lift/fade, per-colour readout, cross-type filters (scan/filter.ts), checkpoint dial redesign.
- 2026-10-11 — D-043: structure & context pipeline (extract-v4 A/B-tested, portfolio-wide incremental clustering, contextualize with evidence graph + RAG, requirement areas), page 2 "Structure" with comment→cluster morph and live agent panel; full run in progress.
- 2026-10-11 — Scan filter bar always shown with a fold/unfold toggle (unused chips hide, chips in use stay); new filters: comment length, research topic + fact type, option availability.
- 2026-10-11 — Bottom-left dock: Guide and Agent are now pills like the Audit button; one panel open at a time.
- 2026-10-11 — D-045: audit trail separated by checkpoint; pre-rebuild history hidden by default (toggle in Everything), nothing deleted.
- 2026-10-11 — Inspector (top-right) moved to the frameless feathered field like the audit trail and dock; findings inside hang off a hairline rail. Hover card and filter value list too; all panels share a `--field` token (cool near-black + faint top glow) so they separate from the volume.
- 2026-10-11 — Renamed the app to "SharkSight": one-line geometric shark-head logo + favicon, wordmark beside the page tabs; top-bar pills 28 → 32px (D-044). No LLM spend.
- 2026-10-11 — Sales verification (research/sales-verification.md): ingest correct (36/36); BMW market split implausible (G60 US ~3× public, G68 CN −21–39 %, 5 Series total matches); ~9 duplicated research claims; Q-015 note added. Recommendation: BMW sales only as a labelled relative weight, never as a trend.
- 2026-10-11 — Scan: the "Research" ring name was missing from the front label column (Research · Study · Options · Sales). Cause: under dev StrictMode the first drei `<Html>` in `Rings` mounts empty; a blank placeholder `<Html />` now takes that hit. The research time ring is rotated so its JUL 26 → JUL 25 gap faces the viewer like the car rings, with the label in that gap (UI only, `layout.ts` TIME_START). No LLM spend.
- 2026-10-11 — Scan: car names (1/5/7 Series) now follow the focus. When an item is selected, its car line rises with its layer and the other names sink and fade (`LabelLift` in Scene.tsx). No LLM spend.
- 2026-10-11 — Scan/Structure navigation: Spread slider (1–4×, layout scales around a fixed camera, marks keep their size) plus fly controls (W/S/A/D/Q/E, hold buttons, reset), zoom-to-cursor and right-drag pan (`web/src/screens/scan/navigate.tsx`).
- 2026-10-11 — D-049: Evidence inspector shows sources only; signals and theme links moved to Structure, with a "View in Structure" link (comment → its cluster). Checked in the browser.
- 2026-10-11 — Structure Agent panel: hovering or focusing a stage (Classify / Cluster / Context / Areas) shows a two-line explanation in place of the feed (`AgentPanel.tsx` EXPLAIN). No LLM spend.
- 2026-10-11 — Structure page steps through the pipeline (frontend only, `structure/stages.ts`): funnel names + ‹ › (or [ / ]) pick Classify / Cluster / Context / Areas. Classify keeps comments in place and lights up the ones with signals; Cluster shows clusters named by top aspect; Context adds themes + arcs; Areas adds the diamonds. No LLM spend.
- 2026-10-11 — Definition page: the requirement list moved behind a "Requirements" pill next to Audit (top-right pill row `.tr-pills`); one of the two panels is open at a time (`components/topPanel.ts`). Picking a pin opens it; closing it or opening Audit deselects. No LLM spend.
- 2026-10-11 — D-046/D-047 (session ed): market context + backfill on areas runs 13/16; relink cp1 → run 17, cp2 → run 18 (runs 12/15 superseded), web + reference items in the evidence pool. $0.06.
- 2026-10-11 — D-048 requirement definition: contract, domains/zones/resources config, cited benchmark table, define/specify/couple stages, `/api/definition`, page 3 with stepper (diamonds rise → split → specified → linked → on the car), Agent panel for page 3. cp1 specify re-run and cp2 in progress. `tests/test_api.py` has 3 legacy failures (old wave tables, no change proposals in the DB), unrelated.
- 2026-10-11 — Page 2 → 3 transition (session 4e): the separate "Areas" stage on page 3 is gone; arrival is one move — the page-2 diamonds rise, swell and burst into their requirements in a sweep around the ring, which settle into domain groups (Drafted = step 1). Leaving for page 2 folds them back into the diamonds before they sink. Funnel's Requirements cell notes "from N areas". Frontend only (`definition/stages.ts`, `StageLayer.tsx`, funnel, guide). No LLM spend.
- 2026-10-11 — Page 3 story moves (rise/split/fly, car rise, volume sink, arrival play) now ignore `prefers-reduced-motion`, like page 2's morph already did; only decorative CSS pulses honour it. (Atahan's Mac has Reduce motion on, so page 3 had been jumping to the last stage.)
- 2026-10-11 — Page 3 plane view centred on screen (camera target x 0, was −0.55 on wide screens), like pages 1 and 2. The selected-zone shift on the car (clear of the inspector) stays.
- 2026-10-11 — Page 2 → 3 arrival is now a quick run-through to "On the car" (holds 1.5 s / 0.55 s / 0.9 s, 3D moves at double speed via `view.fast`), like the page 1 → 2 morph; stepping back with ‹ or [ peels the layers off one at a time at full length (reverse moves now as slow as forward).
- 2026-10-11 — Page 3 "On the car": link arcs now end on their actual pins (each frame both ends re-anchor on the pin's screen centre, unprojected at the zone's depth; pins carry `data-req`), neighbours get a low bridge instead of a tall loop, the same-zone ±0.3 offset is gone, arrow cones smaller. Checked in the browser at cp1.
- 2026-10-11 — Page 4: opening a priority or the priorities panel no longer slides the car/ring left; the skyline camera stays centred (PanelShift removed from `prioritize/Skyline.tsx`).
- 2026-10-11 — Page 4 Matrix panel moved to the far left (left: edge, 560px wide, market columns 64px) so the centred car stays clear; the dock's open Guide/Agent panel folds away while the matrix is open (pills stay). `prioritize/prioritize.css`. Checked in the browser.
- 2026-10-11 — Page 4 top-left now starts at the top edge like pages 1–3: only Must/Should/Could sit in the first row, the open-item counts (proposals, choose jointly, blocked, markets disagree) moved to a compact line under them (`.pstats`). The matrix hangs 14px under the HUD via `--phud-bottom` (ResizeObserver in PrioritizeHud) instead of a fixed top. Checked in the browser.
- 2026-10-11 — D-050/D-051: prioritization layer (gate $0.18 + deterministic prio-v1, cp1 run 33 / cp2 run 35, 39 JUL proposals), page 4 skyline + matrix + waterfall, editable weights/bands with preview, auto re-score, challenged-decision marks, page 5 Document with MD/CSV export. Total spend ≈ $11.9. Open: China targets thin (no CN comments; proposal to target CN from CN study/research as assumptions), brand guardrail too strict on luxury comfort, competitive gap only via fallback.
- 2026-10-11 — Audit: page-4 rows now say what the PM decided — `confirm_priority` → "PM set Must for <requirement> (1 Series · EU), AI had Should — “reason”", proposal accept/reject name the band move and target, weight changes name the version (`api/routers/audit_feed.py` `_prio_summary`); these rows are tagged with their checkpoint. API restarted (nothing was running).
- 2026-10-11 — Repo cleanup + monorepo layout (D-052): legacy Streamlit app (`app.py`, `ui/`, `.streamlit/`, `streamlit` dep) removed; unused npm deps `cmdk`, `motion` removed; `httpx`, `numpy` declared, `pitch` dependency group; `backend/` (src/bmw_req, src/api, tests, scripts, pyproject, uv.lock), `frontend/` (was `web/`), `docs/pitch/`; root `Makefile`. Tests unchanged (122 pass, same 3 pre-existing `test_api` failures).
- 2026-10-11 — Run profiles + containers (D-053): `APP_ENV` development/production in `backend/src/api/main.py` (env `API_HOST`/`API_PORT`/`API_RELOAD`), Vite reads `API_URL`/`VITE_HOST`; `Dockerfile` (targets dev/prod), `compose.yaml` (profiles dev/prod, 127.0.0.1 only, `data/` mounted), allowlist `.dockerignore`; Makefile `serve`/`up`/`up-dev`/`down`/`logs`. Verified: image has no raw data/DB/.env; prod healthy, dev reloads on save. Prod container left running (`restart: unless-stopped`).
- 2026-10-11 — Post-hackathon (Phase 3, Q-007/Q-008 closed). Adjustable budget + API key in the app (D-054): `bmw_req.app_settings` (`data/settings.json`, 0600), guard asks before spending above a limit (terminal y/N, `BUDGET_CONFIRM=1`, `budget.approved()` for API jobs) and stops at a limit; `/api/settings`; Audit → Usage "OpenAI API key" + "Spend limits"; block-non-demo threshold dropped. 135 tests (+10), same 3 old `test_api` failures. Old-pipeline dependency map done (agent) — basis for retiring waves (next).
- 2026-10-11 — AI agents page + Audit page (D-055): agent registry (`bmw_req.llm.agents`, 22 agents), per-agent model / effort / on-off / cap + tiers + custom priced models applied on every call, `/api/agents`; `/agents` sheet (key, limits, tiers, per-pipeline tables, models, usage details) and `/audit` sheet (one checkpoint at a time + "No checkpoint", area + who filters); audit panel = quick look with link. 151 tests (+16), same 3 old failures; checked in the browser. Future: continuous intake instead of checkpoints (Q-027).
- 2026-10-11 — Full-screen 2D pages (D-056): Document, AI agents, Audit no longer drawn over the 3D scene; canvas hidden + paused (`frameloop="never"`, stays mounted), timeline hidden there, Document got its own checkpoint switch. Checked in the browser (3D resumes on return).
- 2026-10-12 — Wave pipeline retired (D-057): 8 old API routers, `pipeline/`, `service.py`, `research/findings.py`, old tests/scripts, `logView`, LangGraph removed; shared helpers moved byte-identical (`bmw_req/audit.py`, `prioritize/factors.py`, `prioritize/fitcheck.py`, `structure/taxonomy.py`, `structure/galaxy.py`); `/api/health`. 114 tests, all green.
- 2026-10-12 — Old wave tables dropped (D-058): verified backup `data/backups/app-before-D058-20261012T024059Z.db`, 11 tables dropped in one transaction + audit event + VACUUM (373 → 366 MB), schema no longer creates them; rehearsed on a copy first; app healthy, all screens load. 114 tests green.
- 2026-10-12 — Database direction: Postgres 17 + pgvector, no graph DB (Atahan). Migration plan written (`documents/postgres-migration.md`, D-059 proposed): P0 infra → P1 switch → P2 Postgres features → P3 ops/docs. Waiting for Atahan's approval of the plan.
- 2026-10-12 — Postgres P0 done (D-059 accepted): `db` compose service (pgvector 0.8.0 / pg17, 127.0.0.1:5433 — 5432 is another project's), `make db`/`migrate`, `.env` DB settings, Alembic baseline (42 tables, utc_now_text(), append-only triggers, vector columns), throwaway test DBs + schema-parity tests. 121 tests green. App still on SQLite — P1 (switch) next.
- 2026-10-12 — Postgres P1 done: app, pipelines and tests run on PostgreSQL (D-059; D-016/D-018 superseded). Compatibility layer `bmw_req.db`, hand ports (RETURNING, upserts, vectors), data copied (267k rows, verified), C.UTF-8 collation + SQLite NULL order + explicit tie orders → 96/99 API answers identical to SQLite, 3 explained; found and fixed hash-random order in "changes since JAN". `make backup` / `make testdata`; demo_state/drop_wave_tables removed. 131 tests green. SQLite `data/app.db` kept read-only. Next: P2 (pgvector search, JSONB, timestamptz, app role).
- 2026-10-12 — No sample data (D-060, Atahan): Definition/Prioritize fixtures, the Document sample overlay and `?sample=1` removed; pages show "Not run yet" + real empty payloads until the AI has run. Checked on an empty DB in the browser and on the real data (cp1 76 / cp2 80 requirements, 252 / 259 targets).
- 2026-10-12 — Postgres P2 done: timestamptz (25 system timestamps, read back as the same ISO text) + jsonb weights; exact pgvector retrieval in SQL (178/178 themes identical to numpy; HNSW later, Q-027); app role `sharksight_app` without UPDATE/DELETE on append-only tables (tests run as it); found + fixed pgvector `Vector` reads that would have broken every embedding step since P1. 99/99 API answers identical, 134 tests green. Next: P3 (backup/restore round trip, drop sqlite-vec, docs).
- 2026-10-12 — Postgres P3 done (Atahan: "just drop the sqlite and finish the docs"; backup→restore round trip not run): sqlite-vec, the copy script, `db_path`, sqlite3 type hints and the 8 no-op `ensure()` stubs (+28 calls) removed; 99/99 API answers unchanged, 134 tests green. Docs brought current: STATE rewritten (phase, done, how to run, next up), README, PRODUCT, architecture, tech-stack, prioritization, foundation README folder map.
- 2026-10-12 — All SQLite files deleted at Atahan's request (app.db, 7 snapshots, 2 SQLite backups incl. the last copy of the D-058 wave tables; ~1.8 GB) after a fresh `pg_dump` (`data/backups/sharksight-20261012T131941Z.dump`). Cloud deployment options researched.
- 2026-10-12 — Cloud deployment (D-062, Q-029; AWS D-061 tried and dropped): `deploy/compose.yaml` + `Caddyfile` (db, app, HTTPS/password proxy) and `deploy/gcp/deploy.sh` (e2-micro free tier, us-central1, own network, image over SSH, data copy, tunnel, budget, destroy); amd64 image built + smoke-tested. Waiting for Atahan: Google Cloud account + `gcloud auth login`.
- 2026-10-13 — Lean repo (Atahan): vision and future work moved to `documents/future-work.md` for another repo — the generalized SharkSight idea (old Q-028, market scan + method packs), continuous intake (Q-027, its Next-up item) and PRODUCT.md's parallel-workstream note. No code changes.
- 2026-10-13 — Lean repo, part 2 (Atahan: remove everything not related to the working app): removed the CarStage lab page, one-off migration scripts, the Checkpoint Atlas page, the pitch deck (+ its `pitch` dependency group), the validation report, the hackathon results/log and the decisions and resolved questions about retired parts (index note in DECISIONS). Git history keeps all of it.
- 2026-10-13 — Official name SharkSight, repo renamed to `shark-sight` (Atahan): README title, AGENTS intro, Python distribution `sharksight` (module stays `bmw_req`), CLI `uv run sharksight`, npm package `sharksight-web`. No tracked file referenced `ehl-munich-final`; only the git remote did.
- 2026-10-13 — Render + Neon deployment (D-063; Google Cloud didn't work out for Atahan): `render.yaml`, shared `ACCESS_KEY` gate (`api/access.py`, +2 tests), `deploy/render/load-data.sh` (full restore without superuser + app role, prints the app URL), compressed CC BY car models in `assets/models/` baked into the image (74 → 8 MB, same triangles). Tested locally end to end (restore as non-superuser, image without disk, 401/200, append-only denial, car renders). Waiting for Atahan: Neon project (Frankfurt) + Render Blueprint.
- 2026-10-13 — Google Cloud VM files (`deploy/gcp/`, `deploy/compose.yaml`, `Caddyfile`) deleted (Atahan); D-062 superseded by D-063.
- 2026-10-13 — D-064 (Atahan): the cloud app is open to read; changes need the shared key, entered in a new Access panel next to Guide (`components/Access.tsx`, `X-Access-Key` from `lib/api.ts`, `GET /api/access`). Tested with pytest, in Docker and in the browser.
- 2026-10-13 — README rewritten for visitors (what SharkSight is and does, every page with a screenshot in `docs/screenshots/`); setup / run / test / deploy notes moved to AGENTS.md, the deliverable map to `challenge-brief.md`. App opens at JAN 26 (no auto-sweep to JUL). Layout fixes at 1568–2240px: the Evidence readout and the Structure funnel no longer run into the centred logo.
