// Briefing: what changed since the last wave, what's waiting for the PM, and how the portfolio stands.
// Composed from the latest prioritization run — no AI call, so it's free and always consistent with the data.
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Flag, GitMerge, Layers, User } from "lucide-react";
import { api } from "@/lib/api";
import type { Briefing as B, FeedItem, PulseCell } from "@/lib/types";
import { CAR, MARKET, car, mkt } from "@/lib/labels";
import { fmtSimDate, fmtWhen, plural } from "@/lib/format";
import { Delta, ErrorNote, PriorityMark, Skeleton, SkeletonBlock } from "@/components/ui";
import "./briefing.css";

const ROWS = ["F70", "G60", "G68", "G70"];
const compact = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
// "only 14 in-scope verbatims" → "14 comments": the cell is small, the tooltip keeps the full text
const shortGap = (g: string) =>
  g
    .replace(/^only (\d+) in-scope verbatims$/, "$1 comments")
    .replace(/^no verbatims$/, "no comments")
    .replace(/^no customer study$/, "no study")
    .replace(/^no web research$/, "no web research")
    .replace(/^verbatims not yet extracted$/, "not read yet");
const COLS = ["US", "EU", "CN", "RoW"];

function Recap({ b }: { b: B }) {
  const h = b.headline;
  const nav = useNavigate();
  const moved = h.risers + h.fallers;
  return (
    <section className="panel recap" aria-labelledby="recap-h">
      <div className="recap-meta">
        <span className="faint t-small">
          Wave {b.wave.n} · {fmtSimDate(b.wave.simulated_date)} · compiled from run {b.run?.id ?? "–"}
          {b.run ? ` · ${fmtWhen(b.run.ts)}` : ""} · no AI call
        </span>
      </div>
      <h1 id="recap-h" className="recap-title">
        {b.wave.label.replace(/^Wave \d+ · /, "")}
      </h1>
      <p className="recap-text">
        {h.new_requirements > 0 ? (
          <>
            The AI surfaced <b>{plural(h.new_requirements, "new requirement")}</b>
            {h.merges_open > 0 ? (
              <> and wants to <b>merge {h.merges_open}</b> repeated needs into existing ones instead of duplicating them. </>
            ) : (
              ". "
            )}
          </>
        ) : (
          <>No new requirements this wave. </>
        )}
        {moved > 0 ? (
          <>
            New evidence moved <b>{plural(moved, "car · market score")}</b> —{" "}
            <span className="chip up">{h.risers} up</span> <span className="chip down">{h.fallers} down</span>
            {h.priority_changes > 0 ? (
              <>
                , and <b>{h.priority_changes}</b> crossed a priority band. The AI proposes those changes; it never applies them.{" "}
              </>
            ) : (
              ". "
            )}
          </>
        ) : (
          <>Scores held steady. </>
        )}
        {h.conflicts > 0 && (
          <>
            <b>{plural(h.conflicts, "requirement")}</b> rank differently across markets — <span className="chip warn">markets disagree</span>.
          </>
        )}
      </p>
      <div className="recap-actions">
        <button className="btn btn-primary btn-lg" onClick={() => nav("/decide")} disabled={!b.decisions_waiting}>
          {b.decisions_waiting ? <>Start deciding · {b.decisions_waiting} waiting</> : <>Nothing waiting</>}
          <ArrowRight />
        </button>
        <Link className="btn btn-ghost btn-lg" to="/cars/G60?market=US">
          See the 5 Series in 3D
        </Link>
      </div>
    </section>
  );
}

