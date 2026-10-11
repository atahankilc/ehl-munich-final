// Page 4 overlays at the edges of the shared canvas: car line, market and view switch with the band readout top-left;
// the ranked priorities and the target inspector behind the top-right "Priorities" pill (factor waterfall, gates,
// what-if rung, bundle, flags, history, proposal and the PM's decision); the market × requirement matrix as the 2D
// alternative; the hover card; and the Guide / Agent dock bottom-left. State lives in ./store (market, selection)
// and page 3's store (car line), so the skyline in the canvas and the overlays stay in step.
import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Rung } from "@/lib/definition";
import type { Band, Proposal, Target } from "@/lib/prioritize";
import { BANDS, gateResult, gateWhy } from "@/lib/prioritize";
import { Dock } from "@/components/Guide";
import { getActor } from "@/lib/api";
import { getTopPanel, setTopPanel, useTopPanel } from "@/components/topPanel";
import { useCheckpoint } from "@/state/checkpoint";
import { AgentPanel, useActivity } from "../structure/AgentPanel";
import { domainColor } from "../definition/data";
import { setView, useView } from "../definition/store";
import { DEF_STAGES } from "../definition/stages";
import type { LineName } from "@/lib/definition";
import {
  CAUSE_LABEL, CP_LABEL, bandsAt, disagreements, factorLabel, flagLabel, isBlocked, linesOf, marketsOf, openProposals, parseFlags,
  pmBand, shownBand, tid, useDecision, usePrioritize, useProposalVerdict, useTargetDetail, useWhatIf, type PrioData,
} from "./data";
import { Arrow, BandMark, GateMark } from "./marks";
import { Waterfall } from "./Waterfall";
import { PrioritizeGuide } from "./guide";
import { getP, selectTarget, setP, useP } from "./store";
import { WeightsButton, WeightsPanel, setWeightsOpen, useWeightsOpen, weightsNote } from "./weights";
import { useRescoring } from "./rescore";
import { Challenged } from "./challenged";
import { BundleMembers, Deciding } from "./deciding";
import { arrow, bandMove, challengeOf, rfRank, riseFallOf } from "./pm";
import { RiseFallBanner } from "./risefall";
import "./pm.css";
import "./prioritize.css";

const fmt = (n: number | undefined | null) => (n == null ? "–" : Math.round(n).toLocaleString("en-US"));
const DOMAIN_LABEL: Record<string, string> = {
  exterior: "Exterior", interior: "Interior & comfort", powertrain: "Powertrain & charging", chassis: "Chassis & dynamics",
  assist: "Driver assistance", digital: "Infotainment & digital", variants: "Variants & packages", quality: "Design & quality",
};
const DOMAIN_ORDER = Object.keys(DOMAIN_LABEL);
const MARKET_NAME: Record<string, string> = { US: "US", EU: "Europe", CN: "China", JP: "Japan", RoW: "Rest of world" };

