// Scan: every raw piece of evidence the system holds, at the current checkpoint, as one 3D space.
import { Suspense, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Canvas } from "@react-three/fiber";
import { useQuery } from "@tanstack/react-query";
import { ChevronsLeft, ChevronsRight, ExternalLink, SlidersHorizontal, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Comment, PointsPayload, ResearchItem, Selection, SourcesPayload, StructurePayload } from "@/lib/types";
import { AreaBody, ClusterBody, Funnel, SignalList, ThemeBody } from "../structure/panels";
import { AgentPanel, useActivity } from "../structure/AgentPanel";
import { PageSwitch } from "@/components/PageSwitch";
import { Dock } from "@/components/Guide";
import { useCheckpoint } from "@/state/checkpoint";
import { Scene, TYPE_COLOR, layerOf, studyValue, type Hover } from "./Scene";
import { CAR_NAME, MARKET_NAME } from "./layout";
import { HOME, NavPad, SPREAD_MAX, SPREAD_MIN, newNav } from "./navigate";
import { DIMS, SCOPE_NOTE, commentMask, isActive, keyValues, passOption, passResearch, passSales, passStudy, valueName, type Dim, type Filter, type Scope } from "./filter";
import "./scan.css";

// the spread is a per-viewer convenience: remembered in this browser, 1× when storage is unavailable
const SPREAD_KEY = "scan.spread";
function storedSpread() {
  try { const v = Number(localStorage.getItem(SPREAD_KEY)); return v >= SPREAD_MIN && v <= SPREAD_MAX ? v : 1; } catch { return 1; }
}

const fmt = (n: number | undefined | null) => (n == null ? "–" : n.toLocaleString("en-US"));


