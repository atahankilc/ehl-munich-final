# Market landscape — evidence-to-requirements & product decision tools

_Researched 2026-10-12 (web search). Purpose: who else works in this space if SharkSight is generalized beyond BMW into a tool anyone can use for ground-up requirements engineering and product decisions. Most sources are vendor pages or vendor-written comparisons, so funding, customer and feature claims are **company-reported** unless noted. Features not checked are marked as such._

## TL;DR

- **Nobody covers the whole chain end to end.** SharkSight's chain is: raw evidence (feedback, studies, sales, web) → findings → measurable requirements → fit/feasibility gates → explainable per-segment priority → human decision → append-only audit, re-run over time. The market splits into tools that stop at **"themes / opportunities"** (feedback intelligence, PM suites) and tools that start from **requirements someone has already written** (requirements management / ALM, systems engineering).
- **Closest threat from above: Productboard Spark** (June 2026). Agents for voice of customer, competitive research, prioritization and specs. Every insight links back to a customer note, and edits are previewed before they are saved. Its ranking logic is not explained, and the launch post mentions no audit trail.
- **Closest threat from below: Flow Engineering.** An AI-native "systems graph" for hardware teams; Rivian uses it for all R1/R2 requirements. It raised a $50M Series B at a $750M valuation on 2026-10-02. Flow starts at engineering requirements, not at customer evidence.
- **Consolidation is fast.** Amplitude bought Kraftful (Jul 2025), Atlassian bought Cycle (Sep 2025) for Jira Product Discovery, and Altium bought Valispace (2023/24). Feedback-to-insight is becoming a feature inside larger suites.
- **Where we could win:** traceable, auditable, segment-aware requirements for **physical / long-cycle / regulated products** (automotive, industrial, medtech, aerospace, consumer hardware). Here the decision is expensive, the PM must defend it, and the SaaS-oriented feedback tools don't fit well.

## 1. Our chain, stated generically

| Step | SharkSight today (BMW) | Generic form |
|---|---|---|
| Evidence | verbatims, customer study, sales, option lists, cited web research (T1–T3) | any feedback + quantitative studies + market data + web research, with provenance |
| Findings | clusters, insights, themes, evidence graph | same |
| Requirements | customer-experienced metric + target ladder, horizon, Kano, evidence vs. assumption | same, domain-agnostic |
| Gates | brand & segment fit, platform/plant feasibility | pluggable gates (brand, feasibility, compliance, strategy) |
| Prioritization | prio-v1 per requirement × line × market, factor breakdown, bundles | per requirement × product line × segment |
| Decision | PM approves / rejects / defers with rationale; AI only proposes | same |
| Audit & continuity | append-only `audit_event`, checkpoints, change proposals | same |

## 2. Landscape by category

### A. Customer-feedback intelligence (upstream; stops at themes)

| Tool | What it does | Where it stops |
|---|---|---|
| **Enterpret** | Adaptive taxonomy over feedback from 50+ channels; launched an "agentic customer intelligence platform" Oct 2025. $20.8M Series A (Dec 2024, Canaan); customers incl. Canva, Notion, Strava. | Insights and alerts; no requirement model, no decision record |
| **Unwrap.ai** | Theme detection over many sources (claims 3,000+ connectors); pushes emerging themes to Slack/email | Same |
| **Dovetail** | Research repository → "customer intelligence platform". July 2026 launch: background agents, **customer "digital twins"** built from what segments said, MCP connectors (Claude, Copilot, Slack, Linear), ISO 42001 | Research synthesis; no prioritization or requirements |
| **Kraftful → Amplitude** | LLM analysis of tickets and app reviews, top requests and complaints; acquired Jul 2025 and folded into product analytics | Part of the analytics suite now |
| **BuildBetter** | Calls, tickets and docs → insights, 100+ integrations | Insights and docs |

### B. Product-management suites with AI (midstream; opportunity → spec)

