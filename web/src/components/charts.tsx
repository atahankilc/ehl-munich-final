// Hand-drawn SVG charts in the instrument style: thin lines, band guides at 45/60, one highlighted series.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Breakdown } from "@/lib/types";
import { BANDS } from "@/lib/labels";
import "./charts.css";

export type Series = { key: string; label: string; points: { x: number; xLabel: string; y: number | null; note?: string | null }[] };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function HistoryChart({ series, focus, height = 200 }: { series: Series[]; focus: string | null; height?: number }) {
  const [hover, setHover] = useState<{ s: string; i: number } | null>(null);
  const [ref, W] = useWidth<HTMLDivElement>();
  const xs = useMemo(() => [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b), [series]);
  const H = height;
  const padL = 30;
  const padR = 92;
  const padT = 14;
  const padB = 26;
  const inner = Math.max(40, W - padL - padR);
  const x = (v: number) => (xs.length < 2 ? padL + inner / 2 : padL + (xs.indexOf(v) / (xs.length - 1)) * inner);
  const y = (v: number) => padT + (1 - v / 100) * (H - padT - padB);
  const xLabel = (v: number) => series.flatMap((s) => s.points).find((p) => p.x === v)?.xLabel ?? String(v);
  const ordered = [...series].sort((a) => (a.key === focus ? 1 : -1));
  return (
    <div className="hchart" ref={ref} style={{ height: H }}>
      {W > 0 && (
        <svg width={W} height={H} role="img" aria-label="Score per car and market across prioritization runs">
          {[0, 25, 50, 75, 100].map((g) => (
            <line key={g} x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} className="hc-grid" />
          ))}
          {[BANDS.Should, BANDS.Must].map((b) => (
            <g key={b}>
              <line x1={padL} x2={W - padR} y1={y(b)} y2={y(b)} className="hc-band" />
              <text x={padL - 6} y={y(b) + 3} className="hc-axis" textAnchor="end">{b}</text>
            </g>
          ))}
          {xs.map((v, i) => (
            <text key={v} x={x(v)} y={H - 8} className="hc-axis" textAnchor={xs.length > 1 && i === 0 ? "start" : xs.length > 1 && i === xs.length - 1 ? "end" : "middle"}>{xLabel(v)}</text>
          ))}
          {ordered.map((s) => {
            const pts = s.points.filter((p) => p.y != null);
            const isF = s.key === focus;
            const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y!)}`).join(" ");
            const last = pts[pts.length - 1];
            return (
              <g key={s.key} className={isF ? "hc-s focus" : "hc-s"}>
                <path d={d} className="hc-line" />
                {pts.map((p, i) => (
                  <circle key={i} cx={x(p.x)} cy={y(p.y!)} r={isF ? 4 : 3} className="hc-dot" onMouseEnter={() => setHover({ s: s.key, i })} onMouseLeave={() => setHover(null)} />
                ))}
                {isF && last && (
                  <text x={x(last.x) + 10} y={y(last.y!) + 4} className="hc-end">
                    {s.label.split(" · ")[1] ?? s.label} {Math.round(last.y!)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      {hover && (() => {
        const s = series.find((z) => z.key === hover.s)!;
        const p = s.points.filter((z) => z.y != null)[hover.i];
        return (
          <div className="hc-tip">
            <b>{s.label}</b> · {p.xLabel} · <span className="num">{p.y?.toFixed(1)}</span>
            {p.note && <div className="muted">{p.note}</div>}
          </div>
        );
      })()}
    </div>
  );
}

/** Score arithmetic for one car · market: factor points → confidence → modifiers → score. */
export function Waterfall({ b }: { b: Breakdown }) {
  const factors = Object.entries(b.factors).filter(([, f]) => f.available);
  const sumW = factors.reduce((s, [, f]) => s + f.weight, 0) || 1;
  const raw = factors.map(([k, f]) => ({ k, label: f.label, v: (100 * f.weight * (f.value ?? 0)) / sumW }));
  const base = raw.reduce((s, r) => s + r.v, 0);
  const conf = base * (b.confidence - 1);
  const mods = Object.entries(b.modifiers ?? {}).filter(([, v]) => v);
  const steps: { label: string; v: number; kind: "f" | "c" | "m" | "t"; note?: string }[] = [
    ...raw.map((r) => ({ label: r.label, v: r.v, kind: "f" as const })),
    ...(Math.abs(conf) > 0.05 ? [{ label: `Evidence ${b.evidence_level} ×${b.confidence}`, v: conf, kind: "c" as const }] : []),
    ...mods.map(([k, v]) => ({ label: MOD_LABEL[k] ?? k.replace(/_/g, " "), v, kind: "m" as const })),
  ];
  let run = 0;
  const bars = steps.map((s) => {
    const from = run;
    run += s.v;
    return { ...s, from, to: run };
  });
  const max = Math.max(100, ...bars.map((x) => Math.max(x.from, x.to)));
  const pct = (v: number) => `${(Math.max(0, v) / max) * 100}%`;
  return (
    <div className="wf">
      {bars.map((s) => (
        <div key={s.label} className={`wf-row wf-${s.kind}`}>
          <span className="wf-label">{s.label}</span>
          <span className="wf-track">
            <span className="wf-bar" style={{ left: pct(Math.min(s.from, s.to)), width: pct(Math.abs(s.to - s.from)) }} />
          </span>
          <span className="wf-val num">{s.v >= 0 ? "+" : "−"}{Math.abs(s.v).toFixed(1)}</span>
        </div>
      ))}
      <div className="wf-row wf-t">
        <span className="wf-label">Score</span>
        <span className="wf-track">
          <span className="wf-bar" style={{ left: 0, width: pct(b.score) }} />
          <span className="wf-guide" style={{ left: pct(BANDS.Should) }} />
          <span className="wf-guide" style={{ left: pct(BANDS.Must) }} />
        </span>
        <span className="wf-val num">{b.score.toFixed(1)}</span>
      </div>
    </div>
  );
}

const MOD_LABEL: Record<string, string> = {
  market_fit: "Market fit",
  effort: "Effort",
  no_comment_cap: "No-comment cap",
  compliance: "Compliance",
};
