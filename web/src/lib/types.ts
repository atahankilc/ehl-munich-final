// API shapes for the checkpoint world (api/routers/scan.py).

export type CheckpointId = "cp1" | "cp2";
export type TrackState = "new" | "held" | "strengthened" | "weakened" | "lost";
export type SourceKind = "feedback" | "study" | "sales" | "option_list" | "research" | "web" | "reference";

export interface Checkpoint {
  id: CheckpointId;
  label: string;          // "JAN 26"
  cutoff: string;         // ISO date
  parent_id: CheckpointId | null;
  position: number;       // 1, 2
  sources: Record<SourceKind, { visible: number; new: number }>;
  acquire: { run_id: number; parent_run_id: number | null; tracks: Record<TrackState, number> } | null;
}

export interface PointsPayload {
  n: number;
  dict: { car: string[]; market: string[]; channel: string[]; engine: string[]; type: (string | null)[] };
  cols: {
    id: number[]; x: number[]; y: number[]; z: number[];
    car: number[]; market: number[]; channel: number[]; engine: number[]; type: number[];
    len: number[]; cp: number[];   // cp = checkpoint position at which the comment becomes visible
  };
}

export interface Comment {
  id: number; external_id: string; car: string; market: string; country: string; text: string;
  channel: string | null; engine: string | null; checkpoint: CheckpointId; ref: string;
  bmw_labels: { feedback_type: string | null; vfc_level2: string | null; vfc_level3: string | null }[];
}

export interface ResearchItem {
  id: number; cars: string[]; ring: "sales" | "study" | "options" | null; market: string | null; region: string | null; tier: string | null; topic: string | null;
  kind: string | null; entity: string | null; published_at: string | null; headline: string;
  yoy: number | null; value: number | null; unit: string | null; pair_key: string | null; url: string | null;
  new: boolean;
}

export interface OptionItem {
  id: number; car: string; code: string | null; name: string | null; category: string | null;
  availability: string | null; package: string | null;
}
export interface SalesRow { car: string; market: string; year: number; units: number | null; is_forecast: number }
export type StudyItem = { id: number; car: string; market: string; scale: string; item: string; z: number | null; value: number | null };

/** Anything on the scan the PM can open. */
export type Selection =
  | { kind: "comment"; id: number }
  | { kind: "study"; item: StudyItem }
  | { kind: "option"; item: OptionItem }
  | { kind: "sales"; item: SalesRow }
  | { kind: "research"; item: ResearchItem }
  | { kind: "cluster"; key: string }
  | { kind: "theme"; key: string }
  | { kind: "area"; key: string };

export interface SourcesPayload {
  checkpoint: CheckpointId;
  sales: SalesRow[];
  study: StudyItem[];
  options: OptionItem[];
  research: ResearchItem[];
  web: { n: number; new: number };
}

/* ---------------------------------------------------------------- structure & context (api/routers/structure.py) */
export interface ClusterNode {
  key: string; polarity: "like" | "improve" | null; category: string | null; state: TrackState | null;
  comments: number; signals: number; tail: boolean; aspects: Record<string, number> | null;
  by_line_market: Record<string, number> | null; x: number; y: number; z: number; theme: string | null;
  insight: { title: string; statement: string; need_type: string; quality_issue: boolean } | null;
}
export interface ThemeNode {
  key: string; title: string; statement: string; category: string; state: TrackState | null; comments: number;
  clusters: string[]; x: number; y: number; z: number;
}
export interface EvidenceEdge {
  src_type: string; src_id: string; dst_type: string; dst_id: string; relation: string; why: string | null; state: TrackState | null;
}
/** D-046: the markets an area's comments come from, with BMW's (stylized, weight-only) volume share, the latest
 *  cited public sales trend and whether BMW's file and public figures disagree there. */
export interface AreaMarket {
  label: string; bmw_volume_share: number;
  markets: { key: string; comments: number; bmw_share: number | null; conflict: boolean;
             trend: { yoy: number; period: string; region: string; tier: string | null; source_id: number } | null }[];
}
export interface AreaNode {
  id: number; key: string; title: string; need: string; kind: "improve" | "keep" | "emerging" | "quality";
  themes: string[]; why_now: string | null; open_questions: string[]; change_note: string | null; state: TrackState | null;
  metrics: { comments?: number; themes?: number; by_line_market?: Record<string, number>; evidence?: Record<string, number>;
             market?: AreaMarket };
}
export interface StructurePayload {
  checkpoint: CheckpointId; ready: boolean;
  stages?: Record<string, boolean>;
  clusters: ClusterNode[]; themes: ThemeNode[]; edges: EvidenceEdge[]; areas: AreaNode[];
  member: { ids: number[]; cluster: number[] };
  funnel: Record<"classify" | "cluster" | "contextualize" | "areas", Record<string, unknown> | null>;
}
export interface SignalRow {
  id: number; aspect: string | null; category: string; nature: string | null; want_kind: string | null; intensity: number | null;
  impact: string | null; occupant: string | null; need_statement: string | null; quote: string | null; quote_verified: number;
  explicit: number | null; future_cue: number | null; benchmark: string | null; benchmark_name: string | null; source_kind: string | null;
}