function Pulse({ cells }: { cells: PulseCell[] }) {
  const by = new Map(cells.map((c) => [`${c.target.vehicle}×${c.target.market}`, c]));
  const nav = useNavigate();
  return (
    <section className="panel pulse" aria-labelledby="pulse-h">
      <div className="panel-head">
        <h2 id="pulse-h">Portfolio pulse</h2>
        <span className="t-micro faint">Must · Should · Could per car and market</span>
      </div>
      <div className="pulse-grid" role="table" aria-label="Requirements per car and market">
        <div role="row" className="pulse-row pulse-headrow">
          <span role="columnheader" />
          {COLS.map((m) => (
            <span role="columnheader" key={m} className="pulse-col">
              {MARKET[m]}
            </span>
          ))}
        </div>
        {ROWS.map((v) => (
          <div role="row" className="pulse-row" key={v}>
            <span role="rowheader" className="pulse-car">
              {CAR[v]}
            </span>
            {COLS.map((m) => {
              const c = by.get(`${v}×${m}`);
              if (!c) return <span role="cell" key={m} className="pulse-cell pulse-none" aria-label="Not a target" />;
              const total = Math.max(1, c.must + c.should + c.could);
              return (
                <button
                  role="cell"
                  key={m}
                  className="pulse-cell"
                  onClick={() => nav(`/cars/${v}?market=${m}`)}
                  title={`${car(v)} · ${mkt(m)}: ${c.must} Must, ${c.should} Should, ${c.could} Could; ${c.voice_base.toLocaleString()} customer comments${c.gaps.length ? ` · gaps: ${c.gaps.join(", ")}` : ""}`}
                >
                  <span className="pulse-must instrument">{c.must}</span>
                  <span className="pulse-unit">Must</span>
                  <span className="pulse-bar" aria-hidden>
                    <i className="m" style={{ width: `${(c.must / total) * 100}%` }} />
                    <i className="s" style={{ width: `${(c.should / total) * 100}%` }} />
                    <i className="c" style={{ width: `${(c.could / total) * 100}%` }} />
                  </span>
                  <span className="pulse-foot">
                    {c.gaps.length ? <span className="telltale amber">{shortGap(c.gaps[0])}</span> : <span className="faint">{compact(c.voice_base)} comments</span>}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}

function Movers({ b }: { b: B }) {
  const nav = useNavigate();
  if (!b.movers.length) return null;
  return (
    <section className="panel" aria-labelledby="movers-h">
      <div className="panel-head">
        <h2 id="movers-h">What moved since run {b.previous_run_id ?? "–"}</h2>
        <Link to="/process?tab=runs" className="t-small">
          All changes
        </Link>
      </div>
      <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Requirement</th>
            <th>Car · market</th>
            <th>Priority</th>
            <th className="r">Score</th>
          </tr>
        </thead>
        <tbody>
          {b.movers.map((m) => (
            <tr key={`${m.req_id}${m.target.key}`} className="clickable" onClick={() => nav(`/requirements/${m.req_id}`)} title={m.cause ?? undefined}>
              <td>
                <div className="ellipsis" style={{ maxWidth: 360 }}>{m.title}</div>
              </td>
              <td className="muted">{m.target.label}</td>
              <td>
                <span className="row" style={{ gap: 6 }}>
                  {m.priority_old && m.priority_old !== m.priority_new ? (
                    <>
                      <PriorityMark p={m.priority_old} size="sm" ai />
                      <ArrowRight size={12} className="faint" />
                    </>
                  ) : null}
                  <PriorityMark p={m.priority_new} size="sm" ai />
                </span>
              </td>
              <td className="r">
                <span className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
                  <span className="num">{m.score_new == null ? "–" : Math.round(m.score_new)}</span>
                  <Delta d={m.delta} />
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </section>
  );
}

const FEED_ICON = { proposal: Bot, decision: User, run: Layers, wave: Flag, challenge: GitMerge } as const;

function Feed({ items }: { items: FeedItem[] }) {
  const nav = useNavigate();
  return (
    <section className="panel" aria-labelledby="feed-h">
      <div className="panel-head">
        <h2 id="feed-h">Since last wave</h2>
        <Link to="/process?tab=audit" className="t-small">
          Full audit trail
        </Link>
      </div>
      <ol className="feed">
        {items.map((f) => {
          const Icon = FEED_ICON[f.kind] ?? Bot;
          return (
            <li key={f.id}>
              <button className="feed-item" onClick={() => f.req_id && nav(`/requirements/${f.req_id}`)} disabled={!f.req_id}>
                <span className={`feed-icon who-${f.actor_type}`} title={f.actor_type === "human" ? f.actor : f.actor_type === "ai" ? "AI" : "System"}>
                  <Icon />
                </span>
                <span className="feed-main">
                  <span className="feed-title">
                    {f.title}
                    {f.chip && <span className={`chip ${f.chip.tone === "neutral" ? "" : f.chip.tone}`}>{f.chip.text}</span>}
                  </span>
                  {f.detail && <span className="feed-detail">{f.detail}</span>}
                </span>
                <span className="feed-when faint">{fmtWhen(f.ts)}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function NewReqs({ b }: { b: B }) {
  const nav = useNavigate();
  return (
    <section className="panel" aria-labelledby="new-h">
      <div className="panel-head">
        <h2 id="new-h">New in this wave</h2>
        <span className="t-small faint">{b.new_requirements.length}</span>
      </div>
      <div className="panel-body newreqs">
        {b.new_requirements.length === 0 && <p className="muted t-small">No new requirements in this wave.</p>}
        {b.new_requirements.map((r) => (
          <button key={r.req_id} className="newreq" onClick={() => nav(`/decide/req:${r.req_id}`)}>
            <span className="id">{r.req_id}</span>
            <span className="newreq-title">{r.title}</span>
            <span className="newreq-meta muted">
              {r.category}
              {r.best_target ? ` · best in ${r.best_target.label}` : ""}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

export default function Briefing() {
  const q = useQuery({ queryKey: ["briefing"], queryFn: () => api.get<B>("/api/briefing") });
  return (
    <main className="page briefing">
      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && (
        <div className="brief-top">
          <div className="panel" style={{ padding: 28 }}>
            <Skeleton h={22} w="40%" />
            <div style={{ height: 18 }} />
            <SkeletonBlock lines={4} />
          </div>
          <div className="panel" style={{ padding: 28 }}>
            <SkeletonBlock lines={6} />
          </div>
        </div>
      )}
      {q.data && (
        <>
          <div className="brief-top">
            <Recap b={q.data} />
            <Pulse cells={q.data.pulse} />
          </div>
          <div className="brief-mid">
            <Movers b={q.data} />
            <NewReqs b={q.data} />
          </div>
          <Feed items={q.data.feed} />
        </>
      )}
    </main>
  );
}