| Tool | What it does | Notes |
|---|---|---|
| **Productboard Spark** (2026-06-22) | Agents for VoC synthesis, competitive research, prioritization, codebase-grounded PRDs; "every insight links back to a real customer note"; previews edits before saving; ranked opportunities (beta); specs go out via MCP to Claude Code / Codex / Cursor | **Closest overall.** Ranking method not explained; no audit trail mentioned; software-product oriented (codebase grounding) |
| **Jira Product Discovery** (+ **Cycle** acquisition, Sep 2025) | AI organizes feedback and connects it to ideas and delivery; Rovo agents; 20k+ customers | Feedback → ideas inside the Atlassian stack |
| **ChatPRD** | AI PRD writer; bootstrapped; claims 100k+ PMs | Document generation, not evidence |
| Aha!, ProdPad, airfocus, Canny, Pendo | Roadmap / idea tools adding AI on top of a user-maintained structure | AI features not checked in this pass |
| Zeda.io | Feedback → roadmap with revenue scoring | A competitor says it is shutting down in 2026 (unverified) |

### C. Classic requirements management / ALM (downstream; starts from written requirements)

| Tool | AI angle | Notes |
|---|---|---|
| **Jama Connect** | Advisor (NLP quality checks on wording), Trace Scores | Strong in regulated product development |
| **IBM DOORS Next**, **Siemens Polarion**, **PTC Codebeamer**, **Visure** | Quality checks, test generation, risk scoring (varies) | Incumbents in automotive and aerospace. No native Polarion AI assistant found; a community MCP server exposes Polarion items to LLMs |
| **Modern Requirements (Copilot4DevOps)** | Scores requirement quality against "6 C's", generates user stories, Gherkin and tests inside Azure DevOps | Authoring help, not elicitation from evidence |
| **Dassault CATIA R2026x** | "Generative systems requirement creation"; Virtual Companions (Feb 2026) for requirements alignment | Engineering-side, PLM-bound |

**Common gap:** these tools assume requirements already exist. AI improves wording, traceability and tests, not *which* requirements customers need.

### D. AI-native systems engineering (downstream, newer)

| Tool | Facts |
|---|---|
| **Flow Engineering** | "Systems graph" linking requirements, CAD, code, simulations, tests and certification. Agents log changes, flag downstream effects and check requirement and test coverage. Rivian runs all R1/R2 requirements on it (scaled to ~1,500 users in 7 months). Series A $23M (Sequoia, Oct 2025); Series B $50M at $750M (Valor / Atreides, 2026-10-02). |
| **Trace.Space** (Riga) | "AI-native requirements management": trace graph from PDFs, Jira, Git and Confluence; change impact, duplicate detection, standards compliance. $4M seed (Cherry Ventures, Feb 2025). |
| **Valispace** (Altium) | AI-assisted systems and requirements engineering for hardware; acquired by Altium (Dec 2023 / 2024). |

These are the natural **hand-off target** for our output (customer requirements → engineering requirements), not direct competitors.

### E. Market & competitive intelligence (the web-evidence layer)

**Crayon**, **Klue** (Gartner 2026 MQ Leaders for competitive and market intelligence) and **AlphaSense** (financial and strategic research, 500M+ documents). They feed sales and strategy teams. None turns competitive facts into requirements.

### F. Preference research & synthetic customers (the "how much do they want it" layer)

- **Qualtrics**, **Conjointly**, **Quantilope**, **OpinionX**: conjoint, MaxDiff and Kano studies; AI mostly helps with survey building and text analysis.
- **Synthetic customers:** **Simile** ($100M Series A Feb 2026, $200M Series B Aug 2026 at $2B; "agentic twins" trained on consented interviews) and **Aaru** (~$1B valuation). Plus Dovetail's digital twins. Trust is still low (one report: 8% of researchers fully trust synthetic alternatives). For us this is a possible *future-needs* input, but it should be labelled an **assumption, not evidence** (rule 4).

### G. Decision-intelligence platforms (adjacent, different job)

The first Gartner MQ for Decision Intelligence Platforms came out on 2026-01-26. Leaders per vendor releases: Quantexa, FICO, IBM; also Aera, o9, Pega, SAS and others. These platforms cover **operational, repeated decisions** (credit, supply chain, fraud), not one-off product-portfolio decisions. They are still useful vocabulary: governance, explainability, decision records.

### H. Industry services (automotive)

