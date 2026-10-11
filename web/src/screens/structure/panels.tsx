// Page 2 overlays: the stage funnel (top-left), inspector bodies for clusters, themes and potential requirements,
// and the list of signals the AI extracted from one source (also shown on page 1 when a comment is opened).
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import type { SignalRow, StructurePayload, TrackState } from "@/lib/types";
import { useCheckpoint } from "@/state/checkpoint";
import { STAGE_LABEL, atLeast, type Stage } from "./stages";
import "./structure.css";

const fmt = (n: unknown) => (typeof n === "number" ? n.toLocaleString("en-US") : "–");
const ASPECT = (a: string | null) => (a ?? "other").replace(/_/g, " ");
const LINE_MARKET = (k: string) => k.replace(":", " · ").replace("RoW", "Rest of world").replace("EU", "Europe").replace("US", "USA").replace("CN", "China");

export function StateMark({ state }: { state: TrackState | null | undefined }) {
  return <i className={`smark s-${state ?? "held"}`} title={state ?? "held"} aria-label={state ?? "held"} />;
}

/* ------------------------------------------------------------------------------------------- funnel */
// what each step shows in the volume, one line (the full explanation sits on the Agent panel's stage bar)
const STEP_NOTE: Record<Stage, string> = {
  classify: "Comments stay in place; the ones turned into signals light up",
  cluster: "Signals grouped into clusters, not yet named",
  contextualize: "Clusters named and grouped into themes, linked to evidence",
  areas: "Themes grouped into requirement areas",
};

export function Funnel({ data, stage, done, onStage, onStep }: {
  data: StructurePayload | undefined; stage: Stage; done: Stage[]; onStage: (s: Stage) => void; onStep: (d: -1 | 1) => void;
}) {
  const { position } = useCheckpoint();
  if (!data?.ready) {
    return (
      <div className="funnel funnel-wait">
        <span className="label">Structure has not run at this checkpoint yet</span>
      </div>
    );
  }
  const newOf = (xs: { state: TrackState | null }[]) => (position > 1 ? xs.filter((x) => x.state === "new").length : 0);
  const changed = (xs: { state: TrackState | null }[]) => (position > 1 ? xs.filter((x) => x.state === "strengthened" || x.state === "weakened").length : 0);
  const clusters = data.clusters.filter((c) => !c.tail && c.comments > 0);
  const areas = data.areas.filter((a) => a.kind !== "quality");
  const signals = (data.funnel.cluster?.signals as number | undefined) ?? undefined;
  const cells: { stage: Stage; label: string; n: number | undefined; sub: { nu: number; ch: number } | null }[] = [
    { stage: "classify", label: "Signals", n: signals, sub: null },
    { stage: "cluster", label: "Clusters", n: clusters.length, sub: { nu: newOf(clusters), ch: changed(clusters) } },
    { stage: "contextualize", label: "Themes", n: data.themes.length, sub: { nu: newOf(data.themes), ch: changed(data.themes) } },
    { stage: "areas", label: "Requirement areas", n: areas.length, sub: { nu: newOf(areas), ch: changed(areas) } },
  ];
  const at = done.indexOf(stage);
  return (
    <div className="funnel-wrap">
    <dl className="funnel" aria-label="What the AI made of the evidence">
      {cells.map((c, i) => (
        <div key={c.label} className="funnel-cell" data-ahead={!atLeast(stage, c.stage) ? "" : undefined} data-current={c.stage === stage ? "" : undefined}>
          <dt className="label">
            <button type="button" className="funnel-pick" disabled={!done.includes(c.stage)} aria-pressed={c.stage === stage}
                    onClick={() => onStage(c.stage)} title={`Show the structure after ${STAGE_LABEL[c.stage]}`}>{c.label}</button>
          </dt>
          <dd>
            <span className="num">{fmt(c.n)}</span>
            {c.sub && (c.sub.nu > 0 || c.sub.ch > 0) && (
              <span className="funnel-delta">
                {c.sub.nu > 0 && <span><StateMark state="new" />{c.sub.nu}</span>}
                {c.sub.ch > 0 && <span><StateMark state="strengthened" />{c.sub.ch}</span>}
              </span>
            )}
          </dd>
          {i < cells.length - 1 && <svg className="funnel-arrow" width="18" height="10" viewBox="0 0 18 10" aria-hidden><path d="M0 5h15M11 1l4 4-4 4" fill="none" stroke="currentColor" /></svg>}
        </div>
      ))}
    </dl>
    <div className="funnel-step" role="group" aria-label="Step through the stages">
      <button type="button" onClick={() => onStep(-1)} disabled={at <= 0} aria-label="Previous stage" title="Previous stage ([)"><ChevronLeft size={14} /></button>
      <span className="funnel-step-n num">{at + 1}/{done.length}</span>
      <button type="button" onClick={() => onStep(1)} disabled={at >= done.length - 1} aria-label="Next stage" title="Next stage (])"><ChevronRight size={14} /></button>
      <span className="funnel-step-name">{STAGE_LABEL[stage]}</span>
      <span className="funnel-step-note" aria-live="polite">{STEP_NOTE[stage]}</span>
    </div>
    </div>
  );
}