export function Scan({ mode = "scan" }: { mode?: "scan" | "structure" }) {
  const { cp, from, sweepId, position, checkpoints } = useCheckpoint();
  const structure = useQuery({ queryKey: ["structure", cp], queryFn: () => api.get<StructurePayload>(`/api/structure?cp=${cp}`),
                               staleTime: 30_000, placeholderData: (prev) => prev });
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const activity = useActivity();
  // when a stage finishes, show its output without a reload
  const doneStages = activity.data?.stages.filter((s) => s.status === "completed").map((s) => s.stage).join(",");
  useEffect(() => { structure.refetch(); }, [doneStages]); // eslint-disable-line react-hooks/exhaustive-deps
  const points = useQuery({ queryKey: ["scan", "points"], queryFn: () => api.get<PointsPayload>("/api/scan/points"), staleTime: Infinity });
  const sources = useQuery({ queryKey: ["scan", "sources"], queryFn: () => api.get<SourcesPayload>("/api/scan/sources?cp=cp2"), staleTime: Infinity });
  // chosen filter values per dimension, and the order the dimensions were first set in (the chip row keeps it)
  const [chosen, setChosen] = useState<{ f: Filter; order: Dim[] }>({ f: {}, order: [] });
  const toggle = (d: Dim, v: string) => setChosen(({ f, order }) => {
    const vals = new Set(f[d]);
    if (vals.has(v)) vals.delete(v); else vals.add(v);
    const next = { ...f, [d]: vals };
    if (!vals.size) delete next[d];
    return { f: next, order: vals.size ? (order.includes(d) ? order : [...order, d]) : order.filter((x) => x !== d) };
  });
  const clear = (d?: Dim) => setChosen(({ f, order }) => {
    if (!d) return { f: {}, order: [] };
    const next = { ...f }; delete next[d];
    return { f: next, order: order.filter((x) => x !== d) };
  });
  const [hover, setHover] = useState<Hover | null>(null);
  const [selected, setSelected] = useState<{ sel: Selection; at: [number, number, number] } | null>(null);
  const [spread, setSpread] = useState(storedSpread);
  useEffect(() => { try { localStorage.setItem(SPREAD_KEY, String(spread)); } catch { /* private mode */ } }, [spread]);
  const nav = useRef(newNav());
  const fromPosition = checkpoints?.find((c) => c.id === from)?.position ?? position;

  // the filters work on page 1 only; page 2 hides them, so nothing stays filtered there unseen
  const filter = useMemo<Filter | null>(() => (mode === "scan" && isActive(chosen.f) ? chosen.f : null), [mode, chosen]);
  const mask = useMemo(() => (points.data ? commentMask(points.data, filter) : new Uint8Array(0)), [points.data, filter]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (selected) setSelected(null); else clear();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);
  useEffect(() => { setSelected(null); setHover(null); }, [mode]);

  return (
    <main className="scan" data-mode={mode} aria-label={mode === "structure" ? "Structure and context at the selected checkpoint" : "Raw evidence at the selected checkpoint"}>
      <div className="scan-canvas">
        {points.data && (
          <Canvas dpr={[1, 2]} camera={{ position: HOME, fov: 40, near: 0.05, far: 60 }}
                  raycaster={{ params: { Points: { threshold: 0.018 }, Line: { threshold: 0 }, Mesh: {}, LOD: {}, Sprite: {} } }}
                  gl={{ antialias: true, alpha: false }} onCreated={({ gl }) => gl.setClearColor("#000000")}
                  onPointerMissed={() => setSelected(null)}>
            <Suspense fallback={null}>
              <Scene points={points.data} sources={sources.data} mask={mask} position={position} fromPosition={fromPosition}
                     sweepId={sweepId} hoverComment={hover?.comment ?? null} locked={selected?.at ?? null} focus={selected ? layerOf(selected.sel) : null}
                     onHover={setHover} onSelect={(sel, at) => { setSelected({ sel, at }); setHover(null); }}
                     mode={mode} structure={structure.data} selected={selected?.sel ?? null} hoverKey={hoverKey}
                     onStructureHover={(h, k) => { setHover(h); setHoverKey(k ?? null); }} pulse={activity.data?.recent} filter={filter}
                     spread={spread} nav={nav} />
            </Suspense>
          </Canvas>
        )}
        {points.isPending && <div className="scan-state"><span className="scan-pulse" aria-hidden />Scanning</div>}
        {points.isError && <div className="scan-state error">{(points.error as Error).message}</div>}
      </div>

      {mode === "scan" ? (
        <div className="hud-tl">
          <Readout points={points.data} mask={mask} filter={filter} />
          {points.data && <FilterBar points={points.data} sources={sources.data} position={position} filter={chosen.f} order={chosen.order}
                                     onToggle={toggle} onClear={clear} />}
        </div>
      ) : <Funnel data={structure.data} />}
      <Dock mode={mode} sel={selected?.sel ?? null} agent={mode === "structure" ? <AgentPanel /> : undefined} running={!!activity.data?.running} />
      <PageSwitch />
      {points.data && <NavPad spread={spread} onSpread={setSpread} nav={nav} />}

      {hover && !selected && <HoverCard hover={hover} points={points.data} />}
      {selected && <Inspector sel={selected.sel} sales={sources.data?.sales ?? []} onClose={() => setSelected(null)} structure={structure.data}
                              cpLabel={(id) => checkpoints?.find((c) => c.id === id)?.label ?? id} />}
    </main>
  );
}

