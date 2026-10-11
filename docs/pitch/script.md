# SharkSight — 3-minute pitch script

Open `docs/pitch/index.html` in a browser. Use → / Space or click to advance, ← to go back, and `f` for fullscreen.
Target: about 420 spoken words, which is about 2:45. Times are cumulative.

The pitch presents a vision, so it gives no exact counts. If a judge asks, use the facts at the end.

---

**1 · Title (0:00–0:12)**
This is SharkSight. Good product decisions need solid evidence. So we built a broad knowledge base from thousands of raw data points: customer voices, BMW's own data and cited web research. The AI structures it, and the product manager decides what the next BMW must deliver.

**2 · Team (0:12–0:20)**
I'm Atahan, and this is team Zimbabwe. The rest of the team was last seen at kickoff.

**3 · Problem (0:20–0:40)**
A product manager faces thousands of customer comments, customer studies, sales and option lists, and a market that changes every month. Customers in the US, Europe and China want different things. These decisions live for years, so every one of them has to stay traceable. Our app moves from evidence to structure to definition, and the PM decides at every step.

**4 · Evidence (0:40–1:02)**
First, every source lives in one space: what customers say, BMW's own data, and cited research from the world, each with a source, a date and a trust level. And it is live: new data keeps flowing in, every update builds on the last, and you always see what changed. We are also honest about data: when internal figures conflict with public ones, we show the conflict instead of hiding it.

**5 · Structure (1:02–1:30)**
Then the AI reads everything. It classifies comments, studies and research into one shared language, clusters them into customer needs, and links each need to the world: what supports it, what contradicts it, and where rivals compete. The result is a set of requirement areas. New data only counts as a trend if it is statistically real, and defects go to Quality, not into requirements.

**6 · Definition (1:30–2:05)**
Then we answer BMW's question: "Range: 600 or 700 miles?" Each area becomes measurable requirements. Each one gets a metric the customer actually feels and a target ladder for each car and market: today's BMW, rival parity, a target projected to launch, and a stretch goal. Every number is marked as cited, projected, an assumption or a gap, and the AI never invents one. The AI recommends a rung, and the PM picks it. Requirements are linked like the roof of a House of Quality. For example, range and agility compete through mass. And all of it sits on the 3D car.

**7 · Trust (2:05–2:25)**
The AI only proposes; a named person decides, and every decision needs a reason. Every requirement traces back to its evidence. Nothing is overwritten, every decision is audited, and every model call is logged with its cost.

**8 · Vision (2:25–2:40)**
Our vision is a product brain that keeps learning across every car line and market. Next comes prioritization per market, where linked requirements are bundled and conflicts are decided together. Let me show you live.

---

## Facts for questions (not on the slides)

- Sources: 10,128 feedback, 391 study, 458 options, 24 sales rows, 1,028 research, 245 web, 96 reference items (`source_item`).
- Structure: 562 clusters; 8,978 evidence edges; 37 areas at cp1, 41 at cp2 (D-043, D-046, D-047).
- Definition (D-048): 76 `def_requirement` (all with evidence ids), 73 `def_link`, 246 `spec_fact`. These are cp1 only, and cp2 is in progress. The cp1 ladders and the conflict links were being re-tuned on 2026-10-11.
- Audit: 2,193 `audit_event`. Spend: $10.95 in `llm_usage`.
- Don't claim: deployment (nothing is deployed), a brand-fit gate in the new pipeline, or prioritization (it is the next layer).
