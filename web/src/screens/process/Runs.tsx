// Runs & weights: every prioritization run is a snapshot. Compare any two (what moved, which band it crossed, why),
// and tune the six scoring weights — a deterministic re-score, no AI, no cost.
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, RotateCcw } from "lucide-react";
import { api, invalidateAll, qs } from "@/lib/api";
import type { Priority, RunDiff, RunDiffRow, RunRow, WeightsPayload } from "@/lib/types";
import { useMeta } from "@/lib/hooks";
import { targetLabel } from "@/lib/labels";
import { fmtInt, fmtScore, fmtWhen } from "@/lib/format";
import { ReasonField, reasonOk } from "@/components/actions";
import { useToast } from "@/components/toast";
import { Delta, Empty, ErrorNote, PriorityMark, Seg, Skeleton, SkeletonBlock } from "@/components/ui";
import { triggerLabel } from "./common";

export function Runs() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.get<RunRow[]>("/api/runs") });
  const [sp, setSp] = useSearchParams();
  const list = useMemo(() => [...(runs.data ?? [])].sort((a, b) => b.id - a.id), [runs.data]);
  const newerParam = Number(sp.get("newer")) || null;
  const newer = list.find((r) => r.id === newerParam)?.id ?? list[0]?.id ?? null;
  const olderParam = Number(sp.get("older")) || null;
  const older =
    list.find((r) => r.id === olderParam && newer != null && r.id < newer)?.id ?? list.find((r) => newer != null && r.id < newer)?.id ?? null;

  const pick = (o: number | null, n: number | null) => {
    const next = new URLSearchParams(sp);
    next.set("tab", "runs");
    if (n != null) next.set("newer", String(n));
    if (o != null) next.set("older", String(o));
    else next.delete("older");
    setSp(next, { replace: true });
  };

  return (
    <div className="runs-grid">
      <div className="col" style={{ gap: 18, minWidth: 0 }}>
        <RunsTable q={runs} list={list} older={older} newer={newer} onPick={(id) => pick(list.find((r) => r.id < id)?.id ?? null, id)} />
        <DiffPanel list={list} older={older} newer={newer} onPick={pick} loading={runs.isLoading} />
      </div>
      <WeightsPanel />
    </div>
  );
}

/* ---------------------------------------------------------------- runs table */

