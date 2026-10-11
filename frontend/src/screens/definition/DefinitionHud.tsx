// Page 3 overlays at the edges of the shared canvas: readout, car-line switch, domain filter and the requirement list
// top-left; the requirement inspector (metric, acceptance, target ladders, links) top-right; the hover card; and the
// Guide dock bottom-left. All state lives in ./store so the 3D layer and the overlays stay in step.
import { useEffect, useMemo, useRef, useState } from "react";
import { useProgress } from "@react-three/drei";
import { ArrowRight, ChevronsLeft, ChevronsRight, SlidersHorizontal, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import type { DefLink, Requirement } from "@/lib/definition";
import { Dock } from "@/components/Guide";
import { AgentPanel, useActivity } from "../structure/AgentPanel";
import { getTopPanel, setTopPanel, useTopPanel } from "@/components/topPanel";
import {
  LINES, RELATION_NAME, domainColor, fmtLevel, isDashed, linkVerdict, rowFor, useChoice, useDefinition, useLinkReview,
  useRequirementDetail, type DefData,
} from "./data";
import { Ladder } from "./Ladder";
import { DefinitionGuide } from "./guide";
import { getView, select, setView, useView, type LinkMode } from "./store";
import { DefinitionFunnel } from "./DefinitionFunnel";
import "./definition.css";

export function DefinitionHud() {
  const def = useDefinition();
  const activity = useActivity("definition");
  const line = useView((s) => s.line);
  const selected = useView((s) => s.selected);
  const domains = useView((s) => s.domains);
  const linkMode = useView((s) => s.links);
  useView((s) => s.pendingLinks);
  const { data } = def;

  const onLine = useMemo(() => data.requirements.filter((r) => r.lines.includes(line)), [data, line]);
  const sel = selected ? data.requirements.find((r) => r.key === selected) ?? null : null;

  // the list and inspector sit behind the Requirements pill, top-right next to Audit; one of the two is open at a time.
  // Picking a requirement (a pin or a row) opens the panel; closing it, or opening Audit, deselects so the car recentres.
  const top = useTopPanel();
  const showReq = top === "requirements";
  useEffect(() => { if (selected && getTopPanel() !== "requirements") setTopPanel("requirements"); }, [selected]);
  useEffect(() => { if (top !== "requirements" && getView().selected) select(null); }, [top]);

  // a requirement that is not on the chosen line closes; Esc closes the inspector, then clears filters, then the panel
  useEffect(() => { if (sel && !sel.lines.includes(line)) select(null); }, [sel, line]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const v = getView();
      if (v.selected) select(null);
      else if (v.domains.length || v.bundle) setView({ domains: [], bundle: null });
      else setTopPanel((t) => (t === "requirements" ? null : t));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => () => setView({ hover: null, hoverPos: null }), []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of onLine) c[r.domain] = (c[r.domain] ?? 0) + 1;
    return c;
  }, [onLine]);
  const toggleDomain = (d: string) => setView((s) => ({ domains: s.domains.includes(d) ? s.domains.filter((x) => x !== d) : [...s.domains, d] }));

  return (
    <>
      <div className="hud-tl dhud">
        {/* the stage funnel replaces the readout: the same counts, as the steps that produced them */}
        <DefinitionFunnel def={def} />
        {def.sample && (
          <p className="dsample" role="status"><b>Sample data</b> {def.why}. Live definitions replace it as soon as the pipeline has run.</p>
        )}
        <div className="dcontrols">
          <div className="dseg" role="radiogroup" aria-label="Car line">
            {LINES.map((l) => (
              <button key={l} role="radio" aria-checked={line === l} onClick={() => setView({ line: l })}>{l}</button>
            ))}
          </div>
          <div className="dseg" role="radiogroup" aria-label="Links">
            <span className="dseg-name label">Links</span>
            {(["strong", "all", "off"] as LinkMode[]).map((m) => (
              <button key={m} role="radio" aria-checked={linkMode === m} onClick={() => setView({ links: m })}>{m === "strong" ? "Strong" : m === "all" ? "All" : "Off"}</button>
            ))}
          </div>
          {/* one line: car line, links, then the domain filter */}
          <DomainFilter data={data} counts={counts} domains={domains} onToggle={toggleDomain} />
        </div>

        <ModelProgress />
      </div>

      {showReq && (sel ? <Inspector key={sel.key} def={def} r={sel} line={line} /> : <RequirementList def={def} reqs={onLine} line={line} />)}
      <PinHover def={def} />
      <Dock mode="definition" sel={null} guide={<DefinitionGuide sel={sel} />} agent={<AgentPanel layer="definition" />} running={!!activity.data?.running} />
    </>
  );
}

