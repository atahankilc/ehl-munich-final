# Checkpoint research schema

Two checkpoints. An item belongs to the checkpoint at which a PM could have known it (source published on or before the cut-off):

| checkpoint | cut-off | typical period covered |
|---|---|---|
| `2026-01` | published ≤ 2026-01-31 | FY2025, Q4 2025, Dec 2025, forecasts for 2026 made in Dec/Jan |
| `2026-07` | published 2026-02-01 … 2026-07-31 | H1 2026, Q2 2026, Jun 2026, mid-year forecast revisions |

Anything published after 2026-07-31 is out (do not record it).

Each raw file `raw/<topic>.json`:

```json
{
  "topic": "<topic>",
  "retrieved_at": "2026-10-11",
  "items": [
    {
      "id": "kebab-case-unique-id",
      "checkpoint": "2026-01 | 2026-07",
      "kind": "metric | event | trend | study | policy",
      "region": "GLOBAL | EU | DE | UK | US | CN | JP | KR",
      "entity": "market | <brand> | <brand model>",
      "segment": "compact_premium | executive | luxury | premium_all | mass | all | null",
      "powertrain": "BEV | PHEV | EREV | HEV | ICE | all | null",
      "metric": "deliveries | registrations | retail_sales | market_share | bev_share | nev_share | yoy | price | rating | survey_share | other | null",
      "period_covered": "FY2025 | Q4-2025 | Dec-2025 | H1-2026 | Q2-2026 | Jun-2026 | ...",
      "value": 123456,
      "unit": "units | pct | usd | eur | cny | km | kw | points | null",
      "yoy_pct": -12.5,
      "headline": "<= 12 words, plain",
      "driver": "<= 30 words: why it happened, as stated by the source (not your opinion)",
      "customer_relevance": "<= 25 words: what it suggests for premium car buyers' needs (this is an assumption)",
      "pair_key": "same string for the matching item at the other checkpoint, e.g. 'mercedes-cn-deliveries'",
      "source": { "url": "...", "publisher": "...", "published_at": "YYYY-MM-DD", "trust_tier": "T1 | T2 | T3" },
      "quote": "verbatim snippet from the page (<= 300 chars) that contains the value/claim",
      "verified": true,
      "notes": "conflicts with other sources, definitions (e.g. EU vs EU+EFTA+UK), caveats"
    }
  ],
  "gaps": ["what you searched for and could not find with a citable source"]
}
```

Trust tiers: T1 = OEM press releases / annual or quarterly reports, registration statistics (ACEA, KBA, SMMT, CPCA, CAAM, Cox/KBB for US); T2 = Reuters, Bloomberg, Automotive News, CnEVPost, Gasgoo, J.D. Power, McKinsey, Deloitte, S&P Global Mobility, Consumer Reports; T3 = blogs, forums, aggregators.

Rules: never invent a number; `verified: true` only if you fetched the page and the quote is on it; prefer T1; when sources disagree, record both and say so in `notes`; record a matching item at the other checkpoint (same `pair_key`) whenever one exists so the two periods can be compared.
