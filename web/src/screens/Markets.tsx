// Markets: each market is its own customer (D-011). Who they are, what they ask of each car, where they
// disagree with the rest of the world, and what competitors and trends are doing there.
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { Priority, Target } from "@/lib/types";
import { MARKET } from "@/lib/labels";
import { fmtInt } from "@/lib/format";
import { ErrorNote, EvidenceMeter, PriorityMark, ScoreBar, SkeletonBlock } from "@/components/ui";
import "./markets.css";

type MarketListItem = { code: string; name: string; label: string; targets: Target[]; n_requirements: number; must: number; voice_base: number; gaps: string[] };
type MarketDetail = {
  code: string;
  name: string;
  label: string;
  profile: { climate: string | null; usage_patterns: string | null; cultural_expectations: string | null; infrastructure: string | null; powertrain_mix: string | null; profile_valid_from?: string | null; sources?: { id: number; url: string | null; title_or_ref?: string; ref?: string; trust_tier: string | null }[] } | null;
  targets: { target: Target; n: number; must: number; should: number; could: number; voice_base: number; gaps: string[]; top: { req_id: string; title: string; score: number; priority: Priority; ai_only: boolean; evidence_level: "E1" | "E2" | "E3" | "E4" | null }[] }[];
  distinctive: { req_id: string; title: string; this_market: { priority: Priority; score: number }; elsewhere: { priority: Priority; score: number; market: string } }[];
  competitors: { id: string; name: string; brand: string; strengths: string | null; segment: string | null }[];
  web_signals: { finding_id: number; title: string; type: string; best_tier: string | null; publishers: string[]; newest_date: string | null }[];
  study_highlights: { finding_id: number; title: string; type: string; vehicle: string | null }[];
};

const ORDER = ["US", "EU", "CN", "RoW"];
type Src = { id: number; url: string | null; title_or_ref?: string; ref?: string; trust_tier: string | null };
/** One chip per publisher (best tier, count), so repeated hostnames don't read as duplicates. */
function byPublisher(sources: Src[]) {
  const m = new Map<string, { host: string; url: string | null; tier: string | null; n: number; refs: string[] }>();
  for (const s of sources) {
    let host = s.title_or_ref ?? s.ref ?? "source";
    try {
      if (s.url) host = new URL(s.url).hostname.replace(/^www\./, "");
    } catch {
      /* keep the ref */
    }
    const g = m.get(host) ?? { host, url: s.url, tier: s.trust_tier, n: 0, refs: [] };
    g.n += 1;
    if (s.trust_tier && (!g.tier || s.trust_tier < g.tier)) g.tier = s.trust_tier;
    g.refs.push(s.url ?? s.ref ?? "");
    m.set(host, g);
  }
  return [...m.values()].sort((a, b) => (a.tier ?? "T9").localeCompare(b.tier ?? "T9") || b.n - a.n);
}
const PROFILE: [keyof NonNullable<MarketDetail["profile"]>, string][] = [
  ["cultural_expectations", "What they expect"],
  ["usage_patterns", "How they drive"],
  ["climate", "Climate"],
  ["infrastructure", "Charging & infrastructure"],
  ["powertrain_mix", "Powertrain mix"],
];
const WEB_TYPE: Record<string, string> = {
  competitor_advantage: "Competitor advantage",
  competitor_feature: "Competitor feature",
  review_criticism: "Review criticism",
  market_trend: "Trend",
  customer_expectation: "Expectation",
};