/* ------------------------------------------------------------------------------------------- glyphs */
type GlyphKind = "comment" | "study" | "option" | "sales" | "research";
const GLYPH_COLOR: Record<GlyphKind, string> = {
  comment: TYPE_COLOR.comment, study: TYPE_COLOR.study, option: TYPE_COLOR.option, sales: TYPE_COLOR.sales, research: TYPE_COLOR.research,
};
function Glyph({ kind }: { kind: GlyphKind }) {
  const c = "currentColor";
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="glyph" style={{ color: GLYPH_COLOR[kind] }}>
      {kind === "comment" && <><circle cx="4" cy="6" r="1.6" fill={c} /><circle cx="9.5" cy="4" r="1.6" fill="none" stroke={c} /><circle cx="8.5" cy="10" r="1.4" fill={c} /></>}
      {kind === "study" && <><path d="M2 8h10" stroke={c} strokeOpacity=".35" /><path d="M4 8V4M7 8v4M10 8V3" stroke={c} strokeWidth="1.3" /></>}
      {kind === "option" && <>{[2.5, 5.5, 8.5, 11.5].map((x) => <circle key={x} cx={x} cy="7" r="1" fill={c} />)}</>}
      {kind === "sales" && <><rect x="2.5" y="6" width="2" height="6" fill={c} /><rect x="6" y="3" width="2" height="9" fill={c} /><rect x="9.5" y="2.5" width="2" height="9.5" fill="none" stroke={c} /></>}
      {kind === "research" && <><path d="M1.5 9.5a6 6 0 0 1 11 0" fill="none" stroke={c} strokeDasharray="1.5 1.5" /><circle cx="7" cy="4.2" r="1.4" fill={c} /></>}
    </svg>
  );
}