/* ------------------------------------------------------------------------------------------- signals */
export function SignalList({ sourceId }: { sourceId: number }) {
  const q = useQuery({ queryKey: ["signals", sourceId], queryFn: () => api.get<{ classified: boolean; in_scope: boolean | null; reason: string | null; signals: SignalRow[] }>(`/api/structure/signals/${sourceId}`), staleTime: 60_000 });
  if (!q.data) return null;
  if (!q.data.classified) return <p className="sig-none label">Not classified yet</p>;
  if (q.data.in_scope === false) return <p className="sig-none label">Out of scope: {q.data.reason}</p>;
  return (
    <div className="sig-list">
      <div className="label">What the AI found</div>
      {q.data.signals.map((s) => <SignalCard key={s.id} s={s} />)}
    </div>
  );
}

export function SignalCard({ s, quote = true }: { s: SignalRow; quote?: boolean }) {
  return (
    <div className="sig" data-nature={s.nature ?? undefined}>
      <div className="sig-head">
        <span className="sig-aspect">{ASPECT(s.aspect)}</span>
        <span className="sig-nature">{(s.nature ?? "").replace(/_/g, " ")}</span>
        <span className="sig-int" aria-label={`intensity ${s.intensity ?? 1} of 3`}>{[1, 2, 3].map((k) => <i key={k} data-on={(s.intensity ?? 1) >= k ? "" : undefined} />)}</span>
      </div>
      <p className="sig-need">{s.need_statement}</p>
      {quote && s.quote && <q className="sig-quote">{s.quote}</q>}
      <div className="sig-tags">
        {s.impact && s.impact !== "none" && <span>{s.impact}</span>}
        {s.occupant && s.occupant !== "unknown" && <span>{s.occupant}</span>}
        {s.benchmark && s.benchmark !== "none" && <span>vs {s.benchmark_name ?? s.benchmark.replace("_", " ")}</span>}
        {!!s.future_cue && <span>future cue</span>}
        {s.explicit === 0 && <span>inferred</span>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------------------------- cluster */
interface ClusterDetail {
  key: string; n: number;
  insight: { title: string; statement: string; need_type: string; quality_issue: number; payload_json: string } | null;
  signals: (SignalRow & { external_id: string; car: string; market: string; checkpoint: string })[];
}

export function ClusterBody({ k, data }: { k: string; data: StructurePayload | undefined }) {
  const { cp } = useCheckpoint();
  const q = useQuery({ queryKey: ["cluster", cp, k], queryFn: () => api.get<ClusterDetail>(`/api/structure/cluster/${encodeURIComponent(k)}?cp=${cp}`) });
  const node = data?.clusters.find((c) => c.key === k);
  const d = q.data;
  const lm = Object.entries(node?.by_line_market ?? {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...lm.map(([, v]) => v));
  return (
    <>
      <h2 className="sheet-title">{d?.insight?.title ?? node?.insight?.title ?? "Cluster"}</h2>
      {d?.insight && <p className="sheet-statement">{d.insight.statement}</p>}
      <div className="chips">
        <span className="chip"><StateMark state={node?.state} />{node?.state ?? "held"}</span>
        <span className="chip">{node?.polarity === "like" ? "keep" : "improve"}</span>
        {d?.insight && <span className="chip">{d.insight.need_type.replace("_", " ")}</span>}
        {!!d?.insight?.quality_issue && <span className="chip chip-amber">quality issue</span>}
        <span className="chip">{fmt(node?.comments)} comments</span>
      </div>
      {lm.length > 0 && (
        <div className="lm">
          {lm.map(([key, v]) => (
            <div key={key} className="lm-row"><span>{LINE_MARKET(key)}</span><span className="lm-bar"><i style={{ transform: `scaleX(${v / max})` }} /></span><span>{v}</span></div>
          ))}
        </div>
      )}
      <div className="sig-list">
        <div className="label">Signals in this cluster · {fmt(d?.n)}</div>
        {(d?.signals ?? []).slice(0, 12).map((s) => <SignalCard key={s.id} s={s} />)}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------------------------------- theme */
interface ThemeDetail {
  theme: { key: string; title: string; statement: string; category: string };
  insights: { cluster_key: string; title: string; statement: string; need_type: string; quality_issue: number; payload_json: string }[];
  evidence: { type: string; id: string; relation: string; why: string | null; text?: string; url?: string; published?: string; tier?: string; car?: string; market?: string; z?: number; availability?: string }[];
  area: { key: string; title: string } | null;
}
const REL_ORDER = ["supports", "trend_for", "competes_with", "available_as_option", "contradicts", "context"];
const REL_NAME: Record<string, string> = { supports: "Supports", trend_for: "Trend", competes_with: "Competitor", available_as_option: "Already offered", contradicts: "Contradicts", context: "Context" };

export function ThemeBody({ k }: { k: string }) {
  const { cp } = useCheckpoint();
  const q = useQuery({ queryKey: ["theme", cp, k], queryFn: () => api.get<ThemeDetail>(`/api/structure/theme/${encodeURIComponent(k)}?cp=${cp}`) });
  const d = q.data;
  if (!d) return <div className="sheet-skel" aria-hidden><span /><span /><span /></div>;
  const byRel = REL_ORDER.map((r) => [r, d.evidence.filter((e) => e.relation === r)] as const).filter(([, xs]) => xs.length);
  return (
    <>
      <h2 className="sheet-title">{d.theme.title}</h2>
      <p className="sheet-statement">{d.theme.statement}</p>
      <div className="label">{d.insights.length} findings</div>
      <ul className="mini-list">
        {d.insights.map((i) => <li key={i.cluster_key}><b>{i.title}</b><span>{JSON.parse(i.payload_json).comments} comments{i.quality_issue ? " · quality" : ""}</span></li>)}
      </ul>
      {byRel.map(([rel, xs]) => (
        <div key={rel} className="ev-group">
          <div className="label">{REL_NAME[rel]} · {xs.length}</div>
          {xs.map((e) => (
            <div key={`${e.type}:${e.id}`} className="ev" data-type={e.type}>
              <i className="ev-dot" aria-hidden />
              <div>
                <p>{e.text}</p>
                <span className="ev-why">{e.why}{e.published ? ` · ${e.published}` : ""}{e.market ? ` · ${e.car ?? ""} ${e.market}` : ""}{e.availability ? ` · ${e.availability}` : ""}</span>
                {e.url && <a className="sheet-link" href={e.url} target="_blank" rel="noreferrer">Source <ExternalLink size={12} /></a>}
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

/* ------------------------------------------------------------------------------------------- area */
const KIND: Record<string, string> = { improve: "improve", keep: "keep — protect in the successor", emerging: "emerging expectation", quality: "quality hand-over" };

export function AreaBody({ k, data }: { k: string; data: StructurePayload | undefined }) {
  const a = data?.areas.find((x) => x.key === k);
  if (!a) return null;
  const themes = a.themes.map((t) => data?.themes.find((x) => x.key === t)).filter(Boolean);
  const lm = Object.entries(a.metrics.by_line_market ?? {}).sort((x, y) => y[1] - x[1]);
  const max = Math.max(1, ...lm.map(([, v]) => v));
  const ev = a.metrics.evidence ?? {};
  return (
    <>
      <h2 className="sheet-title">{a.title}</h2>
      <p className="sheet-statement">{a.need}</p>
      <div className="chips">
        <span className={`chip${a.kind === "quality" ? " chip-amber" : ""}`}><StateMark state={a.state} />{KIND[a.kind]}</span>
        <span className="chip">{fmt(a.metrics.comments)} comments</span>
        <span className="chip">{a.themes.length} themes</span>
        {Object.entries(ev).filter(([r]) => r !== "context").map(([r, n]) => <span key={r} className="chip">{n} {REL_NAME[r]?.toLowerCase() ?? r}</span>)}
      </div>
      {a.change_note && <div className="note"><div className="label">Changed at this checkpoint</div><p>{a.change_note}</p></div>}
      {a.why_now && <div className="facts1"><span className="label">Why now</span><p>{a.why_now}</p></div>}
      {lm.length > 0 && (
        <div className="lm">
          {lm.map(([key, v]) => <div key={key} className="lm-row"><span>{LINE_MARKET(key)}</span><span className="lm-bar"><i style={{ transform: `scaleX(${v / max})` }} /></span><span>{v}</span></div>)}
        </div>
      )}
      {a.open_questions.length > 0 && (
        <div className="assumptions"><div className="label">Open questions for requirement drafting</div><ul>{a.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul></div>
      )}
      <div className="label">Themes</div>
      <ul className="mini-list">{themes.map((t) => <li key={t!.key}><b>{t!.title}</b><span>{t!.comments} comments</span></li>)}</ul>
    </>
  );
}
