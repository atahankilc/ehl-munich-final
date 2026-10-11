// Audit trail: every change by the PM, the AI and the system — append-only, filterable, exportable.
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, Lock, Search, X } from "lucide-react";
import { api, qs, getActor } from "@/lib/api";
import type { ActorType, AuditEvent, AuditPage } from "@/lib/types";
import { targetLabel } from "@/lib/labels";
import { fmtInt, fmtWhen } from "@/lib/format";
import { Empty, ErrorNote, Seg, Skeleton } from "@/components/ui";
import { ACTOR_TYPE, Who, actionLabel, clip, facetList } from "./common";

const STEP = 300;
type ActorFilter = "" | ActorType;

export function Audit() {
  const [actorType, setActorType] = useState<ActorFilter>("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [text, setText] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [limit, setLimit] = useState(STEP);
  const [hideViews, setHideViews] = useState(true);
  const term = useDeferredValue(text.trim());
  const filters = { actor_type: actorType, action, entity_type: entityType, q: term, from, to };
  useEffect(() => setLimit(STEP), [actorType, action, entityType, term, from, to]);

  const q = useQuery({
    queryKey: ["audit", filters, limit, hideViews],
    queryFn: () => api.get<AuditPage>(`/api/audit${qs({ ...filters, limit, hide_views: hideViews && !action ? true : undefined })}`),
    placeholderData: keepPreviousData,
  });
  // facets from the unfiltered trail, so the pickers don't shrink as you filter
  const base = useQuery({ queryKey: ["audit", "facets"], queryFn: () => api.get<AuditPage>(`/api/audit${qs({ limit: 1 })}`), staleTime: 60_000 });
  const facets = base.data?.facets ?? q.data?.facets;
  const actions = useMemo(() => facetList(facets?.actions).sort((a, b) => actionLabel(a.value).localeCompare(actionLabel(b.value))), [facets]);
  const entityTypes = useMemo(() => facetList(facets?.entity_types), [facets]);
  const actorCounts = useMemo(() => Object.fromEntries(facetList(facets?.actor_types).map((f) => [f.value, f.n])), [facets]);

  const items = q.data?.items ?? [];
  const shownBy = useMemo(() => {
    const c = { human: 0, ai: 0, system: 0 } as Record<ActorType, number>;
    for (const e of items) c[e.actor_type] = (c[e.actor_type] ?? 0) + 1;
    return c;
  }, [items]);
  const any = !!(actorType || action || entityType || text || from || to);
  const clear = () => {
    setActorType("");
    setAction("");
    setEntityType("");
    setText("");
    setFrom("");
    setTo("");
  };
  const minDay = facets?.min_ts?.slice(0, 10);
  const maxDay = facets?.max_ts?.slice(0, 10);

  return (
    <section className="panel audit" aria-labelledby="audit-h">
      <h2 id="audit-h" className="sr-only">Audit trail</h2>
      <div className="audit-filters">
        <Seg<ActorFilter>
          label="Who"
          value={actorType}
          onChange={setActorType}
          options={[
            { value: "", label: "Everyone" },
            { value: "human", label: "Product manager", count: actorCounts.human ?? undefined },
            { value: "ai", label: "AI", count: actorCounts.ai ?? undefined },
            { value: "system", label: "System", count: actorCounts.system ?? undefined },
          ]}
        />
        <label className="check t-small" title="Page views are access events — useful for compliance, noisy for reading the decisions">
          <input type="checkbox" checked={hideViews} onChange={(e) => setHideViews(e.target.checked)} /> Hide page views
        </label>
        <select className="select px-select" value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action">
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a.value} value={a.value}>
              {actionLabel(a.value)}
              {a.n != null ? ` · ${a.n}` : ""}
            </option>
          ))}
        </select>
        <select className="select px-select" value={entityType} onChange={(e) => setEntityType(e.target.value)} aria-label="Entity type">
          <option value="">All entities</option>
          {entityTypes.map((a) => (
            <option key={a.value} value={a.value}>
              {a.value.replace(/_/g, " ")}
              {a.n != null ? ` · ${a.n}` : ""}
            </option>
          ))}
        </select>
        <label className="px-search">
          <Search aria-hidden />
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search IDs, values, reasons…" aria-label="Search the audit trail" />
        </label>
        <span className="px-dates">
          <input type="date" className="input" value={from} min={minDay} max={to || maxDay} onChange={(e) => setFrom(e.target.value)} aria-label="From date" />
          <span className="faint">–</span>
          <input type="date" className="input" value={to} min={from || minDay} max={maxDay} onChange={(e) => setTo(e.target.value)} aria-label="To date" />
        </span>
        {any && (
          <button className="btn btn-ghost btn-sm" onClick={clear}>
            <X /> Clear
          </button>
        )}
      </div>

      <div className="audit-bar">
        <span className="t-small">
          {q.data ? (
            <>
              <b className="num">{fmtInt(q.data.total)}</b> <span className="muted">{any ? "matching events" : "events"}</span>
              {items.length < q.data.total && <span className="faint num"> · newest {fmtInt(items.length)} shown</span>}
              {items.length > 0 && (
                <span className="faint num">
                  {" "}
                  · {shownBy.human} by people · {shownBy.ai} by AI · {shownBy.system} by the system
                </span>
              )}
            </>
          ) : (
            <Skeleton h={12} w={260} />
          )}
        </span>
        <span className="audit-lock t-small">
          <Lock aria-hidden /> Append-only — the database rejects edits and deletions.
        </span>
        <a className="btn btn-sm" href={`/api/audit.csv${qs({ ...filters, as_actor: getActor() })}`} download="audit_trail.csv" title="Exports every matching event. The export itself is logged.">
          <Download /> Export CSV
        </a>
      </div>
      <hr className="rule" />

      {q.isLoading && (
        <div className="audit-list" aria-busy>
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="ev-row">
              <Skeleton h={24} w={24} r={7} />
              <div className="col" style={{ gap: 6 }}>
                <Skeleton h={12} w={`${70 - ((i * 13) % 30)}%`} />
                <Skeleton h={10} w={`${45 - ((i * 7) % 20)}%`} />
              </div>
              <Skeleton h={10} w={70} />
            </div>
          ))}
        </div>
      )}
      {q.isError && (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.data && items.length === 0 && (
        <Empty title={any ? "No events match" : "The audit trail is empty"}>
          {any ? "Loosen a filter or clear them all." : "Events appear as soon as a wave is opened or a decision is recorded."}
        </Empty>
      )}
      {items.length > 0 && (
        <ol className={`audit-list${q.isPlaceholderData ? " stale" : ""}`}>
          {items.map((e) => (
            <EventRow key={e.id} e={e} />
          ))}
        </ol>
      )}
      {q.data && items.length < q.data.total && (
        <div className="px-more">
          <button className="btn btn-ghost btn-sm" onClick={() => setLimit((l) => l + STEP)} disabled={q.isFetching}>
            {q.isFetching ? "Loading…" : `Show ${fmtInt(Math.min(STEP, q.data.total - items.length))} more`}
          </button>
        </div>
      )}
    </section>
  );
}

