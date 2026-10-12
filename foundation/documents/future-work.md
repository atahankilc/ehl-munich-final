# Future work (out of this repo's scope)

Moved here on 2026-10-13 at Atahan's request: this repo stays lean and covers the BMW requirements app as it is.
Everything below is vision or future work that will be picked up **in another repo**. Nothing here is a commitment;
agents working in this repo don't act on it. The IDs Q-027 / Q-028 are kept so older decisions that cite them
(D-055, D-059) still resolve.

## 1. A domain-agnostic SharkSight (was Q-028, open)

- Owner: Atahan · raised 2026-10-12
- Atahan is considering a version anyone can use for ground-up requirements engineering and product decisions.
  Market scan: artifact https://claude.ai/artifact/RPFgwBDcz8TFr46pbhLJYA (feedback intelligence, PM suites, RM/ALM,
  AI-native systems engineering, CI, preference research). Finding: no tool covers evidence → measurable requirements →
  gated, per-segment priority → human decision → audit; closest are Productboard Spark upstream and Flow Engineering
  downstream.
- Open: positioning (a layer between VoC tools and RM/ALM tools?), beachhead (long-cycle physical products?), what
  becomes config (org / product line / segment, pluggable gates, generic ingest, optional 3D visualizer), integrations
  (Jira, Jama/Polarion, ReqIF, MCP), and how the BMW-specific rules (brand fit, plant/platform feasibility) map to
  generic gates.
- 2026-10-12 — Method packs + evidence depth (Scrum, Kanban, OKR, SAFe, discovery, stage-gate): artifact
  https://claude.ai/artifact/MMKqm5c2NihxE8uwGBu1SQ. Key point: evidence depth should scale with decision cost /
  reversibility (light / medium / deep); stories inherit evidence from their epic or opportunity; agile evidence comes
  mostly after the decision (outcome measurement). Proposal only.

## 2. Continuous data intake instead of fixed checkpoints (was Q-027, open)

- Owner: Atahan · raised 2026-10-11
- The two fixed checkpoints (D-040) would eventually go; new data gets digested automatically — e.g. a background agent
  that searches the web from time to time, and users uploading new data into the knowledge base.
- Open: how evidence is versioned without checkpoints (rolling snapshots? event time?), what a "run" is then, how the
  audit trail and the PM's decisions stay comparable over time, upload formats + validation + confidentiality (AGENTS
  rule 1), and the cost cap for a background agent (D-054/D-055 limits apply).
- Was "Next up" item: background web agent, uploads to the knowledge base, versioning without fixed checkpoints, a job
  queue in Postgres (`FOR UPDATE SKIP LOCKED`), and an HNSW index once the knowledge base passes ~50k nodes. The
  PostgreSQL move (D-059) was made partly to make this possible (`postgres-migration.md`).
- Until then the app keeps the per-checkpoint separation (D-055).

## 3. More requirement sources and views (was in PRODUCT.md)

- A parallel workstream idea (D-040+): requirement origins (competitors, trends, regulation, personas), a regulatory
  radar, customer & model groups, an offering matrix per market and market intelligence; the information architecture
  would need a home for these. Note: regulation is out of scope for the BMW challenge (AGENTS rule 2).
