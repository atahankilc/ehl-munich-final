// Shapes of the Successor API (contract v1). Codes stay codes here; `labels.ts` turns them into PM language.
export type Priority = "Must" | "Should" | "Could";
export type Evidence = "E1" | "E2" | "E3" | "E4";
export type Status = "proposed" | "challenged" | "approved" | "deferred" | "rejected";
export type FitResult = "pass" | "warn" | "fail" | "overridden";
export type ProposalKind = "priority" | "content" | "link_finding" | "new_requirement" | "extend" | "status";

export interface Target {
  vehicle: string;
  market: string;
  key: string; // "G60×US"
  label: string; // "5 Series · USA"
  car?: string;
  market_label?: string;
}

export interface ZoneDef {
  label: string;
  pos: [number, number, number];
  view: [number, number, number];
  dist: number;
}

export interface WaveInfo {
  label: string;
  simulated_date: string;
  description?: string;
}

export interface Meta {
  actor_default: string;
  vehicles: Record<string, string>;
  markets: Record<string, string>;
  market_names: Record<string, string>;
  targets: Target[];
  focus_targets: string[];
  labels: {
    evidence: Record<string, string>;
    evidence_help: Record<string, string>;
    kano: Record<string, string>;
    horizon: Record<string, string>;
    status: Record<string, string>;
    proposal_kinds: Record<string, string>;
    verdicts?: Record<string, string>;
    fit_types?: Record<string, string>;
    realization?: Record<string, string>;
  };
  priority_bands: { Must: number; Should: number };
  scoring: {
    version: string;
    default_weights: Record<string, number>;
    factor_labels: Record<string, string>;
    confidence: Record<string, number>;
    effort_mod: Record<string, number>;
    market_fit_mod: Record<string, number>;
  };
  editable_fields: string[];
  enums: { horizon: string[]; kano_class: string[]; effort: string[] };
  waves: Record<string, WaveInfo>;
  zones: Record<string, ZoneDef>;
}

export interface AppState {
  current_wave: number;
  wave: WaveInfo | null;
  next_wave: number | null;
  waves_opened: { wave: number; ts: string; actor: string }[];
  spend_usd: number;
  budget: { warn: number; block_non_demo: number; hard_stop: number; total: number };
  running_job: { id: string; kind: string } | null;
  counts: {
    to_review: number;
    open_proposals: number;
    open_by_kind: Partial<Record<ProposalKind, number>>;
    decided: number;
    approved: number;
    requirements: number;
    runs: number;
  };
}

export interface Factor {
  label: string;
  value: number | null;
  weight: number;
  points: number | null;
  available: boolean;
  explanation: string;
}

export interface Breakdown {
  version: string;
  wave?: number;
  score: number;
  base: number;
  evidence_level: Evidence;
  confidence: number;
  modifiers: Record<string, number>;
  factors: Record<string, Factor>;
  gaps: string[];
  gates: Record<string, string | null>;
  verbatims?: { verbatims: number; severity_weighted?: number; channels?: string[] };
  voice_observed?: boolean;
  priority?: Priority;
  cap_note?: string;
  priority_note?: string;
  rationale: string;
  voice_base?: number | null;
  dimensions?: { customer: number | null; business: number | null };
  calibration?: { kind: string; factor: number; note: string } | null;
}

export interface TargetRow {
  target: Target;
  realization: string | null;
  score: number | null;
  ai_priority: Priority | null;
  pm_priority: Priority | null;
  priority: Priority | null;
  ai_only: boolean;
  evidence_level: Evidence | null;
  market_note: string | null;
  brand_gate: FitResult | "–" | null;
  rank: number | null;
}

export interface RequirementSummary {
  id: string;
  title: string;
  category: string;
  status: Status;
  version: number;
  horizon: string | null;
  kano_class: string | null;
  kano_drift: string | null;
  must_not_lose: boolean;
  effort: string | null;
  evidence_level: Evidence | null;
  max_score: number | null;
  best_target: Target | null;
  zone: string;
  brand_blocked: string[];
  targets: TargetRow[];
}

export interface Quote {
  external_id: string;
  market: string;
  country?: string;
  quote: string;
  finding_id?: number;
}

export interface FitRow {
  target: Target;
  check_type: string;
  result: FitResult;
  rationale: string;
  checked_by: string;
  checked_at: string;
}

