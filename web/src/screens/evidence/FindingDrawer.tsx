// One finding, traced end to end: the customer comments it was built from, the signal the AI read out of each
// comment (type, severity, need, verified quote), the sources behind it and the requirements that cite it.
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, ExternalLink, Quote as QuoteIcon } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { FindingDetail, FindingMarketMetrics, FindingSignal, FindingSource } from "@/lib/types";
import { MARKET, mkt } from "@/lib/labels";
import { fmtInt, fmtPct, fmtSimDate, plural } from "@/lib/format";
import { Drawer } from "@/components/Drawer";
import { Empty, ErrorNote, Skeleton, SkeletonBlock, Stat, StatusLight } from "@/components/ui";
import { FEEDBACK_TONE, FEEDBACK_TYPE, KIND, KindChip, MARKETS, POLARITY, SEVERITY_TONE, TIER, humanize, scopeLabel } from "./shared";

export function FindingDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["finding", id],
    queryFn: () => api.get<FindingDetail>(`/api/findings/${id}`),
    enabled: id != null,
  });
  const f = detail.data;
  return (
    <Drawer
      open={id != null}
      onClose={onClose}
      width={720}
      title={f ? f.title : detail.isError ? "Finding" : <Skeleton w={360} h={20} />}
      sub={
        f ? (
          <span className="row wrap" style={{ gap: 8 }}>
            <KindChip kind={f.source_kind} />
            <span>{scopeLabel(f.vehicle, f.market)}</span>
            <span className="faint">·</span>
            <span>Since wave {f.first_wave ?? 1}</span>
            <span className="faint">·</span>
            <span className="id">F{f.id}</span>
          </span>
        ) : undefined
      }
    >
      {detail.isLoading && <SkeletonBlock lines={9} />}
      {detail.isError && <ErrorNote error={detail.error} onRetry={() => detail.refetch()} />}
      {f && <Body f={f} />}
    </Drawer>
  );
}

