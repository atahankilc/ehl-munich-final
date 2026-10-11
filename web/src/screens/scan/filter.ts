// Filtering the scan. Any number of dimensions at once; within a dimension the chosen values are alternatives (OR),
// across dimensions they all have to hold (AND). Car and market exist on every data type, so they filter the whole
// volume; the rest belong to one type and leave the others alone. Items with no value for a global dimension (options
// have no market, global research has none) stay visible: they apply everywhere. Comment length is bucketed client-side
// from the points payload; topic and fact type come with each research item, availability with each option.
import type { OptionItem, PointsPayload, ResearchItem, SalesRow, SourcesPayload, StudyItem } from "@/lib/types";
import { CARS, CAR_NAME, MARKET_NAME } from "./layout";

export type Dim = "car" | "market" | "channel" | "type" | "engine" | "length" | "tier" | "topic" | "fact" | "rating"
  | "category" | "availability" | "year";
export type Scope = "all" | "comment" | "research" | "study" | "option" | "sales";
export const DIMS: { id: Dim; name: string; scope: Scope }[] = [
  { id: "car", name: "Car", scope: "all" }, { id: "market", name: "Market", scope: "all" },
  { id: "channel", name: "Channel", scope: "comment" }, { id: "type", name: "Label", scope: "comment" },
  { id: "engine", name: "Engine", scope: "comment" }, { id: "length", name: "Length", scope: "comment" },
  { id: "tier", name: "Trust", scope: "research" }, { id: "topic", name: "Topic", scope: "research" },
  { id: "fact", name: "Fact type", scope: "research" },
  { id: "rating", name: "Study result", scope: "study" },
  { id: "category", name: "Category", scope: "option" }, { id: "availability", name: "Availability", scope: "option" },
  { id: "year", name: "Sales year", scope: "sales" },
];
export const SCOPE_NOTE: Record<Scope, string> = {
  all: "Filters all data", comment: "Customer comments only", research: "Web research only", study: "Customer study only",
  option: "Equipment options only", sales: "BMW sales volumes only",
};

/** The chosen values per dimension; a dimension without a set (or with an empty one) is not filtered. */
export type Filter = Partial<Record<Dim, Set<string>>>;

const NONE = "∅";
const key = (v: string | null | undefined) => v ?? NONE;
const COMMENT_DIMS = ["car", "market", "channel", "type", "engine"] as const;
type CommentDim = (typeof COMMENT_DIMS)[number];
const isCommentDim = (d: Dim): d is CommentDim => (COMMENT_DIMS as readonly Dim[]).includes(d);
const on = (f: Filter | null, d: Dim) => (f?.[d]?.size ? f[d]! : null);

export const isActive = (f: Filter | null) => !!f && DIMS.some((d) => on(f, d.id));
export const without = (f: Filter | null, d: Dim): Filter => { const g = { ...f }; delete g[d]; return g; };

/** A study item's result against its car × market's average: half a standard deviation either way counts. */
export const ratingOf = (s: StudyItem) => ((s.z ?? 0) >= 0.5 ? "above" : (s.z ?? 0) <= -0.5 ? "below" : "around");
const yearOf = (r: SalesRow) => String(r.year);
/** A comment's length in characters, bucketed: a one-liner, a few sentences, or a full account. */
const LENGTHS = ["short", "medium", "long"] as const;
export const lengthOf = (len: number) => (len < 80 ? "short" : len < 250 ? "medium" : "long");

/** The 5 Series' China research is about the long-wheelbase G68 (as on the rings). */
export const researchCars = (it: ResearchItem) => it.cars.map((c) => (c === "G60" && it.region === "CN" ? "G68" : c));

export function passResearch(f: Filter | null, it: ResearchItem) {
  const car = on(f, "car"), market = on(f, "market"), tier = on(f, "tier");
  return (!car || researchCars(it).some((c) => car.has(c)))
    && (!market || it.market == null || market.has(it.market))
    && (!tier || tier.has(key(it.tier)))
    && (!on(f, "topic") || on(f, "topic")!.has(key(it.topic)))
    && (!on(f, "fact") || on(f, "fact")!.has(key(it.kind)));
}
export function passStudy(f: Filter | null, s: StudyItem) {
  const car = on(f, "car"), market = on(f, "market"), rating = on(f, "rating");
  return (!car || car.has(s.car)) && (!market || market.has(s.market)) && (!rating || rating.has(ratingOf(s)));
}
export function passOption(f: Filter | null, o: OptionItem) {
  const car = on(f, "car"), category = on(f, "category"), availability = on(f, "availability");
  return (!car || car.has(o.car)) && (!category || category.has(key(o.category)))
    && (!availability || availability.has(key(o.availability)));
}
export function passSales(f: Filter | null, r: SalesRow) {
  const car = on(f, "car"), market = on(f, "market"), year = on(f, "year");
  return (!car || car.has(r.car)) && (!market || market.has(r.market)) && (!year || year.has(yearOf(r)));
}

/** 1 = the comment passes every comment dimension that is filtered. */
export function commentMask(points: PointsPayload, f: Filter | null) {
  const m = new Uint8Array(points.n).fill(1);
  for (const d of COMMENT_DIMS) {
    const vals = on(f, d);
    if (!vals) continue;
    const col = points.cols[d], dict = points.dict[d] as (string | null)[];
    for (let i = 0; i < points.n; i++) if (m[i] && !(col[i] >= 0 && vals.has(key(dict[col[i]])))) m[i] = 0;
  }
  const lengths = on(f, "length");
  if (lengths) for (let i = 0; i < points.n; i++) if (m[i] && !lengths.has(lengthOf(points.cols.len[i]))) m[i] = 0;
  return m;
}

