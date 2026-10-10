# Foundation — start here every session

This folder is the project's memory. Every agent (Claude, Codex, humans) reads it at session start and keeps it current.

## Read order (session start)

1. `STATE.md` — where we are, team, demo path, what's next, budget.
2. `OPEN_QUESTIONS.md` — the "Open" section; check if any question blocks your task.
3. `DECISIONS.md` — the **Index** table; open full entries only when relevant (don't re-litigate without new info).
4. Only the `documents/` your task needs (see the table in `AGENTS.md`).

## Write rules (session end / after meaningful work)

- `STATE.md`: update "Current phase", "In progress", "Next up", the Budget table after paid runs, and add one line to the "Session log".
- `DECISIONS.md`: append a new `D-xxx` entry for every decision (who decided, why, alternatives) **and add it to the Index**. Statuses: `accepted` · `proposed` · `superseded by D-xxx`.
- `OPEN_QUESTIONS.md`: add new `Q-xxx` entries in numeric order. When answered, move them to "Resolved" with the answer and link the resulting decision.
- `documents/`: keep reference docs true to the code. If you change the stack, schema or workflow, update the doc in the same change. State each fact **once**: other docs link to it instead of copying it.
- Never present something as decided unless a `D-xxx` says so. Architecture/framework choices need the team (Q-014).

## Folder map

| File | Purpose |
|---|---|
| `STATE.md` | Live project status, team, demo path, budget, session log |
| `DECISIONS.md` | Append-only decision log (`D-xxx`) with index |
| `OPEN_QUESTIONS.md` | Open / resolved questions (`Q-xxx`) |
| `documents/challenge-brief.md` | BMW challenge distilled: mission, scope (+ tensions), deliverables, judging signals, mentor input |
| `documents/data-inventory.md` | Every provided dataset: schema, verified counts, quirks, coverage |
| `documents/tech-stack.md` | What's decided (OpenAI, models, budget) vs. candidates for Q-014 |
| `documents/architecture.md` | End-to-end workflow, AI vs. human steps, logical data model, audit trail |
| `documents/requirement-model.md` | Requirement schema, evidence levels, gates, prioritization draft |
| `documents/knowledge-base.md` | 3-layer knowledge base, research agents, trust tiers, brand fit & feasibility |
| `documents/portfolio-reference.md` | Platforms, plants, production, BMW sales (cited) |
| `documents/competitor-landscape.md` | Competitors per segment × market, demand trends, brand positioning (cited) |
| `documents/bmw-annual-report-2025.md` | BMW Group Report 2025 extract (T1, page-cited) |
| `documents/glossary.md` | Codes, platforms, data and model terms |

## Fresh clone

1. **Raw data** (not in git): put the BMW challenge folder at the repo root under its original name `challange information document/` (typo intended), containing `mission.md`, `BMW_Hackathon_Briefing_Short.pdf`, the three PNGs and `BMW-Data/` (3 feedback xlsx, customer studies xlsx, `sales_volumes.xlsx`, 3 option-list PDFs). Get it from the team. Treat it as read-only.
2. **Python** (data inspection): `uv venv --python 3.12 && uv pip install pandas openpyxl`. Don't use the system anaconda Python (broken pandas).
3. **PDF tools**: `brew install poppler` for `pdftotext` (option lists) and `pdftoppm`. The briefing PDF has no text layer, so render it with `pdftoppm` to read it.
4. **Secrets**: copy `.env.example` to `.env` once it exists (created at scaffolding), then add `OPENAI_API_KEY` (ask Atahan).
5. **Derived data** goes to `data/`. AGENTS rule 1 / D-002 say it is git-ignored, but `.gitignore` doesn't list `data/` yet. Add it before writing anything there. Nothing else is set up yet: no app code exists until Q-014 is decided.