export function PrioritizeHud() {
  const pd = usePrioritize();
  const { data } = pd;
  const activity = useActivity("prioritize");
  const line = useView((s) => s.line);
  const lines = useMemo(() => linesOf(data), [data]);
  const markets = useMemo(() => marketsOf(data, line), [data, line]);
  const stored = useP((s) => s.market[line]);
  const market = stored && markets.includes(stored) ? stored : markets[0] ?? "";
  const selected = useP((s) => s.selected);
  const view = useP((s) => s.view);
  useP((s) => s.pending);
  useP((s) => s.pendingProposals);

  // page 4 continues on the car: page 3's stage is the car, nothing of page 3 stays open
  useEffect(() => { setView({ stage: DEF_STAGES[DEF_STAGES.length - 1], auto: false, selected: null, hover: null, hoverPos: null, bundle: null }); }, []);
  // a line without prioritized targets falls back to one that has them
  useEffect(() => { if (lines.length && !lines.includes(line)) setView({ line: (lines.includes("5 Series") ? "5 Series" : lines[0]) as LineName }); }, [lines, line]);

  const targets = useMemo(() => data.targets.filter((t) => t.line === line && t.market === market), [data, line, market]);
  const sel = selected ? targets.find((t) => t.key === selected) ?? null : null;

  // the list and inspector sit behind the Priorities pill; picking a column opens it, closing it deselects
  const top = useTopPanel();
  const showPanel = top === "priorities";
  useEffect(() => { if (selected && getTopPanel() !== "priorities") setTopPanel("priorities"); }, [selected]);
  useEffect(() => { if (top !== "priorities" && getP().selected) selectTarget(null); }, [top]);
  useEffect(() => { if (selected && !data.targets.some((t) => t.key === selected && t.line === line)) selectTarget(null); }, [selected, line, data]);

  const setMarket = (m: string) => setP((s) => ({ market: { ...s.market, [line]: m } }));
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))) return;
      if (e.key === "Escape") {
        const s = getP();
        if (s.selected) selectTarget(null);
        else if (s.bundle) setP({ bundle: null });
        else if (s.view === "matrix") setP({ view: "skyline" });
        else setTopPanel((t) => (t === "priorities" ? null : t));
      }
      // [ and ] step through the line's markets (the arrow keys belong to the checkpoints)
      if (e.key === "[" || e.key === "]") {
        const i = markets.indexOf(market) + (e.key === "]" ? 1 : -1);
        if (i >= 0 && i < markets.length) setMarket(markets[i]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  useEffect(() => () => setP({ hover: null, hoverPos: null }), []);
  const weightsOpen = useWeightsOpen();
  useEffect(() => { if (view === "matrix") setWeightsOpen(false); }, [view]);   // the matrix and the weights share the left
  useEffect(() => () => setWeightsOpen(false), []);
  const rescoring = useRescoring() || data.rescore?.state === "running";

  /* readout */
  const counts = { Must: 0, Should: 0, Could: 0 } as Record<Band, number>;
  for (const t of targets) counts[shownBand(t)]++;
  const props = openProposals(data).filter((p) => p.line === line && p.market === market);
  const joint = new Set(targets.flatMap((t) => parseFlags(t).filter((f) => f.kind === "choose_jointly").map((f) => [t.key, f.partner].sort().join("~")))).size;
  const blocked = targets.filter(isBlocked).length;
  const disagree = disagreements(data, line);
  const confirmed = targets.filter((t) => pmBand(t)).length;
  // the matrix hangs right under this corner, however tall it is (sample note, wrapped controls)
  const hudRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = hudRef.current;
    if (!el) return;
    const put = () => document.documentElement.style.setProperty("--phud-bottom", `${Math.round(el.getBoundingClientRect().bottom)}px`);
    put();
    const ro = new ResizeObserver(put);
    ro.observe(el);
    window.addEventListener("resize", put);
    return () => { ro.disconnect(); window.removeEventListener("resize", put); };
  }, []);

  return (
    <>
      <div className="hud-tl phud" ref={hudRef}>
        {/* the band numbers stay narrow enough to sit left of the top bar, like pages 1–3; the rest goes under them */}
        <dl className="preadout" aria-label={`Priorities for ${line} in ${market}`}>
          {BANDS.map((b) => (
            <div key={b} className="preadout-band">
              <dt className="label"><BandMark band={b} color="var(--ink)" size="sm" />{b}</dt>
              <dd><span className="num">{counts[b]}</span></dd>
            </div>
          ))}
        </dl>
        <dl className="pstats" aria-label="Open items">
          <div><dt className="label">proposals</dt><dd className="num">{props.length}</dd></div>
          <div><dt className="label">choose jointly</dt><dd className="num">{joint}</dd></div>
          <div><dt className="label">blocked</dt><dd className="num">{blocked}</dd></div>
          {markets.length > 1 && <div><dt className="label">markets disagree</dt><dd className="num">{disagree.size}</dd></div>}
        </dl>
        <Challenged pd={pd} />
        <p className="pnote label">{targets.length} targets · {confirmed} confirmed by the PM · {weightsNote(data.weights)} · market weight {data.labels?.market_weight ?? "stylized (Q-015)"}{rescoring && <span className="prescore" role="status"> · re-scoring…</span>}</p>
        <div className="pcontrols">
          <div className="dseg" role="radiogroup" aria-label="Car line">
            {lines.map((l) => <button key={l} role="radio" aria-checked={line === l} onClick={() => setView({ line: l as LineName })}>{l}</button>)}
          </div>
          <div className="dseg pmarkets" role="radiogroup" aria-label="Market">
            <span className="dseg-name label">Market</span>
            {markets.map((m) => <button key={m} role="radio" aria-checked={market === m} onClick={() => setMarket(m)} title={MARKET_NAME[m] ?? m}>{m}</button>)}
          </div>
          <div className="dseg" role="radiogroup" aria-label="View">
            <button role="radio" aria-checked={view === "skyline"} onClick={() => setP({ view: "skyline" })}>Skyline</button>
            <button role="radio" aria-checked={view === "matrix"} onClick={() => setP({ view: "matrix" })}>Matrix</button>
          </div>
          <WeightsButton pd={pd} />
        </div>
        {pd.sample && <p className="dsample" role="status"><b>Sample data</b> {pd.why}. Live priorities replace it as soon as the stage has run.</p>}
      </div>

      {view === "matrix" && <Matrix pd={pd} line={line} markets={markets} market={market} onMarket={setMarket} />}
      {weightsOpen && view !== "matrix" && <WeightsPanel pd={pd} />}
      {showPanel && (sel ? <Inspector key={tid(sel)} pd={pd} t={sel} markets={markets} onMarket={setMarket} /> : <RankedList pd={pd} targets={targets} line={line} market={market} />)}
      <TargetHover pd={pd} line={line} market={market} />
      <Dock mode="prioritize" sel={null} guide={<PrioritizeGuide sel={sel} view={view} />} agent={<AgentPanel layer="prioritize" />} running={!!activity.data?.running} />
    </>
  );
}

