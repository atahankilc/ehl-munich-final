// Sample data for page 4 (Prioritize) while the prioritize stage has not run (the API 404s or says ready: false).
// Built from the live cp1 definition (requirement keys, titles, domains, zones of /api/definition?cp=cp1) and scored
// with the prio-v1 formula of foundation/documents/prioritization.md, so the page behaves like the real thing: weighted
// factors → base, × confidence, + effort and market-fit modifiers, bands Must ≥ 60 · Should ≥ 45 · Could. Factor values
// are illustrative, never evidence; the page labels them "Sample data".
import type { Rung } from "@/lib/definition";
import type {
  Band, Confidence, ConfidenceLevel, Factor, GateValue, Modifier, PrioBundle, PrioritizePayload, Proposal, Target, TargetDetail, WhatIf,
} from "@/lib/prioritize";

/* ------------------------------------------------------------------------------------------------ the formula */
export const FACTORS: { key: string; dimension: Factor["dimension"]; weight: number; label: string }[] = [
  { key: "customer_voice", dimension: "customer", weight: 30, label: "Customer voice" },
  { key: "satisfaction_gap", dimension: "customer", weight: 15, label: "Satisfaction gap" },
  { key: "competitive_gap", dimension: "business", weight: 15, label: "Competitive gap" },
  { key: "market_weight", dimension: "business", weight: 10, label: "Market weight" },
  { key: "portfolio_leverage", dimension: "business", weight: 10, label: "Portfolio leverage" },
  { key: "future_relevance", dimension: "future", weight: 20, label: "Future relevance" },
];
export const BAND_AT = { Must: 60, Should: 45 };
export const bandOf = (score: number, at = BAND_AT): Band => (score >= at.Must ? "Must" : score >= at.Should ? "Should" : "Could");
export const CONF_MULT: Record<ConfidenceLevel, number> = { E1: 1, E2: 0.92, E3: 0.75, E4: 0.5 };
const EFFORT_PTS = { S: 0, M: -3, L: -6 } as const;
type Effort = keyof typeof EFFORT_PTS;
const FIT_PTS = { pass: 2, warn: -5, fail: -10, unchecked: 0 } as const;

type F6 = [number | null, number | null, number | null, number | null, number | null, number | null];

const r1 = (x: number) => Math.round(x * 10) / 10;

export function scoreFrom(f6: F6, level: ConfidenceLevel, effort: Effort, fit: keyof typeof FIT_PTS) {
  const avail = FACTORS.reduce((s, f, i) => s + (f6[i] == null ? 0 : f.weight), 0) || 1;
  const factors: Factor[] = FACTORS.map((f, i) => {
    const v = f6[i];
    return { key: f.key, dimension: f.dimension, value: v, weight: f.weight, available: v != null,
             points: v == null ? 0 : r1((v * f.weight * 100) / avail), explanation: "" };
  });
  const base = r1(factors.reduce((s, f) => s + f.points, 0));
  const mult = CONF_MULT[level];
  const modifiers: Modifier[] = [
    { key: "effort", points: EFFORT_PTS[effort], why: `Effort ${effort}` },
    { key: "market_fit", points: FIT_PTS[fit], why: fit === "pass" ? "Market fit passes" : fit === "warn" ? "Market fit has a warning" : fit === "fail" ? "Market fit fails" : "Market fit not checked" },
  ];
  const score = r1(Math.max(0, Math.min(100, base * mult + modifiers.reduce((s, m) => s + m.points, 0))));
  return { factors, base, mult, modifiers, score };
}

