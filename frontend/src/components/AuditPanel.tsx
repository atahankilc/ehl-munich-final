// The top-right pill row and the Audit panel. The panel is the quick look: what the current page is about, at the
// selected checkpoint only (on Evidence, what entered the data and when; on Structure, when the agent ran each stage
// and every AI step). The whole trail lives on the Audit page and the model calls, spend and agent settings on the
// AI agents page (D-055); the pills lead there. Styled like the rest of the HUD: 32px pills like the filter chips, a
// glass sheet like the inspector.
import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, NavLink, useLocation, useSearchParams } from "react-router-dom";
import { ArrowRight, Bot, History, ListChecks, ListOrdered, X } from "lucide-react";
import { api } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import { setTopPanel, toggleTopPanel, useTopPanel } from "./topPanel";
import { CP_LABEL, TrailList, WhoChips, type Page, type Who } from "./auditTrail";
import "./audit.css";

type Scope = "evidence" | "structure" | "definition" | "prioritize";
const WHAT: Record<Scope, string> = {
  // the feed has no page-4 scope, so the Prioritize tab reads the whole trail (scope=all) of this checkpoint
  prioritize: "Every recorded change at this checkpoint, including the gate checks, scores and every PM priority decision or proposal verdict.",
  definition: "When the agent defined, specified and coupled requirements, and every PM choice of a target or link.",
  evidence: "What entered the data, and when.",
  structure: "When the agent ran each stage, and every AI step.",
};
const NAME: Record<Scope, string> = { evidence: "Evidence", structure: "Structure", definition: "Definition", prioritize: "Prioritize" };

export function AuditPanel() {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const { cp } = useCheckpoint();
  // the corner is shared with Definition's requirements: opening one closes the other (topPanel.ts)
  const top = useTopPanel();
  const open = top === "audit";
  const setOpen = (v: boolean) => setTopPanel(v ? "audit" : null);
  const [hidden, setHidden] = useState<Set<Who>>(new Set());
  const onSheet = pathname.startsWith("/agents") || pathname.startsWith("/audit");
  const page: Scope = pathname.startsWith("/structure") ? "structure" : pathname.startsWith("/definition") ? "definition" : pathname.startsWith("/prioritize") ? "prioritize" : "evidence";
  const q0 = params.toString() ? `?${params}` : "";
  // the requirements pill exists on Definition only; leaving the page closes that panel
  useEffect(() => { if (pathname !== "/definition") setTopPanel((t) => (t === "requirements" ? null : t)); }, [pathname]);
  useEffect(() => { if (pathname !== "/prioritize") setTopPanel((t) => (t === "priorities" ? null : t)); }, [pathname]);
  useEffect(() => { if (onSheet) setTopPanel((t) => (t === "audit" ? null : t)); }, [onSheet]);

  const q = useInfiniteQuery({
    queryKey: ["audit-feed", page, cp],
    enabled: open,
    initialPageParam: "",
    queryFn: ({ pageParam }) => api.get<Page>(`/api/audit/feed?scope=${page === "prioritize" ? "all" : page}&cp=${cp}&only_cp=true&limit=400${pageParam ? `&before=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (last) => (last.more && last.items.length ? last.items[last.items.length - 1].ts : undefined),
    refetchInterval: open ? 5000 : false,
  });
  const rows = useMemo(() => q.data?.pages.flatMap((p) => p.items) ?? [], [q.data]);
  const shown = useMemo(() => rows.filter((r) => !hidden.has(r.actor_type)), [rows, hidden]);

  useEffect(() => {
    if (!open) return;
    // Esc closes the trail first; captured and stopped so it doesn't also clear the scan's filters or selection
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopImmediatePropagation(); setOpen(false); } };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [open]);

  const toggleWho = (w: Who) => setHidden((h) => { const n = new Set(h); if (n.has(w)) n.delete(w); else n.add(w); return n; });

  return (
    <>
      <div className="tr-pills">
        {pathname === "/definition" && (
          <button className="audit-btn" aria-expanded={top === "requirements"} aria-controls="requirements-panel" onClick={() => toggleTopPanel("requirements")}>
            <ListChecks size={14} aria-hidden /> Requirements
          </button>
        )}
        {pathname === "/prioritize" && (
          <button className="audit-btn" aria-expanded={top === "priorities"} aria-controls="priorities-panel" onClick={() => toggleTopPanel("priorities")}>
            <ListOrdered size={14} aria-hidden /> Priorities
          </button>
        )}
        <NavLink className="audit-btn" to={`/agents${q0}`}><Bot size={14} aria-hidden /> Agents</NavLink>
        {onSheet
          ? <NavLink className="audit-btn" to={`/audit${q0}`}><History size={14} aria-hidden /> Audit</NavLink>
          : <button className="audit-btn" aria-expanded={open} aria-controls="audit-panel" onClick={() => toggleTopPanel("audit")}>
              <History size={14} aria-hidden /> Audit
            </button>}
      </div>
      {open && !onSheet && (
        <aside id="audit-panel" className="audit" aria-label="Audit trail">
          <button className="audit-close" onClick={() => setOpen(false)} aria-label="Close audit"><X size={16} /></button>
          <header className="audit-head">
            <span className="audit-layer"><History size={14} aria-hidden />{NAME[page]} · {CP_LABEL[cp] ?? cp}</span>
            <p className="audit-what">{WHAT[page]}</p>
            <Link className="audit-full" to={`/audit${q0}`} onClick={() => setOpen(false)}>Open the full audit trail <ArrowRight size={13} aria-hidden /></Link>
            <WhoChips rows={rows} hidden={hidden} onToggle={toggleWho} />
          </header>
          <TrailList rows={shown} loading={q.isPending} more={!!q.hasNextPage} showCheckpoint={false} />
          {q.hasNextPage && (
            <button className="audit-more" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
              {q.isFetchingNextPage ? "Loading…" : "Show older"}
            </button>
          )}
        </aside>
      )}
    </>
  );
}
