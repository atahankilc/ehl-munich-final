// API shapes for page 5, Document (api/routers/document.py; foundation/documents/document.md): the deliverable — the
// traceable requirement list per car line × market at a checkpoint.
import type { CheckpointId } from "./types";
import type { Band, GateValue, Proposal } from "./prioritize";
import type { Acceptance, LadderRow, Metric } from "./definition";

export type DocProposal = Omit<Proposal, "status"> & { status: Proposal["status"] | "superseded"; checkpoint: string; explain?: string | null };
export type DocStatus = "confirmed" | "ai_proposal" | "open_proposal" | "open_proposal_against_pm";

export interface DocHeader {
  checkpoint: CheckpointId;
  label: string;
  cutoff: string;
  line: string;
  market: string;
  generated_at: string;
  run: { id: number; finished_at: string } | null;
  weights_version: number | string;
  scheme: string;
  band_thresholds: { Must: number; Should: number };
  lines: string[];
  markets_by_line: Record<string, string[]>;
  by_band: Partial<Record<Band, number>>;
  ai_by_band: Partial<Record<Band, number>>;
  count: number;
  confirmed: number;
  open_proposals: number;
}

export interface DocQuote { quote: string; source_id: number; external_id: string; market: string | null; line: string | null }
export interface DocEvidence {
  id: string;
  kind: string;
  text: string | null;
  url: string | null;
  tier: string | null;
  published: string | null;
  relation: string | null;
  quote: string | null;
  quotes?: DocQuote[];
}

export interface DocLink { key: string; title: string | null; relation: string; via: string | null; strength: number; rationale: string | null; source: "ai" | "pm"; status: string }
export interface DocHistory { checkpoint: CheckpointId; label: string; score: number; band: Band; rank: number; confirmed: Band | null }
export interface DocDecision { priority: Band; rationale: string; actor: string; at: string; checkpoint: string | null }
export interface DocFactor { key: string; label: string; dimension: string; weight: number; points: number; value: number | null; available: boolean; explanation: string }

export interface DocItem {
  key: string;
  id: string;
  number: number;
  version: number;
  title: string;
  statement: string | null;
  domain: string;
  area: { key: string; title?: string; need?: string; kind?: string } | null;
  horizon: string | null;
  horizon_year: number | null;
  kano: string | null;
  decision_type: string | null;
  today_status: string | null;
  req_status: string | null;
  metric: Metric | null;
  acceptance: Acceptance[];
  rung: { level: string | null; by: "pm" | "ai"; recommended: string | null; value?: number | null; text?: string | null; basis?: string | null; note?: string | null;
          source_ids?: string[]; choice: { level: string; rationale: string; actor: string; at: string } | null };
  ladder: LadderRow | null;
  priority: { band: Band; ai_band: Band; ai_score: number; base: number; rank: number; own_band: Band | null;
              confirmed: { priority: Band; actor: string; at: string; rationale: string } | null };
  status: DocStatus;
  open_proposal: DocProposal | null;
  rationale: string | null;
  factors: DocFactor[];
  modifiers: { key: string; points: number; why: string }[];
  effort: unknown;
  evidence: { level: string | null; comments: number | null; count: number; items: DocEvidence[]; trend_ids: string[] };
  assumptions: string[];
  gaps: string[];
  uncertainties: string[];
  flags: string[];
  links: DocLink[];
  gates: Record<string, GateValue>;
  track: string | null;
  prev: { score: number; band: Band; checkpoint: string } | null;
  history: DocHistory[];
  proposals: DocProposal[];
  decisions: DocDecision[];
}

export interface DocumentPayload { ready: boolean; header: DocHeader; items: DocItem[] }

export interface ChangeBrief { key: string; id: string; title: string; domain: string; band: Band; ai_band: Band; score: number }
export interface ChangesPayload {
  from: { checkpoint: CheckpointId; label: string };
  to: { checkpoint: CheckpointId; label: string };
  line: string;
  market: string;
  new: ChangeBrief[];
  removed: ChangeBrief[];
  moved: (ChangeBrief & { from: { ai_band: Band; score: number; confirmed: Band | null }; to: { ai_band: Band; score: number; confirmed: Band | null };
             direction: "up" | "down" | "same"; ai_band_changed: boolean; pm_band_changed: boolean })[];
  band_up: number;
  band_down: number;
  decisions: (DocDecision & { key: string; id: string; title: string })[];
  proposals: Record<"accepted" | "rejected" | "open" | "superseded", (DocProposal & { id_human: string; title: string })[]>;
}
