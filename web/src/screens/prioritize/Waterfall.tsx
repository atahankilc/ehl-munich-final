// The score as a waterfall (D-037 pattern): the six factors add up by dimension (Customer, Business, Future) to the
// base, × the confidence multiplier, then the modifiers (effort, market fit) to the final score, on one 0–100 scale
// with the band thresholds marked. Neutral only: ink steps up, ink-3 hatched steps down, the score in full ink.
import type { Band, Factor, Target } from "@/lib/prioritize";
import { DIM_LABEL, factorLabel } from "./data";

interface Step { kind: "factor" | "gap" | "base" | "conf" | "mod" | "score"; label: string; from: number; to: number; text: string; why?: string; dim?: string }

const pct = (v: number) => `${Math.max(0, Math.min(100, v))}%`;
const sign = (v: number) => (v >= 0 ? `+${fmt(v)}` : `−${fmt(-v)}`);
const fmt = (v: number) => (Math.round(v * 10) / 10).toString();

export function Waterfall({ t, at, band, whatIf }: { t: Target; at: { Must: number; Should: number }; band: Band; whatIf?: { score: number; band: Band } | null }) {
  const steps: Step[] = [];
  let run = 0;
  const dims: Factor["dimension"][] = ["customer", "business", "future"];
  for (const d of dims) {
    for (const f of t.factors.filter((x) => x.dimension === d)) {
      if (!f.available) { steps.push({ kind: "gap", label: factorLabel(f.key), from: run, to: run, text: "gap", why: f.explanation || "No evidence for this factor; weight redistributed.", dim: d }); continue; }
      steps.push({ kind: "factor", label: factorLabel(f.key), from: run, to: run + f.points, text: sign(f.points), why: f.explanation, dim: d });
      run += f.points;
    }
  }
  const base = t.base ?? run;
  steps.push({ kind: "base", label: "Base", from: 0, to: base, text: fmt(base) });
  const afterConf = base * (t.confidence?.mult ?? 1);
  steps.push({ kind: "conf", label: `× ${(t.confidence?.mult ?? 1).toFixed(2)} confidence`, from: base, to: afterConf, text: sign(afterConf - base),
               why: `${t.confidence?.level ?? "–"} from the basis of the ladder's numbers${t.confidence?.basis_mix ? ` (${Object.entries(t.confidence.basis_mix).map(([k, v]) => `${v} ${k}`).join(", ")})` : ""}.` });
  run = afterConf;
  for (const m of t.modifiers) {
    steps.push({ kind: "mod", label: modLabel(m.key), from: run, to: run + m.points, text: m.points ? sign(m.points) : "±0", why: m.why });
    run += m.points;
  }
  steps.push({ kind: "score", label: "Score", from: 0, to: t.score, text: fmt(t.score) });

  let lastDim = "";
  return (
    <div className="pwf" role="img" aria-label={`Score ${fmt(t.score)}: base ${fmt(base)} from six factors, times confidence ${t.confidence?.mult}, plus modifiers`}>
      <div className="pwf-scale" aria-hidden>
        <span className="pwf-th" style={{ left: pct(at.Should) }}><b>Should</b> {at.Should}</span>
        <span className="pwf-th" style={{ left: pct(at.Must) }}><b>Must</b> {at.Must}</span>
      </div>
      <ol className="pwf-rows">
        {steps.map((s, i) => {
          const head = s.dim && s.dim !== lastDim ? DIM_LABEL[s.dim as keyof typeof DIM_LABEL] : null;
          if (s.dim) lastDim = s.dim;
          const lo = Math.min(s.from, s.to), hi = Math.max(s.from, s.to);
          return (
            <li key={i} className="pwf-row" data-kind={s.kind} data-neg={s.to < s.from ? "" : undefined} title={s.why}>
              {head && <span className="pwf-dim">{head}</span>}
              <span className="pwf-label">{s.label}</span>
              <span className="pwf-track">
                <i className="pwf-line" style={{ left: pct(at.Should) }} aria-hidden />
                <i className="pwf-line" style={{ left: pct(at.Must) }} aria-hidden />
                {s.kind === "gap" ? <i className="pwf-gap" style={{ left: pct(s.from) }} />
                  : <i className="pwf-bar" style={{ left: pct(lo), width: `calc(${pct(hi - lo)} + ${hi - lo < 0.6 ? 1 : 0}px)` }} />}
                {s.kind === "score" && whatIf && <i className="pwf-whatif" style={{ left: pct(whatIf.score) }} aria-label={`what-if ${fmt(whatIf.score)}`} />}
              </span>
              <span className="pwf-val">{s.kind === "score" ? <><b>{fmt(s.to)}</b> <em>{band}</em></> : s.text}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function modLabel(k: string) {
  return k === "effort" ? "Effort" : k === "market_fit" ? "Market fit" : k.replace(/_/g, " ");
}
