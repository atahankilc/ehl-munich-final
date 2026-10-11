// API shapes for the prioritization layer (D-050, api/routers/prioritize.py; contract in
// foundation/documents/prioritization.md → "API"). Unit = requirement × car line × market target (D-011).
import type { CheckpointId, TrackState } from "./types";
import type { ChoosableRung, Rung } from "./definition";

export type Band = "Must" | "Should" | "Could";
export const BANDS: Band[] = ["Must", "Should", "Could"];
export type Dimension = "customer" | "business" | "future";
export type GateResult = "pass" | "warn" | "fail" | "unchecked";
/** a gate may arrive as a bare result or with the checker's rationale */
export type GateValue = GateResult | { result: GateResult; rationale?: string | null; checked_by?: string | null };
export type ConfidenceLevel = "E1" | "E2" | "E3" | "E4";
export type ProposalCause = "new_fact" | "area_strengthened" | "market_trend" | "link_changed" | "pm_rung" | "weights_changed" | string;

export interface Factor {
  key: string;                 // customer_voice | satisfaction_gap | competitive_gap | market_weight | portfolio_leverage | future_relevance
  dimension: Dimension;
  value: number | null;        // 0–1, null when not available
  weight: number;              // nominal weight (prio-v1: 30 / 15 / 15 / 10 / 10 / 20)
  points: number;              // after renormalising over the available factors
  explanation: string;
  available: boolean;
}

export interface Modifier { key: string; points: number; why: string }   // effort | market_fit | …

export interface Confidence { level: ConfidenceLevel; mult: number; basis_mix: Record<string, number> }

export interface Confirmed { priority: Band; actor: string; at: string; rationale: string }

export interface Target {
  key: string;
  title: string;
  domain: string;
  zones: string[];
  area_key: string;
  line: string;
  market: string;
  score: number;
  base: number;
  band: Band;                  // the AI's proposed band (bundle-adjusted)
  own_band?: Band | null;      // the band on its own score when a bundle lifted it
  confirmed: Confirmed | null; // the PM's decision, if any
  rank: number;                // within line × market
  state: TrackState | "changed" | null;
  confidence: Confidence;
  factors: Factor[];
  modifiers: Modifier[];
  gates: { brand: GateValue; segment: GateValue; market: GateValue; feasibility: GateValue };
  bundle_id: string | null;
  flags: string[];             // e.g. "choose_jointly|energy|rq:…", "brand_blocked", "volume_conflict", "borrowed_voice"
  rung: { chosen: Rung | null; recommended: ChoosableRung; by?: "pm" | "ai" | "what_if" | null };
  rationale: string;
  prev: { score: number; band: Band } | null;
}

export interface Proposal {
  id: number | string;
  key: string;
  line: string;
  market: string;
  old_band: Band | null;
  proposed_band: Band;
  cause: ProposalCause;
  factor_delta: Record<string, number>;
  /** "pm" = against the PM-confirmed band, "parent" = against the AI's band at the earlier checkpoint */
  against?: "pm" | "parent" | null;
  status: "open" | "accepted" | "rejected";
  decided_by?: string | null;
  decided_at?: string | null;
  decision_rationale?: string | null;
  created_at?: string | null;
}

export interface PrioBundle { id: string; keys: string[]; band_by_target: Record<string, Band>; reason?: string }

export interface PrioRunInfo { id: number; finished_at: string | null; stats: Record<string, unknown> }

export interface PrioritizePayload {
  checkpoint: CheckpointId;
  ready: boolean;
  runs: { prioritize: PrioRunInfo | null; gate: PrioRunInfo | null };
  weights: {
    scheme?: string; version?: string | number; factors?: Record<string, number>; bands?: { Must: number; Should: number };
    /** prio-v1 version as named on the page (v1 = default); `id` = the shared weights_version row */
    id?: number | null; actor?: string | null; at?: string | null; rationale?: string | null; default?: boolean;
  } & Record<string, unknown>;
  /** the automatic re-score after PM actions (api/rescore.py) */
  rescore?: { state: "idle" | "running"; error?: string | null };
  labels: Record<string, string>;
  lines: string[];
  /** market codes; the API may give them per line */
  markets: string[] | Record<string, string[]>;
  targets: Target[];
  bundles: PrioBundle[];
  proposals: Proposal[];
  summary: { by_band: Partial<Record<Band, number>>; by_market: Record<string, Partial<Record<Band, number>>> };
}

export interface TargetDetail extends Target {
  history: { checkpoint: string; score: number; band: Band; rung?: string | null; confirmed?: Band | null }[];
  evidence: { comments?: number; study?: number; research?: number; options?: number; own_market?: boolean } & Record<string, unknown>;
}

export interface WhatIf {
  key: string; line: string; market: string; level: Rung;
  score: number; band: Band; base?: number;
  delta?: number;                                     // vs the stored score
  modifiers?: Modifier[];
  confidence?: Confidence;
  exposures: { key: string; title?: string; via: string; relation: string; note?: string }[];
}

export interface DecisionBody { key: string; line: string; market: string; priority: Band; rationale: string; actor: string; cp?: string }
export interface ProposalBody { verdict: "accept" | "reject"; rationale: string; actor: string }

/** "5 Series|US" — the target's place; with the key in front it identifies one target */
export const targetId = (t: Pick<Target, "key" | "line" | "market">) => `${t.key}|${t.line}|${t.market}`;
export const gateResult = (g: GateValue | undefined | null): GateResult => (!g ? "unchecked" : typeof g === "string" ? g : g.result);
export const gateWhy = (g: GateValue | undefined | null): string | null => (g && typeof g === "object" ? g.rationale ?? null : null);
