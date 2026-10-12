// Page 5, Document: the deliverable — the final, traceable requirement list per car line × market at the selected
// checkpoint (challenge brief; BMW process step 5 "Documentation / tracking"). A full-screen 2D page (no 3D scene, its
// own checkpoint switch). Read-only: the PM decides on page 4; exports are logged as audit events.
import { Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Download, ExternalLink, Search } from "lucide-react";
import { api, getActor } from "@/lib/api";
import type { Band, GateValue } from "@/lib/prioritize";
import type { ChangesPayload, DocEvidence, DocItem, DocumentPayload } from "@/lib/document";
import type { LineName } from "@/lib/definition";
import { useCheckpoint } from "@/state/checkpoint";
import { Dock } from "@/components/Guide";
import { domainColor, fmtLevel } from "../definition/data";
import { setView, useView } from "../definition/store";
import { DEF_STAGES } from "../definition/stages";
import { getP, selectTarget, setP, useP } from "../prioritize/store";
import { BandMark, GateMark } from "../prioritize/marks";
import { TYPE_COLOR } from "../scan/Scene";
import { DocumentGuide } from "./guide";
import { dirOf, type Dir } from "../prioritize/pm";
import "@/components/sheet.css";
import "./document.css";

const BANDS: Band[] = ["Must", "Should", "Could"];
const MARKET_NAME: Record<string, string> = { US: "US", EU: "Europe", CN: "China", RoW: "Rest of world" };
const DOMAIN_LABEL: Record<string, string> = {
  exterior: "Exterior", interior: "Interior & comfort", powertrain: "Powertrain & charging", chassis: "Chassis & dynamics",
  assist: "Driver assistance", digital: "Infotainment & digital", variants: "Variants & packages", quality: "Design & quality",
};
const BASIS: Record<string, string> = { cited: "cited", projected: "projected", assumption: "assumption", gap: "gap" };
const STATUS: Record<string, string> = {
  confirmed: "Confirmed by PM", ai_proposal: "AI proposal", open_proposal: "AI proposal · band change open",
  open_proposal_against_pm: "Confirmed by PM · AI proposes a change",
};
const RUNGS = ["baseline", "threshold", "target", "stretch"] as const;
const fmtDate = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "–");
const sc = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(1));
const gate = (g: GateValue) => (typeof g === "string" ? { result: g, rationale: null as string | null } : { result: g.result, rationale: g.rationale ?? null });

/** Rise / Fall (PM request 2026-10-11): a PM-confirmed row whose open AI proposal is against the PM's band.
 *  down = the AI now places it lower (red), up = higher (green). */
function rfOf(i: DocItem): { dir: Dir; from: Band; to: Band; cause: string } | null {
  const c = i.priority.confirmed, p = i.open_proposal;
  if (!c || !p || (p.against !== "pm" && i.status !== "open_proposal_against_pm")) return null;
  const dir = dirOf(p.proposed_band, c.priority);
  return dir ? { dir, from: c.priority, to: p.proposed_band, cause: p.cause.replace(/_/g, " ") } : null;
}
/** an unconfirmed AI band that moved since the previous checkpoint (the quiet case) */
const moveOf = (i: DocItem): Dir | null => (i.priority.confirmed || !i.prev ? null : dirOf(i.priority.ai_band, i.prev.band));
const rfRankOf = (i: DocItem) => { const r = rfOf(i); return r ? (r.dir === "down" ? 0 : 1) : 2; };

function targetText(i: DocItem) {
  const r = i.rung;
  if (!r.level) return { text: "no target", basis: null };
  const text = r.value != null && i.metric ? `${i.metric.direction === "lower" ? "≤" : i.metric.direction === "higher" ? "≥" : ""} ${fmtLevel(r.value, i.metric.unit)}`.trim() : r.text || "open gap";
  return { text, basis: r.basis ?? null };
}

function evKind(e: DocEvidence): keyof typeof TYPE_COLOR {
  if (e.kind === "comments") return "comment";
  if (e.id.startsWith("study:")) return "study";
  if (e.kind === "option") return "option";
  return "research";
}

