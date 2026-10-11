// The PM's position and challenges to it, shared by the skyline, the matrix and the list (page 4): a confirmed band is
// the one blue mark ("M ✓"); an open proposal against it is white attention ("!", "AI: Should ▼ · cause").
import type { Band, PrioritizePayload, Proposal, Target } from "@/lib/prioritize";
import { CAUSE_LABEL, openProposals, pmBand } from "./data";
import "./risefall.css";

export const BAND_RANK: Record<Band, number> = { Must: 0, Should: 1, Could: 2 };
export interface Challenge { band: Band; from: Band; cause: string }

/** Open proposal against the PM-confirmed band of this target, if any. */
export function challengeOf(d: PrioritizePayload, t: Target): Proposal | null {
  if (!pmBand(t)) return null;
  return openProposals(d).find((p) => p.against === "pm" && p.key === t.key && p.line === t.line && p.market === t.market) ?? null;
}
export const arrow = (to: Band, from: Band | null) => (from && BAND_RANK[to] < BAND_RANK[from] ? "▲" : "▼");

/* ------------------------------------------------------------------------------------------- rise / fall (PM, 2026-10-11)
   After a checkpoint the AI may place a PM-confirmed target in another band than the PM's (open proposal, against "pm").
   DOWN (the proposed band is lower) is the loud red case: the PM's decision is contradicted. UP is the green case: an
   upgrade opportunity. An unconfirmed target whose AI band moved since the previous checkpoint gets the same colours,
   small. Rise / fall colours are used for nothing else (DESIGN.md → Rise/Fall rule). */
export type Dir = "up" | "down";
export const dirOf = (to: Band, from: Band | null | undefined): Dir | null =>
  !from || from === to ? null : BAND_RANK[to] < BAND_RANK[from] ? "up" : "down";

export interface RiseFall { dir: Dir; from: Band; to: Band; cause: string; proposal: Proposal }

/** A PM-confirmed target challenged at this checkpoint, with its direction. */
export function riseFallOf(d: PrioritizePayload, t: Target): RiseFall | null {
  const p = challengeOf(d, t);
  if (!p) return null;
  const from = pmBand(t) ?? p.old_band;
  const dir = dirOf(p.proposed_band, from);
  return dir && from ? { dir, from, to: p.proposed_band, cause: CAUSE_LABEL[p.cause] ?? p.cause, proposal: p } : null;
}

/** Unconfirmed target whose AI band moved since the previous checkpoint (the quiet case). */
export const bandMove = (t: Target): Dir | null => (pmBand(t) || !t.prev ? null : dirOf(t.band, t.prev.band));

/** sort key: downs first, then ups, then the rest */
export const rfRank = (r: RiseFall | null) => (r ? (r.dir === "down" ? 0 : 1) : 2);

/** Challenged PM decisions at this checkpoint, downs first. */
export function challengedAll(d: PrioritizePayload): (RiseFall & { t: Target })[] {
  const out: (RiseFall & { t: Target })[] = [];
  for (const t of d.targets) { const r = riseFallOf(d, t); if (r) out.push({ ...r, t }); }
  return out.sort((a, b) => rfRank(a) - rfRank(b) || BAND_RANK[a.from] - BAND_RANK[b.from]);
}

export function rfSentence(r: Pick<RiseFall, "dir" | "from" | "to" | "cause">, at: string): string {
  return r.dir === "down"
    ? `New evidence at ${at} lowers this below your ${r.from} → AI suggests ${r.to} (cause: ${r.cause.toLowerCase()}). Accept or keep your decision.`
    : `New evidence at ${at} raises this above your ${r.from} → consider upgrading to ${r.to} (cause: ${r.cause.toLowerCase()}).`;
}
