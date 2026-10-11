// The target ladder of one requirement for one car line × market, as one horizontal scale with "better" always to
// the right: today's baseline, then threshold (parity), target (need at launch), stretch (delighter). The mark style
// is the basis of the number: filled = cited, hollow = projected, dashed = assumption, "?" = gap (no number is
// invented). The AI's recommended rung carries an "AI" tag; the PM's chosen rung is the PM's position, in sweep blue.
// Rival / benchmark facts with the same unit (and a compatible test cycle) sit on the rail as quiet neutral ticks.
import { useState } from "react";
import type { ChoosableRung, LadderRow, Level, Metric, Rung } from "@/lib/definition";
import { chosenRung, fmtLevel } from "./data";
import { useView } from "./store";

const RUNGS: Rung[] = ["baseline", "threshold", "target", "stretch"];
const RUNG_NAME: Record<Rung, string> = { baseline: "Today", threshold: "Threshold", target: "Target", stretch: "Stretch" };
const BASIS_NAME = { cited: "cited", projected: "projected", assumption: "assumption", gap: "gap" } as const;

/* ------------------------------------------------------------------ rival / benchmark facts (spec_fact rows) */
interface Rival { id: string; entity: string; short: string; value: number; valueMax: number | null; market: string | null;
  cycle: string | null; tier: string | null; published: string | null; url: string | null; onScale: boolean; why: string | null }

const UNIT_ALIAS: Record<string, string> = {
  minutes: "min", mins: "min", minute: "min", kilometers: "km", kilometres: "km", seconds: "s", sec: "s", secs: "s",
  millimeters: "mm", millimetres: "mm", meters: "m", metres: "m",
};
const normUnit = (u: unknown) => { const s = String(u ?? "").trim().toLowerCase(); return UNIT_ALIAS[s] ?? s; };
const normCycle = (c: unknown) => (c == null || c === "" ? null : String(c).toLowerCase().replace(/[^a-z]/g, ""));
const CYCLE_NAME: Record<string, string> = { realworld: "real-world", wltp: "WLTP", epa: "EPA", cltc: "CLTC", nedc: "NEDC" };
const cycleName = (c: string | null) => (c ? CYCLE_NAME[c] ?? c : "cycle not named");
/** the test cycle the metric itself names, if any */
function metricCycle(m: Metric | null): string | null {
  const t = `${m?.name ?? ""} ${m?.conditions ?? ""} ${m?.method ?? ""}`;
  const hit = t.match(/\b(WLTP|EPA|CLTC|NEDC)\b/i) ?? t.match(/real[\s-]world/i);
  return hit ? normCycle(hit[0]) : null;
}
/** "E-Class" from "Mercedes-Benz E-Class", "Taycan" from "Porsche Taycan"; the brand when nothing is left */
function shortName(entity: string, brand: string | null) {
  let s = entity;
  if (brand && s.toLowerCase().startsWith(brand.toLowerCase())) s = s.slice(brand.length).trim();
  s = s.split(/\s+/).slice(0, 2).join(" ");
  return s || brand || entity;
}
/** Facts whose unit matches the metric. On the scale only when the cycle fits: the metric's own cycle when it names
 * one, otherwise never CLTC next to WLTP / EPA (CLTC only on a China row). The rest are listed with their cycle. */
function rivalsFor(facts: Record<string, unknown>[] | undefined, metric: Metric | null, market: string): Rival[] {
  if (!facts?.length || !metric?.unit || metric.direction === "binary") return [];
  const unit = normUnit(metric.unit), want = metricCycle(metric), cn = market.toUpperCase() === "CN";
  return facts.flatMap((f) => {
    const value = typeof f.value === "number" ? f.value : Number(f.value);
    if (!Number.isFinite(value) || normUnit(f.unit) !== unit) return [];
    const cycle = normCycle(f.cycle);
    const fits = want ? cycle === want : cn ? cycle === "cltc" : cycle !== "cltc";
    const entity = String(f.entity ?? f.brand ?? "Benchmark");
    const brand = f.brand ? String(f.brand) : null;
    const vmax = typeof f.value_max === "number" ? f.value_max : null;
    return [{
      id: String(f.id ?? `${entity}-${value}`), entity, short: shortName(entity, brand), value, valueMax: vmax,
      market: f.market ? String(f.market) : null, cycle, tier: f.tier ? String(f.tier) : null,
      published: f.published_at ? String(f.published_at) : null, url: f.url ? String(f.url) : null,
      onScale: fits, why: fits ? null : want ? `${cycleName(cycle)}, metric is ${cycleName(want)}` : cycleName(cycle),
    }];
  });
}

interface Props {
  reqKey: string;
  row: LadderRow;
  metric: Metric | null;
  evidenceText: (id: string) => string | undefined;
  onSource: (id: string) => void;
  onChoose: (level: ChoosableRung, rationale: string) => void;
  busy: boolean;
  sample: boolean;
  /** spec_fact rows behind the requirement (detail payload); matching ones become quiet ticks on the scale */
  facts?: Record<string, unknown>[];
}

