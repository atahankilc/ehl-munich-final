// The PM's position and challenges to it, shared by the skyline, the matrix and the list (page 4): a confirmed band is
// the one blue mark ("M ✓"); an open proposal against it is white attention ("!", "AI: Should ▼ · cause").
import type { Band, PrioritizePayload, Proposal, Target } from "@/lib/prioritize";
import { openProposals, pmBand } from "./data";

export const BAND_RANK: Record<Band, number> = { Must: 0, Should: 1, Could: 2 };
export interface Challenge { band: Band; from: Band; cause: string }

/** Open proposal against the PM-confirmed band of this target, if any. */
export function challengeOf(d: PrioritizePayload, t: Target): Proposal | null {
  if (!pmBand(t)) return null;
  return openProposals(d).find((p) => p.against === "pm" && p.key === t.key && p.line === t.line && p.market === t.market) ?? null;
}
export const arrow = (to: Band, from: Band | null) => (from && BAND_RANK[to] < BAND_RANK[from] ? "▲" : "▼");
