// DEV / DEMO ONLY (`?sample=1`, see prioritize/data.ts → sampleForced): lays page 4's sample PM decisions and challenged
// proposals (prioritize/fixture.ts) over the live document rows of the same requirement × line × market, so the rise /
// fall marks can be seen and screenshotted before any real PM decision exists. Nothing is written anywhere; the page
// shows a "Sample overlay" note while it is on.
import type { DocItem, DocumentPayload } from "@/lib/document";
import { fixtureFor } from "../prioritize/fixture";

export function withSampleDecisions(d: DocumentPayload, cp: string): DocumentPayload {
  const fx = fixtureFor(cp);
  let confirmed = 0, open = 0;
  const items = d.items.map((i): DocItem => {
    const t = fx.targets.find((x) => x.key === i.key && x.line === d.header.line && x.market === d.header.market);
    if (!t?.confirmed) return i;
    confirmed++;
    const p = fx.proposals.find((x) => x.key === i.key && x.line === t.line && x.market === t.market && x.against === "pm");
    if (p) open++;
    return {
      ...i,
      priority: { ...i.priority, band: t.confirmed.priority, ai_band: p ? p.proposed_band : i.priority.ai_band, confirmed: t.confirmed },
      status: p ? "open_proposal_against_pm" : "confirmed",
      open_proposal: p ? { ...p, checkpoint: cp, explain: "sample overlay (?sample=1)" } : i.open_proposal,
    };
  });
  const by_band: DocumentPayload["header"]["by_band"] = {};
  for (const i of items) by_band[i.priority.band] = (by_band[i.priority.band] ?? 0) + 1;
  return { ...d, items, header: { ...d.header, by_band, confirmed: d.header.confirmed + confirmed, open_proposals: d.header.open_proposals + open } };
}