export function Ladder({ reqKey, row, metric, evidenceText, onSource, onChoose, busy, sample, facts }: Props) {
  useView((s) => s.pending);
  const [pick, setPick] = useState<ChoosableRung | null>(null);
  const [why, setWhy] = useState("");
  const chosen = chosenRung(reqKey, row);
  const unit = metric?.unit;

  const levels = RUNGS.map((k) => ({ k, l: row[k] as Level | null })).filter((x): x is { k: Rung; l: Level } => !!x.l);
  const nums = levels.map((x) => x.l.value).filter((v): v is number => v != null);
  const rivals = rivalsFor(facts, metric, row.market);
  const ticks = rivals.filter((r) => r.onScale);
  // the scale's domain covers the rungs and the rival ticks
  const dom = [...nums, ...ticks.map((t) => t.value)];
  const scaled = dom.length > 1;
  const lo = Math.min(...dom), hi = Math.max(...dom);
  const span = hi - lo || Math.abs(hi) || 1;
  const lower = metric?.direction === "lower";
  const frac = (v: number) => { const f = (v - lo) / span; return lower ? 1 - f : f; };
  // place every rung: numbers on the scale (8%–92%), gaps between their numbered neighbours in rung order
  const placed = levels.map((x, i) => {
    if (x.l.value != null && scaled) return { ...x, at: 0.08 + frac(x.l.value) * 0.84 };
    if (x.l.value != null) return { ...x, at: 0.5 };
    const prev = levels.slice(0, i).reverse().find((y) => y.l.value != null);
    const next = levels.slice(i + 1).find((y) => y.l.value != null);
    const pa = prev?.l.value != null && scaled ? 0.08 + frac(prev.l.value) * 0.84 : null;
    const na = next?.l.value != null && scaled ? 0.08 + frac(next.l.value) * 0.84 : null;
    const at = pa != null && na != null ? (pa + na) / 2 : pa != null ? Math.min(0.97, pa + 0.12) : na != null ? Math.max(0.03, na - 0.12) : 0.15 + i * 0.23;
    return { ...x, at };
  });
  // rungs with (nearly) the same value would sit on top of each other: keep a minimum gap between their buttons
  // (the printed values stay exact), keeping rung order
  const MIN = 0.17;
  const order = [...placed].sort((p, q) => p.at - q.at);
  for (let i = 1; i < order.length; i++) order[i].at = Math.max(order[i].at, order[i - 1].at + MIN);
  if (order.length) order[order.length - 1].at = Math.min(order[order.length - 1].at, 0.94);
  for (let i = order.length - 2; i >= 0; i--) order[i].at = Math.min(order[i].at, order[i + 1].at - MIN);
  if (order.length && order[0].at < 0.06) { const d = 0.06 - order[0].at; for (const p of order) p.at += d; }

  // rival ticks keep their true place on the scale (no spacing); ticks at the same spot merge into one mark
  const tickAt = (v: number) => (scaled ? 0.08 + frac(v) * 0.84 : 0.5);
  const tickGroups: { at: number; items: Rival[] }[] = [];
  for (const t of [...ticks].sort((a, b) => tickAt(a.value) - tickAt(b.value))) {
    const at = tickAt(t.value), g = tickGroups[tickGroups.length - 1];
    if (g && Math.abs(g.at - at) < 0.012) g.items.push(t); else tickGroups.push({ at, items: [t] });
  }
  const rivalText = (r: Rival) => `${r.entity} · ${fmtLevel(r.value, unit)}${r.valueMax != null ? `–${fmtLevel(r.valueMax, unit)}` : ""}`
    + `${r.market ? ` · ${r.market}` : ""}${r.cycle ? ` · ${cycleName(r.cycle)}` : ""}${r.tier ? ` · ${r.tier}` : ""}${r.published ? ` · ${r.published}` : ""}`;

  const submit = () => { if (pick && why.trim().length >= 5) { onChoose(pick, why.trim()); setPick(null); setWhy(""); } };

  return (
    <div className="ladder">
      <div className="ladder-head">
        <span className="ladder-where">{row.line} · {row.market}</span>
        <span className="ladder-dir label">{lower ? "lower is better" : metric?.direction === "binary" ? "yes / no" : "higher is better"} →</span>
      </div>
      <div className="ladder-scale" role="group" aria-label={`Target ladder, ${row.line} ${row.market}`} data-rivals={tickGroups.length ? "" : undefined}>
        <span className="ladder-rail" aria-hidden />
        {tickGroups.map(({ at, items }) => {
          const first = items[0];
          const label = `${items.map((r) => r.short).join(" · ")} ${fmtLevel(first.value, unit)}`;
          const title = items.map(rivalText).join("\n") + (first.url ? "\nOpen source" : "");
          const inner = <><i className="ladder-tick-mark" aria-hidden /><span className="ladder-tick-tag">{label}</span></>;
          return first.url ? (
            <a key={first.id} className="ladder-tick" style={{ left: `${at * 100}%` }} data-edge={at > 0.8 ? "r" : at < 0.2 ? "l" : undefined} href={first.url} target="_blank" rel="noreferrer"
               title={title} aria-label={`Benchmark: ${items.map(rivalText).join("; ")}`}>{inner}</a>
          ) : (
            <span key={first.id} className="ladder-tick" style={{ left: `${at * 100}%` }} data-edge={at > 0.8 ? "r" : at < 0.2 ? "l" : undefined} tabIndex={0} title={title}
                  aria-label={`Benchmark: ${items.map(rivalText).join("; ")}`}>{inner}</span>
          );
        })}
        {placed.map(({ k, l, at }) => {
          const choosable = k !== "baseline";
          const rec = row.recommended === k, mine = chosen === k, picking = pick === k;
          const inner = (
            <>
              <span className="ladder-val">{l.basis === "gap" ? "?" : fmtLevel(l.value, unit)}</span>
              <i className="ladder-mark" data-basis={l.basis} aria-hidden>{l.basis === "gap" ? "?" : null}</i>
              <span className="ladder-name">{RUNG_NAME[k]}</span>
              <span className="ladder-tags">
                {rec && <b className="ladder-ai" title="The AI's recommendation">AI</b>}
                {mine && <b className="ladder-pm" title="The PM's choice">PM</b>}
              </span>
            </>
          );
          const title = `${RUNG_NAME[k]}: ${l.basis === "gap" ? "no number" : l.text} · ${BASIS_NAME[l.basis]}${l.note ? ` — ${l.note}` : ""}`;
          return choosable ? (
            <button key={k} type="button" className="ladder-rung" style={{ left: `${at * 100}%` }} data-rung={k} data-on={mine ? "" : undefined}
                    data-picking={picking ? "" : undefined} title={title} aria-pressed={mine}
                    onClick={() => { setPick(picking ? null : (k as ChoosableRung)); }}>
              {inner}
            </button>
          ) : (
            <span key={k} className="ladder-rung" style={{ left: `${at * 100}%` }} data-rung={k} title={title}>{inner}</span>
          );
        })}
      </div>

      <ul className="ladder-basis">
        {levels.map(({ k, l }) => (
          <li key={k}>
            <i className="ladder-mark sm" data-basis={l.basis} aria-hidden>{l.basis === "gap" ? "?" : null}</i>
            <span className="ladder-basis-k">{RUNG_NAME[k]}</span>
            <span className="ladder-basis-v">
              {l.basis === "gap" ? <em>Gap: {l.note || "no data yet"}</em> : <>{BASIS_NAME[l.basis]}{l.note ? ` · ${l.note}` : ""}</>}
              {l.source_ids.map((id) => (
                <button key={id} type="button" className="ladder-src" title={evidenceText(id) ?? `Source ${id}`} onClick={() => onSource(id)}>{id}</button>
              ))}
            </span>
          </li>
        ))}
      </ul>
      {rivals.length > 0 && (
        <ul className="ladder-rivals" aria-label="Benchmarks">
          {rivals.map((r) => (
            <li key={r.id} data-off={r.onScale ? undefined : ""}>
              <i className="ladder-tick-mark sm" aria-hidden />
              <span className="ladder-rivals-k" title={r.entity}>{r.short}</span>
              <span className="ladder-rivals-v">
                {fmtLevel(r.value, unit)}{r.valueMax != null ? `–${fmtLevel(r.valueMax, unit)}` : ""}
                {[r.market, r.cycle ? cycleName(r.cycle) : null, r.tier].filter(Boolean).map((x) => ` · ${x}`).join("")}
                {!r.onScale && <em> · not on the scale ({r.why})</em>}
                {r.url && <a className="ladder-src" href={r.url} target="_blank" rel="noreferrer" title={rivalText(r)}>source</a>}
              </span>
            </li>
          ))}
        </ul>
      )}
      {row.rationale &&<p className="ladder-why"><span className="label">AI recommends {RUNG_NAME[row.recommended].toLowerCase()}</span> {row.rationale}</p>}
      {row.choice && chosen === row.choice.level && (
        <p className="ladder-why pm"><span className="label">PM chose {RUNG_NAME[row.choice.level].toLowerCase()} · {row.choice.actor}</span> {row.choice.rationale}</p>
      )}

      {pick && (
        <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label className="label" htmlFor={`why-${reqKey}-${row.line}-${row.market}`}>
            Choose {RUNG_NAME[pick].toLowerCase()} · {(row[pick] as Level | null)?.text ?? "?"} for {row.line} · {row.market}. Why?
          </label>
          <textarea id={`why-${reqKey}-${row.line}-${row.market}`} rows={2} value={why} onChange={(e) => setWhy(e.target.value)}
                    placeholder="Rationale (required, goes into the audit trail)" autoFocus />
          <div className="ladder-actions">
            <button type="submit" className="dbtn primary" disabled={busy || why.trim().length < 5}>Choose {RUNG_NAME[pick].toLowerCase()}</button>
            <button type="button" className="dbtn" onClick={() => { setPick(null); setWhy(""); }}>Cancel</button>
            {sample && <span className="label">Sample data: kept in this view only</span>}
          </div>
        </form>
      )}
    </div>
  );
}
