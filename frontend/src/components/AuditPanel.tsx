// Audit, top-right. Opens on what the current page is about, for the selected checkpoint only: on Evidence, what
// entered the data and when; on Structure, when the agent ran each stage and every AI step. "Everything" shows both
// checkpoints, each row tagged; history from before the checkpoint rebuild (the old wave-based app) is kept in the
// append-only trail but only shown there on request. Styled like the rest of the HUD: a 28px pill like the filter chips, a glass sheet like the
// inspector. Inside, the trail runs down one hairline rail: stage runs are milestones, every other row is a step.
// Identical steps of one stream (same action, stage and checkpoint, no gap over 10 minutes; the agent classifies 20
// comments per call) fold into one row with their totals and can be opened, even when another run's steps interleave. Chips on top show or hide who acted.
import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { ChevronRight, History, ListChecks, ListOrdered, X } from "lucide-react";
import { api } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import { line } from "@/screens/structure/AgentPanel";
import { setTopPanel, toggleTopPanel, useTopPanel } from "./topPanel";
import { UsageView } from "./Usage";
import "./audit.css";

interface Row {
  id: string; ts: string; actor_type: "ai" | "system" | "human"; actor: string; model: string | null;
  kind: string; stage: string | null; action: string; payload: Record<string, unknown>; checkpoint: string | null; summary: string | null;
}
interface Page { items: Row[]; more: boolean }
type Who = Row["actor_type"];
type Item = { day: string; rows: Row[] };   // one row, or a fold of identical consecutive steps (newest first)

const CP_LABEL: Record<string, string> = { cp1: "JAN 26", cp2: "JUL 26", ab: "A/B TEST" };
const WHO: Record<Who, string> = { ai: "AI", system: "System", human: "PM" };
const WHO_ORDER: Who[] = ["ai", "system", "human"];
const WHAT: Record<"evidence" | "structure" | "definition" | "prioritize" | "all", string> = {
  // the feed has no page-4 scope yet, so the Prioritize tab reads the whole trail (scope=all)
  prioritize: "Every recorded change, including the gate checks, scores and every PM priority decision or proposal verdict.",
  definition: "When the agent defined, specified and coupled requirements, and every PM choice of a target or link.",
  evidence: "What entered the data, and when.",
  structure: "When the agent ran each stage, and every AI step.",
  all: "Every recorded change at both checkpoints, append-only. Nothing is ever edited or removed.",
};
const USAGE_WHAT = "Every model call the app made: which model each step uses, tokens and cost against the budget.";
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

