// PM language for the data model's codes (same wording as the previous app; AGENTS: keep current terms).
import type { Evidence, Priority, Status } from "./types";

export const CAR: Record<string, string> = { F70: "1 Series", G60: "5 Series", G68: "5 Series LWB", G70: "7 Series" };
export const MARKET: Record<string, string> = { US: "USA", EU: "Europe", CN: "China", RoW: "Rest of world" };
export const MARKET_LONG: Record<string, string> = { US: "United States", EU: "Europe", CN: "China", RoW: "Rest of world" };
export const EVIDENCE: Record<Evidence, string> = {
  E1: "Strong evidence",
  E2: "Good evidence",
  E3: "Limited evidence",
  E4: "Assumption only",
};
export const EVIDENCE_HELP: Record<Evidence, string> = {
  E1: "20+ customer comments from 2+ channels, plus study or cited web evidence",
  E2: "15+ comments, or comments plus study/web evidence",
  E3: "a few comments, or study/web evidence only",
  E4: "no direct evidence — forward-looking assumption",
};
export const KANO: Record<string, string> = { basic: "Expected", performance: "Differentiator", delighter: "Delighter" };
export const HORIZON: Record<string, string> = { today: "Needed today", at_successor_launch: "Needed by successor launch" };
export const STATUS: Record<Status, string> = {
  proposed: "To review",
  challenged: "Challenged",
  approved: "Approved",
  deferred: "Deferred",
  rejected: "Rejected",
};
export const PROPOSAL_KIND: Record<string, string> = {
  priority: "Priority change",
  content: "Content edit",
  link_finding: "Evidence link",
  new_requirement: "New requirement",
  extend: "Merge into existing",
  status: "Status",
  review: "To review",
  challenged: "Challenged",
};
export const VERDICT: Record<string, string> = {
  upheld: "You're right",
  partially_upheld: "Partly right",
  not_upheld: "The evidence holds",
};
export const FIT_TYPE: Record<string, { label: string; effect: string }> = {
  brand: { label: "Brand fit", effect: "Gate — a fail blocks approval" },
  compliance: { label: "Compliance", effect: "Gate — a fail blocks approval" },
  segment: { label: "Segment fit", effect: "Shown for context" },
  market: { label: "Market fit", effect: "Adjusts the score" },
  feasibility: { label: "Plant & platform", effect: "Context only, never blocks" },
};
export const REALIZATION: Record<string, string> = {
  carry_over: "Carry over",
  platform_wide: "Platform-wide",
  derivative_specific: "This car only",
  market_variant: "Market variant",
  package: "Package",
};
export const PRIORITIES: Priority[] = ["Must", "Should", "Could"];
export const BANDS = { Must: 60, Should: 45 } as const;

export const car = (v?: string | null) => (v ? CAR[v] ?? v : "–");
export const mkt = (m?: string | null) => (m ? MARKET[m] ?? m : "–");
export const targetLabel = (key: string) => {
  const [v, m] = key.split("×");
  return `${car(v)} · ${mkt(m)}`;
};
export const bandOf = (score: number | null | undefined): Priority | null =>
  score == null ? null : score >= BANDS.Must ? "Must" : score >= BANDS.Should ? "Should" : "Could";