// Domain chips, organised like the Evidence filter bar: a toggle at the head of the row folds the unused domains away
// and unfolds them again (kept per browser); chosen domains always stay, first, in the order they were chosen, so
// folding never hides an active filter and choosing one never moves a chip that is already set.
const DOMAIN_FOLD_KEY = "definition.domains.folded";
const readDomainFold = () => { try { return localStorage.getItem(DOMAIN_FOLD_KEY) === "1"; } catch { return false; } };

function DomainFilter({ data, counts, domains, onToggle }: {
  data: DefData["data"]; counts: Record<string, number>; domains: string[]; onToggle: (d: string) => void;
}) {
  const [folded, setFolded] = useState(readDomainFold);
  const fold = (f: boolean) => {
    setFolded(f);
    try { localStorage.setItem(DOMAIN_FOLD_KEY, f ? "1" : "0"); } catch { /* storage blocked: the choice just isn't kept */ }
  };
  const byKey = new Map(data.domains.map((d) => [d.key, d]));
  const active = domains.filter((k) => byKey.has(k));
  const idle = data.domains.filter((d) => counts[d.key] && !domains.includes(d.key)).map((d) => d.key);
  return (
    <div className="dfilters" role="toolbar" aria-label="Filter by domain" data-folded={folded ? "" : undefined}>
      <button className="dfilters-fold" aria-expanded={!folded} aria-controls="definition-domain-chips"
              aria-label={folded ? "Show all domains" : "Hide unused domains"} title={folded ? "Show all domains" : "Hide unused domains"}
              onClick={() => fold(!folded)}>
        <SlidersHorizontal size={12} aria-hidden />
        {folded && <span>Domains{idle.length ? ` · ${idle.length}` : ""}</span>}
        {folded ? <ChevronsRight size={13} aria-hidden /> : <ChevronsLeft size={13} aria-hidden />}
      </button>
      {/* one line: chips that don't fit scroll sideways; a plain mouse wheel scrolls them too */}
      <div className="dchips" id="definition-domain-chips"
           onWheel={(e) => { if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) e.currentTarget.scrollLeft += e.deltaY; }}>
        {[...active, ...(folded ? [] : idle)].map((k) => {
          const d = byKey.get(k)!;
          return (
            <button key={k} className="dchip" aria-pressed={domains.includes(k)} onClick={() => onToggle(k)}>
              <i style={{ background: domainColor(k) }} aria-hidden />{d.label}<span>{counts[k] ?? 0}</span>
            </button>
          );
        })}
        {active.length > 0 && <button className="filters-clear" onClick={() => setView({ domains: [] })}>Clear <span className="label">Esc</span></button>}
      </div>
    </div>
  );
}

function ModelProgress() {
  const { active, progress } = useProgress();
  if (!active) return null;
  return <p className="dprogress label" role="status">Loading the car · {Math.round(progress)}%</p>;
}

