// Quality hand-over (D-038): verbatim themes where at least half of the signals are defects. They go to the quality
// teams, not into requirements — unless a requirement already cites them. Expand a row for verified defect quotes.
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Download, Quote as QuoteIcon } from "lucide-react";
import { api, getActor, qs } from "@/lib/api";
import type { QualityItem, QualityPayload } from "@/lib/types";
import { car, mkt } from "@/lib/labels";
import { fmtInt } from "@/lib/format";
import { useMeta } from "@/lib/hooks";
import { Empty, ErrorNote, Skeleton, Stat } from "@/components/ui";

type Setter = (patch: Record<string, string | null>, replace?: boolean) => void;

export function QualityTab({ params, setParam, categories }: { params: URLSearchParams; setParam: Setter; categories: string[] }) {
  const { data: meta } = useMeta();
  const vehicle = params.get("car") ?? "";
  const category = params.get("category") ?? "";
  const q = useQuery({
    queryKey: ["quality", vehicle, category],
    queryFn: () => api.get<QualityPayload>(`/api/quality${qs({ vehicle, category })}`),
    placeholderData: (prev) => prev,
  });
  const [open, setOpen] = useState<Set<number>>(new Set());
  const toggle = (id: number) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const d = q.data;
  const share = d?.defect_share_min ?? 0.5;

  return (
    <section className="ev-section" aria-label="Quality hand-over">
      <div className="qh-stats" aria-busy={q.isLoading}>
        {q.isLoading || !d ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="stat">
              <Skeleton w={90} h={11} />
              <div style={{ height: 8 }} />
              <Skeleton w={56} h={22} />
            </div>
          ))
        ) : (
          <>
            <Stat label="Issues for quality" value={fmtInt(d.n_issues)} sub={`themes with ≥ ${Math.round(share * 100)}% defect signals`} />
            <Stat label="Signals" value={fmtInt(d.n_signals)} sub="customer comments read as signals" />
            <Stat label="High severity" value={fmtInt(d.n_high)} sub={d.n_signals ? `${Math.round((d.n_high / d.n_signals) * 100)}% of signals` : undefined} />
            <Stat label="Cited by a requirement" value={fmtInt(d.n_cited)} sub="also feed a product decision" />
          </>
        )}
      </div>

      <div className="ev-filters">
        <select className="select ev-select" value={vehicle} onChange={(e) => setParam({ car: e.target.value || null })} aria-label="Car">
          <option value="">All cars</option>
          {meta && Object.entries(meta.vehicles).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select>
        <select className="select ev-select ev-select-wide" value={category} onChange={(e) => setParam({ category: e.target.value || null })} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="grow" />
        <a className="btn" href={`/api/quality.csv${qs({ vehicle, category, as_actor: getActor() })}`} download="quality_handover.csv" title="Download this list for the quality teams (logged as an export)">
          <Download /> Download CSV
        </a>
      </div>

      <div className={`panel ev-tablewrap${q.isFetching && !q.isLoading ? " ev-refetch" : ""}`}>
        {q.isError ? (
          <div className="ev-pad">
            <ErrorNote error={q.error} onRetry={() => q.refetch()} />
          </div>
        ) : (
          <table className="table ev-table qh-table">
            <colgroup>
              <col className="c-chev" />
              <col />
              <col className="c-car" />
              <col className="c-cat" />
              <col className="c-n" />
              <col className="c-share" />
              <col className="c-n" />
              <col className="c-mk" />
              <col className="c-cited" />
            </colgroup>
            <thead>
              <tr>
                <th aria-label="Expand" />
                <th>Theme</th>
                <th className="hide-sm">Car</th>
                <th className="hide-md">Category</th>
                <th className="r">Signals</th>
                <th className="r">Defects</th>
                <th className="r hide-sm">High</th>
                <th className="hide-md">Markets</th>
                <th className="hide-sm">Cited by</th>
              </tr>
            </thead>
            <tbody>
              {q.isLoading
                ? Array.from({ length: 7 }).map((_, i) => (
                    <tr key={i} aria-hidden>
                      <td />
                      <td><Skeleton w={`${72 - ((i * 11) % 30)}%`} h={13} /></td>
                      <td className="hide-sm"><Skeleton w={70} h={12} /></td>
                      <td className="hide-md"><Skeleton w={110} h={12} /></td>
                      <td className="r"><Skeleton w={24} h={12} /></td>
                      <td className="r"><Skeleton w={60} h={12} /></td>
                      <td className="r hide-sm"><Skeleton w={20} h={12} /></td>
                      <td className="hide-md"><Skeleton w={100} h={12} /></td>
                      <td className="hide-sm"><Skeleton w={70} h={12} /></td>
                    </tr>
                  ))
                : d?.items.map((it) => <QRow key={it.finding_id} it={it} open={open.has(it.finding_id)} onToggle={() => toggle(it.finding_id)} onOpenFinding={() => setParam({ f: String(it.finding_id) }, false)} />)}
            </tbody>
          </table>
        )}
        {d && !q.isError && d.items.length === 0 && (
          <div className="ev-pad">
            <Empty title={vehicle || category ? "No defect-led themes for this filter" : "Nothing to hand over"}>
              {vehicle || category ? "Try another car or category." : "No customer theme is mostly defects in the current evidence."}
            </Empty>
          </div>
        )}
      </div>
    </section>
  );
}

