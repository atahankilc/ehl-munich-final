// API shapes for the requirement-definition layer (D-048, api/routers/definition.py; contract in
// foundation/documents/requirement-definition.md → "API").
import type { CheckpointId, TrackState } from "./types";
import type { Orientation, ZoneDef } from "@/three/frame";

export type LineName = "1 Series" | "5 Series" | "7 Series";
export type Basis = "cited" | "projected" | "assumption" | "gap";
export type Rung = "baseline" | "threshold" | "target" | "stretch";
export type ChoosableRung = Exclude<Rung, "baseline">;
export type Relation = "conflicts" | "competes_for" | "enables" | "synergy";
export type Via = "energy" | "mass" | "thermal" | "package" | "attention" | "aero" | "acoustic" | "compute";
/** Track state of a requirement / link; the spec track reports a moved recommended target as "changed". */
export type DefState = TrackState | "changed";

export interface Level {
  value: number | null;
  text: string;
  basis: Basis;
  source_ids: string[];
  note: string;
}

export interface Choice { level: ChoosableRung; rationale: string; actor: string; at: string }

export interface LadderRow {
  line: LineName | string;
  market: string;
  baseline: Level | null;
  threshold: Level;
  target: Level;
  stretch: Level | null;
  recommended: ChoosableRung;
  rationale: string;
  choice?: Choice | null;
}

export interface Metric {
  name: string;
  unit: string;
  direction: "higher" | "lower" | "binary";
  method?: string | null;
  conditions?: string | null;
}

export interface Acceptance { criterion: string; condition: string; pass: string }

export interface Requirement {
  key: string;
  version: number;
  area_key: string;
  area_title: string;
  title: string;
  statement: string;
  domain: string;
  aspects: string[];
  zones: string[];
  lines: string[];
  markets: string[];
  decision_type: string | null;
  today_status: string | null;
  horizon: string | null;
  horizon_year: number | null;
  kano: string | null;
  state: DefState | null;
  change_note: string | null;
  metric: Metric | null;
  acceptance: Acceptance[];
  ladder: LadderRow[];
  gaps: string[];
  assumptions: string[];
  evidence_count: number;
}

export interface LinkReview { verdict: "confirmed" | "removed" | "added"; actor: string; rationale: string; at: string }

export interface DefLink {
  id: string | number;
  a: string;
  b: string;
  relation: Relation;
  via: Via | string;
  strength: 1 | 2 | 3 | number;
  direction: "a_to_b" | "b_to_a" | "mutual";
  rationale: string;
  state: DefState | null;
  review: LinkReview | null;
}

export interface Bundle { id: string; keys: string[]; reason: string }

export interface RunInfo { id: number; finished_at: string | null; stats: Record<string, unknown> }

export interface ModelInfo { url: string | null; orientation: Orientation; attribution?: string | null; stand_in?: string | null }

export interface DefinitionPayload {
  checkpoint: CheckpointId;
  ready: boolean;
  runs: { define: RunInfo | null; specify: RunInfo | null; couple: RunInfo | null };
  domains: { key: string; label: string; aspects: string[] }[];
  resources: Record<string, string>;
  zones: Record<string, ZoneDef>;
  models: Record<string, ModelInfo>;
  requirements: Requirement[];
  links: DefLink[];
  bundles: Bundle[];
}

export interface EvidenceRef {
  id: string | number;
  kind: string;
  text: string;
  url: string | null;
  tier: string | null;
  published: string | null;
  relation: string | null;
  quote: string | null;
}

export interface RequirementDetail extends Requirement {
  evidence: EvidenceRef[];
  facts: Record<string, unknown>[];
  area: { key: string; title: string; need: string } | null;
  history: { checkpoint: string; version: number; change_note: string | null }[];
}

export interface ChoiceBody { key: string; line: string; market: string; level: ChoosableRung; rationale: string; actor: string }
export interface LinkReviewBody {
  a: string; b: string; relation: Relation; verdict: LinkReview["verdict"]; via?: string; strength?: number; rationale: string; actor: string;
}
