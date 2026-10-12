// Page 4 weights: the PM edits the prio-v1 factor weights and the band thresholds (Must / Should). While a slider
// moves, POST /api/prioritize/preview re-scores every target in memory (nothing stored) and the skyline morphs to the
// previewed heights and bands; the panel counts the band changes and the PM decisions that would get a proposal.
// Saving needs a rationale: a new weights version + audit event, then the server re-scores cp1 → cp2 on its own.
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api, getActor, queryClient } from "@/lib/api";
import type { Band } from "@/lib/prioritize";
import { useCheckpoint } from "@/state/checkpoint";
import { CP_LABEL, factorLabel, type PrioData } from "./data";
import { getP, setP } from "./store";
import { trackRescore } from "./rescore";
import "./weights.css";

export type Factors = Record<string, number>;
export interface Bands { Must: number; Should: number }
interface Draft { factors: Factors; bands: Bands }
interface PreviewRow { key: string; line: string; market: string; score: number; band: Band; prev_score: number | null; prev_band: Band | null; confirmed: Band | null }
interface PreviewResp {
  checkpoint: string; bands: Bands; targets: PreviewRow[]; changes: PreviewRow[]; decisions_affected: PreviewRow[];
  summary: { targets: number; by_band: Partial<Record<Band, number>>; changes: number; moves: Record<string, number>; decisions_affected: number };
}
interface HistoryRow { version: number; id: number; factors: Factors; bands: Bands; actor: string; at: string; rationale: string; default?: boolean }

const GROUPS: { name: string; keys: string[] }[] = [
  { name: "Customer", keys: ["customer_voice", "satisfaction_gap"] },
  { name: "Business", keys: ["competitive_gap", "market_weight", "portfolio_leverage"] },
  { name: "Future", keys: ["future_relevance"] },
];
const NOTE: Record<string, string> = { market_weight: "stylized (Q-015)" };
const F_MAX = 50;

/* --------------------------------------------------------------------------------------------- tiny stores */
function store<T>(init: T) {
  let v = init;
  const subs = new Set<() => void>();
  return {
    get: () => v,
    set: (n: T) => { if (n !== v) { v = n; subs.forEach((f) => f()); } },
    use: () => useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, () => v),
  };
}
const previewStore = store<PreviewResp | null>(null);
/** the panel sits on the far left under the HUD, where the matrix goes: one of the two at a time */
const openStore = store<boolean>(false);
export const useWeightsOpen = () => openStore.use();
export function setWeightsOpen(v: boolean) {
  openStore.set(v);
  if (v && getP().view === "matrix") setP({ view: "skyline" });
}

/** The live weights preview (proposed bands + per-target score/band), or null when none is shown. */
export function usePreview() {
  const p = previewStore.use();
  return useMemo(() => p && {
    bands: p.bands,
    by: new Map(p.targets.map((t) => [`${t.key}|${t.line}|${t.market}`, t])),
  }, [p]);
}

/* --------------------------------------------------------------------------------------------- button */
export function WeightsButton({ pd }: { pd: PrioData }) {
  const open = useWeightsOpen();
  const v = pd.data.weights?.version;
  return (
    <div className="dseg">
      <button className="pweights-open" aria-expanded={open} aria-controls="weights-panel" title="Change factor weights and the Must/Should thresholds"
              onClick={() => setWeightsOpen(!open)}>
        Weights{v != null && <span>v{String(v)}</span>}
      </button>
    </div>
  );
}

/** Plain words for the HUD's micro line: which formula, which weights version, by whom. */
export function weightsNote(w: PrioData["data"]["weights"]): string {
  const v = w?.version ?? 1;
  const by = w?.default !== false ? "default, D-050" : `by ${String(w?.actor ?? "PM")}${w?.at ? `, ${fmtDay(String(w.at)).split(" ").slice(0, 2).join(" ")}` : ""}`;
  return `Scoring formula ${String(w?.scheme ?? "prio-v1")} · weights v${String(v)} (${by})`;
}

/* --------------------------------------------------------------------------------------------- panel */
const same = (a: Draft, b: Draft) =>
  a.bands.Must === b.bands.Must && a.bands.Should === b.bands.Should && Object.keys(b.factors).every((k) => a.factors[k] === b.factors[k]);