**J.D. Power** brings customer voice into OEM strategy and development, assigning requirements and priorities per vehicle system (consulting plus data such as AutoPlanner). **NTT Data** offers GenAI VoC agents (RAG + knowledge graphs) for automotive. These are services, not self-serve software, so BMW-like customers currently **buy this as consulting**.

### I. Research & open source

- **OpenReq** (EU H2020, 2017–2020): open-source RE platform with recommenders, **group decision support for release planning**, dependency detection and user-feedback analytics. It is the closest academic ancestor of what we do.
- **LLM4RE literature:** a systematic review of 74 studies (arXiv 2509.11446) finds a +136% jump in studies in 2024. Focus is shifting to elicitation and validation, mostly with app-store reviews. No end-to-end evidence → decision systems were reported.
- **StrictDoc, Doorstop, sphinx-needs:** docs-as-code requirements tools (text + Git traceability). They could serve as an export target.

## 3. White space — what nobody else combines

1. **Requirements built from evidence, not just "insights".** A measurable customer-experienced metric, a target ladder (baseline / threshold / target / stretch), and every number tagged cited / projected / assumption / gap. Feedback tools stop before this; RM tools start after it.
2. **Mixed evidence with provenance and trust tiers.** Internal feedback, quantitative studies, sales and cited web research in one evidence graph, with conflicts surfaced (e.g. BMW vs public sales figures).
3. **Segment-aware prioritization.** The same requirement is scored per product line × market, and cross-market conflicts are shown. SaaS tools mostly rank globally or by revenue.
4. **Explainable, deterministic scoring.** A factor breakdown the PM can re-weight. Spark's ranking is opaque in public material.
5. **Decision governance.** The AI only proposes; humans decide with a rationale; append-only audit; snapshots over time. Spark previews edits, but no tool here offers a decision record built for review by others.
6. **Fit / feasibility gates.** Brand fit and platform feasibility generalize to pluggable gates: brand, manufacturability, regulation, strategy.
7. **Future-needs projection.** A 3–5-year horizon from past feedback + competitors + trends, kept separate from evidence.

## 4. Implications if we generalize

- **Positioning:** a "decision-grade requirements" layer **between** the VoC tools and the RM/ALM tools. Ingest from Dovetail, Enterpret, Gong, surveys and CSV/xlsx; hand off to Jira, Jama, Polarion, Flow and ReqIF/StrictDoc. Integrate with both sides instead of competing with them; MCP connectors are now table stakes (Spark, Dovetail and Crayon all ship them).
- **Beachhead:** long-cycle physical products where decisions are costly and must be defended: automotive OEMs and suppliers, industrial equipment, medtech, consumer electronics. Today they rely on consulting (J.D. Power-style) plus spreadsheets.
- **What to make configurable** (largely in line with AGENTS rule 7):
  - brand / model / market → organization / product line / segment
  - brand-fit and plant/platform checks → a gate plug-in interface
  - the 3D car → an optional product visualizer, with a 2D fallback
  - BMW file loaders → a generic ingest with column mapping
  - taxonomy / aspect space → a per-domain template
- **Risks:**
  - Productboard or Atlassian could add audit and segment scoring.
  - Flow could move upstream into customer evidence.
  - LLM synthesis is commoditizing, so the moat has to be the **requirement model, decision governance and integrations**, not the extraction.
  - Enterprise customers need data controls (redaction, no training on their data, ISO 42001-style certification is becoming expected).

## Sources