/* --------------------------------------------------------------------------------------------- ranked list */
function RankedList({ pd, targets, line, market }: { pd: PrioData; targets: Target[]; line: string; market: string }) {
  const selected = useP((s) => s.selected);
  const sorted = [...targets].sort((a, b) => b.score - a.score);
  const proposals = new Map(openProposals(pd.data).filter((p) => p.line === line && p.market === market).map((p) => [p.key, p]));
  return (
    <nav className="dlist plist" id="priorities-panel" aria-label="Priorities">
      <p className="dlist-head"><span className="sheet-layer">Priorities · {line} · {market}</span><span className="label">Score</span></p>
      {BANDS.map((b) => {
        // challenged PM decisions first: downgrades (red ▼) above upgrade opportunities (green ▲), then by score
        const items = sorted.filter((t) => shownBand(t) === b).sort((x, y) => rfRank(riseFallOf(pd.data, x)) - rfRank(riseFallOf(pd.data, y)));
        if (!items.length) return null;
        return (
          <section key={b}>
            <h3 className="dlist-domain plist-band"><BandMark band={b} color="var(--ink-2)" size="sm" />{b}<span>{items.length}</span></h3>
            <ul>
              {items.map((t) => {
                const pm = pmBand(t);
                const flags = parseFlags(t);
                const p = proposals.get(t.key);
                const d = t.prev ? t.score - t.prev.score : 0;
                const rf = riseFallOf(pd.data, t);
                const mv = bandMove(t);
                return (
                  <li key={t.key}>
                    <button className="dlist-row plist-row" aria-current={selected === t.key ? "true" : undefined} data-rf={rf?.dir}
                            onClick={() => selectTarget(selected === t.key ? null : t.key)}
                            onPointerEnter={() => setP({ hover: t.key })} onPointerLeave={() => setP({ hover: null })}>
                      <span className="plist-rank">{t.rank}</span>
                      <BandMark band={shownBand(t)} color={domainColor(t.domain)} />
                      <span className="dlist-title">{t.title}</span>
                      <span className="plist-tags">
                        {rf && <b className="prf-tag" data-rf={rf.dir} title={`${rf.dir === "down" ? "Downgrade" : "Upgrade suggested"}: your ${rf.from} → AI ${rf.to} · ${rf.cause}`}>{rf.dir === "down" ? "▼" : "▲"} {rf.from} → {rf.to}</b>}
                        {pm && <span className="ptag-pmok">PM ✓</span>}
                        {isBlocked(t) && <span className="psky-blocked" title="Brand fit blocks approval" />}
                        {flags.some((f) => f.kind === "choose_jointly") && <span className="ptag" data-dashed="" title="Choose jointly">joint</span>}
                        {p && !rf && <span className="ptag" title={`AI proposes ${p.proposed_band}`}>→ {p.proposed_band}</span>}
                        <span className="plist-conf" title="Confidence">{t.confidence.level}</span>
                      </span>
                      <span className="dlist-val">{fmt(t.score)}{mv ? <Arrow d={mv === "up" ? 1 : -1} rf={mv} /> : Math.abs(d) >= 1 && <Arrow d={d} />}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}

/* --------------------------------------------------------------------------------------------- hover */
function TargetHover({ pd, line, market }: { pd: PrioData; line: string; market: string }) {
  const hover = useP((s) => s.hover);
  const pos = useP((s) => s.hoverPos);
  const selected = useP((s) => s.selected);
  if (!hover || !pos || hover === selected) return null;
  const t = pd.data.targets.find((x) => x.key === hover && x.line === line && x.market === market);
  if (!t) return null;
  const left = Math.min(pos.x + 16, window.innerWidth - 336), top = Math.min(pos.y + 16, window.innerHeight - 140);
  return (
    <div className="hovercard" style={{ left, top }} role="tooltip">
      <p>{t.title}</p>
      <div className="hovercard-meta">
        <BandMark band={shownBand(t)} color={domainColor(t.domain)} size="sm" /><span>{shownBand(t)} · {fmt(t.score)}</span>
        <span>#{t.rank} in {line} · {market}</span><span>{t.confidence.level}</span>
      </div>
      <div className="hovercard-meta"><span>{DOMAIN_LABEL[t.domain] ?? t.domain}</span>{t.prev && <span>JAN {fmt(t.prev.score)} → JUL {fmt(t.score)}</span>}</div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------------- matrix */
// Rows grouped by domain, one column per market of the line; each cell the band mark (domain hue) with its score,
// an arrow where JAN → JUL moved it, a blue ring where the PM confirmed it. A white tick marks rows whose band differs
// between markets.
function Matrix({ pd, line, markets, market, onMarket }: { pd: PrioData; line: string; markets: string[]; market: string; onMarket: (m: string) => void }) {
  const { position } = useCheckpoint();
  const selected = useP((s) => s.selected);
  const hover = useP((s) => s.hover);
  const onLine = pd.data.targets.filter((t) => t.line === line);
  const cell = new Map(onLine.map((t) => [tid(t), t]));
  const reqs = [...new Map(onLine.map((t) => [t.key, t])).values()];
  const best = (k: string) => Math.max(...onLine.filter((t) => t.key === k).map((t) => t.score));
  const groups = DOMAIN_ORDER.map((d) => ({ d, items: reqs.filter((r) => r.domain === d).sort((a, b) => best(b.key) - best(a.key)) })).filter((g) => g.items.length);
  const disagree = disagreements(pd.data, line);
  const props = new Set(openProposals(pd.data).map((p) => `${p.key}|${p.line}|${p.market}`));
  return (
    <section className="pmatrix" aria-label={`Market by requirement, ${line}`}>
      <header className="pmatrix-head">
        <span className="sheet-layer">Market × requirement · {line}</span>
        <span className="pmatrix-legend label">
          <span><BandMark band="Must" color="var(--ink-2)" size="sm" />Must</span><span><BandMark band="Should" color="var(--ink-2)" size="sm" />Should</span>
          <span><BandMark band="Could" color="var(--ink-2)" size="sm" />Could</span><span><i className="pmatrix-pm" />PM confirmed</span>
          {position > 1 && <span>▲▼ since JAN</span>}<span><i className="pmatrix-dis" />markets disagree</span>
          {position > 1 && <><span className="prf-legend" data-rf="down"><b>▼</b>below your band</span><span className="prf-legend" data-rf="up"><b>▲</b>above your band</span></>}
        </span>
      </header>
      <div className="pmatrix-grid" style={{ ["--m" as string]: markets.length }}>
        <div className="pmatrix-row pmatrix-cols" aria-hidden>
          <span />
          {markets.map((m) => <button key={m} className="pmatrix-mkt" aria-pressed={m === market} onClick={() => onMarket(m)}>{m}</button>)}
          <span />
        </div>
        {groups.map(({ d, items }) => (
          <div key={d} className="pmatrix-group">
            <h3 className="dlist-domain"><i style={{ background: domainColor(d) }} aria-hidden />{DOMAIN_LABEL[d] ?? d}<span>{items.length}</span></h3>
            {items.map((r) => (
              <div key={r.key} className="pmatrix-row" data-on={selected === r.key ? "" : undefined} data-hover={hover === r.key ? "" : undefined}
                   onPointerEnter={() => setP({ hover: r.key })} onPointerLeave={() => setP({ hover: null })}>
                <button className="pmatrix-title" onClick={() => selectTarget(selected === r.key ? null : r.key)}>{r.title}</button>
                {markets.map((m) => {
                  const t = cell.get(`${r.key}|${line}|${m}`);
                  if (!t) return <span key={m} className="pmatrix-cell" data-empty="">·</span>;
                  const d = t.prev && position > 1 ? t.score - t.prev.score : 0;
                  const b = shownBand(t);
                  return (
                    <button key={m} className="pmatrix-cell" data-current={m === market ? "" : undefined} data-rf={riseFallOf(pd.data, t)?.dir} title={`${m}: ${b} · ${fmt(t.score)}`}
                            onClick={() => { onMarket(m); selectTarget(r.key); }}>
                      <BandMark band={b} color={domainColor(t.domain)} pm={!!pmBand(t)} />
                      <span className="pmatrix-score">{fmt(t.score)}</span>
                      {(() => { const mv = position > 1 ? bandMove(t) : null; return mv
                        ? <Arrow d={mv === "up" ? 1 : -1} rf={mv} />
                        : (Math.abs(d) >= 3 || (t.prev && t.prev.band !== t.band && position > 1)) && <Arrow d={d} />; })()}
                      {pmBand(t) && <span className="pmatrix-ok" aria-label="PM confirmed">✓</span>}
                      {(() => { const rf = riseFallOf(pd.data, t); const ch = rf ? null : challengeOf(pd.data, t); return rf
                        ? <span className="prf-cell" data-rf={rf.dir} title={`${rf.dir === "down" ? "Downgrade" : "Upgrade suggested"}: your ${rf.from} → AI ${rf.to} · ${rf.cause}`}>{rf.dir === "down" ? "▼" : "▲"}{rf.to[0]}</span>
                        : ch ? <span className="pmatrix-chal" title={`AI proposes ${ch.proposed_band} against your ${pmBand(t)}`}><b className="ptag-chal">!</b>{ch.proposed_band[0]}{arrow(ch.proposed_band, pmBand(t))}</span>
                        : props.has(tid(t)) && <span className="pmatrix-prop" title="Open AI proposal">P</span>; })()}
                    </button>
                  );
                })}
                <span className="pmatrix-dis" data-on={disagree.has(r.key) ? "" : undefined} aria-label={disagree.has(r.key) ? "markets disagree" : undefined} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

/* --------------------------------------------------------------------------------------------- inspector */
const RUNGS: Rung[] = ["baseline", "threshold", "target", "stretch"];

function Inspector({ pd, t, markets, onMarket }: { pd: PrioData; t: Target; markets: string[]; onMarket: (m: string) => void }) {
  const { data } = pd;
  const { position } = useCheckpoint();
  const detail = useTargetDetail(t, pd);
  const at = bandsAt(data);
  const band = shownBand(t);
  const pm = pmBand(t);
  const [rung, setRung] = useState<Rung | null>(null);
  const cur = t.rung.chosen ?? t.rung.recommended;
  const wi = useWhatIf(t, rung && rung !== cur ? rung : null, pd);
  const flags = parseFlags(t);
  const titleOf = (k: string) => data.targets.find((x) => x.key === k)?.title ?? k;
  const others = markets.map((m) => data.targets.find((x) => x.key === t.key && x.line === t.line && x.market === m) ?? null);
  const disagree = new Set(others.filter(Boolean).map((x) => shownBand(x!))).size > 1;
  const bundle = t.bundle_id ? data.bundles.find((b) => b.id === t.bundle_id) ?? null : null;
  const bundleOn = useP((s) => s.bundle);
  const proposal = openProposals(data).find((p) => p.key === t.key && p.line === t.line && p.market === t.market) ?? null;
  const rf = riseFallOf(data, t);   // a challenged PM decision: the red / green banner with Accept / Reject replaces the proposal box
  const d = t.prev ? t.score - t.prev.score : 0;
  const gates: [string, keyof Target["gates"]][] = [["Brand fit", "brand"], ["Segment fit", "segment"], ["Market fit", "market"], ["Feasibility", "feasibility"]];

  return (
    <aside className="sheet dsheet psheet" id="priorities-panel" aria-label="Target priority">
      <button className="sheet-close" onClick={() => selectTarget(null)} aria-label="Close"><X size={16} /></button>
      <header className="sheet-head">
        <span className="sheet-layer"><BandMark band={band} color={domainColor(t.domain)} size="sm" />{DOMAIN_LABEL[t.domain] ?? t.domain} · {t.line} · {t.market}</span>
        <p className="sheet-what">One requirement in one market. The AI scores it and proposes a band; the PM decides.</p>
      </header>
      <h2 className="sheet-title">{t.title}</h2>
      {rf && <RiseFallBanner key={String(rf.proposal.id)} pd={pd} rf={rf} />}
      <Deciding t={t} />

      <div className="pfigure">
        <span className="pfigure-num">{fmt(t.score)}</span>
        <span className="pfigure-side">
          <span className="pfigure-band">{band}{pm && <span className="ptag-pm">PM</span>}{!pm && <span className="ptag">AI proposal</span>}</span>
          <span className="label">#{t.rank} of {data.targets.filter((x) => x.line === t.line && x.market === t.market).length} in {t.line} · {t.market} · {t.confidence.level} confidence</span>
          {t.prev && position > 1 && <span className="label">JAN {fmt(t.prev.score)} {t.prev.band} → JUL {fmt(t.score)} {t.band} <Arrow d={Math.abs(d) >= 1 ? d : 0} /></span>}
        </span>
      </div>

      {markets.length > 1 && (
        <div className="dblock">
          <span className="label">Across {t.line} markets{disagree ? " · markets disagree" : ""}</span>
          <div className="pmkts">
            {markets.map((m, i) => {
              const o = others[i];
              return (
                <button key={m} className="pmkt" aria-pressed={m === t.market} disabled={!o} onClick={() => o && onMarket(m)}>
                  <span className="pmkt-m">{m}</span>
                  {o ? <><BandMark band={shownBand(o)} color={domainColor(o.domain)} pm={!!pmBand(o)} /><span className="pmkt-s">{fmt(o.score)}</span></> : <span className="pmkt-s">not targeted</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="dblock">
        <span className="label">How the score adds up</span>
        <Waterfall t={t} at={at} band={band} whatIf={wi.data ? { score: wi.data.score, band: wi.data.band } : null} />
        <p className="dnote"><span className="label">Rationale</span>{t.rationale}</p>
      </div>

      <div className="dblock">
        <span className="label">Gates</span>
        <ul className="pgates">
          {gates.map(([name, k]) => {
            const r = gateResult(t.gates?.[k]);
            return (
              <li key={k} data-r={r}>
                <GateMark result={r} /><span className="pgates-name">{name}</span><span className="pgates-r">{r}</span>
                {gateWhy(t.gates?.[k]) && <span className="pgates-why">{gateWhy(t.gates?.[k])}</span>}
              </li>
            );
          })}
        </ul>
        {isBlocked(t) && <p className="pblock">Brand fit fails: a PM approval needs an override with a rationale (D-008).</p>}
      </div>

      <div className="dblock">
        <div className="dlinks-head"><span className="label">Ladder rung · what if</span><span className="label">AI recommends {t.rung.recommended}{t.rung.chosen ? ` · PM chose ${t.rung.chosen}` : ""}</span></div>
        <div className="dseg prungs" role="radiogroup" aria-label="What-if rung">
          {RUNGS.map((r) => (
            <button key={r} role="radio" aria-checked={(rung ?? cur) === r} onClick={() => setRung(r === cur ? null : r)}>
              {r}{r === cur ? " ·" : ""}
            </button>
          ))}
        </div>
        {rung && rung !== cur && (
          wi.data ? (
            <div className="pwhatif">
              <p><span className="num">{fmt(t.score)}</span> → <span className="num">{fmt(wi.data.score)}</span>
                <span className="label"> {band === wi.data.band ? `stays ${band}` : `${band} → ${wi.data.band}`} · not stored</span></p>
              {wi.data.exposures.length > 0 ? (
                <ul className="drail">{wi.data.exposures.map((x, i) => <li key={i}><b>{x.note ?? `exposure via ${x.via}`}</b> · {x.title ?? titleOf(x.key)}</li>)}</ul>
              ) : <p className="label">No linked requirement exposed.</p>}
            </div>
          ) : wi.error ? <p className="derror">What-if unavailable: {wi.error.message}</p> : <p className="label">Recomputing…</p>
        )}
      </div>

      {bundle && (
        <div className="dblock">
          <div className="dlinks-head">
            <span className="label">Bundle · prioritized together</span>
            <button className="dtext" aria-pressed={bundleOn === bundle.id} onClick={() => setP({ bundle: bundleOn === bundle.id ? null : bundle.id })}>{bundleOn === bundle.id ? "Hide bundle" : "Show bundle"}</button>
          </div>
          <BundleMembers t={t} bundle={bundle} targets={data.targets} />
          {bundle.reason && <p className="label">{bundle.reason}; the bundle shares its strongest member's band.</p>}
        </div>
      )}

      {flags.filter((f) => f.kind !== "brand_blocked").length > 0 && (
        <div className="dblock">
          <span className="label">Flags</span>
          <ul className="pflags">
            {flags.filter((f) => f.kind !== "brand_blocked").map((f) => (
              <li key={f.raw}>
                <span className="ptag" data-dashed={f.kind === "choose_jointly" ? "" : undefined}>{flagLabel(f.kind)}{f.via ? ` · ${f.via}` : ""}</span>
                {f.kind === "choose_jointly" && f.partner && <button className="dlink-other" onClick={() => selectTarget(f.partner!)}>with {titleOf(f.partner)}</button>}
                {f.kind === "bundle_band" && <span className="label">scored {f.band} on its own</span>}
                {f.kind === "borrowed_voice" && <span className="label">no own-market comments; × 0.5 and capped (D-038)</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(detail?.history?.length ?? 0) > 0 && (
        <div className="dblock">
          <span className="label">History</span>
          <ol className="phistory">
            {detail!.history.map((h) => (
              <li key={h.checkpoint}>
                <span className="phistory-cp">{CP_LABEL[h.checkpoint] ?? h.checkpoint}</span>
                <BandMark band={h.band} color={domainColor(t.domain)} size="sm" />
                <span className="phistory-s">{fmt(h.score)}</span>
                <span className="label">{h.band}{h.rung ? ` · ${h.rung}` : ""}{h.confirmed ? ` · PM ${h.confirmed}` : ""}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {proposal && !rf && <ProposalBlock pd={pd} p={proposal} />}
      <DecisionBlock pd={pd} t={t} bundled={!!bundle && bundle.keys.length > 1} />
    </aside>
  );
}

function ProposalBlock({ pd, p }: { pd: PrioData; p: Proposal }) {
  const verdict = useProposalVerdict(pd);
  const [open, setOpen] = useState<"accept" | "reject" | null>(null);
  const [why, setWhy] = useState("");
  const deltas = Object.entries(p.factor_delta ?? {}).filter(([, v]) => v);
  const down = deltas.reduce((s, [, v]) => s + v, 0) < 0;
  return (
    <div className="dblock pproposal">
      <span className="label">AI proposal · JAN → JUL</span>
      <p className="pproposal-line"><BandMark band={p.old_band} color="var(--ink-2)" size="sm" />{p.old_band ?? "–"} <span aria-hidden>→</span> <BandMark band={p.proposed_band} color="var(--ink)" size="sm" />{p.proposed_band}
        <span className="label"> · {CAUSE_LABEL[p.cause] ?? p.cause}{p.cause === "area_strengthened" && down ? " (weaker)" : ""}</span></p>
      {deltas.length > 0 && <ul className="drail">{deltas.map(([k, v]) => <li key={k}>{factorLabel(k)} <b>{v > 0 ? "+" : "−"}{Math.abs(v)} pts</b></li>)}</ul>}
      {open ? (
        <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); if (why.trim().length >= 5) { verdict.mutate({ p, verdict: open, rationale: why.trim() }); setOpen(null); setWhy(""); } }}>
          <textarea rows={2} value={why} onChange={(e) => setWhy(e.target.value)} autoFocus placeholder={`Why ${open} this proposal? (required)`} aria-label="Rationale" />
          <div className="ladder-actions">
            <button type="submit" className="dbtn primary" disabled={why.trim().length < 5 || verdict.isPending}>{open === "accept" ? `Accept → ${p.proposed_band}` : "Reject"}</button>
            <button type="button" className="dbtn" onClick={() => setOpen(null)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="dlink-actions">
          <button className="dtext" onClick={() => setOpen("accept")}>Accept</button>
          <button className="dtext" onClick={() => setOpen("reject")}>Reject</button>
        </div>
      )}
      {verdict.isError && <p className="derror">Not saved: {(verdict.error as Error).message}</p>}
    </div>
  );
}

function DecisionBlock({ pd, t, bundled = false }: { pd: PrioData; t: Target; bundled?: boolean }) {
  const decide = useDecision(pd);
  const pm = pmBand(t);
  const [pick, setPick] = useState<Band | null>(null);
  const [why, setWhy] = useState("");
  const [lastWhy, setLastWhy] = useState("");
  const blocked = isBlocked(t);
  const send = () => {
    if (!pick || why.trim().length < 5) return;
    decide.mutate({ key: t.key, line: t.line, market: t.market, priority: pick, rationale: blocked ? `[brand-fit override] ${why.trim()}` : why.trim() });
    setLastWhy(why.trim()); setPick(null); setWhy("");
  };
  return (
    <div className="dblock pdecide">
      <span className="label">PM decision · {t.line} · {t.market}</span>
      {pm && (pm === t.confirmed?.priority
        ? <p className="ladder-why pm"><span className="label">PM</span>{pm} · {t.confirmed.actor}{t.confirmed.rationale ? ` · ${t.confirmed.rationale}` : ""}</p>
        : <p className="ladder-why pm"><span className="label">PM</span>{pm} · {getActor()} · {lastWhy || "just now"}</p>)}
      <p className="pdecide-scope">{pick ? <>You confirm <b>{pick}</b> for “{t.title}” in {t.line} · {t.market} only.</> : <>A decision applies to this requirement in {t.line} · {t.market} only.</>}
        {bundled ? " Bundle members keep their own decisions." : ""}</p>
      <div className="pdecide-bands" role="radiogroup" aria-label="Priority">
        {BANDS.map((b) => (
          <button key={b} role="radio" aria-checked={pick === b} data-pm={pm === b ? "" : undefined} onClick={() => setPick(pick === b ? null : b)}>
            <BandMark band={b} color={pm === b ? "var(--sweep-hi)" : "var(--ink)"} pm={pm === b} />{b}{t.band === b && <span className="ladder-ai">AI</span>}
          </button>
        ))}
      </div>
      {pick && (
        <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <textarea rows={2} value={why} onChange={(e) => setWhy(e.target.value)} autoFocus aria-label="Rationale"
                    placeholder={blocked ? "Brand fit fails. Why override it? (required)" : `Why ${pick} for ${t.market}? (required)`} />
          <div className="ladder-actions">
            <button type="submit" className="dbtn primary" disabled={why.trim().length < 5 || decide.isPending}>{blocked ? `Override and confirm ${pick}` : `Confirm ${pick}`}</button>
            <button type="button" className="dbtn" onClick={() => setPick(null)}>Cancel</button>
          </div>
        </form>
      )}
      {decide.isError && <p className="derror">Not saved: {(decide.error as Error).message}</p>}
      {pd.sample && <p className="label">Sample data: decisions are kept in this view only.</p>}
    </div>
  );
}