/* ------------------------------------------------------------------------------------------- readout */
// One cell per colour in the scene, named and counted. The car rings carry BMW's own data plus cited public research
// in the same colour, so their cell gives both: BMW's count large, the public items beneath.
// While filters are set, every count is what they leave visible.
function Readout({ points, mask, filter }: { points: PointsPayload | undefined; mask: Uint8Array; filter: Filter | null }) {
  const { current, position } = useCheckpoint();
  const src = useQuery({ queryKey: ["scan", "sources"], queryFn: () => api.get<SourcesPayload>("/api/scan/sources?cp=cp2"), staleTime: Infinity }).data;
  const s = current?.sources;
  const plus = (n: number | undefined) => (position > 1 && n ? <span className="plus">+{fmt(n)}</span> : null);
  const comments = useMemo(() => {
    if (!filter || !points) return { n: s?.feedback.visible, nu: s?.feedback.new };
    let n = 0, nu = 0;
    for (let i = 0; i < points.n; i++) if (mask[i] && points.cols.cp[i] <= position) { n++; if (points.cols.cp[i] === position && position > 1) nu++; }
    return { n, nu };
  }, [filter, points, mask, position, s]);
  const research = (ring: ResearchItem["ring"]) => {
    const items = (src?.research ?? []).filter((r) => r.ring === ring && (position > 1 || !r.new) && passResearch(filter, r));
    return src ? { n: items.length, nu: items.filter((r) => r.new).length } : undefined;
  };
  const time = research(null), rating = research("study"), news = research("options"), pub = research("sales");
  const cells: { k: GlyphKind; label: string; n: number | undefined; nu?: number; pub?: { label: string; c?: { n: number; nu: number } } }[] = [
    { k: "comment", label: "Customer comments", n: comments.n, nu: comments.nu },
    { k: "research", label: "Web research", n: time?.n, nu: time?.nu },
    { k: "study", label: "Customer study", n: src?.study.filter((x) => passStudy(filter, x)).length, pub: { label: "public ratings", c: rating } },
    { k: "option", label: "Equipment options", n: src?.options.filter((x) => passOption(filter, x)).length, pub: { label: "product news", c: news } },
    { k: "sales", label: "Sales volumes", n: src?.sales.filter((r) => r.units && r.units > 0 && passSales(filter, r)).length, pub: { label: "public sales", c: pub } },
  ];
  return (
    <dl className="readout" aria-label="Evidence at this checkpoint">
      {cells.map((c) => (
        <div key={c.label}>
          <dt><Glyph kind={c.k} /><span className="label">{c.label}</span></dt>
          <dd><span className="num">{fmt(c.n)}</span>{plus(c.nu)}</dd>
          {c.pub && (
            <dd className="readout-pub">
              <i style={{ borderColor: GLYPH_COLOR[c.k] }} aria-hidden />
              <span>{fmt(c.pub.c?.n)} {c.pub.label}</span>{plus(c.pub.c?.nu)}
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------------------------------- filters */
// One chip per dimension, under the readout, always shown. Dimensions in use come first, in the order they were set,
// so choosing a value never moves a chip that is already set. A toggle at the head of the row folds the unused chips
// away (the ones in use stay, so nothing is filtered unseen) and unfolds them to the right again; the choice is kept
// per browser. Hovering a chip opens its values; choosing one closes the list again, so only the choice stays. Car and
// market filter every data type; the other chips belong to one type and carry its glyph (comments: channel, label,
// engine, length; research: trust, topic, fact type; study: result; options: category, availability; sales: year).
const SCOPE_GLYPH: Record<Exclude<Scope, "all">, GlyphKind> = { comment: "comment", research: "research", study: "study", option: "option", sales: "sales" };
const isMouse = (e: ReactPointerEvent) => e.pointerType === "mouse";

interface FilterProps {
  points: PointsPayload; sources: SourcesPayload | undefined; position: number; filter: Filter; order: Dim[];
  onToggle: (d: Dim, v: string) => void; onClear: (d?: Dim) => void;
}

const FOLD_KEY = "scan.filters.folded";
const readFolded = () => { try { return localStorage.getItem(FOLD_KEY) === "1"; } catch { return false; } };

function FilterBar(p: FilterProps) {
  const [folded, setFolded] = useState(readFolded);
  const [open, setOpen] = useState<Dim | null>(null);
  const fold = (f: boolean) => {
    setFolded(f); setOpen(null);
    try { localStorage.setItem(FOLD_KEY, f ? "1" : "0"); } catch { /* storage blocked: the choice just isn't kept */ }
  };
  const active = p.order.filter((d) => p.filter[d]?.size);
  const idle = DIMS.map((d) => d.id).filter((d) => !active.includes(d));
  return (
    <div className="filters" role="toolbar" aria-label="Filter the scan" data-folded={folded ? "" : undefined}>
      <button className="filters-fold" aria-expanded={!folded} aria-controls="scan-filter-chips"
              aria-label={folded ? "Show all filters" : "Hide unused filters"} title={folded ? "Show all filters" : "Hide unused filters"}
              onClick={() => fold(!folded)}>
        <SlidersHorizontal size={12} aria-hidden />
        {folded && <span>Filter{idle.length ? ` · ${idle.length}` : ""}</span>}
        {folded ? <ChevronsRight size={13} aria-hidden /> : <ChevronsLeft size={13} aria-hidden />}
      </button>
      <div className="filters-chips" id="scan-filter-chips">
        {[...active, ...(folded ? [] : idle)].map((d) => (
          <Chip key={d} dim={d} {...p} open={open === d} setOpen={(o) => setOpen(o ? d : null)} />
        ))}
        {active.length > 0 && <button className="filters-clear" onClick={() => p.onClear()}>Clear all <span className="label">Esc</span></button>}
      </div>
    </div>
  );
}

function Chip({ dim, open, setOpen, ...p }: FilterProps & { dim: Dim; open: boolean; setOpen: (o: boolean) => void }) {
  const meta = DIMS.find((d) => d.id === dim)!;
  const chosen = p.filter[dim];
  const values = useMemo(() => (open ? keyValues(dim, p.points, p.sources, p.position, p.filter) : []),
    [open, dim, p.points, p.sources, p.position, p.filter]);
  const max = Math.max(1, ...values.map((v) => v.n));
  const names = [...(chosen ?? [])].map((v) => valueName(dim, v));
  return (
    <div className="fchip" data-on={chosen?.size ? "" : undefined} data-open={open ? "" : undefined}
         onPointerEnter={(e) => isMouse(e) && setOpen(true)} onPointerLeave={(e) => isMouse(e) && setOpen(false)}>
      <button className="fchip-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
        {meta.scope !== "all" && <Glyph kind={SCOPE_GLYPH[meta.scope]} />}
        <span className="fchip-dim">{meta.name}</span>
        {names.length > 0 && <span className="fchip-val">{names[0]}{names.length > 1 ? ` +${names.length - 1}` : ""}</span>}
      </button>
      {chosen?.size ? <button className="fchip-x" aria-label={`Clear ${meta.name} filter`} onClick={() => p.onClear(dim)}><X size={12} /></button> : null}
      {open && (
        <div className="fpop">
          <div className="fpop-panel" role="listbox" aria-multiselectable aria-label={meta.name}>
            <p className="fpop-scope">{meta.scope !== "all" && <Glyph kind={SCOPE_GLYPH[meta.scope]} />}{SCOPE_NOTE[meta.scope]}</p>
            {values.map(({ v, name, n }) => (
              <button key={v} role="option" aria-selected={!!chosen?.has(v)} onClick={() => { p.onToggle(dim, v); setOpen(false); }}>
                <span className="fpop-name">{name}</span>
                <span className="fpop-bar" aria-hidden><span style={{ transform: `scaleX(${n / max})` }} /></span>
                <span className="fpop-n">{fmt(n)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------------------------- hover */
const useComment = (id: number | null) =>
  useQuery({ queryKey: ["comment", id], queryFn: () => api.get<Comment>(`/api/scan/comment/${id}`), staleTime: Infinity, enabled: id != null });

function HoverCard({ hover, points }: { hover: Hover; points: PointsPayload | undefined }) {
  const id = hover.comment != null && points ? points.cols.id[hover.comment] : null;
  const q = useComment(id);
  const left = Math.min(hover.x + 16, window.innerWidth - 336), top = Math.min(hover.y + 16, window.innerHeight - 140);
  return (
    <div className="hovercard" style={{ left, top }} role="tooltip">
      {id != null ? (
        <>
          <p>{q.data?.text ?? " "}</p>
          {q.data && (
            <div className="hovercard-meta">
              <i className={`mark ${hover.acquiredHere ? "new" : "held"}`} aria-hidden />
              <span>{CAR_NAME[q.data.car] ?? q.data.car}</span><span>{q.data.country}</span><span>{q.data.channel}</span>
            </div>
          )}
        </>
      ) : (
        <>
          <p>{hover.title}</p>
          {hover.sub && <div className="hovercard-meta"><span>{hover.sub}</span></div>}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------------------------- inspector */
const LAYER: Record<Selection["kind"], { name: string; what: string; glyph: GlyphKind }> = {
  comment: { name: "Customer comment", what: "Placed by meaning: comments that say similar things sit close together.", glyph: "comment" },
  cluster: { name: "Cluster", what: "Signals from many comments that express the same need. Blue = improve, white = keep.", glyph: "comment" },
  theme: { name: "Theme", what: "Related findings grouped by the AI, connected to research, study and options that confirm or contradict them.", glyph: "research" },
  area: { name: "Potential requirement area", what: "Themes the AI grouped into an area a requirement could address. Requirements are drafted in the next step.", glyph: "sales" },
  study: { name: "Customer study 2025", what: "Tick length: how far this topic is rated above or below this car's average.", glyph: "study" },
  option: { name: "Equipment option", what: "Today's car, from the German price list.", glyph: "option" },
  sales: { name: "BMW sales volume", what: "BMW-internal figures, stylized (Q-015). Outline = 2030 forecast.", glyph: "sales" },
  research: { name: "Web research", what: "Cited source, placed on the outer ring by publication date.", glyph: "research" },
};

const PUBLIC_LAYER: Record<"sales" | "study" | "options", { name: string; what: string; glyph: GlyphKind }> = {
  sales: { name: "Public sales figure", what: "Cited, published figure for this car. Dots and rings sit beside BMW's own bars, never mixed with them.", glyph: "sales" },
  study: { name: "Public rating", what: "Published review, award or study result about this car.", glyph: "study" },
  options: { name: "Product news", what: "Published news about this car's equipment, prices or availability.", glyph: "option" },
};

function Inspector({ sel, sales, onClose, cpLabel, structure }: { sel: Selection; sales: SourcesPayload["sales"]; onClose: () => void; cpLabel: (id: string) => string; structure?: StructurePayload }) {
  const L = sel.kind === "research" && sel.item.ring ? PUBLIC_LAYER[sel.item.ring] : LAYER[sel.kind];
  return (
    <aside className="sheet" aria-label={L.name}>
      <button className="sheet-close" onClick={onClose} aria-label="Close"><X size={16} /></button>
      <header className="sheet-head">
        <span className="sheet-layer"><Glyph kind={L.glyph} />{L.name}</span>
        <p className="sheet-what">{L.what}</p>
      </header>
      {sel.kind === "comment" && <><CommentBody id={sel.id} cpLabel={cpLabel} /><SignalList sourceId={sel.id} /></>}
      {sel.kind === "cluster" && <ClusterBody k={sel.key} data={structure} />}
      {sel.kind === "theme" && <ThemeBody k={sel.key} />}
      {sel.kind === "area" && <AreaBody k={sel.key} data={structure} />}
      {sel.kind === "study" && <><StudyBody s={sel.item} /><EvidenceUse type="study" id={sel.item.id} structure={structure} /></>}
      {sel.kind === "option" && (
        <>
          <h2 className="sheet-title">{sel.item.name ?? sel.item.code}</h2>
          <Facts rows={[["Car", CAR_NAME[sel.item.car] ?? sel.item.car], ["Category", sel.item.category], ["Availability", sel.item.availability],
                        ["Package", sel.item.package], ["Option code", sel.item.code]]} />
          <EvidenceUse type="option" id={sel.item.id} structure={structure} />
        </>
      )}
      {sel.kind === "sales" && <SalesBody row={sel.item} all={sales} />}
      {sel.kind === "research" && (
        <>
          <h2 className="sheet-title">{sel.item.headline}</h2>
          {(sel.item.value != null || sel.item.yoy != null) && (
            <div className="sheet-figure">
              {sel.item.value != null && <span className="num">{sel.item.value.toLocaleString("en-US")}{sel.item.unit === "pct" ? "%" : ""}</span>}
              {sel.item.yoy != null && <span className="sheet-yoy">{sel.item.yoy > 0 ? "+" : ""}{sel.item.yoy}% YoY</span>}
            </div>
          )}
          <Facts rows={[["Published", sel.item.published_at ?? "undated"], ["Known from", sel.item.new ? "JUL 26" : "JAN 26"],
                        ["About", sel.item.entity], ["Region", sel.item.region], ["Trust", sel.item.tier]]} />
          {sel.item.url && <a className="sheet-link" href={sel.item.url} target="_blank" rel="noreferrer">Open source <ExternalLink size={13} /></a>}
          <EvidenceUse type="research" id={sel.item.id} structure={structure} />
          <SignalList sourceId={sel.item.id} />
        </>
      )}
    </aside>
  );
}

// Which themes the AI linked this research / study / option item to at this checkpoint, and why. Research, study and
// options are not split into signals like comments: they enter the analysis as evidence for themes.
const RELATION: Record<string, string> = {
  supports: "Supports", contradicts: "Contradicts", competes_with: "Competitor", trend_for: "Trend",
  available_as_option: "Already offered", context: "Context",
};
function EvidenceUse({ type, id, structure }: { type: "research" | "study" | "option"; id: number; structure?: StructurePayload }) {
  if (!structure) return null;
  const edges = structure.ready ? structure.edges.filter((e) => e.src_type === type && e.src_id === String(id) && e.dst_type === "theme") : [];
  const theme = Object.fromEntries((structure.themes ?? []).map((t) => [t.key, t]));
  return (
    <div className="use">
      <div className="label">Used as evidence</div>
      {!structure.ready ? <p className="use-none">The AI has not structured this checkpoint yet.</p>
        : !edges.length ? <p className="use-none">Not linked to any theme at this checkpoint.</p>
        : edges.map((e) => (
          <div key={`${e.relation}>${e.dst_id}`} className="use-row" data-rel={e.relation}>
            <div className="use-head"><span className="use-theme">{theme[e.dst_id]?.title ?? e.dst_id}</span><span className="use-rel">{RELATION[e.relation] ?? e.relation}</span></div>
            {e.why && <p className="use-why">{e.why}</p>}
          </div>
        ))}
    </div>
  );
}

function Facts({ rows }: { rows: [string, string | null | undefined][] }) {
  return (
    <dl className="sheet-facts">
      {rows.filter(([, v]) => v).map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd>{v}</dd></div>)}
    </dl>
  );
}

function CommentBody({ id, cpLabel }: { id: number; cpLabel: (id: string) => string }) {
  const q = useComment(id);
  const c = q.data;
  if (!c) return <div className="sheet-skel" aria-hidden><span /><span /><span /></div>;
  const label = c.bmw_labels?.[0];
  return (
    <>
      <blockquote className="sheet-quote">{c.text}</blockquote>
      <Facts rows={[["Car", CAR_NAME[c.car] ?? c.car],
                    ["Market", `${MARKET_NAME[c.market] ?? c.market}${c.country && c.country !== c.market ? ` · ${c.country}` : ""}`],
                    ["Channel", c.channel], ["Engine", c.engine],
                    ["BMW label", `${label?.feedback_type ?? "Unlabelled"}${label?.vfc_level2 && label.vfc_level2 !== "no_class_found" ? ` · ${label.vfc_level2}` : ""}`],
                    ["Acquired", cpLabel(c.checkpoint)], ["ID", c.external_id]]} />
    </>
  );
}

function StudyBody({ s }: { s: Extract<Selection, { kind: "study" }>["item"] }) {
  const z = Math.max(-2.5, Math.min(2.5, s.z ?? 0));
  return (
    <>
      <h2 className="sheet-title">{s.item}</h2>
      <div className="sheet-figure"><span className="num">{studyValue(s)}</span></div>
      <div className="zbar" role="img" aria-label={`${z >= 0 ? "Above" : "Below"} this car's average by ${Math.abs(z).toFixed(1)} standard deviations`}>
        <span className="zbar-mid" />
        <span className="zbar-fill" style={{ left: z >= 0 ? "50%" : `${50 + (z / 2.5) * 50}%`, width: `${(Math.abs(z) / 2.5) * 50}%` }} />
        <span className="zbar-l label">below average</span><span className="zbar-r label">above average</span>
      </div>
      <Facts rows={[["Car", CAR_NAME[s.car] ?? s.car], ["Market", MARKET_NAME[s.market] ?? s.market],
                    ["Scale", s.scale === "dist_7" ? "7-point, share of top two answers" : "Mean rating, 0–10"]]} />
    </>
  );
}

function SalesBody({ row, all }: { row: Extract<Selection, { kind: "sales" }>["item"]; all: SourcesPayload["sales"] }) {
  const series = all.filter((s) => s.car === row.car && s.market === row.market).sort((a, b) => a.year - b.year);
  const max = Math.max(1, ...series.map((s) => s.units ?? 0));
  return (
    <>
      <h2 className="sheet-title">{CAR_NAME[row.car] ?? row.car} · {MARKET_NAME[row.market] ?? row.market}</h2>
      <div className="minibars" role="img" aria-label="Sales by year">
        {series.map((s) => (
          <div key={s.year} className="minibar" data-on={s.year === row.year ? "" : undefined} data-forecast={s.is_forecast ? "" : undefined}>
            <span className="minibar-n">{fmt(s.units)}</span>
            <span className="minibar-col"><span style={{ transform: `scaleY(${(s.units ?? 0) / max})` }} /></span>
            <span className="label">{s.year}{s.is_forecast ? " fc" : ""}</span>
          </div>
        ))}
      </div>
    </>
  );
}