export interface ChallengeAnswer {
  verdict: "upheld" | "partially_upheld" | "not_upheld";
  answer: string;
  evidence_for: string[];
  evidence_against: string[];
  proposed_edits: { field: string; new_value: string; reason: string }[];
  link_finding_ids: number[];
}

export interface Proposal {
  id: number;
  kind: ProposalKind;
  status: "open" | "accepted" | "rejected" | "superseded";
  requirement_id: string;
  requirement_title: string;
  requirement_status: Status;
  target: Target | null;
  vehicle?: string | null;
  market?: string | null;
  field: string;
  old_value: string | null;
  proposed_value: string | null;
  reason: string | null;
  run: { id: number; ts: string; trigger: string } | null;
  delta: Record<string, unknown> | null;
  finding?: { id: number; source_kind: string; title: string; summary: string } | null;
  findings?: { id: number; source_kind: string; title: string }[];
  decided_by: string | null;
  decided_at: string | null;
  decision_rationale: string | null;
}

export interface RequirementDetail extends Omit<RequirementSummary, "targets"> {
  description: string | null;
  target_metric: string | null;
  acceptance_criteria: string | null;
  assumptions: string | null;
  uncertainties: string | null;
  conflicting_evidence: string | null;
  created_by: string | null;
  created_at: string;
  derivation: {
    product_decision?: string;
    evidence_summary?: string;
    horizon_reason?: string;
    effort_reason?: string;
    supporting_finding_ids?: number[];
    conflicting_finding_ids?: number[];
    wave?: number;
    prompt?: string;
  } | null;
  assumptions_list: string[];
  uncertainties_list: string[];
  targets: (TargetRow & {
    breakdown: Breakdown | null;
    voice: { verbatims: number; base: number | null; share: number | null; own: boolean } | null;
  })[];
  overridden: string[];
  quotes: Quote[];
  study: { finding_id: number; title: string; type: string; market: string | null; vehicle: string | null; mean?: number; z?: number; scale?: string }[];
  web: { finding_id: number; title: string; type: string; best_tier: string | null; publishers: string[]; newest_date: string | null }[];
  contradicting: { finding_id: number; title: string; source_kind: string }[];
  fit: FitRow[];
  open_proposals: Proposal[];
  challenges: { asked_at: string; actor: string; question: string; answered_at: string | null; model: string | null; answer: ChallengeAnswer | null }[];
}

export interface FeedItem {
  id: string;
  ts: string;
  kind: "proposal" | "decision" | "run" | "wave" | "challenge";
  title: string;
  detail: string | null;
  req_id: string | null;
  target: Target | null;
  actor_type: "human" | "ai" | "system";
  actor: string;
  chip: { text: string; tone: "up" | "down" | "neutral" | "warn" } | null;
}

export interface PulseCell {
  target: Target;
  n: number;
  must: number;
  should: number;
  could: number;
  approved: number;
  pm_confirmed: number;
  voice_base: number;
  gaps: string[];
  top: { req_id: string; title: string; score: number; priority: Priority } | null;
}

export interface Briefing {
  wave: { n: number; label: string; simulated_date: string };
  run: { id: number; ts: string; trigger: string; initiated_by: string } | null;
  previous_run_id: number | null;
  headline: { new_requirements: number; priority_changes: number; risers: number; fallers: number; merges_open: number; conflicts: number };
  movers: { req_id: string; title: string; target: Target; score_old: number | null; score_new: number | null; delta: number; priority_old: Priority | null; priority_new: Priority | null; cause: string | null }[];
  new_requirements: { req_id: string; title: string; category: string; max_score: number | null; best_target: Target | null; reason: string | null }[];
  feed: FeedItem[];
  pulse: PulseCell[];
  decisions_waiting: number;
}

export interface QueueItem {
  uid: string;
  type: "requirement" | "proposal";
  kind: "review" | "challenged" | "priority" | "extend" | "content" | "link_finding" | "new_requirement";
  req_id: string;
  title: string;
  subtitle: string | null;
  score: number | null;
  priority: Priority | null;
  target: Target | null;
  created_at: string | null;
  run_id: number | null;
  is_new_in_wave?: boolean;
  proposal_id?: number;
}

export interface CarRequirement {
  id: string;
  title: string;
  category: string;
  status: Status;
  zone: string;
  priority: Priority;
  ai_only: boolean;
  score: number;
  evidence_level: Evidence | null;
  kano_class: string | null;
  horizon: string | null;
  product_decision: string | null;
  description: string | null;
  markets: { market: string; label: string; priority: Priority | null; ai_only: boolean; score: number | null }[];
}