export default function Markets() {
  const { market } = useParams();
  const nav = useNavigate();
  const list = useQuery({ queryKey: ["markets"], queryFn: () => api.get<MarketListItem[]>("/api/markets") });
  const q = useQuery({ queryKey: ["market", market], queryFn: () => api.get<MarketDetail>(`/api/markets/${market}`), enabled: !!market });
  if (!market) return <Navigate to="/markets/US" replace />;
  const d = q.data;
  const items = [...(list.data ?? [])].sort((a, b) => ORDER.indexOf(a.code) - ORDER.indexOf(b.code));

  return (
    <main className="page markets">
      <nav className="mk-tabs" aria-label="Markets">
        {items.map((m) => (
          <button key={m.code} className={`mk-tab${m.code === market ? " on" : ""}`} onClick={() => nav(`/markets/${m.code}`)} aria-current={m.code === market}>
            <span className="mk-tab-name">{m.label}</span>
            <span className="mk-tab-meta">
              <span className="num">{m.must}</span> Must · <span className="num">{fmtInt(m.voice_base)}</span> comments
            </span>
            {m.gaps.length > 0 && <span className="telltale amber mk-tab-gap">{m.gaps[0]}</span>}
          </button>
        ))}
        {list.isLoading && <SkeletonBlock lines={2} />}
      </nav>

      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && <SkeletonBlock lines={10} />}
      {d && (
        <>
          <section className="mk-hero">
            <div>
              <h1 className="mk-title">{d.name}</h1>
              <p className="mk-lede">
                {d.targets.map((t) => t.target.car ?? t.target.label.split(" · ")[0]).join(", ")} sold here ·{" "}
                {fmtInt(d.targets.reduce((s, t) => s + t.voice_base, 0))} customer comments
              </p>
              {d.distinctive.length > 0 && (
                <div className="mk-differs">
                  <div className="sec-label">Ranks differently here</div>
                  {d.distinctive.slice(0, 4).map((x) => (
                    <button key={x.req_id} className="mk-differs-row" onClick={() => nav(`/requirements/${x.req_id}`)}>
                      <span className="mk-differs-title">{x.title}</span>
                      <span className="row" style={{ gap: 6 }}>
                        <PriorityMark p={x.this_market.priority} size="sm" ai />
                        <span className="faint t-micro">vs {MARKET[x.elsewhere.market] ?? x.elsewhere.market}</span>
                        <PriorityMark p={x.elsewhere.priority} size="sm" ai />
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <dl className="mk-profile">
                {PROFILE.map(([k, label]) =>
                  d.profile?.[k] ? (
                    <div key={k}>
                      <dt>{label}</dt>
                      <dd>{String(d.profile[k])}</dd>
                    </div>
                  ) : null,
                )}
              </dl>
              {d.profile?.sources && d.profile.sources.length > 0 && (
                <div className="mk-sources">
                  <span className="t-micro faint">
                    Cited web research{d.profile.profile_valid_from ? `, as of ${d.profile.profile_valid_from}` : ""} · “(U)” marks an unverified claim ·
                  </span>
                  {byPublisher(d.profile.sources).map((g) => (
                    <a key={g.host} className="mk-src" href={g.url ?? undefined} target="_blank" rel="noreferrer" title={g.refs.join("\n")}>
                      {g.tier && <span className={`chip ${g.tier === "T1" ? "up" : g.tier === "T2" ? "warn" : "down"}`}>{g.tier}</span>}
                      {g.host}
                      {g.n > 1 && <span className="faint"> ×{g.n}</span>}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section aria-labelledby="mk-asks">
            <h2 id="mk-asks" className="t-title mk-h">What {MARKET[d.code] ?? d.name} asks of each car</h2>
            <div className="mk-cars">
              {d.targets.map((t) => (
                <div key={t.target.key} className="panel mk-car">
                  <div className="panel-head">
                    <h3>{t.target.label.split(" · ")[0]}</h3>
                    <Link to={`/cars/${t.target.vehicle}?market=${t.target.market}`} className="t-small">In 3D <ChevronRight size={13} /></Link>
                  </div>
                  <div className="mk-car-stats">
                    <span><b className="num">{t.must}</b> Must</span>
                    <span><b className="num">{t.should}</b> Should</span>
                    <span><b className="num">{t.could}</b> Could</span>
                    {t.gaps.length > 0 ? <span className="telltale amber">{t.gaps[0]}</span> : <span className="faint">{fmtInt(t.voice_base)} comments</span>}
                  </div>
                  <ol className="mk-top">
                    {t.top.map((r) => (
                      <li key={r.req_id}>
                        <button onClick={() => nav(`/requirements/${r.req_id}?t=${encodeURIComponent(t.target.key)}`)}>
                          <span className="mk-top-title">{r.title}</span>
                          <span className="mk-top-meta">
                            <PriorityMark p={r.priority} ai={r.ai_only} size="sm" />
                            <EvidenceMeter level={r.evidence_level} />
                            <ScoreBar score={r.score} width={44} />
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          </section>

          {d.distinctive.length > 0 && (
            <section className="panel" aria-labelledby="mk-diff">
              <div className="panel-head">
                <h2 id="mk-diff">Where {MARKET[d.code] ?? d.name} disagrees with the other markets</h2>
                <span className="t-small muted">same requirement, same car, different priority</span>
              </div>
              <div className="table-scroll">
              <table className="table">
                <tbody>
                  {d.distinctive.map((x) => (
                    <tr key={x.req_id} className="clickable" onClick={() => nav(`/requirements/${x.req_id}`)}>
                      <td><div className="ellipsis" style={{ maxWidth: 520 }}>{x.title}</div></td>
                      <td>
                        <span className="row" style={{ gap: 8 }}>
                          <span className="t-small muted">{MARKET[d.code]}</span>
                          <PriorityMark p={x.this_market.priority} size="sm" ai />
                        </span>
                      </td>
                      <td className="faint"><ArrowRight size={13} /></td>
                      <td>
                        <span className="row" style={{ gap: 8 }}>
                          <span className="t-small muted">{MARKET[x.elsewhere.market] ?? x.elsewhere.market}</span>
                          <PriorityMark p={x.elsewhere.priority} size="sm" ai />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </section>
          )}

          <section className="mk-intel">
            <div className="panel">
              <div className="panel-head"><h2>What's moving in the market</h2><span className="t-micro faint">cited web research · trust tier</span></div>
              <ol className="mk-web">
                {d.web_signals.length === 0 && <li className="muted t-small">No cited web research for this market yet.</li>}
                {d.web_signals.map((w) => (
                  <li key={w.finding_id}>
                    <div className="row wrap" style={{ gap: 6 }}>
                      <span className="chip outline">{WEB_TYPE[w.type] ?? w.type.replace(/_/g, " ")}</span>
                      {w.best_tier && <span className={`chip ${w.best_tier === "T1" ? "up" : w.best_tier === "T2" ? "warn" : "down"}`}>{w.best_tier}</span>}
                      <span className="t-micro faint">{w.publishers.slice(0, 3).join(" · ")}{w.newest_date ? ` · ${w.newest_date}` : ""}</span>
                    </div>
                    <div className="mk-web-title">{w.title}</div>
                  </li>
                ))}
              </ol>
            </div>
            <div className="col" style={{ gap: 18 }}>
              <div className="panel">
                <div className="panel-head"><h2>Competitors here</h2></div>
                <ul className="ctx-comp">
                  {d.competitors.length === 0 && <li className="muted t-small">No competitor profiles.</li>}
                  {d.competitors.map((c) => (
                    <li key={c.id}>
                      <div className="ctx-comp-name">{c.name}</div>
                      {c.strengths && <div className="muted t-small">{c.strengths}</div>}
                    </li>
                  ))}
                </ul>
              </div>
              {d.study_highlights.length > 0 && (
                <div className="panel">
                  <div className="panel-head"><h2>Customer study stand-outs</h2></div>
                  <ul className="mk-study">
                    {d.study_highlights.map((s) => (
                      <li key={s.finding_id}>
                        <span className={`telltale ${s.type.includes("strength") ? "green" : "amber"}`} />
                        {s.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