export function DocumentPage() {
  const { cp, setCp, checkpoints } = useCheckpoint();
  const line = useView((s) => s.line);
  const storedMarket = useP((s) => s.market[line]);
  // the scene behind is page 4's skyline on the car: land it on its last stage, nothing open
  useEffect(() => {
    setView({ stage: DEF_STAGES[DEF_STAGES.length - 1], auto: false, selected: null, hover: null, hoverPos: null, bundle: null });
    selectTarget(null);
  }, []);
  const lineList = useQuery({ queryKey: ["document", "lines", cp], queryFn: () => api.get<DocumentPayload>(`/api/document?cp=${cp}&line=5%20Series&market=US`),
                              staleTime: 30_000, select: (d) => d.header });
  const markets = lineList.data?.markets_by_line[line] ?? [];
  const market = storedMarket && markets.includes(storedMarket) ? storedMarket : markets.includes("US") ? "US" : markets[0] ?? "US";
  const q = useQuery({
    queryKey: ["document", cp, line, market],
    queryFn: () => api.get<DocumentPayload>(`/api/document?cp=${cp}&line=${encodeURIComponent(line)}&market=${market}`),
    staleTime: 15_000, placeholderData: (p) => p, enabled: !!lineList.data,
  });
  const [showChanges, setShowChanges] = useState(false);
  const changes = useQuery({
    queryKey: ["document", "changes", line, market],
    queryFn: () => api.get<ChangesPayload>(`/api/document/changes?line=${encodeURIComponent(line)}&market=${market}`),
    enabled: cp === "cp2" && showChanges, staleTime: 15_000,
  });
  const [open, setOpen] = useState<string | null>(null);
  const [domain, setDomain] = useState<string | null>(null);
  const [text, setText] = useState("");
  useEffect(() => { setOpen(null); }, [line, market]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(null); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const d = q.data;
  const items = useMemo(() => (d?.items ?? []).filter((i) => (!domain || i.domain === domain) &&
    (!text || `${i.id} ${i.title} ${i.statement ?? ""}`.toLowerCase().includes(text.toLowerCase()))), [d, domain, text]);
  const domains = useMemo(() => {
    const n: Record<string, number> = {};
    (d?.items ?? []).forEach((i) => { n[i.domain] = (n[i.domain] ?? 0) + 1; });
    return Object.entries(n).sort((a, b) => b[1] - a[1]);
  }, [d]);
  const h = d?.header;
  const rfAll = useMemo(() => (d?.items ?? []).map((i) => ({ i, r: rfOf(i) })).filter((x) => x.r), [d]);
  const downs = rfAll.filter((x) => x.r!.dir === "down").length, ups = rfAll.length - downs;
  const exportHref = (format: "md" | "csv") =>
    `/api/document/export?cp=${cp}&line=${encodeURIComponent(line)}&market=${market}&format=${format}&as_actor=${encodeURIComponent(getActor())}`;
  const navigate = useNavigate();
  const { search } = useLocation();
  const openInPrioritize = (key: string) => {
    setP({ market: { ...getP().market, [line]: market } });
    selectTarget(key);
    navigate(`/prioritize${search}`);
  };

  return (
    <>
      <section className="docsheet" aria-label="Requirement document">
        <header className="doc-top">
          <div className="doc-title-row">
            <div className="doc-title">
              <span className="doc-kicker">Requirement document · {h?.label ?? "…"}{h ? ` · evidence to ${fmtDate(h.cutoff)}` : ""}</span>
              <h1>{line} <span className="doc-sep">·</span> {MARKET_NAME[market] ?? market}</h1>
            </div>
            <div className="doc-export" role="group" aria-label="Export">
              <a className="doc-btn" href={exportHref("md")} download><Download size={13} aria-hidden /> Markdown</a>
              <a className="doc-btn" href={exportHref("csv")} download><Download size={13} aria-hidden /> CSV</a>
            </div>
          </div>
          <div className="doc-controls">
            <div className="dseg" role="radiogroup" aria-label="Checkpoint">
              {(checkpoints ?? []).map((c) => (
                <button key={c.id} role="radio" aria-checked={c.id === cp} onClick={() => setCp(c.id)}>{c.label}</button>
              ))}
            </div>
            <div className="dseg" role="radiogroup" aria-label="Car line">
              {(lineList.data?.lines ?? []).map((l) => (
                <button key={l} role="radio" aria-checked={l === line} onClick={() => setView({ line: l as LineName })}>{l}</button>
              ))}
            </div>
            <div className="dseg" role="radiogroup" aria-label="Market">
              {markets.map((m) => (
                <button key={m} role="radio" aria-checked={m === market} onClick={() => setP({ market: { ...getP().market, [line]: m } })}>{m}</button>
              ))}
            </div>
            {cp === "cp2" && (
              <button className="doc-btn" aria-expanded={showChanges} onClick={() => setShowChanges((v) => !v)}>
                {showChanges ? <ChevronDown size={13} aria-hidden /> : <ChevronRight size={13} aria-hidden />} Changes since JAN
              </button>
            )}
          </div>
          {h && (
            <dl className="doc-readout">
              {BANDS.map((b) => (
                <div key={b}><dt><BandMark band={b} color="#b4bac4" /> {b}</dt><dd className="num">{h.by_band[b] ?? 0}</dd></div>
              ))}
              <div className="doc-readout-rule" aria-hidden />
              <div><dt>Confirmed by PM</dt><dd className="num sm">{h.confirmed}<span className="of">/{h.count}</span></dd></div>
              <div><dt>Open proposals</dt><dd className="num sm">{h.open_proposals}</dd></div>
              {downs > 0 && <div className="doc-rfstat" data-rf="down"><dt>▼ Downgrades — review</dt><dd className="num sm">{downs}</dd></div>}
              {ups > 0 && <div className="doc-rfstat" data-rf="up"><dt>▲ Upgrade opportunities</dt><dd className="num sm">{ups}</dd></div>}
              <div className="doc-meta"><dt>Generated</dt><dd>{new Date(h.generated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })} · {h.scheme} weights v{h.weights_version} · run {h.run?.id ?? "–"}</dd></div>
            </dl>
          )}
          <div className="doc-filter">
            <label className="doc-search"><Search size={13} aria-hidden /><input value={text} onChange={(e) => setText(e.target.value)} placeholder="Search ID, title" aria-label="Search requirements" /></label>
            <div className="dchips">
              {domains.map(([k, n]) => (
                <button key={k} className="dchip" aria-pressed={domain === k} data-on={domain === k ? "" : undefined} onClick={() => setDomain(domain === k ? null : k)}>
                  <i style={{ background: domainColor(k) }} aria-hidden />{DOMAIN_LABEL[k] ?? k} <span className="num">{n}</span>
                </button>
              ))}
            </div>
          </div>
        </header>
        {showChanges && cp === "cp2" && <Changes data={changes.data} loading={changes.isPending} items={d?.items ?? []} onOpen={(k) => setOpen(k)} />}

        {q.isError && <p className="doc-empty">{(q.error as Error).message}</p>}
        {d && !d.ready && <p className="doc-empty">No prioritization run at {h?.label} yet: run Prioritize at this checkpoint first.</p>}
        {d?.ready && BANDS.map((b) => {
          // challenged PM decisions first: downgrades (red) above upgrade opportunities (green); the rest keep their order
          const group = items.filter((i) => i.priority.band === b).sort((x, y) => rfRankOf(x) - rfRankOf(y));
          if (!group.length) return null;
          return (
            <section key={b} className="doc-band" aria-label={`${b} requirements`}>
              <h2><BandMark band={b} color="#f2f4f7" /> {b} <span className="num">{group.length}</span></h2>
              <ul className="doc-list">
                {group.map((i) => (
                  <Fragment key={i.key}>
                    <Row item={i} open={open === i.key} onToggle={() => setOpen(open === i.key ? null : i.key)} />
                    {open === i.key && <Record item={i} onPrioritize={() => openInPrioritize(i.key)} />}
                  </Fragment>
                ))}
              </ul>
            </section>
          );
        })}
        {d?.ready && !items.length && <p className="doc-empty">Nothing matches the filter.</p>}
      </section>
      <Dock mode="document" sel={null} guide={<DocumentGuide open={!!open} />} />
    </>
  );
}