export function AuditPanel() {
  const { pathname } = useLocation();
  const { cp } = useCheckpoint();
  // the corner is shared with Definition's requirements: opening one closes the other (topPanel.ts)
  const top = useTopPanel();
  const open = top === "audit";
  const setOpen = (v: boolean) => setTopPanel(v ? "audit" : null);
  const [all, setAll] = useState(false);
  const [usage, setUsage] = useState(false);         // the Usage tab: model calls and spend instead of the trail
  const [history, setHistory] = useState(false);
  const [hidden, setHidden] = useState<Set<Who>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const page = pathname.startsWith("/structure") ? "structure" : pathname.startsWith("/definition") ? "definition" : pathname.startsWith("/prioritize") ? "prioritize" : "evidence";
  const scope = all ? "all" : page;
  const withHistory = all && history;
  // the requirements pill exists on Definition only; leaving the page closes that panel
  useEffect(() => { if (page !== "definition") setTopPanel((t) => (t === "requirements" ? null : t)); }, [page]);
  useEffect(() => { if (page !== "prioritize") setTopPanel((t) => (t === "priorities" ? null : t)); }, [page]);

  const q = useInfiniteQuery({
    queryKey: ["audit-feed", scope, cp, withHistory],
    enabled: open && !usage,
    initialPageParam: "",
    queryFn: ({ pageParam }) => api.get<Page>(`/api/audit/feed?scope=${scope === "prioritize" ? "all" : scope}&cp=${cp}&limit=400${withHistory ? "&history=true" : ""}${pageParam ? `&before=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (last) => (last.more && last.items.length ? last.items[last.items.length - 1].ts : undefined),
    refetchInterval: open ? 5000 : false,
  });
  const rows = useMemo(() => q.data?.pages.flatMap((p) => p.items) ?? [], [q.data]);
  const counts = useMemo(() => {
    const c: Record<Who, number> = { ai: 0, system: 0, human: 0 };
    for (const r of rows) c[r.actor_type] = (c[r.actor_type] ?? 0) + 1;
    return c;
  }, [rows]);
  const items = useMemo(() => fold(rows.filter((r) => !hidden.has(r.actor_type))), [rows, hidden]);
  const oldest = rows.length ? Date.parse(rows[rows.length - 1].ts) : 0;

  useEffect(() => {
    if (!open) return;
    // Esc closes the trail first; captured and stopped so it doesn't also clear the scan's filters or selection
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopImmediatePropagation(); setOpen(false); } };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [open]);

  const toggleWho = (w: Who) => setHidden((h) => { const n = new Set(h); if (n.has(w)) n.delete(w); else n.add(w); return n; });
  const toggleFold = (id: string) => setExpanded((x) => { const n = new Set(x); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  let lastDay = "";
  return (
    <>
      <div className="tr-pills">
        {page === "definition" && (
          <button className="audit-btn" aria-expanded={top === "requirements"} aria-controls="requirements-panel" onClick={() => toggleTopPanel("requirements")}>
            <ListChecks size={14} aria-hidden /> Requirements
          </button>
        )}
        {page === "prioritize" && (
          <button className="audit-btn" aria-expanded={top === "priorities"} aria-controls="priorities-panel" onClick={() => toggleTopPanel("priorities")}>
            <ListOrdered size={14} aria-hidden /> Priorities
          </button>
        )}
        <button className="audit-btn" aria-expanded={open} aria-controls="audit-panel" onClick={() => toggleTopPanel("audit")}>
          <History size={14} aria-hidden /> Audit
        </button>
      </div>
      {open && (
        <aside id="audit-panel" className="audit" aria-label="Audit trail" data-wide={usage ? "" : undefined}>
          <button className="audit-close" onClick={() => setOpen(false)} aria-label="Close audit"><X size={16} /></button>
          <header className="audit-head">
            <span className="audit-layer"><History size={14} aria-hidden />Audit trail</span>
            <p className="audit-what">{usage ? USAGE_WHAT : WHAT[scope]}</p>
            <div className="audit-tabs" role="tablist">
              <button role="tab" aria-selected={!all && !usage} onClick={() => { setAll(false); setUsage(false); }}>{`${page === "structure" ? "Structure" : page === "definition" ? "Definition" : page === "prioritize" ? "Prioritize" : "Evidence"} · ${CP_LABEL[cp] ?? cp}`}</button>
              <button role="tab" aria-selected={all && !usage} onClick={() => { setAll(true); setUsage(false); }}>Everything</button>
              <button role="tab" aria-selected={usage} onClick={() => setUsage(true)}>Usage</button>
            </div>
            {!usage && <div className="audit-who-chips" aria-label="Who acted">
              {WHO_ORDER.filter((w) => counts[w]).map((w) => (
                <button key={w} className="audit-chip" aria-pressed={!hidden.has(w)} onClick={() => toggleWho(w)}>
                  <i className="audit-mark" data-who={w} aria-hidden />{WHO[w]}<span className="audit-chip-n">{counts[w].toLocaleString("en-US")}</span>
                </button>
              ))}
            </div>}
          </header>

          {usage ? <UsageView /> : <>
          <ol className="audit-list">
            {q.isPending && <li className="audit-empty label">Loading…</li>}
            {!q.isPending && items.length === 0 && <li className="audit-empty label">Nothing recorded here yet.</li>}
            {items.map((it) => {
              const head = it.day !== lastDay ? (lastDay = it.day) : null;
              const f = it.rows[0], n = it.rows.length, last = it.rows[n - 1];
              const milestone = f.kind === "run";
              const isOpen = expanded.has(f.id);
              // the last fold may continue into rows not loaded yet: say so rather than show a partial total as the total
              const partial = n > 1 && q.hasNextPage && Date.parse(last.ts) - oldest <= GAP;
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
                    {f.checkpoint && <span className="audit-cp">{CP_LABEL[f.checkpoint] ?? f.checkpoint}</span>}
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
          {all && !q.hasNextPage && !q.isPending && (
            <button className="audit-more" aria-pressed={history} onClick={() => setHistory((h) => !h)}>
              {history ? "Hide history before the checkpoint rebuild" : "Show history before the checkpoint rebuild"}
            </button>
          )}
          {q.hasNextPage && (
            <button className="audit-more" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
              {q.isFetchingNextPage ? "Loading…" : "Show older"}
            </button>
          )}
          </>}
        </aside>
      )}
    </>
  );
}
