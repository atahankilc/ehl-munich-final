// The audit trail as a list, shared by the top-right Audit panel (this page, this checkpoint) and the Audit page (every
// area, one checkpoint at a time, D-055). One hairline rail: stage runs are milestones, every other row is a step.
// Identical steps of one stream (same action, stage and checkpoint, no gap over 10 minutes; the agent classifies 20
// comments per call) fold into one row with their totals and can be opened, even when another run's steps interleave.
import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { line } from "@/screens/structure/AgentPanel";

export interface Row {
  id: string; ts: string; actor_type: "ai" | "system" | "human"; actor: string; model: string | null;
  kind: string; stage: string | null; action: string; payload: Record<string, unknown>; checkpoint: string | null; summary: string | null;
  area?: Area;
}
export interface Page { items: Row[]; more: boolean }
export type Who = Row["actor_type"];
export type Area = "evidence" | "structure" | "definition" | "prioritize" | "settings" | "other";
type Item = { day: string; rows: Row[] };   // one row, or a fold of identical consecutive steps (newest first)

export const CP_LABEL: Record<string, string> = { cp1: "JAN 26", cp2: "JUL 26", ab: "A/B TEST" };
export const WHO: Record<Who, string> = { ai: "AI", system: "System", human: "PM" };
export const WHO_ORDER: Who[] = ["ai", "system", "human"];
// steps whose counts add up when folded ("Classified 20 comments" × 153 → "Classified 3,060 comments")
const SUMMABLE = new Set(["classify_comments", "map_study", "map_options", "map_research", "standardize", "duplicates"]);

const day = (ts: string) => new Date(ts).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const time = (ts: string) => new Date(ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const text = (r: Row) => r.summary ?? line({ action: r.action, stage: r.stage ?? "", payload: r.payload });

const GAP = 10 * 60_000;
function fold(rows: Row[]): Item[] {
  const out: Item[] = [];
  const open = new Map<string, Item>();
  const stream = (r: Row) => `${r.actor_type}|${r.kind}|${r.stage}|${r.action}|${r.checkpoint}`;
  for (const r of rows) {                                    // newest first
    if (r.kind === "run") {                                  // a stage starting or finishing closes its streams
      for (const k of [...open.keys()]) if (k.includes(`|${r.stage}|`) && k.endsWith(`|${r.checkpoint}`)) open.delete(k);
      out.push({ day: day(r.ts), rows: [r] });
      continue;
    }
    const g = open.get(stream(r));
    const prev = g?.rows[g.rows.length - 1];
    if (g && prev && g.day === day(r.ts) && Date.parse(prev.ts) - Date.parse(r.ts) <= GAP) { g.rows.push(r); continue; }
    const item = { day: day(r.ts), rows: [r] };
    out.push(item);
    open.set(stream(r), item);
  }
  return out;
}

function foldText(rows: Row[]) {
  const f = rows[0];
  if (rows.length === 1 || f.summary != null || !SUMMABLE.has(f.action)) return text(f);
  const payload: Record<string, unknown> = { ...f.payload };
  for (const k of Object.keys(payload)) {
    if (typeof payload[k] === "number") payload[k] = rows.reduce((s, r) => s + (Number(r.payload[k]) || 0), 0);
  }
  return line({ action: f.action, stage: f.stage ?? "", payload });
}

export function countBy<K extends string>(rows: Row[], key: (r: Row) => K | undefined): Partial<Record<K, number>> {
  const c: Partial<Record<K, number>> = {};
  for (const r of rows) {
    const k = key(r);
    if (k) c[k] = (c[k] ?? 0) + 1;
  }
  return c;
}

/** Who-acted chips: show or hide AI, System, PM. */
export function WhoChips({ rows, hidden, onToggle }: { rows: Row[]; hidden: Set<Who>; onToggle: (w: Who) => void }) {
  const counts = useMemo(() => countBy(rows, (r) => r.actor_type), [rows]);
  return (
    <div className="audit-who-chips" aria-label="Who acted">
      {WHO_ORDER.filter((w) => counts[w]).map((w) => (
        <button key={w} className="audit-chip" aria-pressed={!hidden.has(w)} onClick={() => onToggle(w)}>
          <i className="audit-mark" data-who={w} aria-hidden />{WHO[w]}<span className="audit-chip-n">{(counts[w] ?? 0).toLocaleString("en-US")}</span>
        </button>
      ))}
    </div>
  );
}

/** The trail itself. `rows` newest first; `more`: older rows exist that are not loaded yet. */
export function TrailList({ rows, loading, more, showCheckpoint = true }: { rows: Row[]; loading: boolean; more: boolean; showCheckpoint?: boolean }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const items = useMemo(() => fold(rows), [rows]);
  const oldest = rows.length ? Date.parse(rows[rows.length - 1].ts) : 0;
  const toggleFold = (id: string) => setExpanded((x) => { const n = new Set(x); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  let lastDay = "";
  return (
    <ol className="audit-list">
      {loading && <li className="audit-empty label">Loading…</li>}
      {!loading && items.length === 0 && <li className="audit-empty label">Nothing recorded here yet.</li>}
      {items.map((it) => {
        const head = it.day !== lastDay ? (lastDay = it.day) : null;
        const f = it.rows[0], n = it.rows.length, last = it.rows[n - 1];
        const milestone = f.kind === "run";
        const isOpen = expanded.has(f.id);
        // the last fold may continue into rows not loaded yet: say so rather than show a partial total as the total
        const partial = n > 1 && more && Date.parse(last.ts) - oldest <= GAP;
        const meta = [WHO[f.actor_type], f.model, n > 1 ? `${n}${partial ? "+" : ""} steps` : null,
                      n > 1 ? `${partial ? "…" : time(last.ts)}–${time(f.ts)}` : time(f.ts)].filter(Boolean).join(" · ");
        const body = (
          <>
            <span className="audit-text">{partial ? "Latest: " : ""}{foldText(it.rows)}</span>
            <span className="audit-meta">{meta}</span>
          </>
        );
        return (
          <li key={f.id} className="audit-item" data-milestone={milestone ? "" : undefined}>
            {head && <div className="audit-day">{head}</div>}
            <div className="audit-row">
              <i className="audit-mark" data-who={f.actor_type} data-milestone={milestone ? "" : undefined} aria-hidden />
              {n > 1 ? (
                <button className="audit-body audit-fold" aria-expanded={isOpen} onClick={() => toggleFold(f.id)}>
                  {body}<ChevronRight className="audit-chev" size={14} aria-hidden />
                </button>
              ) : <div className="audit-body">{body}</div>}
              {showCheckpoint && f.checkpoint && <span className="audit-cp">{CP_LABEL[f.checkpoint] ?? f.checkpoint}</span>}
            </div>
            {isOpen && (
              <ol className="audit-steps">
                {it.rows.map((r) => <li key={r.id}><span className="audit-step-t">{time(r.ts)}</span>{text(r)}</li>)}
              </ol>
            )}
          </li>
        );
      })}
    </ol>
  );
}