const fmtDay = (iso: string) => { const d = new Date(iso); return isNaN(+d) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + " " + d.toTimeString().slice(0, 5); };

export function WeightsPanel({ pd }: { pd: PrioData }) {
  const { cp } = useCheckpoint();
  const w = pd.data.weights ?? {};
  const current = useMemo<Draft>(() => ({
    factors: { ...(w.factors ?? {}) } as Factors,
    bands: { Must: w.bands?.Must ?? 60, Should: w.bands?.Should ?? 45 },
  }), [w.factors, w.bands]);   // eslint-disable-line react-hooks/exhaustive-deps
  const [draft, setDraft] = useState<Draft>(current);
  const dirty = !same(draft, current);
  // a new current version (saved here or elsewhere) resets the draft
  const ver = String(w.version ?? "");
  useEffect(() => { setDraft(current); }, [ver]);   // eslint-disable-line react-hooks/exhaustive-deps

  /* the preview, debounced */
  const preview = previewStore.use();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    if (!dirty || pd.notRun) { previewStore.set(null); setErr(null); return; }
    const me = ++seq.current;
    setBusy(true);
    const h = setTimeout(() => {
      api.post<PreviewResp>("/api/prioritize/preview", { ...draft, cp })
        .then((r) => { if (me === seq.current) { previewStore.set(r); setErr(null); } })
        .catch((e: Error) => { if (me === seq.current) setErr(e.message); })
        .finally(() => { if (me === seq.current) setBusy(false); });
    }, 250);
    return () => clearTimeout(h);
  }, [draft, dirty, cp, pd.notRun]);
  useEffect(() => () => previewStore.set(null), []);

  const hist = useQuery({
    queryKey: ["prioritize-weights-history"],
    queryFn: () => api.get<{ history: HistoryRow[] }>("/api/prioritize/weights/history?limit=6"),
    enabled: !pd.notRun, staleTime: 10_000,
  });

  const [saving, setSaving] = useState<false | "form" | "posting">(false);
  const [why, setWhy] = useState("");
  const save = async () => {
    setSaving("posting");
    try {
      const r = await api.post("/api/prioritize/weights", { factors: draft.factors, bands: draft.bands, rationale: why.trim(), actor: getActor() });
      setSaving(false); setWhy("");
      previewStore.set(null);
      await queryClient.invalidateQueries({ queryKey: ["prioritize-weights-history"] });
      await trackRescore(r);
    } catch (e) {
      setErr((e as Error).message); setSaving("form");
    }
  };

  const total = Object.values(draft.factors).reduce((s, v) => s + v, 0) || 1;
  const setF = (k: string, v: number) => setDraft((d) => ({ ...d, factors: { ...d.factors, [k]: v } }));
  const setB = (k: keyof Bands, v: number) => setDraft((d) => {
    const b = { ...d.bands, [k]: v };
    if (k === "Must" && b.Should >= v) b.Should = Math.max(1, v - 1);
    if (k === "Should" && b.Must <= v) b.Must = Math.min(100, v + 1);
    return { ...d, bands: b };
  });
  const s = dirty ? preview?.summary : null;
  const moves = Object.entries(s?.moves ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <aside className="pweights" id="weights-panel" aria-label="Weights">
      <button className="audit-close" onClick={() => setWeightsOpen(false)} aria-label="Close weights"><X size={16} /></button>
      <p className="dlist-head"><span className="sheet-layer">Weights v{String(w.version ?? 1)}{w.default !== false ? " · default" : ""} · {String(w.scheme ?? "prio-v1")}</span></p>
      {pd.notRun && <p className="dnotrun" role="status"><b>Not run yet</b> Weights apply to scores, and there are none at this checkpoint.</p>}

      {GROUPS.map((g) => {
        const sum = g.keys.reduce((a, k) => a + (draft.factors[k] ?? 0), 0);
        return (
          <section key={g.name} className="pw-group">
            <h3 className="dlist-domain">{g.name}<span>{Math.round((100 * sum) / total)}%</span></h3>
            {g.keys.map((k) => (
              <Slider key={k} label={factorLabel(k)} note={NOTE[k]} value={draft.factors[k] ?? 0} was={current.factors[k] ?? 0} max={F_MAX}
                      share={(100 * (draft.factors[k] ?? 0)) / total} onChange={(v) => setF(k, v)} disabled={pd.notRun} />
            ))}
          </section>
        );
      })}
      <section className="pw-group">
        <h3 className="dlist-domain">Band thresholds<span>score</span></h3>
        <Slider label="Must ≥" value={draft.bands.Must} was={current.bands.Must} min={2} max={100} onChange={(v) => setB("Must", v)} disabled={pd.notRun} />
        <Slider label="Should ≥" value={draft.bands.Should} was={current.bands.Should} min={1} max={99} onChange={(v) => setB("Should", v)} disabled={pd.notRun} />
      </section>

      <section className="pw-preview" aria-live="polite">
        {!dirty ? <p className="label">Move a slider to preview · {CP_LABEL[cp] ?? cp}, all lines</p> : err ? <p className="pw-err">{err}</p> : (
          <>
            <div className="pw-readout" data-busy={busy ? "" : undefined}>
              <div><span className="num">{s?.changes ?? "–"}</span><span className="label">band changes</span></div>
              <div><span className="num">{s?.decisions_affected ?? "–"}</span><span className="label">PM decisions → proposal</span></div>
            </div>
            {moves.length > 0 && <p className="pw-moves">{moves.map(([m, n]) => <span key={m}>{m.replace("→", " → ")} <b>{n}</b></span>)}</p>}
            <p className="label">{CP_LABEL[cp] ?? cp}, all lines · preview, nothing stored</p>
          </>
        )}
      </section>

      {saving ? (
        <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); if (why.trim().length >= 5) save(); }}>
          <textarea rows={2} value={why} onChange={(e) => setWhy(e.target.value)} autoFocus placeholder="Why these weights? (required)" aria-label="Rationale" />
          <div className="ladder-actions">
            <button type="submit" className="dbtn primary" disabled={why.trim().length < 5 || saving === "posting"}>{saving === "posting" ? "Saving…" : "Save as new version"}</button>
            <button type="button" className="dbtn" onClick={() => setSaving(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="ladder-actions">
          <button className="dbtn primary" disabled={!dirty || pd.notRun} onClick={() => setSaving("form")}>Save…</button>
          <button className="dbtn" disabled={!dirty} onClick={() => setDraft(current)}>Reset</button>
        </div>
      )}

      {(hist.data?.history.length ?? 0) > 0 && (
        <section className="pw-hist">
          <h3 className="dlist-domain">History<span>load, then save to revert</span></h3>
          <ul>
            {hist.data!.history.map((h) => (
              <li key={h.version}>
                <button className="pw-hrow" aria-current={String(h.version) === ver ? "true" : undefined}
                        onClick={() => setDraft({ factors: { ...current.factors, ...h.factors }, bands: { ...h.bands } })}
                        title={h.rationale}>
                  <span className="pw-hv">v{h.version}{h.default ? " · default" : ""}</span>
                  <span className="pw-hwho">{h.actor} · {fmtDay(h.at)}</span>
                  <span className="pw-hwhy">{h.rationale}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}

function Slider({ label, note, value, was, min = 0, max, share, onChange, disabled }: {
  label: string; note?: string; value: number; was: number; min?: number; max: number; share?: number; onChange: (v: number) => void; disabled?: boolean;
}) {
  const pos = (x: number) => `${(100 * (Math.min(max, Math.max(min, x)) - min)) / (max - min)}%`;
  return (
    <label className="pw-row" data-moved={value !== was ? "" : undefined}>
      <span className="pw-label">{label}{note && <i>{note}</i>}</span>
      <span className="pw-track">
        <input type="range" min={min} max={max} step={1} value={value} disabled={disabled} onChange={(e) => onChange(Number(e.target.value))} aria-label={label} />
        {value !== was && <i className="pw-was" style={{ left: pos(was) }} aria-hidden title={`current ${was}`} />}
      </span>
      <span className="pw-val">{Math.round(value)}</span>
      {share != null && <span className="pw-share">{Math.round(share)}%</span>}
    </label>
  );
}
