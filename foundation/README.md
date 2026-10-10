# Foundation — start here every session

This folder is the project's memory. Every agent (Claude, Codex, humans) reads it at session start and keeps it current.

## Read order (session start)

1. `STATE.md` — where we are, what's in progress, what's next.
2. `OPEN_QUESTIONS.md` — unresolved questions; check if any block your task.
3. `DECISIONS.md` — what has been decided (don't re-litigate without new info).
4. The relevant file(s) in `documents/` for your task.

## Write rules (session end / after meaningful work)

- `STATE.md`: update "Current phase", "In progress", "Next up", and add one line to the "Session log".
- `DECISIONS.md`: append a new `D-xxx` entry for every decision (who decided, why, alternatives).
- `OPEN_QUESTIONS.md`: add new `Q-xxx` entries; when answered, move them to "Resolved" with the answer and link the resulting decision.
- `documents/`: keep reference docs true to the code. If you change the stack, schema or workflow, update the doc in the same change.

## Folder map

| File | Purpose |
|---|---|
| `STATE.md` | Live project status + session log |
| `DECISIONS.md` | Append-only decision log (`D-xxx`) |
| `OPEN_QUESTIONS.md` | Open / resolved questions (`Q-xxx`) |
| `documents/challenge-brief.md` | BMW challenge distilled: mission, scope, deliverables, judging signals |
| `documents/data-inventory.md` | Every provided dataset: schema, size, quirks, how to use it |
| `documents/tech-stack.md` | Chosen / proposed tech stack and setup notes |
| `documents/architecture.md` | End-to-end workflow, AI vs. human steps, data model, audit trail |
| `documents/requirement-model.md` | Requirement schema, evidence levels, gates, prioritization logic |
| `documents/knowledge-base.md` | 3-layer knowledge base, research agents, trust tiers, brand fit & feasibility |
| `documents/portfolio-reference.md` | Platforms, plants, production allocation, BMW sales (web-researched, cited) |
| `documents/competitor-landscape.md` | Competitors per segment × market, demand trends, brand positioning (web-researched, cited) |

Raw challenge material lives in `../challange information document/` (folder name typo is intentional — it's the original; read-only, git-ignored).
