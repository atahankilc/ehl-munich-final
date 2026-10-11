// Findings and Gaps share one table. Findings: every finding, filterable. Gaps: the uncovered pain/wish themes as a
// work queue, loudest first. Filters live in the URL so a view can be linked and survives a reload.
import { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { FindingRow, FindingsPage } from "@/lib/types";
import { useAppState, useMeta } from "@/lib/hooks";
import { fmtInt, plural } from "@/lib/format";
import { Empty, ErrorNote, Kbd, Skeleton } from "@/components/ui";
import { KIND, KindChip, MarketBars, isTyping, scopeLabel } from "./shared";

const PAGE = 50;
type Setter = (patch: Record<string, string | null>, replace?: boolean) => void;

export function FindingsTab({
  mode,
  params,
  setParam,
  categories,
  onOpen,
  openId,
}: {
  mode: "findings" | "gaps";
  params: URLSearchParams;
  setParam: Setter;
  categories: string[];
  onOpen: (id: number) => void;
  openId: number | null;
}) {
  const gaps = mode === "gaps";
  const { data: meta } = useMeta();
  const { data: state } = useAppState();
  const vehicle = params.get("car") ?? "";
  const market = params.get("market") ?? "";
  const kind = params.get("kind") ?? "";
  const category = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const uncovered = !gaps && params.get("uncovered") === "1";
  const visibleOnly = params.get("all") !== "1";
  const [shown, setShown] = useState(PAGE);
  const [text, setText] = useState(q);
  const searchRef = useRef<HTMLInputElement>(null);

  // debounce the search box into the URL
  useEffect(() => {
    if (text === q) return;
    const t = setTimeout(() => setParam({ q: text.trim() || null }), 220);
    return () => clearTimeout(t);
  }, [text, q, setParam]);
  useEffect(() => setShown(PAGE), [vehicle, market, kind, category, q, uncovered, visibleOnly]);

  // "/" focuses the search box
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key !== "/" || isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return;
      e.preventDefault();
      searchRef.current?.focus();
      searchRef.current?.select();
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  // Gaps: the API has no polarity filter, so pull every uncovered finding once and page client-side.
  const filters = { vehicle, market, kind, category, q, visible_only: visibleOnly };
  const query = useQuery({
    queryKey: ["findings", mode, filters, gaps ? "all" : uncovered, gaps ? 0 : shown],
    queryFn: () =>
      api.get<FindingsPage>(
        `/api/findings${qs({ ...filters, uncovered: gaps || uncovered ? true : undefined, limit: gaps ? 2000 : shown, offset: 0 })}`,
      ),
    placeholderData: keepPreviousData,
  });

  const rows: FindingRow[] = useMemo(() => {
    const items = query.data?.items ?? [];
    return gaps ? items.filter((f) => f.polarity === "pain_or_want") : items;
  }, [query.data, gaps]);
  const total = gaps ? rows.length : (query.data?.total ?? 0);
  const visibleRows = gaps ? rows.slice(0, shown) : rows;
  const gapComments = useMemo(() => (gaps ? rows.reduce((s, f) => s + f.verbatims, 0) : 0), [rows, gaps]);

  const anyFilter = !!(vehicle || market || kind || category || q || uncovered || !visibleOnly);
  const clear = () => {
    setText("");
    setParam({ car: null, market: null, kind: null, category: null, q: null, uncovered: null, all: null });
  };

  return (
    <section className="ev-section" aria-label={gaps ? "Uncovered customer themes" : "Findings"}>
      <div className="ev-filters" role="search">
        <label className="ev-search">
          <Search aria-hidden />
          <input
            ref={searchRef}
            className="input"
            type="search"
            placeholder={gaps ? "Search uncovered themes" : "Search findings"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                if (text) setText("");
                else (e.target as HTMLInputElement).blur();
              }
            }}
            aria-label="Search title and summary"
          />
          {!text && <Kbd>/</Kbd>}
        </label>
        <select className="select ev-select" value={vehicle} onChange={(e) => setParam({ car: e.target.value || null })} aria-label="Car">
          <option value="">All cars</option>
          {meta && Object.entries(meta.vehicles).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          <option value="line">Line-wide only</option>
        </select>
        <select className="select ev-select" value={market} onChange={(e) => setParam({ market: e.target.value || null })} aria-label="Market">
          <option value="">All markets</option>
          {meta && Object.entries(meta.markets).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select>
        <select className="select ev-select" value={kind} onChange={(e) => setParam({ kind: e.target.value || null })} aria-label="Kind of evidence">
          <option value="">All kinds</option>
          {Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v.long}</option>)}
        </select>
        <select className="select ev-select ev-select-wide" value={category} onChange={(e) => setParam({ category: e.target.value || null })} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="ev-toggles">
          {!gaps && (
            <button type="button" className="ev-toggle" aria-pressed={uncovered} onClick={() => setParam({ uncovered: uncovered ? null : "1" })}>
              Only not covered
            </button>
          )}
          <button
            type="button"
            className="ev-toggle"
            aria-pressed={visibleOnly}
            onClick={() => setParam({ all: visibleOnly ? "1" : null })}
            title="Only findings the evidence waves have brought in so far"
          >
            Up to wave {state?.current_wave ?? "–"}
          </button>
        </div>
      </div>

      <div className="ev-summary t-small" aria-live="polite">
        {query.isLoading ? (
          <Skeleton w={320} h={12} />
        ) : query.data ? (
          gaps ? (
            <>
              <span><b className="num">{fmtInt(total)}</b> uncovered themes</span>
              <span className="dot" aria-hidden />
              <span><b className="num">{fmtInt(gapComments)}</b> customer comments behind them</span>
              <span className="dot" aria-hidden />
              <span className="faint">Loudest first · comment counts as of wave {query.data.metrics_wave}</span>
            </>
          ) : (
            <>
              <span><b className="num">{fmtInt(total)}</b> {total === 1 ? "finding" : "findings"}</span>
              <span className="dot" aria-hidden />
              <span>
                <b className="num">{fmtInt(query.data.used)}</b> cited by requirements
              </span>
              <span className="dot" aria-hidden />
              <button className="ev-linkish" onClick={() => setParam({ uncovered: uncovered ? null : "1" })}>
                <span className="telltale amber">{fmtInt(query.data.uncovered)} not covered</span>
              </button>
              <span className="dot" aria-hidden />
              <span className="faint">Comment counts as of wave {query.data.metrics_wave}</span>
            </>
          )
        ) : null}
        {anyFilter && (
          <button className="btn btn-ghost btn-sm ev-clear" onClick={clear}>
            <X /> Clear filters
          </button>
        )}
      </div>

      <div className={`panel ev-tablewrap${query.isFetching && !query.isLoading ? " ev-refetch" : ""}`}>
        {query.isError ? (
          <div className="ev-pad">
            <ErrorNote error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : (
          <table className="table ev-table">
            <colgroup>
              <col />
              <col className="c-kind" />
              <col className="c-scope" />
              <col className="c-comments" />
              <col className="c-sources" />
              <col className="c-used" />
            </colgroup>
            <thead>
              <tr>
                <th>{gaps ? "Customer theme" : "Finding"}</th>
                <th className="hide-sm">Kind</th>
                <th className="hide-sm">Car · market</th>
                <th className="r">Comments</th>
                <th className="r hide-sm">Sources</th>
                <th className="hide-sm">{gaps ? "First seen" : "Used by"}</th>
              </tr>
            </thead>
            <tbody>
              {query.isLoading
                ? Array.from({ length: 9 }).map((_, i) => <SkeletonRow key={i} i={i} />)
                : visibleRows.map((f) => <Row key={f.id} f={f} gaps={gaps} active={openId === f.id} onOpen={onOpen} />)}
            </tbody>
          </table>
        )}
        {!query.isLoading && !query.isError && visibleRows.length === 0 && (
          <div className="ev-pad">
            {gaps && !anyFilter ? (
              <Empty title="No uncovered customer themes">Every pain point and wish customers raised is cited by at least one requirement.</Empty>
            ) : (
              <Empty title="Nothing matches these filters">
                Loosen a filter or{" "}
                <button className="ev-linkish ev-link" onClick={clear}>
                  clear them all
                </button>
                .
              </Empty>
            )}
          </div>
        )}
      </div>

      {!query.isLoading && visibleRows.length < total && (
        <div className="ev-more">
          <button className="btn" onClick={() => setShown((n) => n + PAGE)} disabled={query.isFetching}>
            {query.isFetching ? "Loading…" : `Show ${Math.min(PAGE, total - visibleRows.length)} more`}
          </button>
          <span className="faint t-small num">
            {fmtInt(visibleRows.length)} of {plural(total, gaps ? "theme" : "finding")}
          </span>
        </div>
      )}
    </section>
  );
}