function RunsTable({
  q,
  list,
  older,
  newer,
  onPick,
}: {
  q: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => void };
  list: RunRow[];
  older: number | null;
  newer: number | null;
  onPick: (id: number) => void;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? list : list.slice(0, 8);
  return (
    <section className="panel" aria-labelledby="runs-h">
      <div className="panel-head">
        <h2 id="runs-h">Prioritization runs</h2>
        <span className="t-small faint">Pick a run to compare it with the one before</span>
      </div>
      {q.isLoading && (
        <div className="panel-body">
          <SkeletonBlock lines={5} />
        </div>
      )}
      {q.isError && (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={q.refetch} />
        </div>
      )}
      {!q.isLoading && !q.isError && list.length === 0 && (
        <Empty title="No runs yet">Open the first wave on the Timeline — it ends with a prioritization run.</Empty>
      )}
      {list.length > 0 && (
        <div className="px-scroll">
          <table className="table runs-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>When</th>
                <th>Trigger</th>
                <th>By</th>
                <th className="r">Wave</th>
                <th className="r">Targets scored</th>
                <th className="r">Proposals</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr
                  key={r.id}
                  className={`clickable${r.id === newer ? " is-newer" : r.id === older ? " is-older" : ""}`}
                  onClick={() => onPick(r.id)}
                  title={r.note ?? undefined}
                >
                  <td>
                    <span className="run-id num">
                      <i aria-hidden />
                      {r.id}
                    </span>
                  </td>
                  <td className="muted num">{fmtWhen(r.ts)}</td>
                  <td>
                    <span className={`chip${r.trigger === "weight_change" ? " violet" : r.trigger === "new_evidence" ? " blue" : ""}`}>{triggerLabel(r.trigger)}</span>
                  </td>
                  <td className="muted ellipsis" style={{ maxWidth: 160 }}>{r.initiated_by ?? "–"}</td>
                  <td className="r">{r.wave ?? "–"}</td>
                  <td className="r">{fmtInt(r.targets_scored)}</td>
                  <td className="r">{fmtInt(r.proposals)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list.length > 8 && (
        <div className="px-more">
          <button className="btn btn-ghost btn-sm" onClick={() => setAll((x) => !x)}>
            {all ? "Show the latest 8" : `Show all ${list.length} runs`}
          </button>
        </div>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- what changed between two runs */

type DiffView = "moves" | "bands" | "newdrop";

function parseChange(c: string | null): { from: Priority | null; to: Priority | null } | null {
  if (!c || !c.includes("→")) return null;
  const [a, b] = c.split("→").map((x) => x.trim());
  return { from: (a as Priority) || null, to: (b as Priority) || null };
}

function DiffPanel({
  list,
  older,
  newer,
  onPick,
  loading,
}: {
  list: RunRow[];
  older: number | null;
  newer: number | null;
  onPick: (o: number | null, n: number | null) => void;
  loading: boolean;
}) {
  const [view, setView] = useState<DiffView>("moves");
  const [all, setAll] = useState(false);
  const q = useQuery({
    queryKey: ["runs", "diff", older, newer],
    queryFn: () => api.get<RunDiff>(`/api/runs/diff${qs({ older, newer })}`),
    enabled: older != null && newer != null,
  });
  useEffect(() => setAll(false), [older, newer, view]);

  const rows = useMemo(() => {
    const r = q.data?.rows ?? [];
    const f =
      view === "bands"
        ? r.filter((x) => parseChange(x.change))
        : view === "newdrop"
          ? r.filter((x) => x.change === "new" || x.change === "dropped")
          : r.filter((x) => (x.delta != null && Math.abs(x.delta) >= 0.5) || parseChange(x.change));
    return [...f].sort((a, b) => {
      const pa = parseChange(a.change) ? 1 : 0;
      const pb = parseChange(b.change) ? 1 : 0;
      if (pa !== pb) return pb - pa;
      return Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0);
    });
  }, [q.data, view]);
  const shown = all ? rows : rows.slice(0, 30);
  const s = q.data?.stats;

  return (
    <section className="panel" aria-labelledby="diff-h">
      <div className="panel-head diff-head">
        <h2 id="diff-h">What changed</h2>
        <div className="row diff-pick">
          <label className="sr-only" htmlFor="diff-older">Older run</label>
          <select id="diff-older" className="select px-select" value={older ?? ""} onChange={(e) => onPick(Number(e.target.value) || null, newer)} disabled={!list.length}>
            {list
              .filter((r) => newer == null || r.id < newer)
              .map((r) => (
                <option key={r.id} value={r.id}>
                  Run {r.id}
                </option>
              ))}
          </select>
          <ArrowRight className="faint" size={14} aria-hidden />
          <label className="sr-only" htmlFor="diff-newer">Newer run</label>
          <select
            id="diff-newer"
            className="select px-select"
            value={newer ?? ""}
            onChange={(e) => {
              const n = Number(e.target.value);
              onPick(older != null && older < n ? older : list.find((r) => r.id < n)?.id ?? null, n);
            }}
            disabled={!list.length}
          >
            {list.slice(0, -1).map((r) => (
              <option key={r.id} value={r.id}>
                Run {r.id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading || (q.isLoading && q.fetchStatus !== "idle") ? (
        <div className="panel-body">
          <div className="diff-stats">
            {[0, 1, 2, 3].map((i) => (
              <div key={i}>
                <Skeleton h={22} w={48} />
                <div style={{ height: 6 }} />
                <Skeleton h={10} w={80} />
              </div>
            ))}
          </div>
          <div style={{ height: 18 }} />
          <SkeletonBlock lines={6} />
        </div>
      ) : older == null || newer == null ? (
        <Empty title="Nothing to compare yet">A comparison needs two runs. The next wave or a weight change creates one.</Empty>
      ) : q.isError ? (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={() => q.refetch()} />
        </div>
      ) : q.data && s ? (
        <>
          <div className="panel-body diff-body">
            <div className="diff-stats">
              <div>
                <span className="instrument diff-n">{fmtInt(s.compared)}</span>
                <small>car · market scores compared</small>
              </div>
              <div>
                <span className="instrument diff-n">{fmtInt(s.moved)}</span>
                <small>moved by 0.5 or more</small>
              </div>
              <div className={s.priority_changed ? "hot" : ""}>
                <span className="instrument diff-n">{fmtInt(s.priority_changed)}</span>
                <small>crossed a priority band</small>
              </div>
              <div>
                <span className="instrument diff-n">{fmtInt(s.new_or_dropped)}</span>
                <small>new or dropped</small>
              </div>
            </div>
            {q.data.weight_changes.length > 0 && (
              <div className="diff-weights">
                <span className="t-small muted">Weights changed between these runs</span>
                <div className="row wrap" style={{ gap: 6 }}>
                  {q.data.weight_changes.map((w) => (
                    <span key={w.factor} className="chip violet">
                      {w.label ?? w.factor.replace(/_/g, " ")} {w.old ?? "–"} → {w.new ?? "–"}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div>
            <Seg<DiffView>
              label="Which changes"
              value={view}
              onChange={setView}
              options={[
                { value: "moves", label: "Moves" },
                { value: "bands", label: "Band changes", count: s.priority_changed },
                { value: "newdrop", label: "New & dropped", count: s.new_or_dropped },
              ]}
            />
            </div>
          </div>
          {rows.length === 0 ? (
            <Empty title={view === "moves" ? "Scores held steady" : view === "bands" ? "No band changes" : "Nothing new or dropped"}>
              {view === "moves" ? "No car · market score moved by 0.5 or more between these runs." : "Try another view or another pair of runs."}
            </Empty>
          ) : (
            <ol className="moves">
              {shown.map((r, i) => (
                <MoveRow key={`${r.req_id}${r.target_key}`} r={r} i={i} />
              ))}
            </ol>
          )}
          {rows.length > 30 && (
            <div className="px-more">
              <button className="btn btn-ghost btn-sm" onClick={() => setAll((x) => !x)}>
                {all ? "Show the top 30" : `Show all ${fmtInt(rows.length)}`}
              </button>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

function MoveRow({ r, i }: { r: RunDiffRow; i: number }) {
  const band = parseChange(r.change);
  return (
    <li>
      <Link to={`/requirements/${r.req_id}`} className="move">
        <span className="move-i num faint">{i + 1}</span>
        <span className="move-main">
          <span className="move-title">
            <span className="ellipsis">{r.title}</span>
          </span>
          <span className="move-sub">
            <span className="id">{r.req_id}</span>
            <span className="muted">{targetLabel(r.target_key)}</span>
            {r.rank_move != null && r.rank_move !== 0 && (
              <span className="faint num">
                rank {r.rank_old ?? "–"} → {r.rank_new ?? "–"}
              </span>
            )}
          </span>
          {r.cause && <span className="move-cause">{r.cause}</span>}
        </span>
        <span className="move-band">
          {band ? (
            <>
              <PriorityMark p={band.from} size="sm" ai />
              <ArrowRight size={12} className="faint" aria-hidden />
              <PriorityMark p={band.to} size="sm" ai />
            </>
          ) : r.change === "dropped" ? (
            <span className="chip outline">dropped</span>
          ) : null}
        </span>
        <span className="move-score num">
          <span className="faint">{fmtScore(r.score_old)}</span>
          <ArrowRight size={11} className="faint" aria-hidden />
          <span>{fmtScore(r.score_new)}</span>
        </span>
        <span className="move-delta">{r.change === "dropped" ? <span className="chip down">dropped</span> : <Delta d={r.change === "new" ? null : r.delta} />}</span>
      </Link>
    </li>
  );
}

/* ---------------------------------------------------------------- weights editor */

const SHADES = ["#4d94ff", "#3478dc", "#2a5da9", "#7c8aa3", "#56627a", "#394252"];

function WeightsPanel() {
  const { data: meta } = useMeta();
  const q = useQuery({ queryKey: ["weights"], queryFn: () => api.get<WeightsPayload>("/api/weights") });
  const toast = useToast();
  const labels = q.data?.labels ?? meta?.scoring.factor_labels ?? {};
  const help = q.data?.help ?? (meta?.labels as { factor_help?: Record<string, string> } | undefined)?.factor_help ?? {};
  const saved = q.data?.current?.weights ?? q.data?.defaults ?? meta?.scoring.default_weights ?? null;
  const keys = Object.keys(meta?.scoring.factor_labels ?? labels ?? {}).length ? Object.keys(meta?.scoring.factor_labels ?? labels) : Object.keys(saved ?? {});
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const [why, setWhy] = useState("");
  useEffect(() => {
    if (saved && !draft) setDraft({ ...saved });
  }, [saved, draft]);

  const w = draft ?? saved ?? {};
  const sum = keys.reduce((a, k) => a + (w[k] ?? 0), 0);
  const savedSum = keys.reduce((a, k) => a + (saved?.[k] ?? 0), 0);
  const changed = !!saved && keys.some((k) => (w[k] ?? 0) !== (saved[k] ?? 0));
  const isDefault = !!q.data?.defaults && keys.every((k) => (w[k] ?? 0) === (q.data!.defaults[k] ?? 0));

  const save = useMutation({
    mutationFn: () => api.post<{ weights_version_id: number; run_id: number }>("/api/weights", { weights: w, rationale: why }),
    onSuccess: (r) => {
      toast({ tone: "ok", title: `Weights saved · run ${r.run_id}`, body: "Every target was re-scored. Band changes wait in Decide. Recorded in the audit trail." });
      setWhy("");
      setDraft(null);
      invalidateAll();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Weights not saved", body: e.message }),
  });

  const problems = [!changed && "Change at least one weight", sum <= 0 && "Weights must add up to more than zero", !reasonOk(why) && "Give a reason"].filter(Boolean) as string[];

  return (
    <section className="panel weights" aria-labelledby="w-h">
      <div className="panel-head">
        <h2 id="w-h">Scoring weights</h2>
        {q.data?.current && (
          <span className="t-small faint" title={q.data.current.rationale ?? undefined}>
            {q.data.current.id == null ? "Default weights" : <>Version {q.data.current.id} · {fmtWhen(q.data.current.created_at)}</>}
          </span>
        )}
      </div>
      <div className="panel-body col" style={{ gap: 16 }}>
        <p className="t-small muted">
          How much each factor counts towards the 0–100 score. Saving re-scores every car · market <b className="w-free">deterministically — no AI, no cost</b>, in seconds.
          Priority band changes arrive in Decide as suggestions.
        </p>
        {q.isLoading || !saved ? (
          q.isError ? (
            <ErrorNote error={q.error} onRetry={() => q.refetch()} />
          ) : (
            <SkeletonBlock lines={8} />
          )
        ) : (
          <>
            <div className="share" aria-label="Share of the score per factor">
              <div className="share-bar">
                {keys.map((k, i) => (
                  <i key={k} style={{ width: `${sum ? ((w[k] ?? 0) / sum) * 100 : 0}%`, background: SHADES[i % SHADES.length] }} title={`${labels[k] ?? k}: ${sum ? Math.round(((w[k] ?? 0) / sum) * 100) : 0}%`} />
                ))}
              </div>
              <div className="share-bar saved" title="Saved weights">
                {keys.map((k, i) => (
                  <i key={k} style={{ width: `${savedSum ? ((saved[k] ?? 0) / savedSum) * 100 : 0}%`, background: SHADES[i % SHADES.length] }} />
                ))}
              </div>
              <div className="share-legend t-micro faint">
                <span>New</span>
                <span>Saved</span>
              </div>
            </div>
            <div className="sliders">
              {keys.map((k, i) => {
                const v = w[k] ?? 0;
                const share = sum ? (v / sum) * 100 : 0;
                const d = v - (saved[k] ?? 0);
                return (
                  <div key={k} className="slider">
                    <div className="slider-top">
                      <label htmlFor={`w-${k}`} className="slider-label">
                        <span className="slider-dot" style={{ background: SHADES[i % SHADES.length] }} aria-hidden />
                        {labels[k] ?? k}
                      </label>
                      <span className="slider-val num">
                        {d !== 0 && <span className={d > 0 ? "up" : "down"}>{d > 0 ? `+${d}` : `−${-d}`}</span>}
                        <b>{v}</b>
                        <span className="faint">{Math.round(share)}%</span>
                      </span>
                    </div>
                    <input
                      id={`w-${k}`}
                      type="range"
                      min={0}
                      max={60}
                      step={1}
                      value={v}
                      className="range"
                      style={{ ["--p" as string]: `${(v / 60) * 100}%` }}
                      onChange={(e) => setDraft({ ...w, [k]: Number(e.target.value) })}
                      aria-describedby={help[k] ? `wh-${k}` : undefined}
                    />
                    {help[k] && (
                      <p id={`wh-${k}`} className="slider-help">
                        {help[k]}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="row wrap" style={{ gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={!changed} onClick={() => setDraft({ ...saved })}>
                <RotateCcw /> Back to saved
              </button>
              {q.data?.defaults && (
                <button className="btn btn-ghost btn-sm" disabled={isDefault} onClick={() => setDraft({ ...q.data!.defaults })}>
                  Defaults
                </button>
              )}
              <span className="t-small faint num" style={{ marginLeft: "auto" }}>
                Sum {sum}
              </span>
            </div>
            <ReasonField id="w-why" value={why} onChange={setWhy} placeholder="Why — e.g. competitor pressure matters more after the market event" />
            <div className="col" style={{ gap: 8 }}>
              <button className="btn btn-primary" disabled={problems.length > 0 || save.isPending} onClick={() => save.mutate()}>
                {save.isPending ? "Re-scoring…" : "Save & re-score"}
              </button>
              {problems.length > 0 && changed && <span className="t-small faint">{problems.join(" · ")}</span>}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