/* ------------------------------------------------------------------------------------------------ requirements (live cp1 keys) */
interface Seed { title: string; domain: string; zone: string; kano: string; decision: string; horizon: "today" | "at_successor_launch" }
const SEEDS: Record<string, Seed> = {
  "rq:easy-common-controls:0": { title: "Provide direct physical access to frequent driving functions", domain: "digital", zone: "cockpit", kano: "basic", decision: "change_design", horizon: "at_successor_launch" },
  "rq:easy-common-controls:1": { title: "Separate controls to make intentional operation clear", domain: "digital", zone: "cockpit", kano: "basic", decision: "change_design", horizon: "today" },
  "rq:practical-premium-touchpoints:0": { title: "Provide substantial, tactile physical cabin controls", domain: "digital", zone: "cockpit", kano: "performance", decision: "change_design", horizon: "at_successor_launch" },
  "rq:confident-real-world-range:0": { title: "Increase usable electric range across everyday conditions", domain: "powertrain", zone: "underfloor", kano: "performance", decision: "raise_capability", horizon: "at_successor_launch" },
  "rq:convenient-reliable-charging:2": { title: "Reduce time spent charging", domain: "powertrain", zone: "charging", kano: "performance", decision: "raise_capability", horizon: "today" },
  "rq:effortless-climate-comfort:0": { title: "Increase prompt, sustained cabin heating and cooling", domain: "interior", zone: "cabin", kano: "performance", decision: "raise_capability", horizon: "today" },
  "rq:engaging-driving-dynamics:0": { title: "Preserve engaging, confident BMW handling", domain: "chassis", zone: "chassis", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:dependable-driving-parking-assistance:0": { title: "Expand assistance for tight parking maneuvers", domain: "assist", zone: "front", kano: "performance", decision: "raise_capability", horizon: "at_successor_launch" },
  "rq:understandable-digital-features:0": { title: "Prioritize everyday functions in the interface", domain: "digital", zone: "cockpit", kano: "basic", decision: "change_design", horizon: "at_successor_launch" },
  "rq:transparent-digital-services:0": { title: "Let customers organize their in-car apps", domain: "digital", zone: "cockpit", kano: "performance", decision: "change_design", horizon: "today" },
  "rq:quiet-smooth-ride:0": { title: "Preserve a peaceful cabin at speed", domain: "interior", zone: "cabin", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:quiet-smooth-ride:1": { title: "Preserve a supple, relaxing ride", domain: "chassis", zone: "chassis", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:suitable-tires-wheels:1": { title: "Offer comfort-oriented wheel and tire setups", domain: "exterior", zone: "chassis", kano: "performance", decision: "package_variant", horizon: "today" },
  "rq:refined-cabin-character:1": { title: "Preserve rich, carefully finished cabin materials", domain: "interior", zone: "cabin", kano: "basic", decision: "keep_strength", horizon: "today" },
  "rq:comfortable-space-access:1": { title: "Preserve usable passenger room", domain: "interior", zone: "rear_seats", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:everyday-cabin-storage:0": { title: "Expand accessible everyday cabin storage", domain: "interior", zone: "front_seats", kano: "performance", decision: "raise_capability", horizon: "today" },
  "rq:valuable-vehicle-technology:2": { title: "Preserve clear, customizable head-up guidance", domain: "digital", zone: "cockpit", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:roof-openness-experience:0": { title: "Offer a panoramic roof with open-air capability", domain: "exterior", zone: "doors", kano: "performance", decision: "change_design", horizon: "today" },
  "rq:refined-cabin-character:2": { title: "Preserve adjustable ambient cabin lighting", domain: "interior", zone: "cabin", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:reliable-connected-entertainment:2": { title: "Preserve convenient voice-operated functions", domain: "digital", zone: "cockpit", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:manageable-compact-dimensions:0": { title: "Preserve compact, manageable exterior dimensions", domain: "exterior", zone: "front", kano: "performance", decision: "keep_strength", horizon: "at_successor_launch" },
  "rq:refined-powertrain-character:1": { title: "Preserve strong everyday fuel economy", domain: "powertrain", zone: "underfloor", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:practical-premium-touchpoints:2": { title: "Choose easy-care cabin finishes", domain: "interior", zone: "cabin", kano: "performance", decision: "change_design", horizon: "today" },
  "rq:distinctive-exterior-appeal:0": { title: "Preserve attractive, recognizably BMW exterior styling", domain: "exterior", zone: "front", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:transparent-digital-services:1": { title: "Make digital-service subscriptions explicit and opt-in", domain: "digital", zone: "cockpit", kano: "basic", decision: "change_design", horizon: "at_successor_launch" },
  "rq:premium-ownership-identity:1": { title: "Preserve BMW's distinctive premium character", domain: "quality", zone: "front", kano: "performance", decision: "keep_strength", horizon: "today" },
  "rq:choice-for-different-lifestyles:0": { title: "Preserve useful package and personalization choices", domain: "variants", zone: "cabin", kano: "performance", decision: "keep_strength", horizon: "today" },
};
const EFFORT_OF: Record<string, Effort> = { keep_strength: "S", package_variant: "S", change_design: "M", add_feature: "M", raise_capability: "L" };

/* ------------------------------------------------------------------------------------------------ targets */
// [key, line, market, factors JAN (customer_voice, satisfaction_gap, competitive_gap, market_weight, portfolio_leverage,
//  future_relevance), options]. `jul` adds factor deltas at JUL 26; `pm` is a PM decision taken at JAN 26.
interface Opt {
  conf?: ConfidenceLevel; brand?: GateValue; segment?: GateValue; market?: GateValue; feasibility?: GateValue;
  jul?: Partial<Record<number, number>>; pm?: Band; pmWhy?: string; julOnly?: boolean; chosen?: Rung; rec?: "threshold" | "target" | "stretch";
  flags?: string[];
}
type Row = [string, string, string, F6, Opt?];
const S5 = "5 Series", S7 = "7 Series", S1 = "1 Series";
const ROWS: Row[] = [
  // 5 Series · US: the deepest market (≈3.6k comments): customer voice carries it
  ["rq:easy-common-controls:0", S5, "US", [0.9, 0.7, 0.55, 0.72, 0.6, 0.62], { conf: "E1", jul: { 0: 0.06 }, pm: "Must", pmWhy: "Top complaint across US owners; touch-only climate keeps coming up." }],
  ["rq:confident-real-world-range:0", S5, "US", [0.5, 0.3, 0.62, 0.7, 0.55, 0.82], { conf: "E2", jul: { 0: 0.14, 2: 0.35, 4: 0.1 }, rec: "target",
    pm: "Should", pmWhy: "Range matters, but US owners rank controls and comfort higher; keep it Should for now." }],
  ["rq:convenient-reliable-charging:2", S5, "US", [0.42, 0.32, 0.6, 0.7, 0.4, 0.78], { conf: "E2" }],
  ["rq:effortless-climate-comfort:0", S5, "US", [0.74, 0.6, 0.45, 0.72, 0.35, 0.5], { conf: "E1" }],
  ["rq:engaging-driving-dynamics:0", S5, "US", [0.8, 0.62, 0.4, 0.72, 0.45, 0.4], { conf: "E1", jul: { 0: -0.16, 5: -0.04 },
    pm: "Must", pmWhy: "Handling is the brand core; never let it slip in the successor." }],
  ["rq:dependable-driving-parking-assistance:0", S5, "US", [0.46, 0.4, 0.55, 0.72, 0.35, 0.66], { conf: "E2" }],
  ["rq:understandable-digital-features:0", S5, "US", [0.8, 0.6, 0.42, 0.72, 0.6, 0.58], { conf: "E1" }],
  ["rq:transparent-digital-services:0", S5, "US", [0.4, 0.3, 0.35, 0.72, 0.55, 0.5], { conf: "E2" }],
  ["rq:quiet-smooth-ride:0", S5, "US", [0.72, 0.55, 0.4, 0.72, 0.62, 0.38], { conf: "E1" }],
  ["rq:quiet-smooth-ride:1", S5, "US", [0.58, 0.45, 0.35, 0.72, 0.5, 0.3], { conf: "E1" }],
  ["rq:suitable-tires-wheels:1", S5, "US", [0.5, 0.38, 0.3, 0.72, 0.45, 0.28], { conf: "E2" }],
  ["rq:refined-cabin-character:1", S5, "US", [0.66, 0.58, 0.45, 0.72, 0.35, 0.4], { conf: "E1" }],
  ["rq:comfortable-space-access:1", S5, "US", [0.38, 0.35, 0.3, 0.72, 0.3, 0.35], { conf: "E2" }],
  ["rq:everyday-cabin-storage:0", S5, "US", [0.6, 0.42, 0.5, 0.72, 0.3, 0.35], { conf: "E1" }],
  ["rq:valuable-vehicle-technology:2", S5, "US", [0.56, 0.55, 0.38, 0.72, 0.25, 0.45], { conf: "E2", jul: { 0: -0.18 },
    pm: "Should", pmWhy: "Head-up display is valued by the owners who have it; keep it in the core package." }],
  ["rq:roof-openness-experience:0", S5, "US", [0.4, 0.25, 0.55, 0.72, 0.2, 0.4], { conf: "E2", jul: { 0: -0.12 } }],
  ["rq:refined-cabin-character:2", S5, "US", [0.32, 0.3, 0.4, 0.72, 0.2, 0.45], { conf: "E2" }],
  ["rq:reliable-connected-entertainment:2", S5, "US", [0.36, 0.3, 0.45, 0.72, 0.35, 0.6], { conf: "E2" }],
  // 5 Series · EU: ~110 comments plus the study; winter conditions, tight streets
  ["rq:confident-real-world-range:0", S5, "EU", [0.42, 0.55, 0.7, 0.62, 0.55, 0.88], { conf: "E2", jul: { 2: 0.12 } }],
  ["rq:convenient-reliable-charging:2", S5, "EU", [0.38, 0.5, 0.72, 0.62, 0.4, 0.84], { conf: "E2" }],
  ["rq:easy-common-controls:0", S5, "EU", [0.6, 0.62, 0.5, 0.62, 0.6, 0.6], { conf: "E2" }],
  ["rq:engaging-driving-dynamics:0", S5, "EU", [0.7, 0.66, 0.45, 0.62, 0.45, 0.42], { conf: "E2" }],
  ["rq:effortless-climate-comfort:0", S5, "EU", [0.48, 0.5, 0.42, 0.62, 0.35, 0.52], { conf: "E3", jul: { 0: 0.2, 1: 0.22, 2: 0.12 } }],
  ["rq:dependable-driving-parking-assistance:0", S5, "EU", [0.5, 0.52, 0.6, 0.62, 0.35, 0.7], { conf: "E2" }],
  ["rq:understandable-digital-features:0", S5, "EU", [0.52, 0.5, 0.42, 0.62, 0.6, 0.58], { conf: "E2" }],
  ["rq:quiet-smooth-ride:0", S5, "EU", [0.5, 0.5, 0.4, 0.62, 0.62, 0.38], { conf: "E2" }],
  ["rq:refined-cabin-character:1", S5, "EU", [0.55, 0.6, 0.45, 0.62, 0.35, 0.4], { conf: "E2" }],
  ["rq:everyday-cabin-storage:0", S5, "EU", [0.4, 0.42, 0.45, 0.62, 0.3, 0.35], { conf: "E3" }],
  ["rq:suitable-tires-wheels:1", S5, "EU", [0.32, 0.3, 0.3, 0.62, 0.45, 0.28], { conf: "E3" }],
  ["rq:comfortable-space-access:1", S5, "EU", [0.35, 0.38, 0.3, 0.62, 0.3, 0.35], { conf: "E3" }],
  // 5 Series · CN (G68 long wheelbase): no comments of its own, so the voice is borrowed (× 0.5, capped); study, market
  // weight and trend research carry it, and rear-seat, ambience and digital needs rise
  ["rq:comfortable-space-access:1", S5, "CN", [0.4, 0.9, 0.62, 0.9, 0.3, 0.75], { conf: "E2", flags: ["borrowed_voice"], pm: "Must", pmWhy: "Chauffeured rear use defines the LWB; the study shows the largest gap." }],
  ["rq:refined-cabin-character:2", S5, "CN", [0.3, 0.82, 0.78, 0.9, 0.2, 0.8], { conf: "E2", flags: ["borrowed_voice"], jul: { 3: 0.1, 5: 0.06 } }],
  ["rq:transparent-digital-services:0", S5, "CN", [0.3, 0.75, 0.82, 0.9, 0.55, 0.88], { conf: "E2", flags: ["borrowed_voice"], jul: { 2: 0.12 } }],
  ["rq:reliable-connected-entertainment:2", S5, "CN", [0.3, 0.7, 0.8, 0.9, 0.35, 0.85], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:confident-real-world-range:0", S5, "CN", [0.3, 0.68, 0.8, 0.9, 0.55, 0.86], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:convenient-reliable-charging:2", S5, "CN", [0.28, 0.6, 0.82, 0.9, 0.4, 0.84], { conf: "E2", flags: ["borrowed_voice"], jul: { 1: 0.25, 4: 0.22 } }],
  ["rq:effortless-climate-comfort:0", S5, "CN", [0.3, 0.8, 0.7, 0.9, 0.35, 0.72], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:dependable-driving-parking-assistance:0", S5, "CN", [0.25, 0.62, 0.7, 0.9, 0.35, 0.75], { conf: "E3", flags: ["borrowed_voice"] }],
  ["rq:easy-common-controls:0", S5, "CN", [0.22, 0.3, 0.2, 0.9, 0.6, 0.35], { conf: "E3", flags: ["borrowed_voice"] }],
  ["rq:engaging-driving-dynamics:0", S5, "CN", [0.24, 0.3, 0.3, 0.9, 0.45, 0.3], { conf: "E3", flags: ["borrowed_voice"] }],
  ["rq:refined-cabin-character:1", S5, "CN", [0.3, 0.7, 0.55, 0.9, 0.35, 0.55], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:roof-openness-experience:0", S5, "CN", [0.2, 0.55, 0.65, 0.9, 0.2, 0.55], { conf: "E3", flags: ["borrowed_voice"] }],
  // 7 Series · US
  ["rq:quiet-smooth-ride:0", S7, "US", [0.82, 0.62, 0.45, 0.6, 0.62, 0.42], { conf: "E1", pm: "Must", pmWhy: "Refinement is the 7's reason to exist; owners notice every regression." }],
  ["rq:quiet-smooth-ride:1", S7, "US", [0.76, 0.6, 0.4, 0.6, 0.5, 0.36], { conf: "E1" }],
  ["rq:comfortable-space-access:1", S7, "US", [0.55, 0.5, 0.42, 0.6, 0.3, 0.4], { conf: "E1" }],
  ["rq:refined-cabin-character:1", S7, "US", [0.72, 0.64, 0.5, 0.6, 0.35, 0.42], { conf: "E1" }],
  ["rq:refined-cabin-character:2", S7, "US", [0.48, 0.46, 0.5, 0.6, 0.2, 0.5], { conf: "E2", jul: { 0: 0.1 },
    pm: "Could", pmWhy: "Ambient lighting is a nice-to-have in the US flagship." }],
  ["rq:valuable-vehicle-technology:2", S7, "US", [0.55, 0.5, 0.35, 0.6, 0.25, 0.45], { conf: "E2" }],
  ["rq:easy-common-controls:0", S7, "US", [0.8, 0.6, 0.5, 0.6, 0.6, 0.6], { conf: "E1" }],
  ["rq:effortless-climate-comfort:0", S7, "US", [0.6, 0.52, 0.42, 0.6, 0.35, 0.5], { conf: "E1" }],
  ["rq:roof-openness-experience:0", S7, "US", [0.45, 0.3, 0.55, 0.6, 0.2, 0.4], { conf: "E2" }],
  ["rq:understandable-digital-features:0", S7, "US", [0.66, 0.55, 0.42, 0.6, 0.6, 0.58], { conf: "E1" }],
  // 7 Series · CN
  ["rq:comfortable-space-access:1", S7, "CN", [0.32, 0.88, 0.6, 0.95, 0.3, 0.75], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:refined-cabin-character:2", S7, "CN", [0.3, 0.8, 0.82, 0.95, 0.2, 0.82], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:reliable-connected-entertainment:2", S7, "CN", [0.28, 0.72, 0.78, 0.95, 0.35, 0.86], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:transparent-digital-services:0", S7, "CN", [0.28, 0.7, 0.8, 0.95, 0.55, 0.86], { conf: "E3", flags: ["borrowed_voice"] }],
  ["rq:quiet-smooth-ride:0", S7, "CN", [0.32, 0.8, 0.6, 0.95, 0.62, 0.55], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:refined-cabin-character:1", S7, "CN", [0.32, 0.76, 0.6, 0.95, 0.35, 0.55], { conf: "E2", flags: ["borrowed_voice"] }],
  ["rq:effortless-climate-comfort:0", S7, "CN", [0.28, 0.72, 0.62, 0.95, 0.35, 0.7], { conf: "E3", flags: ["borrowed_voice"] }],
  ["rq:practical-premium-touchpoints:2", S7, "CN", [0.25, 0.5, 0.4, 0.95, 0.3, 0.45], { conf: "E3", flags: ["borrowed_voice"],
    brand: { result: "fail", rationale: "Wipe-clean plastics in place of leather and open-pore wood read as a cost cut in the flagship." } }],
  // 7 Series · EU: almost no comments; mostly assumption
  ["rq:quiet-smooth-ride:0", S7, "EU", [0.3, 0.6, 0.45, 0.4, 0.62, 0.42], { conf: "E3" }],
  ["rq:refined-cabin-character:1", S7, "EU", [0.28, 0.6, 0.5, 0.4, 0.35, 0.42], { conf: "E3" }],
  ["rq:confident-real-world-range:0", S7, "EU", [0.25, 0.5, 0.7, 0.4, 0.55, 0.86], { conf: "E4" }],
  ["rq:engaging-driving-dynamics:0", S7, "EU", [0.22, 0.45, 0.4, 0.4, 0.45, 0.35], { conf: "E4" }],
  // 1 Series · EU
  ["rq:manageable-compact-dimensions:0", S1, "EU", [0.78, 0.62, 0.5, 0.75, 0.2, 0.55], { conf: "E1" }],
  ["rq:easy-common-controls:0", S1, "EU", [0.7, 0.58, 0.5, 0.75, 0.6, 0.6], { conf: "E1" }],
  ["rq:refined-powertrain-character:1", S1, "EU", [0.66, 0.55, 0.45, 0.75, 0.3, 0.5], { conf: "E2", jul: { 5: -0.3, 0: -0.1 } }],
  ["rq:everyday-cabin-storage:0", S1, "EU", [0.62, 0.5, 0.55, 0.75, 0.3, 0.38], { conf: "E1" }],
  ["rq:understandable-digital-features:0", S1, "EU", [0.55, 0.48, 0.42, 0.75, 0.6, 0.55], { conf: "E2" }],
  ["rq:dependable-driving-parking-assistance:0", S1, "EU", [0.45, 0.44, 0.5, 0.75, 0.35, 0.62], { conf: "E2" }],
  ["rq:roof-openness-experience:0", S1, "EU", [0.35, 0.3, 0.4, 0.75, 0.2, 0.35], { conf: "E3",
    segment: { result: "warn", rationale: "A panoramic roof is rare in the compact segment; fits only as an option package." } }],
  ["rq:engaging-driving-dynamics:0", S1, "EU", [0.72, 0.6, 0.4, 0.75, 0.45, 0.4], { conf: "E1" }],
  ["rq:transparent-digital-services:1", S1, "EU", [0.6, 0.55, 0.5, 0.75, 0.35, 0.7], { conf: "E2", julOnly: true }],
];

/** couplings that matter for prioritization (the live cp1 bundles, plus the conflicts a PM must weigh) */
const LINKS: { a: string; b: string; relation: "conflicts" | "competes_for" | "synergy" | "enables"; via: string; strength: number }[] = [
  { a: "rq:confident-real-world-range:0", b: "rq:effortless-climate-comfort:0", relation: "conflicts", via: "energy", strength: 2 },
  { a: "rq:comfortable-space-access:1", b: "rq:everyday-cabin-storage:0", relation: "competes_for", via: "package", strength: 2 },
  { a: "rq:refined-cabin-character:2", b: "rq:reliable-connected-entertainment:2", relation: "competes_for", via: "attention", strength: 2 },
  { a: "rq:engaging-driving-dynamics:0", b: "rq:quiet-smooth-ride:1", relation: "competes_for", via: "mass", strength: 1 },
  { a: "rq:roof-openness-experience:0", b: "rq:confident-real-world-range:0", relation: "competes_for", via: "mass", strength: 1 },
  { a: "rq:quiet-smooth-ride:0", b: "rq:quiet-smooth-ride:1", relation: "synergy", via: "acoustic", strength: 3 },
  { a: "rq:quiet-smooth-ride:1", b: "rq:suitable-tires-wheels:1", relation: "synergy", via: "acoustic", strength: 2 },
  { a: "rq:easy-common-controls:0", b: "rq:easy-common-controls:1", relation: "synergy", via: "attention", strength: 3 },
  { a: "rq:easy-common-controls:0", b: "rq:practical-premium-touchpoints:0", relation: "synergy", via: "attention", strength: 2 },
  { a: "rq:understandable-digital-features:0", b: "rq:transparent-digital-services:0", relation: "synergy", via: "attention", strength: 2 },
  { a: "rq:convenient-reliable-charging:2", b: "rq:confident-real-world-range:0", relation: "enables", via: "energy", strength: 2 },
];
const BUNDLES: { id: string; keys: string[]; reason: string }[] = [
  { id: "bundle:1", keys: ["rq:quiet-smooth-ride:0", "rq:quiet-smooth-ride:1", "rq:suitable-tires-wheels:1"], reason: "synergy via acoustic ×2" },
  { id: "bundle:2", keys: ["rq:understandable-digital-features:0", "rq:transparent-digital-services:0"], reason: "synergy via attention" },
  { id: "bundle:3", keys: ["rq:easy-common-controls:0", "rq:easy-common-controls:1", "rq:practical-premium-touchpoints:0"], reason: "synergy via attention ×2" },
  { id: "bundle:6", keys: ["rq:convenient-reliable-charging:2", "rq:confident-real-world-range:0"], reason: "enables via energy" },
];

export const fixtureLinks = LINKS;

const BASIS: Record<ConfidenceLevel, Record<string, number>> = {
  E1: { cited: 3, projected: 1 }, E2: { cited: 2, projected: 1, assumption: 1 }, E3: { cited: 1, projected: 1, assumption: 1, gap: 1 }, E4: { assumption: 2, gap: 2 },
};
const RANK_BAND: Record<Band, number> = { Must: 3, Should: 2, Could: 1 };
const DIM_WORD: Record<string, string> = {
  customer_voice: "customer voice", satisfaction_gap: "the study's satisfaction gap", competitive_gap: "the gap to rivals",
  market_weight: "market weight", portfolio_leverage: "portfolio leverage", future_relevance: "future relevance",
};

function explain(key: string, v: number | null, market: string, borrowed: boolean): string {
  if (v == null) return "No evidence for this factor in this market.";
  const lvl = v >= 0.7 ? "strong" : v >= 0.45 ? "moderate" : "weak";
  switch (key) {
    case "customer_voice": return borrowed ? `Borrowed from other markets (× 0.5, capped): no ${market} comments of its own.` : `${lvl[0].toUpperCase()}${lvl.slice(1)} share of ${market} comments on this need, after shrinkage.`;
    case "satisfaction_gap": return `Customer study, ${market}: ${v >= 0.6 ? "rated clearly below the line's average" : v >= 0.4 ? "around the average" : "rated above average"}.`;
    case "competitive_gap": return `Cited rival thresholds vs. today's car: ${v >= 0.6 ? "behind" : v >= 0.4 ? "at parity" : "ahead"}.`;
    case "market_weight": return `BMW volume share (stylized, Q-015) and the public trend for ${market}.`;
    case "portfolio_leverage": return `Spread over lines and markets${v >= 0.5 ? ", plus enabler credit" : ""}.`;
    case "future_relevance": return `Horizon, dated trends and Kano drift: ${lvl}.`;
    default: return "";
  }
}

// the sample values are authored on a compressed scale; spread them so the bands separate like a real portfolio
const contrast = (f: F6) => f.map((v) => (v == null ? v : Math.max(0, Math.min(1, 0.5 + (v - 0.5) * 1.5)))) as F6;

function build(julCp: boolean) {
  const targets: Target[] = [];
  // JUL compares with JAN's final (bundle-adjusted) bands
  const janBands = julCp ? new Map(build(false).targets.map((t) => [`${t.key}|${t.line}|${t.market}`, { score: t.score, band: t.band }])) : null;
  for (const [key, line, market, f6, o = {}] of ROWS) {
    const seed = SEEDS[key];
    if (!seed) continue;
    const level = o.conf ?? "E2";
    const brand = o.brand ?? "pass", segment = o.segment ?? "pass", mkt = o.market ?? "pass", feas = o.feasibility ?? "pass";
    const fit = (typeof mkt === "string" ? mkt : mkt.result) as keyof typeof FIT_PTS;
    const effort = EFFORT_OF[seed.decision] ?? "M";
    if (o.julOnly && !julCp) continue;
    const f = julCp && o.jul ? f6.map((v, i) => (v == null ? v : v + (o.jul![i] ?? 0))) as F6 : f6;
    const s = scoreFrom(contrast(f), level, effort, fit);
    const borrowed = !!o.flags?.includes("borrowed_voice");
    s.factors.forEach((x) => { x.explanation = explain(x.key, x.value, market, borrowed); });
    const flags = [...(o.flags ?? [])];
    if (typeof brand !== "string" && brand.result === "fail") flags.push("brand_blocked");
    const prev = julCp && !o.julOnly ? janBands?.get(`${key}|${line}|${market}`) ?? null : null;
    targets.push({
      key, title: seed.title, domain: seed.domain, zones: [seed.zone], area_key: key.split(":")[1], line, market,
      score: s.score, base: s.base, band: bandOf(s.score), rank: 0,
      confirmed: o.pm ? { priority: o.pm, actor: "Atahan (PM)", at: "2026-01-22T10:14:00Z", rationale: o.pmWhy ?? "" } : null,
      state: julCp ? (o.julOnly ? "new" : prev && Math.abs(prev.score - s.score) >= 3 ? (s.score > prev.score ? "strengthened" : "weakened") : "held") : "new",
      confidence: { level, mult: CONF_MULT[level], basis_mix: BASIS[level] } as Confidence,
      factors: s.factors, modifiers: s.modifiers,
      gates: { brand, segment, market: mkt, feasibility: feas },
      bundle_id: null, flags, rung: { chosen: o.chosen ?? null, recommended: o.rec ?? "target" },
      rationale: "", prev,
    });
  }
  // bundles share one proposed band per line × market: the strongest member's
  const bundles: PrioBundle[] = [];
  for (const b of BUNDLES) {
    const band_by_target: Record<string, Band> = {};
    for (const t of targets) if (b.keys.includes(t.key)) {
      const id = `${t.line}|${t.market}`;
      if (!band_by_target[id] || RANK_BAND[t.band] > RANK_BAND[band_by_target[id]]) band_by_target[id] = t.band;
    }
    for (const t of targets) if (b.keys.includes(t.key)) {
      const lm = targets.filter((x) => b.keys.includes(x.key) && x.line === t.line && x.market === t.market);
      if (lm.length < 2) continue;
      t.bundle_id = b.id;
      const shared = band_by_target[`${t.line}|${t.market}`];
      if (shared !== t.band) { t.flags.push(`bundle_band|${t.band}`); t.band = shared; }
    }
    if (Object.keys(band_by_target).length) bundles.push({ id: b.id, keys: b.keys, band_by_target, reason: b.reason });
  }
  // two Musts in a strong conflict in one line × market: choose their ladder levels jointly
  for (const l of LINKS) {
    if ((l.relation !== "conflicts" && l.relation !== "competes_for") || l.strength < 2) continue;
    for (const ta of targets) {
      if (ta.key !== l.a || ta.band !== "Must") continue;
      const tb = targets.find((x) => x.key === l.b && x.line === ta.line && x.market === ta.market && x.band === "Must");
      if (!tb) continue;
      ta.flags.push(`choose_jointly|${l.via}|${l.b}`);
      tb.flags.push(`choose_jointly|${l.via}|${l.a}`);
    }
  }
  // ranks and rationale per line × market
  const groups = new Map<string, Target[]>();
  for (const t of targets) groups.set(`${t.line}|${t.market}`, [...(groups.get(`${t.line}|${t.market}`) ?? []), t]);
  for (const list of groups.values()) {
    list.sort((a, b) => b.score - a.score).forEach((t, i) => { t.rank = i + 1; });
  }
  for (const t of targets) t.rationale = rationaleFor(t);
  return { targets, bundles };
}

export function rationaleFor(t: Target): string {
  const top = [...t.factors].filter((f) => f.available).sort((a, b) => b.points - a.points).slice(0, 2);
  const weak = [...t.factors].filter((f) => f.available).sort((a, b) => a.points / a.weight - b.points / b.weight)[0];
  const eff = t.modifiers.find((m) => m.key === "effort");
  const parts = [
    `${t.band} in ${t.line} · ${t.market}: driven by ${top.map((f) => `${DIM_WORD[f.key]} (${Math.round(f.points)} pts)`).join(" and ")}`,
    weak ? `held back by ${DIM_WORD[weak.key]}` : null,
    `${t.confidence.level} confidence (× ${t.confidence.mult.toFixed(2)})${eff && eff.points ? `, ${eff.why.toLowerCase()} ${eff.points}` : ""}.`,
  ].filter(Boolean);
  let s = parts.join(", ");
  const bb = t.flags.find((f) => f.startsWith("bundle_band|"));
  if (bb) s += ` Scored ${bb.split("|")[1]} on its own; shares its bundle's ${t.band}.`;
  return s;
}

const CAUSE_OF: Record<number, Proposal["cause"]> = { 0: "area_strengthened", 1: "area_strengthened", 2: "new_fact", 3: "market_trend", 4: "link_changed", 5: "market_trend" };

export function fixtureFor(cp: string): PrioritizePayload {
  const jul = cp === "cp2";
  const { targets, bundles } = build(jul);
  const proposals: Proposal[] = [];
  if (jul) {
    let id = 1;
    for (const t of targets) {
      const from = t.confirmed?.priority ?? t.prev?.band ?? null;
      if (!from || from === t.band) continue;
      const row = ROWS.find((r) => r[0] === t.key && r[1] === t.line && r[2] === t.market);
      const deltas = row?.[4]?.jul ?? {};
      const delta: Record<string, number> = {};
      let big = -1, bigV = 0;
      for (const [i, d] of Object.entries(deltas)) {
        const f = FACTORS[Number(i)];
        delta[f.key] = r1((d ?? 0) * f.weight);
        if (Math.abs(d ?? 0) > bigV) { bigV = Math.abs(d ?? 0); big = Number(i); }
      }
      proposals.push({ id: id++, key: t.key, line: t.line, market: t.market, old_band: from, proposed_band: t.band,
                       cause: CAUSE_OF[big] ?? "link_changed", factor_delta: delta, against: t.confirmed ? "pm" : "parent",
                       status: "open", created_at: "2026-07-31T18:02:00Z" });
    }
  }
  const by_band: Partial<Record<Band, number>> = {};
  const by_market: Record<string, Partial<Record<Band, number>>> = {};
  for (const t of targets) {
    by_band[t.band] = (by_band[t.band] ?? 0) + 1;
    const m = (by_market[`${t.line}|${t.market}`] ??= {});
    m[t.band] = (m[t.band] ?? 0) + 1;
  }
  return {
    checkpoint: jul ? "cp2" : "cp1", ready: true, runs: { prioritize: null, gate: null },
    weights: { scheme: "prio-v1", version: 1, factors: Object.fromEntries(FACTORS.map((f) => [f.key, f.weight])), bands: BAND_AT },
    labels: { market_weight: "stylized (Q-015)" },
    lines: ["1 Series", "5 Series", "7 Series"],
    markets: { "1 Series": ["EU"], "5 Series": ["US", "EU", "CN"], "7 Series": ["US", "CN", "EU"] },
    targets, bundles, proposals, summary: { by_band, by_market },
  };
}

export function fixtureDetail(t: Target): TargetDetail {
  const jan = fixtureFor("cp1").targets.find((x) => x.key === t.key && x.line === t.line && x.market === t.market);
  const history: TargetDetail["history"] = [];
  if (jan) history.push({ checkpoint: "cp1", score: jan.score, band: jan.band, rung: jan.rung.chosen ?? jan.rung.recommended, confirmed: jan.confirmed?.priority ?? null });
  if (t.prev || !jan) history.push({ checkpoint: "cp2", score: t.score, band: t.band, rung: t.rung.chosen ?? t.rung.recommended, confirmed: t.confirmed?.priority ?? null });
  const borrowed = t.flags.includes("borrowed_voice");
  return { ...t, history, evidence: { comments: borrowed ? 0 : Math.round((t.factors[0].value ?? 0) * 140), study: 3, research: 4, options: 1, own_market: !borrowed } };
}

/** Sample what-if: the rung moves effort one step and confidence with the basis of that rung. */
export function fixtureWhatIf(t: Target, level: Rung, titleOf: (k: string) => string | undefined): WhatIf {
  const eff = t.modifiers.find((m) => m.key === "effort")?.points ?? 0;
  const step = level === "threshold" ? 3 : level === "stretch" ? -3 : level === "baseline" ? -eff : 0;
  const cur = t.rung.chosen ?? t.rung.recommended;
  const curStep = cur === "threshold" ? 3 : cur === "stretch" ? -3 : cur === "baseline" ? -eff : 0;
  const multK = level === "stretch" ? 0.92 : level === "threshold" ? 1.04 : level === "baseline" ? 1.06 : 1;
  const curK = cur === "stretch" ? 0.92 : cur === "threshold" ? 1.04 : cur === "baseline" ? 1.06 : 1;
  const mult = Math.min(1, (t.confidence.mult / curK) * multK);
  const mods = t.modifiers.reduce((s, m) => s + m.points, 0) - curStep + step;
  const score = r1(Math.max(0, Math.min(100, t.base * mult + mods)));
  const exposures = level === cur ? [] : LINKS.filter((l) => l.a === t.key || l.b === t.key).map((l) => {
    const other = l.a === t.key ? l.b : l.a;
    return { key: other, title: titleOf(other), via: l.via, relation: l.relation,
             note: level === "stretch" || (level === "target" && cur === "threshold") ? `+1 exposure via ${l.via}` : `−1 exposure via ${l.via}` };
  });
  return { key: t.key, line: t.line, market: t.market, level, score, band: bandOf(score), base: t.base, delta: r1(score - t.score), exposures };
}
