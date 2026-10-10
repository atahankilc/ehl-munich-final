# Validation Report — judge + QA pass (2026-10-10)

Scope: the `demo` state (53 requirements, 165 targets, 3 runs) plus a live PM flow on `wave1`. Method: aggregate DB queries, three end-to-end traces, code review, Streamlit AppTest for all 11 pages and the PM actions, browser for opening a wave and the inbox. No raw verbatim text was read. The validation cost $0.06 (challenge $0.049; wave 2 replayed mostly from the LLM cache). The DB was restored afterwards (`pre_validation` = `demo` + 2 view events). Fixes: D-034. Open points: Q-021–Q-023.

## 1. Deliverables checklist

| BMW item | Verdict | Proof |
|---|---|---|
| Concept + working prototype | **Pass** | 11 pages render without exceptions (AppTest). Overview shows which steps the AI does and where human gates are. |
| Ingest + web enrichment | **Pass** | 10,128 verbatims, study 391 items, sales, 458 option items, 219 web items with tier and URL. |
| Signals linked to sources | **Pass** | `signal` → `source_item` (verbatim ID, file#sheet). Findings: 0 without a source (benchmark). |
| Unique ID, description, findings + sources | **Pass** | `requirement.id`, `requirement_finding`, `finding_source`. Every requirement has ≥ 1 supporting finding. |
| Priority / score + rationale | **Pass** | Per-target `score_breakdown_json` (factors, points, gaps, rationale). AI band and PM band are kept separate. |
| Evidence level | **Pass** | E1–E4 per target. The requirement shows the best target level, which can look better than a weak market. |
| Future assumptions & uncertainties | **Partial** | The fields are filled everywhere. But 42/53 requirements are `horizon=today` and only 1 is a delighter. The "future needs" story (D-012) is thin. |
| Decision status | **Pass** | proposed / approved / rejected / deferred / challenged. Only humans set it (0 non-human status/priority events). |
| Workflow: AI vs. human | **Pass** | Overview page. `service.py` is the only write path. A brand fail blocks approval (verified live). |
| Audit: sources → findings → **consolidation** → scoring → decision | **Partial** | Every step has events with actor, time, rationale and model. **Consolidation is only partly traceable:** the pre-merge per-line drafts are not stored; there is only a "[merged across …]" note in the summary. |
| Audit: content / score / priority / evidence / status changes | **Pass** | edit (per field, versioned), rescore (with factor delta), set_priority, link_findings / edit_evidence, set_status. Append-only triggers verified (UPDATE/DELETE abort). |
| Access events | **Partial** | Only requirement views and exports are logged. Backlog, audit trail, findings and the inbox are not. |
| Review / challenge / modify / approve / reject | **Pass** | Verified live. Challenge took 26 s and $0.049; its edits became 3 content proposals. |
| Markets differ (mentor) | **Partial** | Per-target scores, conflicts page, CN honestly marked "no data for customer voice". But see Q-023. |
| Continuous re-prioritization (mentor) | **Pass** | Snapshots per run; priority proposals with a factor-level cause (verified in wave 2). |
| Scope (no regulatory / engineering / pricing) | **Pass** | Keyword scan + manual check: clean. Range, charging and fuel targets are phrased as the customer experiences them. |
| Brand fit | **Pass, but untested in data** | 0 brand fails in 165 targets, so the gate is never shown in the demo (it works: tested with a synthetic fail). 6 comfort warns on 7 Series look too strict for luxury. |

## 2. Traces (all chains complete)

- **REQ-0018 G60×US** (highway assistance): 2 US pain clusters (70 + 58 US verbatims), 1 strength cluster cited as contradicting. Score 53 = Should. Customer voice: 123/3,346 verbatims. Study z −0.42 drives the "gap" while a *contradicting* study strength (z +0.91) is ignored by the score. Fit: pass (feasibility warn). PM confirmed Should (scripted). Audit 886 → 1586 complete.
- **REQ-0005 G68×CN** (natural voice): cited CN web T1/T2 (AI cabin assistants), no CN study item on voice. Score 52 Should, driven by future relevance (21.8 pts) + volume. Gaps "customer voice, satisfaction gap" shown, E3 ×0.8 — honest. It is a portfolio merge of 5 targets with per-line metrics in one field (bundled).
- **REQ-0001 portfolio** (tactile controls, F70 + G60/G68 + G70): 57 links. Scripted approval 3 ms after scoring (visible as scripted). The linker kept adding evidence after approval (Q-021), incl. off-topic web findings.

## 3. Ranked findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| 1 | High (fixed) | Rejecting a "new requirement" proposal left the requirement `proposed`, in the backlog and in scoring | `decide_proposal` had no reject branch; the inbox text says "reject to drop it" | D-034 + test |
| 2 | High (fixed, D-035) | ~9 cross-line near-duplicate requirements | consolidation only within one run, derivation saw only its own line | Dedup vs whole backlog → `extend` proposals; demo rebuilt (53 → 39) |
| 3 | Medium (fixed) | The app was served on all interfaces (Network/External URL) with confidential data | `lsof *:8501`, streamlit.log | D-034 `server.address=localhost` |
| 4 | Medium | Customer voice barely separates markets; 1 verbatim reads as "driven by customer voice" | median 0.36 for 0–2 verbatims vs 0.69 for 50+ | Q-023 |
| 5 | Medium | Contradicting evidence never affects score or confidence (text only) | `satisfaction_gap` uses min z; web factors use supports only | Q-023 |
| 6 | Medium | Linker changes evidence of approved requirements directly and over-links tangential web findings | REQ-0001 links in waves 2–3; F907/F909/F925 | Q-021 |
| 7 | Medium | Future orientation thin: 42/53 `today`, 1 delighter | requirement table | Prompt: require ≥ ⅓ `at_successor_launch` with trend citations |
| 8 | Medium (fixed) | Wave ≥ 2 "new evidence" cause was false for 5/25 requirements (REQ-0030/31/44/48/49 cite no new finding) | derivation_json vs `first_wave` | D-034 honest cause |
| 9 | Low (fixed) | A stale open priority proposal stays open when a later run agrees with the PM | `run_prioritization` superseded only when it differed | D-034 + test |
| 10 | Low | Brand gate never triggers in demo data (0 fails) | fit_check counts | Show the gate with a seeded example, or say so in the demo |
| 11 | Low | Consolidation is not in the audit trail (pre-merge drafts lost) | `store()` keeps only the merged draft | Store the drafts in derivation_json + a `consolidate` audit event |
| 12 | Low | "Confirm priorities" writes one rationale to all targets (e.g. "CN raised…" on 9 targets) | live audit | Only write changed targets, or per-target rationale |
| 13 | Low | `requirement.first_run_id` is never set; linker/fit audit events lack `run_id` | NULL in all rows | Pass run_id through the graph |
| 14 | Low | Actor is free text with a default "Atahan (PM)"; a lost input attributed my wave-2 run to Atahan | audit `open_wave 2` | Require an explicit name per session |
| 15 | Demo risk | Wave run / challenge block the UI; a failed derive leaves the wave "open" with no re-run button | `node_open` commits first | Rehearse with cached replays; add retry |
| 16 | Info | Self-judging (sol judges sol); brand guardrails unsigned (D-031); clusters computed on all data | known | Say so in the pitch |
