# BMW Requirements Studio

AI-assisted, evidence-linked **customer requirements for BMW successor vehicles** — built for the BMW
"AI for Product Decision Making" hackathon challenge. The AI ingests BMW customer feedback, customer studies,
sales and option lists, enriches them with cited web research, extracts signals, clusters findings, derives and
scores requirements per derivative × market — and the **product manager decides**, with every step in an
append-only audit trail.

Portfolio-level from day one: 1 Series (F70), 5 Series (G60 + China LWB G68), 7 Series (G70) × EU / US / CN / RoW.

## Quick start

```bash
uv sync                                   # Python 3.12 venv
cp .env.example .env                      # add OPENAI_API_KEY (LLM provider: OpenAI)
uv run streamlit run app.py               # PM app on http://localhost:8501
```

The raw BMW data (`challange information document/`) and the database (`data/app.db`) are git-ignored.
Demo states (`data/snapshots/`):

| Snapshot | Contents | Use |
|---|---|---|
| `evidence` | all evidence ingested, no requirements | rebuild the pipeline |
| `wave1` | wave 1 done, no PM decisions | **live demo**: review as the PM from scratch |
| `demo` | wave 1 → PM review → wave 2 → PM decides proposals → wave 3 | explore the full ~2-year history |

```bash
uv run python scripts/demo_state.py restore wave1   # stop the app first; keeps the LLM usage log + cache
uv run python scripts/demo_build.py                 # rebuild wave1 + demo from the evidence snapshot
```

## End-to-end workflow

| # | Step | Who | Where |
|---|---|---|---|
| 1 | Ingest feedback (10,128 verbatims), customer study, sales, option lists | AI/system, autonomous | `bmw_req.ingest` |
| 2 | Curated reference layer (platforms, plants, competitors, market profiles, brand guardrails) | AI-researched, **PM signs off guardrails** | `bmw_req.reference_data` |
| 3 | Web research agents → cited evidence (URL in search citations, quote verified) | AI, autonomous | `bmw_req.research` |
| 4 | Signal extraction (luna) → findings (embeddings + clustering, per-market/per-wave metrics) | AI, autonomous | `pipeline.extract`, `pipeline.findings` |
| 5 | Requirement derivation (sol), portfolio consolidation, dedup against the existing backlog (merge proposals), evidence linking | AI **proposes** | `pipeline.requirements`, `pipeline.linker` |
| 6 | Fit checks: brand (gate), segment, market, feasibility (context) | AI checks, sol re-checks warn/fail | `pipeline.fit` |
| 7 | Explainable per-target scoring, snapshots, change proposals | AI computes, **PM sets weights** | `pipeline.scoring` |
| 8 | Review: approve / reject / defer / edit / challenge / override gate / confirm priority | **Human, mandatory** | PM app |
| 9 | Audit trail, export | system | PM app → Audit trail / Export |

Repeated per **simulated ingest wave** (LangGraph orchestrator `pipeline.graph`): wave 1 kick-off, wave 2
(+6 months: more feedback, customer study, new sales), wave 3 (+12 months: market event from web research).
Scores are recomputed automatically; priority changes against a PM-confirmed priority become **change
proposals** with their factor-level cause.

## How the deliverables map

| BMW deliverable | Where |
|---|---|
| Concept + working prototype | this repo; PM app: Home → Review requirements → Priorities by market → AI suggestions (sidebar "Demo tour" walks the path) |
| Structured requirement list (ID, description, findings+sources, score, rationale, evidence level, assumptions/uncertainties, status) | Export page (JSON / CSV / Markdown), `service.export_requirements` |
| Workflow definition: AI autonomous vs mandatory human review | table above; Home ("How it works") and Pipeline & data pages; `foundation/documents/architecture.md` |
| Audit trail: sources → findings → consolidation → scoring → prioritization → human decision | Requirement → Audit tab; Audit trail page; `audit_event` (append-only via triggers) |

## Key design choices

- **Evidence vs assumption** kept apart in every requirement; conflicting evidence linked as `contradicts`.
- **Markets are different customers** — every derivative × market target has its own score, evidence level and
  priority; missing data (e.g. no China verbatims) is shown as an evidence gap, not silently scored as zero.
- **Brand fit** is an approval gate (PM override with rationale); **feasibility** is non-blocking context.
- **$100 OpenAI budget** enforced by a reserving wrapper; every call logged in `llm_usage`, identical calls cached.

Project memory, decisions (D-001 … ) and open questions live in `foundation/`.
