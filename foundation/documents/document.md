# Document (page 5) — the deliverable

The challenge's deliverable (challenge-brief.md; BMW process step 5 "Documentation / tracking") as a page and an
export: the final, traceable requirement list **per car line × market at a checkpoint**. Read-only over the
definition (D-048) and prioritization (D-050) layers; the PM decides on page 4, never here.

## API (`api/routers/document.py`)

| Endpoint | Returns |
|---|---|
| `GET /api/document?cp=&line=&market=` | `header` (checkpoint label/cutoff, counts by band (PM band else AI), AI counts, confirmed by PM, open proposals, generated_at, weights version, run, available lines/markets) + `items` |
| `GET /api/document/changes?line=&market=` | JAN → JUL diff: new, removed, moved (AI band, PM band, score ≥ 3), PM decisions at cp2, cp2 proposals by outcome |
| `GET /api/document/export?cp=&line=&market=&format=md\|csv` | Markdown deliverable (all fields + sources) or CSV (one row per requirement); logged as an `audit_event` (`action=export`, `entity_type=export`, actor from `X-Actor` or `?as_actor=`) |

Each item: stable ID (`REQ-<line digit><market>-<n>`, n = order of first appearance of the requirement key across all
definition runs, so the same requirement keeps its number across checkpoints and markets) + key; title, statement,
domain, area (title, need); metric + acceptance criteria; the rung in use (PM's `def_choice` else the AI-recommended
rung) with value, text, basis and the full ladder row; priority (AI score/band/rank, PM-confirmed band with
rationale/actor/date); decision status (`confirmed`, `ai_proposal`, `open_proposal`, `open_proposal_against_pm`);
prioritization rationale + factor breakdown + modifiers; evidence (level, confidence, comment count, every linked
source via `definition._evidence` with URL/tier/date, plus two verbatim quotes with comment IDs per comment cluster);
assumptions, gaps and uncertainties (flags and gate warnings in words); links to other requirements; gates; track
state; history per checkpoint; proposals and decisions.

Ordering: confirmed band (PM) else AI band, then AI score.

## Checkpoint visibility

Everything is read as of `cp`: `def_choice`, `def_link_review` and `prio_decision` rows with a later
`checkpoint_id` are ignored; proposals only from runs at checkpoints visible at `cp`; history only up to `cp`. The
document reuses helpers from `api/routers/prioritize.py` (`_target`, `_proposal`, `_prev_band`, `_states`, `_runs`) and
`api/routers/definition.py` (`_evidence`, `_area_titles`) but filters choices, link reviews, proposals and decisions
itself.

## Frontend

`web/src/screens/document/` (DocumentPage, guide, document.css), types in `web/src/lib/document.ts`, route
`/document`. The scene behind is page 4's (Scan treats `document` as `prioritize`), dimmed behind a full-height
sheet. Visual spec: DESIGN.md → "Document (page 5)". Tests: `tests/test_document.py`.