function Row({ item: i, open, onToggle }: { item: DocItem; open: boolean; onToggle: () => void }) {
  const t = targetText(i);
  const pm = !!i.priority.confirmed;
  const brand = i.gates?.brand ? gate(i.gates.brand).result : null;
  const delta = i.prev ? i.priority.ai_score - i.prev.score : 0;
  const rf = rfOf(i), mv = moveOf(i);
  return (
    <li className="doc-row" data-open={open ? "" : undefined} data-rf={rf?.dir}>
      <button onClick={onToggle} aria-expanded={open}>
        <span className="doc-id">{i.id}</span>
        <BandMark band={i.priority.band} color={domainColor(i.domain)} pm={pm} />
        <span className="doc-rtitle">{i.title}</span>
        <span className="doc-target" title={i.rung.text ?? undefined}>
          {t.text}{t.basis && <span className="doc-basis"> · {BASIS[t.basis] ?? t.basis}</span>}
          {i.rung.by === "pm" && <span className="doc-pm" title="Rung chosen by the PM">PM</span>}
        </span>
        <span className="doc-tags">
          {rf && <span className="doc-rf" data-rf={rf.dir} title={`${rf.dir === "down" ? "Downgrade: new evidence lowers this below your" : "Upgrade opportunity: new evidence raises this above your"} ${rf.from} (${rf.cause})`}>{rf.dir === "down" ? "▼" : "▲"} {rf.from} → {rf.to}</span>}
          {i.open_proposal && !rf && <span className="doc-gtag" title={`AI proposes ${i.open_proposal.proposed_band} (${i.open_proposal.cause})`}>→ {i.open_proposal.proposed_band}</span>}
          {(brand === "warn" || brand === "fail") && <span title={`Brand fit ${brand}`}><GateMark result={brand} /></span>}
          {i.flags.includes("borrowed_voice") && <span className="doc-gtag dashed" title="Customer voice borrowed from other markets">borrowed</span>}
        </span>
        <span className="doc-ev" title="Evidence level">{i.evidence.level ?? "–"}</span>
        <span className="doc-check" aria-label={pm ? "Confirmed by PM" : "Not confirmed"}>{pm ? "PM ✓" : ""}</span>
        <span className="doc-score num">{Math.round(i.priority.ai_score)}{mv ? <span className="doc-delta" data-d={mv} data-rf={mv} title={`AI band ${i.prev?.band} → ${i.priority.ai_band} since ${i.prev?.checkpoint === "cp1" ? "JAN" : "the last checkpoint"}`}>{mv === "up" ? "▲" : "▼"}</span>
          : delta ? <span className="doc-delta" data-d={delta > 0 ? "up" : "down"}>{delta > 0 ? "▲" : "▼"}</span> : null}</span>
      </button>
    </li>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="doc-sec"><h3>{title}</h3>{children}</section>;
}

function Record({ item: i, onPrioritize }: { item: DocItem; onPrioritize: () => void }) {
  const c = i.priority.confirmed;
  const max = Math.max(1, ...i.factors.map((f) => f.points));
  return (
    <li className="doc-record">
      <div className="doc-rec-head">
        <span className="doc-kicker"><i style={{ background: domainColor(i.domain) }} aria-hidden />{DOMAIN_LABEL[i.domain] ?? i.domain} · {i.area?.title ?? i.area?.key ?? "–"}</span>
        <p className="doc-statement">{i.statement}</p>
        <p className="doc-small">{i.id} · <code>{i.key}</code> v{i.version} · horizon {i.horizon ?? "–"}{i.horizon_year ? ` ${i.horizon_year}` : ""} · Kano {i.kano ?? "–"} · {i.decision_type?.replace(/_/g, " ") ?? "–"} · status {i.req_status ?? "proposed"}</p>
      </div>

      <div className="doc-grid">
        <Section title="Decision">
          <div className="doc-decision">
            <span className="doc-bignum num">{sc(i.priority.ai_score)}</span>
            <div>
              <p><BandMark band={i.priority.band} color={domainColor(i.domain)} pm={!!c} size="lg" /> <b>{i.priority.band}</b> · {STATUS[i.status]}</p>
              <p className="doc-small">AI band {i.priority.ai_band} · rank {i.priority.rank} · base {sc(i.priority.base)}</p>
            </div>
          </div>
          {c && <p className="doc-rail pm"><b>{c.priority}</b> by {c.actor} · {fmtDate(c.at)} — {c.rationale}</p>}
          {(() => { const rf = rfOf(i); return rf && (
            <p className="doc-rail" data-rf={rf.dir}><b>{rf.dir === "down" ? "▼ Downgrade" : "▲ Upgrade opportunity"}</b> · {rf.dir === "down"
              ? `New evidence lowers this below the PM's ${rf.from} → AI suggests ${rf.to} (${rf.cause}). Accept or keep the decision in Prioritize.`
              : `New evidence raises this above the PM's ${rf.from} → consider upgrading to ${rf.to} (${rf.cause}).`}</p>
          ); })()}
          {i.open_proposal && !rfOf(i) && <p className="doc-rail">Open AI proposal {i.open_proposal.old_band ?? "–"} → <b>{i.open_proposal.proposed_band}</b> ({i.open_proposal.cause.replace(/_/g, " ")}){i.open_proposal.explain ? `: ${i.open_proposal.explain}` : ""}</p>}
          <button className="doc-link" onClick={onPrioritize}>Open in Prioritize →</button>
        </Section>

        <Section title="Metric and target">
          {i.metric ? (
            <>
              <p><b>{i.metric.name}</b> <span className="doc-small">[{i.metric.unit || "–"}] · {i.metric.direction} is better</span></p>
              <p className="doc-target-big num">{targetText(i).text} <span className="doc-small">· {i.rung.level} · {BASIS[i.rung.basis ?? ""] ?? i.rung.basis ?? "–"} · {i.rung.by === "pm" ? <span className="doc-pm">PM choice</span> : "AI recommended"}</span></p>
              {i.rung.text && <p className="doc-small">{i.rung.text}</p>}
              {i.metric.conditions && <p className="doc-small">Conditions: {i.metric.conditions}</p>}
            </>
          ) : <p className="doc-small">No metric yet.</p>}
          {i.ladder && (
            <table className="doc-ladder">
              <tbody>
                {RUNGS.map((r) => {
                  const lv = i.ladder?.[r];
                  if (!lv) return null;
                  return (
                    <tr key={r} data-use={i.rung.level === r ? "" : undefined}>
                      <th>{r}{i.ladder?.recommended === r && <span className="doc-gtag">AI</span>}{i.rung.by === "pm" && i.rung.level === r && <span className="doc-pm">PM</span>}</th>
                      <td className="num">{lv.value != null ? fmtLevel(lv.value, i.metric?.unit) : "?"}</td>
                      <td><span className="doc-basis-mark" data-b={lv.basis} aria-hidden />{BASIS[lv.basis] ?? lv.basis}</td>
                      <td className="doc-small">{lv.note || lv.text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Section>

        <Section title="Acceptance criteria">
          {i.acceptance.length ? <ul className="doc-acc">{i.acceptance.map((a) => (
            <li key={a.criterion}><b>{a.criterion}</b><span>{a.pass}</span><span className="doc-small">{a.condition}</span></li>
          ))}</ul> : <p className="doc-small">–</p>}
        </Section>

        <Section title="Prioritization rationale">
          <p className="doc-rail">{i.rationale ?? "–"}</p>
          <ul className="doc-factors">
            {i.factors.map((f) => (
              <li key={f.key} data-gap={f.available ? undefined : ""} title={f.explanation}>
                <span>{f.label}</span>
                <span className="doc-bar"><i style={{ width: `${(f.points / max) * 100}%` }} /></span>
                <span className="num">{f.available ? f.points.toFixed(1) : "gap"}</span>
                <span className="doc-small">{f.explanation}</span>
              </li>
            ))}
            {i.modifiers.map((m) => (
              <li key={m.key} className="mod"><span>{m.key.replace(/_/g, " ")}</span><span /><span className="num">{m.points > 0 ? "+" : ""}{m.points.toFixed(1)}</span><span className="doc-small">{m.why}</span></li>
            ))}
          </ul>
        </Section>

        <Section title={`Evidence · ${i.evidence.level ?? "–"} · ${i.evidence.comments ?? 0} comments · ${i.evidence.count} sources`}>
          <ul className="doc-evidence">
            {i.evidence.items.map((e) => (
              <li key={e.id}>
                <i className="doc-evdot" style={{ background: TYPE_COLOR[evKind(e)] }} aria-hidden />
                <div>
                  <p>{e.text ?? e.id}</p>
                  <p className="doc-small">
                    {e.id}{e.tier ? ` · ${e.tier}` : ""}{e.published ? ` · ${e.published}` : ""}{e.relation ? ` · ${e.relation}` : ""}
                    {e.url && <> · <a href={e.url} target="_blank" rel="noreferrer">source <ExternalLink size={11} aria-hidden /></a></>}
                  </p>
                  {e.quotes?.map((qq) => <blockquote key={qq.source_id}>“{qq.quote}”<cite> comment {qq.external_id}{qq.market ? ` · ${qq.market}` : ""}</cite></blockquote>)}
                </div>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Assumptions, gaps and uncertainties">
          {i.assumptions.length > 0 && <><p className="doc-sub">Assumptions (forward-looking)</p><ul className="doc-rails">{i.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></>}
          {i.gaps.length > 0 && <><p className="doc-sub">Open gaps</p><ul className="doc-rails">{i.gaps.map((a) => <li key={a}>{a}</li>)}</ul></>}
          {i.uncertainties.length > 0 && <><p className="doc-sub">Uncertainties</p><ul className="doc-rails">{i.uncertainties.map((a) => <li key={a}>{a}</li>)}</ul></>}
          {!i.assumptions.length && !i.gaps.length && !i.uncertainties.length && <p className="doc-small">–</p>}
        </Section>

        <Section title="Gates">
          <ul className="doc-gates">
            {Object.entries(i.gates ?? {}).map(([k, v]) => { const g = gate(v); return (
              <li key={k}><GateMark result={g.result} /><b>{k}</b><span className="doc-small">{g.result}{g.rationale ? ` — ${g.rationale}` : ""}</span></li>
            ); })}
          </ul>
        </Section>

        {i.links.length > 0 && (
          <Section title="Linked requirements">
            <ul className="doc-links">
              {i.links.map((l) => (
                <li key={`${l.key}${l.relation}`} data-removed={l.status === "removed" ? "" : undefined}>
                  <span className="doc-gtag" data-dashed={l.relation === "conflicts" || l.relation === "competes_for" ? "" : undefined}>{l.relation.replace(/_/g, " ")}</span>
                  <span>{l.title ?? l.key}</span><span className="doc-small">via {l.via ?? "–"} · strength {l.strength} · {l.status}{l.source === "pm" ? " · added by PM" : ""}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="History">
          <ul className="doc-history">
            {i.history.map((x) => (
              <li key={x.checkpoint}><b>{x.label}</b><span className="num">{sc(x.score)}</span><span>AI {x.band}{x.confirmed ? <> · <span className="doc-pm">PM {x.confirmed}</span></> : null}</span><span className="doc-small">rank {x.rank}</span></li>
            ))}
            {i.proposals.map((p) => (
              <li key={String(p.id)} className="doc-small"><b>{p.checkpoint === "cp1" ? "JAN 26" : "JUL 26"}</b><span>proposal</span><span>{p.old_band ?? "–"} → {p.proposed_band} ({p.cause.replace(/_/g, " ")})</span>
                <span>{p.status}{p.decided_by ? ` by ${p.decided_by}` : ""}{p.decision_rationale ? ` — ${p.decision_rationale}` : ""}</span></li>
            ))}
            {i.decisions.map((x) => (
              <li key={x.at} className="doc-small"><b>{x.checkpoint === "cp2" ? "JUL 26" : x.checkpoint === "cp1" ? "JAN 26" : "–"}</b><span>PM</span><span>{x.priority} by {x.actor}</span><span>{x.rationale}</span></li>
            ))}
          </ul>
        </Section>
      </div>
    </li>
  );
}

function Changes({ data, loading, items, onOpen }: { data: ChangesPayload | undefined; loading: boolean; items: DocItem[]; onOpen: (key: string) => void }) {
  // first: PM decisions the new checkpoint contradicts (down, red), then upgrade opportunities (up, green)
  const rf = items.map((i) => ({ i, r: rfOf(i)! })).filter((x) => x.r);
  const groups = (["down", "up"] as const).map((dir) => ({ dir, rows: rf.filter((x) => x.r.dir === dir) })).filter((g) => g.rows.length);
  const top = groups.length > 0 && (
    <div className="doc-rfgroups">
      {groups.map((g) => (
        <div key={g.dir} className="doc-rfgroup" data-rf={g.dir}>
          <h3>{g.dir === "down" ? `▼ PM decisions now contradicted (down) · ${g.rows.length}` : `▲ Upgrade opportunities (up) · ${g.rows.length}`}</h3>
          <ul>{g.rows.map(({ i, r }) => (
            <li key={i.key}>
              <button onClick={() => onOpen(i.key)}>{i.title}</button>
              <span className="doc-rf" data-rf={g.dir}>{g.dir === "down" ? "▼" : "▲"} {r.from} → {r.to}</span>
              <span className="doc-small">{i.id} · {r.cause}{g.dir === "down" ? " · accept or keep in Prioritize" : " · consider upgrading"}</span>
            </li>
          ))}</ul>
        </div>
      ))}
    </div>
  );
  if (loading || !data) return <section className="doc-changes">{top}<p className="doc-small">Comparing JAN 26 with JUL 26…</p></section>;
  const p = data.proposals;
  const cells: [string, number][] = [["New", data.new.length], ["Removed", data.removed.length], ["Band up", data.band_up], ["Band down", data.band_down],
    ["PM decisions", data.decisions.length], ["Accepted", p.accepted.length], ["Rejected", p.rejected.length], ["Open", p.open.length]];
  const bandMoves = data.moved.filter((m) => m.ai_band_changed || m.pm_band_changed);
  return (
    <section className="doc-changes" aria-label="Changes since JAN">
      <h2>Changes {data.from.label} → {data.to.label}</h2>
      {top}
      <dl className="doc-readout compact">{cells.map(([k, n]) => <div key={k}><dt>{k}</dt><dd className="num sm">{n}</dd></div>)}</dl>
      <div className="doc-change-cols">
        {data.new.length > 0 && <div><p className="doc-sub">New at {data.to.label}</p><ul>{data.new.map((x) => <li key={x.key}><BandMark band={x.band} color={domainColor(x.domain)} size="sm" /> {x.title} <span className="num doc-small">{Math.round(x.score)}</span></li>)}</ul></div>}
        {data.removed.length > 0 && <div><p className="doc-sub">Removed</p><ul>{data.removed.map((x) => <li key={x.key}>{x.title}</li>)}</ul></div>}
        {bandMoves.length > 0 && <div><p className="doc-sub">Band moves</p><ul>{bandMoves.map((m) => (
          <li key={m.key}><span className="doc-delta" data-d={m.direction === "down" ? "down" : "up"}
                                data-rf={m.ai_band_changed && !m.to.confirmed && m.direction !== "same" ? m.direction : undefined}>{m.direction === "down" ? "▼" : m.direction === "up" ? "▲" : "·"}</span> {m.title}
            <span className="doc-small"> AI {m.from.ai_band} → {m.to.ai_band}{m.pm_band_changed ? ` · PM ${m.from.confirmed ?? "–"} → ${m.to.confirmed ?? "–"}` : ""} · {sc(m.from.score)} → {sc(m.to.score)}</span></li>
        ))}</ul></div>}
        {(data.decisions.length > 0 || p.accepted.length + p.rejected.length > 0) && <div><p className="doc-sub">PM decisions at {data.to.label}</p><ul>
          {data.decisions.map((x) => <li key={x.at}><span className="doc-pm">PM</span> {x.title}: {x.priority} <span className="doc-small">— {x.rationale}</span></li>)}
          {[...p.accepted, ...p.rejected].map((x) => <li key={String(x.id)}>{x.title}: proposal {x.old_band} → {x.proposed_band} <span className="doc-small">{x.status}</span></li>)}
        </ul></div>}
        {p.open.length > 0 && <div><p className="doc-sub">Open AI proposals</p><ul>{p.open.map((x) => <li key={String(x.id)}>{x.title} <span className="doc-small">{x.old_band} → {x.proposed_band} · {x.cause.replace(/_/g, " ")}</span></li>)}</ul></div>}
      </div>
    </section>
  );
}