function Body({ f }: { f: FindingDetail }) {
  const supports = f.used_by.filter((u) => u.relation !== "contradicts").length;
  return (
    <div className="fd">
      <div className="row wrap" style={{ gap: 6 }}>
        {f.category && <span className="chip outline">{f.category}</span>}
        <span className="chip">{humanize(f.type)}</span>
        {f.polarity && <span className="chip">{POLARITY[f.polarity] ?? humanize(f.polarity)}</span>}
      </div>
      {f.summary && <p className="fd-summary">{f.summary}</p>}

      <Chain f={f} supports={supports} />

      {f.source_kind === "verbatim" && f.markets && Object.keys(f.markets).length > 0 && (
        <Section title="Per market" note={`Comment counts as of wave ${f.metrics_wave}`}>
          <MarketMetrics markets={f.markets} />
        </Section>
      )}
      {f.source_kind === "study" && <StudyMetrics f={f} />}
      {f.source_kind === "web" && <WebMetrics f={f} />}

      {f.n_signals > 0 && <Signals f={f} />}

      <Sources f={f} />

      <Section title="Used by" note={f.used_by.length ? plural(f.used_by.length, "requirement") : undefined}>
        {f.used_by.length ? (
          <ul className="fd-used">
            {f.used_by.map((u) => (
              <li key={`${u.req_id}${u.relation}`}>
                <Link to={`/requirements/${u.req_id}`} className="fd-used-link">
                  <span className="id">{u.req_id}</span>
                  <span className="fd-used-title">
                    <span>{u.title}</span>
                    {u.relation === "contradicts" && <span className="chip warn">Contradicts</span>}
                  </span>
                  <StatusLight s={u.status} />
                  <ArrowRight className="fd-used-arrow" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="fd-uncovered">
            <span className="telltale amber">Not covered</span>
            <span className="muted t-small">No requirement cites this finding yet — a candidate when the next wave derives requirements.</span>
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: ReactNode; children: ReactNode }) {
  return (
    <section className="fd-sec">
      <div className="fd-sec-head">
        <h3>{title}</h3>
        {note && <span className="faint t-micro">{note}</span>}
      </div>
      {children}
    </section>
  );
}

/** The trace as a strip: comments → signals → this finding → requirements. */
function Chain({ f, supports }: { f: FindingDetail; supports: number }) {
  const steps: { n: ReactNode; label: string; tone?: string }[] =
    f.source_kind === "verbatim"
      ? [
          { n: fmtInt(f.n_sources), label: f.n_sources === 1 ? "customer comment" : "customer comments" },
          { n: fmtInt(f.n_signals), label: f.n_signals === 1 ? "signal read by the AI" : "signals read by the AI" },
          { n: "1", label: "finding" },
          { n: fmtInt(supports), label: supports === 1 ? "requirement" : "requirements", tone: supports ? "" : "amber" },
        ]
      : [
          { n: fmtInt(f.n_sources), label: f.source_kind === "web" ? (f.n_sources === 1 ? "cited web source" : "cited web sources") : f.n_sources === 1 ? "study item" : "study items" },
          { n: "1", label: "finding" },
          { n: fmtInt(supports), label: supports === 1 ? "requirement" : "requirements", tone: supports ? "" : "amber" },
        ];
  return (
    <ol className="fd-chain" aria-label="Evidence chain">
      {steps.map((s, i) => (
        <li key={i} className={s.tone ? `tone-${s.tone}` : undefined}>
          <span className="fd-chain-n num">{s.n}</span>
          <span className="fd-chain-l">{s.label}</span>
          {i < steps.length - 1 && <ArrowRight className="fd-chain-arrow" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

const top = (o: Record<string, number> | undefined, n: number) =>
  Object.entries(o ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, n);

function MarketMetrics({ markets }: { markets: Record<string, FindingMarketMetrics> }) {
  const rows = MARKETS.filter((m) => markets[m]).concat(Object.keys(markets).filter((m) => !MARKETS.includes(m as never)) as never[]);
  return (
    <div className="fd-tablewrap">
      <table className="table fd-mt">
        <thead>
          <tr>
            <th>Market</th>
            <th className="r">Comments</th>
            <th className="r" title="Share of this market's in-scope comments">Share</th>
            <th className="r" title="Comments weighted by severity">Weighted</th>
            <th>Mostly</th>
            <th>Countries</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => {
            const x = markets[m];
            return (
              <tr key={m}>
                <td className="fd-mt-m">{MARKET[m] ?? m}</td>
                <td className="r">{fmtInt(x.verbatims)}</td>
                <td className="r">
                  {fmtPct(x.share)}
                  {x.base != null && <span className="faint"> of {fmtInt(x.base)}</span>}
                </td>
                <td className="r">{x.severity_weighted != null ? x.severity_weighted.toFixed(1) : "–"}</td>
                <td className="fd-mt-types">
                  {top(x.types, 2).map(([t, n]) => (
                    <span key={t}>
                      {FEEDBACK_TYPE[t] ?? humanize(t)} <span className="faint num">{n}</span>
                    </span>
                  ))}
                </td>
                <td className="fd-mt-types">
                  {top(x.countries, 3).map(([c, n]) => (
                    <span key={c}>
                      {c} <span className="faint num">{n}</span>
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function StudyMetrics({ f }: { f: FindingDetail }) {
  const m = f.metrics;
  return (
    <Section title="Customer study" note={m.scale ? `Scale ${m.scale.replace("mean_", "mean of ")}` : undefined}>
      <div className="fd-stats">
        <Stat label="Mean score" value={m.mean != null ? m.mean.toFixed(2) : "–"} />
        <Stat label="Against other items" value={m.z != null ? `${m.z > 0 ? "+" : m.z < 0 ? "−" : ""}${Math.abs(m.z).toFixed(2)} z` : "–"} sub={m.z != null ? (m.z >= 0 ? "above the study average" : "below the study average") : undefined} />
        <Stat label="Rank" value={m.rank != null ? `${m.rank}` : "–"} sub={m.n_items ? `of ${m.n_items} items · 1 = weakest` : undefined} />
      </div>
    </Section>
  );
}

function WebMetrics({ f }: { f: FindingDetail }) {
  const m = f.metrics;
  return (
    <Section title="Web research" note={m.newest_date ? `Newest source ${fmtSimDate(m.newest_date)}` : undefined}>
      <div className="fd-web">
        <div className="row wrap" style={{ gap: 6 }}>
          {Object.entries(m.tiers ?? {})
            .sort()
            .map(([t, n]) => (
              <span key={t} className={`chip ${t === "T1" ? "up" : t === "T2" ? "" : "warn"}`} title={TIER[t]}>
                {t} · {n}
              </span>
            ))}
        </div>
        {m.publishers && m.publishers.length > 0 && <p className="t-small muted">{m.publishers.join(" · ")}</p>}
      </div>
    </Section>
  );
}

/* ---------------------------------------------------------------- signals: finding → signal → verbatim */

function Signals({ f }: { f: FindingDetail }) {
  const [limit, setLimit] = useState(8);
  const q = useQuery({
    queryKey: ["finding", f.id, "signals", limit],
    queryFn: () => api.get<FindingSignal[]>(`/api/findings/${f.id}/signals${qs({ limit })}`),
    placeholderData: (prev) => prev,
  });
  const sigs = q.data ?? [];
  return (
    <Section title="Customer signals" note={`${fmtInt(f.n_signals)} · high severity first`}>
      <p className="fd-explain">
        The AI read each comment into a signal — what kind of feedback, how severe, the need behind it — and checked the quote word for word against the comment.
      </p>
      {q.isLoading && <SkeletonBlock lines={5} />}
      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
      {sigs.length > 0 && (
        <ol className="fd-signals">
          {sigs.map((s) => (
            <li key={s.signal_id} className="sig">
              <div className="sig-head">
                <span className={`chip ${FEEDBACK_TONE[s.feedback_type] ?? ""}`}>{FEEDBACK_TYPE[s.feedback_type] ?? humanize(s.feedback_type)}</span>
                {s.severity && <span className={`telltale ${SEVERITY_TONE[s.severity] ?? ""}`}>{humanize(s.severity)}</span>}
                {s.topic && <span className="sig-topic ellipsis">{s.topic}</span>}
                {s.support_question && <span className="chip outline" title="The customer asked for help rather than gave feedback">Support question</span>}
              </div>
              {s.need_statement && <p className="sig-need">{s.need_statement}</p>}
              {s.quote && (
                <figure className="sig-quote">
                  <QuoteIcon className="sig-quote-mark" aria-hidden />
                  <blockquote>{s.quote}</blockquote>
                </figure>
              )}
              <div className="sig-meta">
                <span className="id">{s.source.external_id}</span>
                {s.source.market && <span>{mkt(s.source.market)}</span>}
                {s.source.country && <span>{s.source.country}</span>}
                {s.source.channel && <span>{s.source.channel}</span>}
                {s.source.wave != null && <span>Wave {s.source.wave}</span>}
                {s.quote &&
                  (s.quote_verified ? (
                    <span className="sig-verified">
                      <BadgeCheck aria-hidden /> Quote verified
                    </span>
                  ) : (
                    <span className="telltale amber">Quote not verified</span>
                  ))}
              </div>
            </li>
          ))}
        </ol>
      )}
      {f.n_signals > sigs.length && sigs.length > 0 && (
        <button className="btn btn-ghost btn-sm fd-more" onClick={() => setLimit(Math.min(f.n_signals, limit + 40))} disabled={q.isFetching}>
          {q.isFetching ? "Loading…" : `Show ${Math.min(40, f.n_signals - sigs.length)} more of ${fmtInt(f.n_signals)}`}
        </button>
      )}
    </Section>
  );
}

/* ---------------------------------------------------------------- sources, rendered per kind */

function Sources({ f }: { f: FindingDetail }) {
  const [limit, setLimit] = useState(f.source_kind === "verbatim" ? 6 : 30);
  const q = useQuery({
    queryKey: ["finding", f.id, "sources", limit],
    queryFn: () => api.get<FindingSource[]>(`/api/findings/${f.id}/sources${qs({ limit })}`),
    placeholderData: (prev) => prev,
  });
  const src = q.data ?? [];
  const label = f.source_kind === "verbatim" ? "Customer comments" : f.source_kind === "web" ? "Cited sources" : "Study items";
  return (
    <Section title={label} note={`${fmtInt(f.n_sources)} · ${KIND[f.source_kind]?.long ?? f.source_kind}`}>
      {q.isLoading && <SkeletonBlock lines={4} />}
      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
      {!q.isLoading && !q.isError && src.length === 0 && <Empty title="No sources linked" />}
      {src.length > 0 && (
        <ul className="fd-sources">
          {src.map((s) => (
            <li key={s.id} className="src">
              {s.kind === "web" ? <WebSource s={s} /> : s.kind === "study" ? <StudySource s={s} /> : s.kind === "feedback" ? <FeedbackSource s={s} /> : <OtherSource s={s} />}
            </li>
          ))}
        </ul>
      )}
      {f.n_sources > src.length && src.length > 0 && (
        <button className="btn btn-ghost btn-sm fd-more" onClick={() => setLimit(Math.min(f.n_sources, limit + 30))} disabled={q.isFetching}>
          {q.isFetching ? "Loading…" : `Show ${Math.min(30, f.n_sources - src.length)} more of ${fmtInt(f.n_sources)}`}
        </button>
      )}
    </Section>
  );
}

const Contra = ({ s }: { s: FindingSource }) => (s.relation === "contradicts" ? <span className="chip warn">Contradicts</span> : null);

function FeedbackSource({ s }: { s: FindingSource }) {
  const text = s.quote || s.text;
  return (
    <>
      {text && <p className="src-quote">“{text}”</p>}
      <div className="src-meta">
        <span className="id">{s.external_id}</span>
        {s.market && <span>{mkt(s.market)}</span>}
        {s.country && <span>{s.country}</span>}
        {s.meta.channel && <span>{s.meta.channel}</span>}
        {s.meta.engine && <span>{s.meta.engine}</span>}
        {s.wave != null && <span>Wave {s.wave}</span>}
        <Contra s={s} />
      </div>
    </>
  );
}

function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
const day = (ts: string | null) => (ts ? new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : null);

function WebSource({ s }: { s: FindingSource }) {
  const tier = s.trust_tier;
  return (
    <>
      <div className="src-head">
        <span className="src-pub">{s.meta.publisher ?? (s.url ? host(s.url) : "Web source")}</span>
        {tier && (
          <span className={`chip ${tier === "T1" ? "up" : tier === "T2" ? "" : "warn"}`} title={TIER[tier] ?? tier}>
            {tier}
          </span>
        )}
        <Contra s={s} />
      </div>
      {(s.quote || s.text) && <p className="src-quote">“{s.quote || s.text}”</p>}
      <div className="src-meta">
        <span>{s.published_at ? `Published ${day(s.published_at)}` : "No publish date"}</span>
        {s.retrieved_at && <span>Retrieved {day(s.retrieved_at)}</span>}
        {s.market && <span>{mkt(s.market)}</span>}
        {s.url && (
          <a href={s.url} target="_blank" rel="noreferrer noopener" className="src-url">
            {host(s.url)} <ExternalLink aria-hidden />
          </a>
        )}
      </div>
    </>
  );
}

function StudySource({ s }: { s: FindingSource }) {
  const m = s.meta;
  const z = m.z_within_column;
  return (
    <>
      <div className="src-head">
        <span className="src-pub">{s.external_id}</span>
        <Contra s={s} />
      </div>
      <div className="src-meta">
        {m.mean != null && <span className="num">Mean {Number(m.mean).toFixed(2)}</span>}
        {z != null && <span className="num">z {z > 0 ? "+" : z < 0 ? "−" : ""}{Math.abs(z).toFixed(2)}</span>}
        {m.rank_within_column != null && <span className="num">Rank {m.rank_within_column}{m.n_items_in_column ? ` of ${m.n_items_in_column}` : ""}</span>}
        {s.vehicle && s.market && <span>{scopeLabel(s.vehicle, s.market)}</span>}
        {m.scale && <span>{m.scale.replace("mean_", "scale ")}</span>}
      </div>
    </>
  );
}

function OtherSource({ s }: { s: FindingSource }) {
  return (
    <>
      <div className="src-head">
        <span className="src-pub">{s.external_id ?? s.ref ?? humanize(s.kind)}</span>
        <span className="chip outline">{humanize(s.kind)}</span>
        <Contra s={s} />
      </div>
      {s.text && <p className="src-quote">{s.text}</p>}
    </>
  );
}