const TIER_NAME: Record<string, string> = { T1: "T1 · official", T2: "T2 · press & analysts", T3: "T3 · forums & social" };
const RATING_NAME: Record<string, string> = { above: "Above average", around: "Around average", below: "Below average" };
const LENGTH_NAME: Record<string, string> = { short: "Short · under 80 chars", medium: "Medium · 80–250", long: "Long · 250+" };
const TOPIC_NAME: Record<string, string> = {
  bmw: "BMW", markets: "Markets", segment_sales: "Segment sales", premium_competitors: "Premium competitors",
  ev_challengers: "EV challengers", consumer_studies: "Consumer studies", tech_trends: "Tech trends",
  policy_macro: "Policy & macro", china_market: "China · market", china_models: "China · models", china_context: "China · context",
};
const FACT_NAME: Record<string, string> = { metric: "Figure", event: "Event · launch, news", study: "Study or rating", policy: "Policy", trend: "Trend" };
const AVAILABILITY_NAME: Record<string, string> = { standard: "Standard", optional: "Optional", package: "In a package" };
const humanize = (v: string) => v.charAt(0).toUpperCase() + v.slice(1).replace(/_/g, " ");

/** The values a dimension offers, with how many items carry each one at this checkpoint, given the other filters. */
export function keyValues(dim: Dim, points: PointsPayload, src: SourcesPayload | undefined, position: number, f: Filter | null = null) {
  const rest = without(f, dim);
  const n = new Map<string, number>();
  const add = (v: string | null | undefined) => n.set(key(v), (n.get(key(v)) ?? 0) + 1);
  if (isCommentDim(dim)) {
    const mask = commentMask(points, rest);
    const col = points.cols[dim], dict = points.dict[dim] as (string | null)[], cps = points.cols.cp;
    for (let i = 0; i < points.n; i++) if (mask[i] && col[i] >= 0 && cps[i] <= position) add(dict[col[i]]);
  }
  if (dim === "length") {
    const mask = commentMask(points, rest), cps = points.cols.cp;
    for (let i = 0; i < points.n; i++) if (mask[i] && cps[i] <= position) add(lengthOf(points.cols.len[i]));
  }
  const research = (src?.research ?? []).filter((r) => (position > 1 || !r.new) && passResearch(rest, r));
  const study = (src?.study ?? []).filter((s) => passStudy(rest, s));
  const options = (src?.options ?? []).filter((o) => passOption(rest, o));
  const sales = (src?.sales ?? []).filter((r) => r.units && r.units > 0 && passSales(rest, r));   // as drawn: one bar per figure
  if (dim === "car") {
    for (const r of research) new Set(researchCars(r)).forEach(add);
    for (const s of study) add(s.car);
    for (const o of options) add(o.car);
    for (const r of sales) add(r.car);
  }
  if (dim === "market") {
    for (const r of research) if (r.market) add(r.market);
    for (const s of study) add(s.market);
    for (const r of sales) add(r.market);
  }
  if (dim === "tier") for (const r of research) add(r.tier);
  if (dim === "topic") for (const r of research) add(r.topic);
  if (dim === "fact") for (const r of research) add(r.kind);
  if (dim === "category") for (const o of options) add(o.category);
  if (dim === "availability") for (const o of options) add(o.availability);
  if (dim === "rating") for (const s of study) add(ratingOf(s));
  if (dim === "year") for (const r of sales) add(yearOf(r));

  // a chosen value stays listed even when the other filters leave nothing for it, so it can be unchosen
  const chosen = on(f, dim);
  const order: string[] =
    dim === "car" ? [...CARS] : dim === "market" ? ["EU", "US", "CN", "RoW"] : dim === "tier" ? ["T1", "T2", "T3"]
      : dim === "rating" ? ["above", "around", "below"] : dim === "year" ? [...new Set((src?.sales ?? []).map(yearOf))].sort()
      : dim === "length" ? [...LENGTHS] : dim === "availability" ? ["standard", "optional", "package", NONE]
      : isCommentDim(dim) ? (points.dict[dim] as (string | null)[]).map(key)
        : [...n.keys(), ...(chosen ?? [])].filter((v, i, a) => a.indexOf(v) === i)   // topic, fact type, category: largest first
            .sort((a, b) => (n.get(b) ?? 0) - (n.get(a) ?? 0));
  return order.filter((v) => n.get(v) || chosen?.has(v)).map((v) => ({ v, name: valueName(dim, v), n: n.get(v) ?? 0 }));
}

export function valueName(dim: Dim, v: string) {
  if (v === NONE) return dim === "type" ? "Unlabelled" : "Unknown";
  if (dim === "car") return CAR_NAME[v] ?? v;
  if (dim === "market") return MARKET_NAME[v] ?? v;
  if (dim === "tier") return TIER_NAME[v] ?? v;
  if (dim === "rating") return RATING_NAME[v] ?? v;
  if (dim === "year") return v === "2030" ? "2030 forecast" : v;
  if (dim === "length") return LENGTH_NAME[v] ?? v;
  if (dim === "topic") return TOPIC_NAME[v] ?? humanize(v);
  if (dim === "fact") return FACT_NAME[v] ?? humanize(v);
  if (dim === "availability") return AVAILABILITY_NAME[v] ?? humanize(v);
  return v;
}