function QRow({ it, open, onToggle, onOpenFinding }: { it: QualityItem; open: boolean; onToggle: () => void; onOpenFinding: () => void }) {
  const markets = Object.entries(it.markets).filter(([, n]) => (n ?? 0) > 0);
  const quotes = it.quotes ?? [];
  return (
    <Fragment>
      <tr
        className={`clickable${open ? " on" : ""}`}
        tabIndex={0}
        aria-expanded={open}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <td className="qh-chev">
          <ChevronRight className={open ? "rot" : ""} aria-hidden />
        </td>
        <td className="ev-titlecell">
          <div className="ev-title">{it.title}</div>
          {it.summary && <div className="ev-sum">{it.summary}</div>}
        </td>
        <td className="hide-sm ev-scope">{it.car ?? car(it.vehicle)}</td>
        <td className="hide-md ev-scope">{it.category ?? "–"}</td>
        <td className="r num">{fmtInt(it.n_signals)}</td>
        <td className="r">
          <span className="qh-share">
            <span className="qh-share-track" aria-hidden>
              <span style={{ width: `${Math.round(it.defect_share * 100)}%` }} />
            </span>
            <span className="num">{Math.round(it.defect_share * 100)}%</span>
          </span>
        </td>
        <td className="r hide-sm num">{it.n_high ? <span className="qh-high">{it.n_high}</span> : <span className="faint">0</span>}</td>
        <td className="hide-md qh-mk">
          {markets.length
            ? markets.map(([m, n], i) => (
                <span key={m}>
                  {i > 0 && <span className="faint"> · </span>}
                  {mkt(m)} <span className="num">{n}</span>
                </span>
              ))
            : <span className="faint">–</span>}
        </td>
        <td className="hide-sm" onClick={(e) => e.stopPropagation()}>
          {it.cited_by.length ? (
            <span className="qh-cited">
              {it.cited_by.map((r) => (
                <Link key={r} to={`/requirements/${r}`} className="id qh-req">
                  {r}
                </Link>
              ))}
            </span>
          ) : (
            <span className="faint">–</span>
          )}
        </td>
      </tr>
      {open && (
        <tr className="qh-x">
          <td />
          <td colSpan={8}>
            {quotes.length ? (
              <div className="qh-quotes">
                {quotes.map((q, i) => (
                  <figure key={`${q.external_id}${i}`} className="quote">
                    <QuoteIcon className="quote-mark" aria-hidden />
                    <blockquote>{q.quote}</blockquote>
                    <figcaption>
                      {mkt(q.market)} · <span className="id">{q.external_id}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            ) : (
              <p className="muted t-small">No verified defect quote for this theme — open the finding in Findings to read the comments.</p>
            )}
            <div className="qh-x-foot t-small">
              <button className="ev-linkish ev-link" onClick={onOpenFinding}>Open the finding with all signals</button>
              {it.cited_by.length > 0 && (
                <span className="faint show-sm-inline"> · cited by {it.cited_by.join(", ")}</span>
              )}
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}