function EntityRef({ e }: { e: AuditEvent }) {
  const m = /^(REQ-\d+)(?::(.+))?$/.exec(e.entity_id ?? "");
  if (m)
    return (
      <>
        <Link to={`/requirements/${m[1]}`} className="ev-ent num" onClick={(x) => x.stopPropagation()}>
          {m[1]}
        </Link>
        {m[2] && <span className="muted"> · {targetLabel(m[2])}</span>}
      </>
    );
  if (!e.entity_id) return null;
  const type = (e.entity_type ?? "").replace(/_/g, " ");
  return (
    <span className="muted">
      {type ? `${type} ` : ""}
      <span className="num">{clip(e.entity_id, 40)}</span>
    </span>
  );
}

function Value({ v, strong }: { v: string | null; strong?: boolean }) {
  if (v == null || v === "") return <span className="faint">–</span>;
  const long = v.length > 64;
  return (
    <span className={strong ? "ev-new" : "ev-old"} title={long ? v : undefined}>
      {clip(v, 64)}
    </span>
  );
}

function EventRow({ e }: { e: AuditEvent }) {
  const who = e.actor_type === "human" ? e.actor_id || "Product manager" : e.actor_type === "ai" ? "AI" : "System";
  const hasChange = e.old_value != null || e.new_value != null;
  const meta = [e.model && `model ${e.model}`, e.prompt_ref && `prompt ${e.prompt_ref}`, e.run_id != null && `run ${e.run_id}`].filter(Boolean) as string[];
  return (
    <li className="ev-row">
      <Who type={e.actor_type} name={e.actor_id} size={24} />
      <div className="ev-main">
        <div className="ev-line">
          <b className="ev-who" title={ACTOR_TYPE[e.actor_type]}>{who}</b> <span className="ev-act">{actionLabel(e.action)}</span> <EntityRef e={e} />
          {e.field && <span className="ev-field"> · {e.field.replace(/_/g, " ")}</span>}
        </div>
        {hasChange && (
          <div className="ev-change">
            <Value v={e.old_value} />
            <span className="faint" aria-label="changed to">→</span>
            <Value v={e.new_value} strong />
          </div>
        )}
        {e.rationale && <p className="ev-why">{e.rationale}</p>}
        {meta.length > 0 && <div className="ev-meta">{meta.join(" · ")}</div>}
      </div>
      <span className="ev-when num">
        <time dateTime={e.ts}>{fmtWhen(e.ts)}</time>
        <span className="ev-id">#{e.id}</span>
      </span>
    </li>
  );
}