function Row({ f, gaps, active, onOpen }: { f: FindingRow; gaps: boolean; active: boolean; onOpen: (id: number) => void }) {
  return (
    <tr
      className={`clickable${active ? " on" : ""}`}
      tabIndex={0}
      onClick={() => onOpen(f.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(f.id);
        }
      }}
      aria-label={`Open finding: ${f.title}`}
    >
      <td className="ev-titlecell">
        <div className="ev-title">{f.title}</div>
        {f.summary && <div className="ev-sum">{f.summary}</div>}
        <div className="ev-mobmeta show-sm">
          <KindChip kind={f.source_kind} />
          <span>{scopeLabel(f.vehicle, f.market)}</span>
          {!gaps && f.n_requirements === 0 && <span className="telltale amber">Not covered</span>}
        </div>
      </td>
      <td className="hide-sm">
        <KindChip kind={f.source_kind} />
      </td>
      <td className="hide-sm ev-scope">{scopeLabel(f.vehicle, f.market)}</td>
      <td className="r">
        {f.source_kind === "verbatim" ? (
          <span className="ev-comments">
            <span className="num">{fmtInt(f.verbatims)}</span>
            <MarketBars by={f.by_market} />
          </span>
        ) : (
          <span className="faint">–</span>
        )}
      </td>
      <td className="r hide-sm num ev-dim">{fmtInt(f.n_sources)}</td>
      <td className="hide-sm">
        {gaps ? (
          <span className="ev-used num">Wave {f.first_wave ?? 1}</span>
        ) : f.n_requirements > 0 ? (
          <span className="ev-used num">{plural(f.n_requirements, "requirement")}</span>
        ) : (
          <span className="telltale amber">Not covered</span>
        )}
      </td>
    </tr>
  );
}

function SkeletonRow({ i }: { i: number }) {
  return (
    <tr aria-hidden>
      <td>
        <Skeleton w={`${70 - ((i * 13) % 30)}%`} h={13} />
        <div style={{ height: 7 }} />
        <Skeleton w={`${88 - ((i * 7) % 24)}%`} h={10} />
      </td>
      <td className="hide-sm"><Skeleton w={78} h={18} /></td>
      <td className="hide-sm"><Skeleton w={110} h={12} /></td>
      <td className="r"><Skeleton w={70} h={12} /></td>
      <td className="r hide-sm"><Skeleton w={24} h={12} /></td>
      <td className="hide-sm"><Skeleton w={96} h={12} /></td>
    </tr>
  );
}