export interface CarPayload {
  vehicle: string;
  car: string;
  market: string;
  markets: { market: string; label: string; n: number; must: number; should: number; could: number; voice_base: number; gaps: string[] }[];
  model: {
    url: string | null;
    shared_with: string | null;
    orientation: { up: string; front: string };
    attribution: { name: string; author: string; license: string; source_url: string };
  };
  zones: Record<string, ZoneDef>;
  requirements: CarRequirement[];
  comparison: { id: string; title: string; zone: string; cells: Record<string, { priority: Priority | null; score: number | null; ai_only: boolean } | null>; spread: number; differs: boolean }[];
  market_profile: { code: string; name: string; climate: string | null; usage_patterns: string | null; cultural_expectations: string | null; infrastructure: string | null; powertrain_mix: string | null } | null;
  competitors: { id: string; name: string; brand: string; segment: string | null; strengths: string | null; markets: string[] }[];
  equipment: Record<string, { name: string; availability: string }[]>;
  equipment_note: string;
  configurator_url: string | null;
  production: { plant: string; country: string; market_variant: string | null; markets_served: string[] }[];
  successor_launch: string | null;
}

export interface Job {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  started_at: string;
  finished_at: string | null;
  log: string[];
  error: string | null;
  result: unknown;
}

// Evidence ------------------------------------------------------------------------------------------------
export type FindingKind = "verbatim" | "study" | "web";
export type MarketCode = "US" | "EU" | "CN" | "RoW";

export interface FindingRow {
  id: number;
  source_kind: FindingKind;
  type: string;
  category: string | null;
  title: string;
  summary: string | null;
  vehicle: string | null;
  market: string | null;
  polarity: "pain_or_want" | "like" | "context" | string | null;
  first_wave: number | null;
  scope: string;
  verbatims: number;
  by_market: Partial<Record<MarketCode, number>>;
  n_sources: number;
  n_requirements: number;
}

export interface FindingsPage {
  total: number;
  used: number;
  uncovered: number;
  metrics_wave: string;
  items: FindingRow[];
}

export interface FindingMarketMetrics {
  verbatims?: number;
  share?: number;
  base?: number;
  severity_weighted?: number;
  types?: Record<string, number>;
  severity?: Record<string, number>;
  channels?: Record<string, number>;
  engines?: Record<string, number>;
  countries?: Record<string, number>;
  support_questions?: number;
}

export interface FindingDetail {
  id: number;
  source_kind: FindingKind;
  type: string;
  category: string | null;
  title: string;
  summary: string | null;
  vehicle: string | null;
  market: string | null;
  polarity: string | null;
  first_wave: number | null;
  scope_level?: string | null;
  created_by?: string | null;
  metrics: Record<string, unknown> & {
    // study
    mean?: number; z?: number; scale?: string; rank?: number; n_items?: number;
    // web
    n_sources?: number; tiers?: Record<string, number>; publishers?: string[]; newest_date?: string | null;
  };
  markets?: Record<string, FindingMarketMetrics>;
  n_sources: number;
  n_signals: number;
  metrics_wave: string;
  used_by: { req_id: string; title: string; status: Status; relation: "supports" | "contradicts" | string }[];
}

export interface FindingSource {
  id: number;
  kind: "feedback" | "study" | "web" | "sales" | "option_list" | "reference" | string;
  external_id: string | null;
  ref: string | null;
  country: string | null;
  market: string | null;
  vehicle: string | null;
  url: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  trust_tier: string | null;
  wave: number | null;
  relation: string | null;
  quote: string | null;
  text: string | null;
  meta: Record<string, unknown> & {
    channel?: string; engine?: string; publisher?: string; scale?: string; mean?: number;
    z_within_column?: number; rank_within_column?: number; n_items_in_column?: number; competitor?: string;
  };
}

export interface FindingSignal {
  signal_id: number;
  feedback_type: "like" | "complaint" | "want" | "defect" | "difficult_to_use" | string;
  severity: "low" | "medium" | "high" | string | null;
  category: string | null;
  topic: string | null;
  need_statement: string | null;
  quote: string | null;
  quote_verified: boolean;
  support_question: boolean;
  extractor_version?: string;
  source: { id: number; external_id: string; market: string | null; country: string | null; vehicle: string | null; channel: string | null; wave: number | null };
}

