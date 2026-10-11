// Instrument primitives shared by every screen. Each encodes one piece of state the same way everywhere:
// priority (fill = PM-confirmed, dashed = AI suggestion), evidence (signal bars), score (band-ticked bar / arc).
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { Evidence, Priority, Status } from "@/lib/types";
import { BANDS, EVIDENCE, EVIDENCE_HELP, STATUS } from "@/lib/labels";
import { fmtDelta, fmtScore } from "@/lib/format";
import "./ui.css";

export function PriorityMark({ p, ai, size = "md" }: { p: Priority | null | undefined; ai?: boolean; size?: "sm" | "md" }) {
  if (!p) return <span className={`pm pm-none pm-${size}`}>–</span>;
  return (
    <span
      className={`pm pm-${p.toLowerCase()} pm-${size}${ai ? " pm-ai" : ""}`}
      title={ai ? `${p} — AI suggests, not yet confirmed by the PM` : `${p} — confirmed by the PM`}
    >
      {p}
      {ai && <span className="pm-ai-tag">AI</span>}
    </span>
  );
}

export function EvidenceMeter({ level, label = false }: { level: Evidence | null | undefined; label?: boolean }) {
  const lit = level ? 5 - Number(level.slice(1)) : 0;
  const tone = lit >= 3 ? "good" : lit === 2 ? "mid" : "low";
  return (
    <span className="ev" title={level ? `${EVIDENCE[level]} — ${EVIDENCE_HELP[level]}` : "No evidence level"}>
      <span className={`ev-bars ev-${tone}`} aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <i key={i} className={i < lit ? "on" : ""} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {label && <span className="ev-label">{level ? EVIDENCE[level] : "No level"}</span>}
      {!label && <span className="sr-only">{level ? EVIDENCE[level] : "No evidence level"}</span>}
    </span>
  );
}

export function ScoreBar({ score, width = 96, showValue = true }: { score: number | null | undefined; width?: number; showValue?: boolean }) {
  const s = score == null ? null : Math.max(0, Math.min(100, score));
  const band = s == null ? "none" : s >= BANDS.Must ? "must" : s >= BANDS.Should ? "should" : "could";
  return (
    <span className="sb" title={s == null ? "Not scored" : `Score ${s.toFixed(1)} of 100 · Must ≥ 60 · Should ≥ 45`}>
      <span className="sb-track" style={{ width }}>
        <span className={`sb-fill sb-${band}`} style={{ width: `${s ?? 0}%` }} />
        <span className="sb-tick" style={{ left: `${BANDS.Should}%` }} />
        <span className="sb-tick" style={{ left: `${BANDS.Must}%` }} />
      </span>
      {showValue && <span className="sb-val num">{fmtScore(s)}</span>}
    </span>
  );
}

/** Gauge for a headline score: 240° sweep, band ticks at Should/Must, wide light numerals. */
export function ScoreArc({ score, size = 168, caption }: { score: number | null | undefined; size?: number; caption?: ReactNode }) {
  const s = score == null ? 0 : Math.max(0, Math.min(100, score));
  const r = size / 2 - 10;
  const cx = size / 2;
  const cy = size / 2;
  const start = 150; // degrees, SVG coordinates (0 = 3 o'clock, clockwise)
  const sweep = 240;
  const pt = (deg: number, rr = r) => {
    const a = (deg * Math.PI) / 180;
    return [cx + rr * Math.cos(a), cy + rr * Math.sin(a)];
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = pt(from);
    const [x2, y2] = pt(to);
    const large = to - from > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };
  const end = start + (sweep * s) / 100;
  const band = score == null ? "none" : s >= BANDS.Must ? "must" : s >= BANDS.Should ? "should" : "could";
  const tick = (v: number) => {
    const d = start + (sweep * v) / 100;
    const [x1, y1] = pt(d, r - 9);
    const [x2, y2] = pt(d, r + 6);
    return <line key={v} x1={x1} y1={y1} x2={x2} y2={y2} className="arc-tick" />;
  };
  return (
    <div className="arc" style={{ width: size, height: size * 0.86 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <path d={arc(start, start + sweep)} className="arc-track" />
        {score != null && s > 0.5 && <path d={arc(start, end)} className={`arc-fill arc-${band}`} />}
        {tick(BANDS.Should)}
        {tick(BANDS.Must)}
      </svg>
      <div className="arc-center">
        <div className="instrument arc-num" style={{ fontSize: size * 0.3 }}>{fmtScore(score)}</div>
        {caption && <div className="arc-cap">{caption}</div>}
      </div>
    </div>
  );
}

export function Delta({ d, digits }: { d: number | null | undefined; digits?: number }) {
  if (d == null) return <span className="chip outline">new</span>;
  const tone = d > 0.05 ? "up" : d < -0.05 ? "down" : "";
  const Icon = d > 0.05 ? ArrowUpRight : d < -0.05 ? ArrowDownRight : Minus;
  return (
    <span className={`chip ${tone}`}>
      <Icon aria-hidden />
      {digits === 0 ? `${d > 0 ? "+" : ""}${Math.round(d)}` : fmtDelta(d)}
    </span>
  );
}

const STATUS_TONE: Record<Status, string> = {
  proposed: "blue",
  challenged: "violet",
  approved: "green",
  deferred: "amber",
  rejected: "red",
};
export function StatusLight({ s }: { s: Status }) {
  return <span className={`telltale ${STATUS_TONE[s]}`}>{STATUS[s]}</span>;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}

export function Seg<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode; count?: number }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
          {o.count != null && <span className="count">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ h = 14, w = "100%", r }: { h?: number; w?: number | string; r?: number }) {
  return <div className="skel" style={{ height: h, width: w, borderRadius: r }} />;
}

export function SkeletonBlock({ lines = 4 }: { lines?: number }) {
  return (
    <div className="col" style={{ gap: 10 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} w={`${92 - ((i * 17) % 40)}%`} />
      ))}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="errnote" role="alert">
      <span className="telltale red">Couldn't load</span>
      <span className="errnote-msg">{msg}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-title">{title}</div>
      {children && <div className="empty-body">{children}</div>}
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value num">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