/* --------------------------------------------------------------------------------------------- list */
function RequirementList({ def, reqs, line }: { def: DefData; reqs: Requirement[]; line: string }) {
  const selected = useView((s) => s.selected);
  const domains = useView((s) => s.domains);
  const groups = def.data.domains
    .map((d) => ({ d, items: reqs.filter((r) => r.domain === d.key && (!domains.length || domains.includes(r.domain))) }))
    .filter((g) => g.items.length);
  return (
    <nav className="dlist" id="requirements-panel" aria-label="Requirements">
      <p className="dlist-head"><span className="sheet-layer">Requirements · {line}</span><span className="label">Recommended target</span></p>
      {groups.map(({ d, items }) => (
        <section key={d.key}>
          <h3 className="dlist-domain"><i style={{ background: domainColor(d.key) }} aria-hidden />{d.label}<span>{items.length}</span></h3>
          <ul>
            {items.map((r) => {
              const row = rowFor(r, line);
              const lvl = row ? row[row.recommended] : null;
              return (
                <li key={r.key}>
                  <button className="dlist-row" aria-current={selected === r.key ? "true" : undefined}
                          onClick={() => select(selected === r.key ? null : r.key)}
                          onPointerEnter={() => setView({ hover: r.key })} onPointerLeave={() => setView({ hover: null })}>
                    <PinMark r={r} />
                    <span className="dlist-title">{r.title}</span>
                    <span className="dlist-val">{lvl ? (lvl.basis === "gap" ? "?" : fmtLevel(lvl.value, r.metric?.unit)) : ""}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </nav>
  );
}

export function PinMark({ r }: { r: Pick<Requirement, "domain" | "state"> }) {
  return <i className="dmark" data-state={r.state ?? "held"} style={{ ["--c" as string]: domainColor(r.domain) }} aria-label={r.state ?? "held"} />;
}

/* --------------------------------------------------------------------------------------------- hover */
function PinHover({ def }: { def: DefData }) {
  const hover = useView((s) => s.hover);
  const pos = useView((s) => s.hoverPos);
  const line = useView((s) => s.line);
  const selected = useView((s) => s.selected);
  if (!hover || !pos || hover === selected) return null;
  const r = def.data.requirements.find((x) => x.key === hover);
  if (!r) return null;
  const row = rowFor(r, line);
  const lvl = row ? row[row.recommended] : null;
  const domain = def.data.domains.find((d) => d.key === r.domain)?.label ?? r.domain;
  const left = Math.min(pos.x + 16, window.innerWidth - 336), top = Math.min(pos.y + 16, window.innerHeight - 140);
  return (
    <div className="hovercard" style={{ left, top }} role="tooltip">
      <p>{r.title}</p>
      <div className="hovercard-meta">
        <PinMark r={r} /><span>{domain}</span>
        {r.metric && lvl && <span>{r.metric.name}: {lvl.basis === "gap" ? "?" : fmtLevel(lvl.value, r.metric.unit)}</span>}
      </div>
      <div className="hovercard-meta"><span>from area · {r.area_title}</span></div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------------- inspector */
function Inspector({ def, r, line }: { def: DefData; r: Requirement; line: string }) {
  const detail = useRequirementDetail(r.key, def);
  const choice = useChoice(def);
  const [allRows, setAllRows] = useState(false);
  const [hot, setHot] = useState<string | null>(null);
  const evRef = useRef<HTMLDivElement>(null);
  const domain = def.data.domains.find((d) => d.key === r.domain)?.label ?? r.domain;
  const evidence = detail?.evidence ?? [];
  const evText = (id: string) => evidence.find((e) => String(e.id) === id)?.text;
  const onSource = (id: string) => {
    setHot(id);
    requestAnimationFrame(() => evRef.current?.querySelector(`[data-ev="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
  };
  const rows = r.ladder.filter((x) => x.line === line);
  const others = r.ladder.filter((x) => x.line !== line);
  const shown = allRows ? [...rows, ...others] : rows;
  const lines = r.lines.join(", ");

  return (
    <aside className="sheet dsheet" id="requirements-panel" aria-label="Requirement definition">
      <button className="sheet-close" onClick={() => select(null)} aria-label="Close"><X size={16} /></button>
      <header className="sheet-head">
        <span className="sheet-layer"><PinMark r={r} />{domain}</span>
        <p className="sheet-what">A customer requirement with one measurable target. The AI recommends a rung; the PM chooses.</p>
      </header>
      <div className="dsheet-titleblock">
        <h2 className="sheet-title">{r.title}</h2>
        <p className="dsheet-statement">{r.statement}</p>
      </div>
      <FromArea r={r} />
      {r.change_note && <p className="dnote"><span className="label">What changed</span>{r.change_note}</p>}

      {r.metric && (
        <div className="dmetric">
          <span className="label">Metric</span>
          <p className="dmetric-name">{r.metric.name} <span>· {r.metric.unit} · {r.metric.direction === "lower" ? "lower is better" : r.metric.direction === "binary" ? "yes / no" : "higher is better"}</span></p>
          {(r.metric.method || r.metric.conditions) && <p className="dmetric-how">{[r.metric.method, r.metric.conditions].filter(Boolean).join(" · ")}</p>}
        </div>
      )}

      <div className="dblock">
        <span className="label">Target ladder · {line}</span>
        {shown.length === 0 && <p className="use-none">No ladder for {line} yet.</p>}
        {shown.map((row) => (
          <Ladder key={`${row.line}|${row.market}`} reqKey={r.key} row={row} metric={r.metric} evidenceText={evText} onSource={onSource}
                  busy={choice.isPending} sample={def.sample} facts={detail?.facts}
                  onChoose={(level, rationale) => choice.mutate({ key: r.key, line: row.line, market: row.market, level, rationale })} />
        ))}
        {others.length > 0 && (
          <button className="dtext" onClick={() => setAllRows((v) => !v)}>
            {allRows ? "Show only " + line : `Show other lines (${others.map((o) => `${o.line} · ${o.market}`).join(", ")})`}
          </button>
        )}
        {choice.isError && <p className="derror">Not saved: {(choice.error as Error).message}</p>}
      </div>

      {r.acceptance.length > 0 && (
        <div className="dblock">
          <span className="label">Acceptance criteria</span>
          <ul className="daccept">
            {r.acceptance.map((a, i) => (
              <li key={i}><span className="daccept-c">{a.criterion}</span><span className="daccept-pass">{a.pass}</span><span className="daccept-cond">{a.condition}</span></li>
            ))}
          </ul>
        </div>
      )}

      <dl className="sheet-facts">
        {([["Kano", r.kano], ["Horizon", r.horizon_year ? `${r.horizon ?? ""} ${r.horizon_year}`.trim() : r.horizon], ["Today", r.today_status],
           ["Decision", r.decision_type], ["Area", r.area_title], ["Car lines", lines], ["Markets", r.markets.join(", ")],
           ["Evidence", r.evidence_count ? `${r.evidence_count} items` : null]] as [string, string | null][])
          .filter(([, v]) => v).map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd>{v}</dd></div>)}
      </dl>

      <Links def={def} r={r} />

      {(r.gaps.length > 0 || r.assumptions.length > 0) && (
        <div className="dblock">
          {r.gaps.length > 0 && <><span className="label">Open gaps</span><ul className="drail">{r.gaps.map((g) => <li key={g}>{g}</li>)}</ul></>}
          {r.assumptions.length > 0 && <><span className="label">Assumptions</span><ul className="drail">{r.assumptions.map((g) => <li key={g}>{g}</li>)}</ul></>}
        </div>
      )}

      {evidence.length > 0 && (
        <div className="dblock" ref={evRef}>
          <span className="label">Sources behind the numbers</span>
          <ul className="dev">
            {evidence.map((e) => (
              <li key={String(e.id)} data-ev={String(e.id)} data-hot={hot === String(e.id) ? "" : undefined}>
                <span className="dev-id">{String(e.id)}{e.tier ? ` · ${e.tier}` : ""}{e.published ? ` · ${e.published}` : ""}</span>
                <span className="dev-text">{e.quote ? `“${e.quote}”` : e.text}</span>
                {e.url && <a href={e.url} target="_blank" rel="noreferrer">Open source</a>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

/** Back to page 2 with the area this requirement was drafted from selected (Scan reads ?area=). */
function FromArea({ r }: { r: Requirement }) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const go = () => { const p = new URLSearchParams(search); p.set("area", r.area_key); navigate(`/structure?${p}`); };
  return (
    <div className="bridge dfrom">
      <span>From area</span>
      <button className="bridge-go" onClick={go}>{r.area_title} <ArrowRight size={13} /></button>
    </div>
  );
}

/* --------------------------------------------------------------------------------------------- links */
function Links({ def, r }: { def: DefData; r: Requirement }) {
  const review = useLinkReview(def);
  const bundle = useView((s) => s.bundle);
  useView((s) => s.pendingLinks);
  const [open, setOpen] = useState<{ id: string; verdict: "confirmed" | "removed" } | null>(null);
  const [why, setWhy] = useState("");
  const mine = def.data.links.filter((l) => l.a === r.key || l.b === r.key).sort((a, b) => b.strength - a.strength);
  const byKey = new Map(def.data.requirements.map((x) => [x.key, x]));
  const myBundle = def.data.bundles.find((b) => b.keys.includes(r.key));
  if (!mine.length) return (
    <div className="dblock"><span className="label">Linked requirements</span><p className="use-none">No coupling proposed for this requirement.</p></div>
  );
  const send = (l: DefLink, verdict: "confirmed" | "removed") => {
    if (why.trim().length < 5) return;
    review.mutate({ link: l, a: l.a, b: l.b, relation: l.relation, verdict, via: String(l.via), strength: l.strength, rationale: why.trim() });
    setOpen(null); setWhy("");
  };
  return (
    <div className="dblock">
      <div className="dlinks-head">
        <span className="label">Linked requirements</span>
        {myBundle && (
          <button className="dtext" aria-pressed={bundle === myBundle.id} onClick={() => setView({ bundle: bundle === myBundle.id ? null : myBundle.id })}>
            {bundle === myBundle.id ? "Hide bundle" : `Show bundle · ${myBundle.keys.length}`}
          </button>
        )}
      </div>
      <ul className="dlinks">
        {mine.map((l) => {
          const other = byKey.get(l.a === r.key ? l.b : l.a);
          const verdict = linkVerdict(l);
          const out = l.relation === "enables" ? ((l.a === r.key) === (l.direction !== "b_to_a") ? "enables" : "enabled by") : RELATION_NAME[l.relation].toLowerCase();
          const id = String(l.id);
          return (
            <li key={id} data-removed={verdict === "removed" ? "" : undefined}>
              <div className="dlink-top">
                <span className="use-rel dlink-rel" data-dashed={isDashed(l.relation) ? "" : undefined}>{out}</span>
                <span className="dlink-via">via {l.via}</span>
                <span className="dlink-str" aria-label={`strength ${l.strength} of 3`}>{[1, 2, 3].map((i) => <i key={i} data-on={i <= l.strength ? "" : undefined} />)}</span>
                {l.state === "new" && <span className="dlink-new label">new</span>}
              </div>
              {other ? (
                <button className="dlink-other" onClick={() => select(other.key)}><PinMark r={other} />{other.title}</button>
              ) : <span className="dlink-other">{l.a === r.key ? l.b : l.a}</span>}
              <p className="use-why">{l.rationale}</p>
              {verdict === "confirmed" || verdict === "removed" ? (
                <p className="dlink-review label">{verdict === "confirmed" ? "Confirmed" : "Removed"} by {l.review?.actor ?? "PM"}{l.review?.rationale ? ` · ${l.review.rationale}` : ""}</p>
              ) : open?.id === id ? (
                <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); send(l, open.verdict); }}>
                  <textarea rows={2} value={why} onChange={(e) => setWhy(e.target.value)} autoFocus
                            placeholder={`Why ${open.verdict === "confirmed" ? "confirm" : "remove"} this link? (required)`} aria-label="Rationale" />
                  <div className="ladder-actions">
                    <button type="submit" className="dbtn primary" disabled={why.trim().length < 5 || review.isPending}>{open.verdict === "confirmed" ? "Confirm link" : "Remove link"}</button>
                    <button type="button" className="dbtn" onClick={() => { setOpen(null); setWhy(""); }}>Cancel</button>
                  </div>
                </form>
              ) : (
                <div className="dlink-actions">
                  <button className="dtext" onClick={() => { setOpen({ id, verdict: "confirmed" }); setWhy(""); }}>Confirm</button>
                  <button className="dtext" onClick={() => { setOpen({ id, verdict: "removed" }); setWhy(""); }}>Remove</button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {review.isError && <p className="derror">Not saved: {(review.error as Error).message}</p>}
      {def.sample && <p className="label">Sample data: reviews are kept in this view only.</p>}
    </div>
  );
}