export interface QualityItem {
  finding_id: number;
  vehicle: string | null;
  car?: string;
  category: string | null;
  title: string;
  summary: string | null;
  n_signals: number;
  defect_share: number;
  n_high: number;
  markets: Record<string, number | null>;
  cited_by: string[];
  quotes?: { external_id: string; market: string | null; quote: string }[];
}

export interface QualityPayload {
  n_issues: number;
  n_signals: number;
  n_high: number;
  n_cited: number;
  defect_share_min?: number;
  metrics_wave?: string;
  items: QualityItem[];
}

// Process -------------------------------------------------------------------------------------------------
export type WaveState = "done" | "now" | "next" | "later";

export interface WaveRow {
  n: number;
  label: string;
  simulated_date: string;
  description?: string | null;
  state: WaveState;
  opened: { ts: string; actor: string } | null;
  brought: { feedback?: number; study?: number; sales?: number; web?: number } | null;
  run: { id: number; targets_scored: number; proposals: number } | null;
}

export interface RunRow {
  id: number;
  ts: string;
  trigger: string;
  initiated_by: string | null;
  weights_version_id: number | null;
  model: string | null;
  wave: number | null;
  targets_scored: number;
  proposals: number;
  note: string | null;
}

export interface RunDiffRow {
  req_id: string;
  title: string;
  target_key: string;
  score_old: number | null;
  score_new: number | null;
  delta: number | null;
  rank_old: number | null;
  rank_new: number | null;
  rank_move: number | null;
  change: string | null; // "" | "new" | "dropped" | "Should → Could"
  cause: string | null;
}

export interface RunDiff {
  weight_changes: { factor: string; label?: string; old: number | null; new: number | null }[];
  rows: RunDiffRow[];
  stats: { compared: number; moved: number; priority_changed: number; new_or_dropped: number };
}

export interface WeightsPayload {
  current: { id: number | null; weights: Record<string, number>; created_by: string | null; created_at: string | null; rationale: string | null } | null;
  defaults: Record<string, number>;
  labels?: Record<string, string>;
  help?: Record<string, string>;
  min?: number;
  max?: number;
}

export type ActorType = "human" | "ai" | "system";

export interface AuditEvent {
  id: number;
  ts: string;
  actor_type: ActorType;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  rationale: string | null;
  model: string | null;
  prompt_ref: string | null;
  run_id: number | null;
}

/** Facet lists may come as plain values, {value, n} rows or a value→count map; the screen normalises them. */
export type AuditFacet = string[] | { value: string; n?: number; label?: string }[] | Record<string, number>;

export interface AuditPage {
  total: number;
  shown?: number;
  by_actor_type?: Partial<Record<ActorType, number>>;
  facets: {
    actor_types?: AuditFacet;
    actors?: AuditFacet;
    actions?: AuditFacet;
    entity_types?: AuditFacet;
    min_ts?: string | null;
    max_ts?: string | null;
  };
  items: AuditEvent[];
}

export interface BudgetPayload {
  spent: number;
  committed: number;
  thresholds: { warn: number; block_non_demo: number; hard_stop: number };
  total?: number;
  calls: number;
  cache_entries: number;
  by_job: { job: string; calls: number; usd: number; reserved?: number }[];
  by_group?: { job_group: string; calls: number; usd: number }[];
  by_model: { model: string; kind: string; calls: number; usd: number; input_tokens: number; cached_tokens: number; output_tokens: number; searches: number }[];
  by_status: { status: string; calls: number; usd: number }[];
}

export interface PipelineStats {
  sources_by_kind: Record<string, number>;
  extractor_version?: string | null;
  extracted: number;
  in_scope: number;
  signals: number;
  unverified_quotes?: number;
  findings_by_kind: Record<string, number>;
  requirements_by_status: Partial<Record<Status, number>>;
  reqs_with_fit: number;
  runs: number;
  open_proposals: number;
  audit_events: number;
  match_existing_events?: number;
  fit_matrix: { check_type: string; result: string; n: number }[];
  trust_tiers?: { kind: string; tier: string | null; n: number }[];
  spend_by_prefix?: Record<string, { calls: number; usd: number }>;
}

export type DemoSnapshot = string | { name: string; created_at?: string | null; wave?: number | null; size?: number | null; description?: string | null };