- Enterpret: https://www.enterpret.com/blog/enterpret-series-a · https://en.wikipedia.org/wiki/Enterpret · https://www.enterpret.com/guides/customer-intelligence-ai-for-product-managers-5-platforms-evaluated-for-2026
- Unwrap: https://www.unwrap.ai/post/best-enterpret-alternatives-2026 · https://blog.buildbetter.ai/enterpret-vs-unwrap-ai/
- Dovetail: https://dovetail.com/blog/suns-out-summer-launch-26/ · https://martechseries.com/predictive-ai/ai-platforms-machine-learning/dovetail-launches-major-ai-powered-platform-expansion-including-agents-and-category-defining-digital-twins-to-close-the-gap-between-customer-signal-and-business-outcomes/
- Kraftful/Amplitude: https://amplitude.com/press/amplitude-acquires-kraftful · https://martech.org/amplitude-acquires-kraftul-to-improve-customer-feedback-analysis/
- Productboard Spark: https://www.productboard.com/blog/introducing-spark-agentic-product-system/ · https://www.productboard.com/spark/ · https://businesstechnavigator.com/news/productboard-spark-agentic-product-system-2026
- Jira Product Discovery / Cycle: https://www.atlassian.com/blog/company-news/cycle-joining-atlassian · https://tech.eu/2025/09/03/french-startup-cycle-joins-atlassian-embedding-customer-insight-tech-into-jira/ · https://www.eesel.ai/blog/jira-product-discovery-ai-features
- ChatPRD: https://rywalker.com/research/chatprd
- PM tool roundups: https://blog.buildbetter.ai/best-productboard-alternatives-in-2026-10-ai-powered-product-management-tools/ · https://resources.rework.com/tools/ai-tools/best-ai-tools-for-product-managers-2026
- RM tools: https://thenextweb.com/news/best-ai-requirements-management-software-2026 · https://www.modernrequirements.com/webinar/supercharge-your-requirements-quality-with-copilot4devops-powered-by-chatgpt/ · https://extensions2.polarion.com/
- Dassault: https://blog.3ds.com/brands/catia/industrial-ai-catia-r2026x-fd03/ · https://softprom.com/cad-dassault-systemes-ai-assistants-3dexperience
- Flow Engineering: https://flowengineering.com/blog/flow-raises-23m-from-sequoia-to-accelerate-the-future-of-hardware-development · https://pulse2.com/flow-engineering-raises-50-million-series-b-at-750-million-valuation/ · https://eletric-vehicles.com/rivian/rivian-adopts-sequoia-backed-platform-as-single-engineering-system/
- Trace.Space: https://techcrunch.com/2025/02/05/aiming-to-accelerate-product-design-with-ai-trace-space-raises-a-seed-round · https://www.incose.org/resource/se-lab-demo-day-016-bringing-requirements-engineering-into-the-ai-age-building-the-first-ai-native-systems-engineering-platform/
- Valispace/Altium: https://www.aviaspace-bremen.de/en/2024/05/22/elevating-engineering-with-valispaces-acquisition-by-altium/ · https://www.cbinsights.com/company/valispace
- Competitive intelligence: https://dupple.com/learn/best-ai-competitive-intelligence-tools · https://www.autobound.ai/blog/top-15-competitive-intelligence-tools-2026
- Preference research: https://conjointly.com/solutions/feature-selection/ · https://cleverx.com/blog/best-platform-kano-max-diff-feature-prioritization · https://www.quantilope.com/resources/best-conjoint-analysis-tools-in-2026-full-comparison
- Synthetic customers: https://www.renascence.io/news/30097/simile-raises-200m-at-2b-valuation-for-synthetic-user-ai-testing · https://startupintros.com/news/2026-02-12-simile-series-a · https://www.newcomer.co/p/startups-target-the-tricky-task-of
- Decision intelligence MQ: https://www.gartner.com/doc/7363830 · https://www.quantexa.com/press/quantexa-recognized-as-a-leader-in-2026-gartner-magic-quadranttm-for-decision-intelligence-platforms/ · https://marketplace.fico.com/blogs/fico-named-leader-2026-gartner-magic-quadrant-decision-intelligence-platforms
- Automotive VoC: https://www.jdpower.com/business/mexico-automotive-product-consulting/ · https://www.nttdata.com/global/en/insights/focus/genai-in-motion-redefining-automotive---innovating-with-customer-insights
- OpenReq: https://cordis.europa.eu/project/id/732463 · https://ecai2020.eu/papers/pais/6_paper.pdf
- LLM4RE: https://arxiv.org/abs/2509.11446v1 · https://arxiv.org/html/2409.15473v1 · https://arxiv.org/html/2601.16699v1 · https://ceur-ws.org/Vol-4208/pure-short1.pdf
- Open-source RM: https://strictdoc.readthedocs.io/en/stable/strictdoc_20_L1_Open_Requirements_Tool.html · https://docs.rtems.org/docs/6.1/eng/req/tooling.html
