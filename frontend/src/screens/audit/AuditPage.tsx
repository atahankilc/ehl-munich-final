// The Audit page (D-055): the whole append-only trail, every area together, one checkpoint at a time — JAN 26 and
// JUL 26 follow the app's checkpoint (the timeline bottom-right steps it too); "No checkpoint" holds what belongs to
// neither (settings, exports). Filter by area and by who acted; history from before the checkpoint rebuild (the old
// wave-based app) is kept in the table and shown on request. A full-height sheet over the dimmed scene, like Document.
import { useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import { CP_LABEL, TrailList, WhoChips, countBy, type Area, type Page, type Who } from "@/components/auditTrail";
import "@/components/sheet.css";
import "@/components/audit.css";

const AREAS: { key: Area; label: string }[] = [
  { key: "evidence", label: "Evidence" }, { key: "structure", label: "Structure" }, { key: "definition", label: "Definition" },
  { key: "prioritize", label: "Prioritize" }, { key: "settings", label: "Settings" }, { key: "other", label: "Other" },
];

export function AuditPage() {
  const { cp, setCp, checkpoints } = useCheckpoint();
  const [none, setNone] = useState(false);           // "No checkpoint" instead of the app's checkpoint
  const [area, setArea] = useState<Area | null>(null);
  const [hidden, setHidden] = useState<Set<Who>>(new Set());
  const [history, setHistory] = useState(false);
  const view = none ? "none" : cp;

  const q = useInfiniteQuery({
    queryKey: ["audit-page", view, history],
    initialPageParam: "",
    queryFn: ({ pageParam }) => api.get<Page>(`/api/audit/feed?scope=all&cp=${view}&only_cp=true&limit=500${history ? "&history=true" : ""}${pageParam ? `&before=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (last) => (last.more && last.items.length ? last.items[last.items.length - 1].ts : undefined),
    refetchInterval: 10_000,
  });
  const rows = useMemo(() => q.data?.pages.flatMap((p) => p.items) ?? [], [q.data]);
  const byArea = useMemo(() => countBy(rows, (r) => r.area), [rows]);
  const inArea = useMemo(() => (area ? rows.filter((r) => r.area === area) : rows), [rows, area]);
  const shown = useMemo(() => inArea.filter((r) => !hidden.has(r.actor_type)), [inArea, hidden]);
  const toggleWho = (w: Who) => setHidden((h) => { const n = new Set(h); if (n.has(w)) n.delete(w); else n.add(w); return n; });

  return (
    <section className="pagesheet auditpage" aria-label="Audit trail">
      <header className="ps-top">
        <div className="ps-title">
          <h1>Audit trail</h1>
          <p className="ps-lede">Every recorded change, append-only: nothing is ever edited or removed. One checkpoint at a time; what an AI agent did,
            what the system loaded and what the PM decided, with the reason.</p>
        </div>
        <div className="ps-row">
          <div className="ps-seg" role="group" aria-label="Checkpoint">
            {(checkpoints?.map((c) => c.id) ?? ["cp1", "cp2"]).map((id) => (
              <button key={id} aria-pressed={!none && cp === id} onClick={() => { setNone(false); setCp(id); }}>{CP_LABEL[id] ?? id}</button>
            ))}
            <button aria-pressed={none} onClick={() => setNone(true)} title="Settings changes, exports and other events tied to no checkpoint">No checkpoint</button>
          </div>
          <div className="ps-chips" role="group" aria-label="Area">
            <button className="ps-chip" aria-pressed={area === null} onClick={() => setArea(null)}>All <span>{rows.length.toLocaleString("en-US")}{q.hasNextPage ? "+" : ""}</span></button>
            {AREAS.filter((a) => byArea[a.key]).map((a) => (
              <button key={a.key} className="ps-chip" aria-pressed={area === a.key} onClick={() => setArea(area === a.key ? null : a.key)}>
                {a.label} <span>{(byArea[a.key] ?? 0).toLocaleString("en-US")}</span>
              </button>
            ))}
          </div>
        </div>
        <WhoChips rows={inArea} hidden={hidden} onToggle={toggleWho} />
      </header>

      <TrailList rows={shown} loading={q.isPending} more={!!q.hasNextPage} showCheckpoint={false} />
      {q.hasNextPage && (
        <button className="audit-more" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          {q.isFetchingNextPage ? "Loading…" : "Show older"}
        </button>
      )}
      {!q.hasNextPage && !q.isPending && (
        <button className="audit-more" aria-pressed={history} onClick={() => setHistory((h) => !h)}>
          {history ? "Hide history before the checkpoint rebuild" : "Show history before the checkpoint rebuild"}
        </button>
      )}
    </section>
  );
}
