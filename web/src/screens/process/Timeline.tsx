// Timeline: the three simulated evidence waves on one instrument track. Opening the next wave is the one paid
// action here — it runs the AI pipeline in the background; everything it produces arrives as proposals.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, Play } from "lucide-react";
import { api, invalidateAll } from "@/lib/api";
import type { Job, WaveRow } from "@/lib/types";
import { useAppState } from "@/lib/hooks";
import { fmtInt, fmtSimDate, fmtUsd, fmtWhen, plural } from "@/lib/format";
import { Drawer } from "@/components/Drawer";
import { ReasonField, reasonOk, useJob } from "@/components/actions";
import { useToast } from "@/components/toast";
import { ErrorNote, Skeleton, SkeletonBlock } from "@/components/ui";
import { fmtElapsed, monthIdx, useNow } from "./common";

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const BROUGHT: { k: "feedback" | "study" | "sales" | "web"; label: string }[] = [
  { k: "feedback", label: "Feedback" },
  { k: "study", label: "Study" },
  { k: "sales", label: "Sales" },
  { k: "web", label: "Web" },
];

const stripWave = (label: string) => label.replace(/^Wave \d+\s*·\s*/, "");

export function Timeline() {
  const q = useQuery({ queryKey: ["waves"], queryFn: () => api.get<WaveRow[]>("/api/waves") });
  const { data: st } = useAppState();
  const [drawer, setDrawer] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobWave, setJobWave] = useState<number | null>(null);
  const runningWave = st?.running_job?.kind === "wave" ? st.running_job.id : null;
  const activeJob = jobId ?? runningWave;
  const job = useJob(activeJob);
  const waves = q.data ?? [];
  const next = waves.find((w) => w.state === "next") ?? null;
  // which wave the job is opening: ours, else the job's own record, else the wave the pipeline just made current
  const jd = job.data as (Job & { meta?: { wave?: number } }) | undefined;
  const openingN = jobWave ?? jd?.meta?.wave ?? (jd?.result as { wave?: number } | null)?.wave ?? null;
  const target = activeJob
    ? waves.find((w) => w.n === openingN) ?? waves.find((w) => w.state === "now") ?? next
    : next;
  const openNext = () => {
    if (job.data && job.data.status !== "running") {
      setJobId(null);
      setJobWave(null);
    }
    setDrawer(true);
  };

  if (q.isLoading)
    return (
      <section className="panel tl" aria-busy>
        <div className="tl-pad">
          <Skeleton h={12} w="30%" />
          <div style={{ height: 26 }} />
          <Skeleton h={2} />
          <div className="tl-cols" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))", marginTop: 26 }}>
            {[0, 1, 2].map((i) => (
              <div key={i} className="tl-col">
                <SkeletonBlock lines={5} />
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  if (!waves.length)
    return (
      <section className="panel tl">
        <div className="tl-pad muted">No evidence waves are configured.</div>
      </section>
    );

  return (
    <>
      <section className="panel tl" aria-labelledby="tl-h">
        <div className="tl-pad">
          <div className="tl-top">
            <h2 id="tl-h" className="tl-h">
              {st?.current_wave ? (
                <>
                  Wave {st.current_wave} of {waves.length}
                  <span className="muted"> · simulated {fmtSimDate(waves.find((w) => w.state === "now")?.simulated_date)}</span>
                </>
              ) : (
                <>No wave opened yet</>
              )}
            </h2>
            {activeJob && job.data?.status === "running" ? (
              <button className="tl-live" onClick={() => setDrawer(true)}>
                <span className="telltale blue pulse">Opening wave {target?.n ?? ""}…</span>
                <span className="faint">Watch progress</span>
              </button>
            ) : (
              <span className="t-small faint">Simulated dates · the real process runs about two years</span>
            )}
          </div>
          <Track waves={waves} />
          <div className="tl-cols" style={{ gridTemplateColumns: `repeat(${waves.length}, minmax(0, 1fr))` }}>
            {waves.map((w) => (
              <WaveColumn key={w.n} w={w} onOpen={openNext} busy={!!st?.running_job} />
            ))}
          </div>
        </div>
        <hr className="rule" />
        <Flow />
        {!next && (
          <>
            <hr className="rule" />
            <div className="tl-foot">
              <Check aria-hidden />
              <span>
                The simulation is complete — all {waves.length} waves are open. To replay it from an earlier point, restore a demo snapshot in{" "}
                <Link to="/process?tab=system">System</Link>.
              </span>
            </div>
          </>
        )}
      </section>
      {target && (
        <OpenWaveDrawer
          wave={target}
          open={drawer}
          onClose={() => setDrawer(false)}
          jobId={activeJob}
          job={job.data ?? null}
          onStarted={(id) => {
            setJobId(id);
            setJobWave(target.n);
          }}
          spend={st?.spend_usd ?? null}
          hardStop={st?.budget.hard_stop ?? 90}
        />
      )}
    </>
  );
}

/* ---------------------------------------------------------------- the instrument track */

function Track({ waves }: { waves: WaveRow[] }) {
  const n = waves.length;
  const first = monthIdx(waves[0].simulated_date);
  const last = monthIdx(waves[n - 1].simulated_date);
  const gap = n > 1 ? (last - first) / (n - 1) : 6;
  const span = gap * n; // wave i sits at i/n — the left edge of its column
  const months = Array.from({ length: Math.round(span) + 1 }, (_, i) => first + i);
  const pos = (m: number) => ((m - first) / span) * 100;
  const nowIdx = waves.findIndex((w) => w.state === "now");
  const fill = nowIdx < 0 ? 0 : pos(monthIdx(waves[nowIdx].simulated_date));
  return (
    <div className="tl-track" aria-hidden>
      <div className="tl-rail" />
      <div className="tl-fill" style={{ width: `${fill}%` }} />
      {months.map((m) => {
        const mo = m % 12;
        return (
          <span key={m} className={`tl-tick${mo === 0 ? " year" : ""}`} style={{ left: `${pos(m)}%` }}>
            {mo === 0 ? <b>{Math.floor(m / 12)}</b> : pos(m) < 99 ? <i>{MONTHS[mo]}</i> : null}
          </span>
        );
      })}
      {waves.map((w) => (
        <span key={w.n} className={`tl-node tl-${w.state}`} style={{ left: `${pos(monthIdx(w.simulated_date))}%` }} />
      ))}
    </div>
  );
}

function WaveColumn({ w, onOpen, busy }: { w: WaveRow; onOpen: () => void; busy: boolean }) {
  const STATE = { done: "Done", now: "Current", next: "Next", later: "Later" } as const;
  const b = w.brought ?? {};
  return (
    <article className={`tl-col tl-${w.state}`} aria-current={w.state === "now" ? "step" : undefined}>
      <div className="tl-col-top">
        <span className="tl-n">Wave {w.n}</span>
        <span className={`tl-state tl-state-${w.state}`}>{STATE[w.state]}</span>
      </div>
      <h3 className="tl-title">{stripWave(w.label)}</h3>
      <div className="tl-date num">{fmtSimDate(w.simulated_date)}</div>
      {w.description && <p className="tl-desc">{w.description}</p>}

      <div className="tl-brought" aria-label="What this wave brought">
        {BROUGHT.map(({ k, label }) => {
          const v = b[k] ?? 0;
          return (
            <div key={k} className={v ? "" : "zero"}>
              <span className="num">{w.state === "done" || w.state === "now" || v ? fmtInt(v) : "–"}</span>
              <small>{label}</small>
            </div>
          );
        })}
      </div>

      <dl className="tl-facts">
        <div>
          <dt>Opened</dt>
          <dd>{w.opened ? <>{w.opened.actor} · {fmtWhen(w.opened.ts)}</> : <span className="faint">{w.state === "next" ? "Waiting for you" : "Not yet"}</span>}</dd>
        </div>
        <div>
          <dt>Run</dt>
          <dd>
            {w.run ? (
              <Link to={`/process?tab=runs&newer=${w.run.id}`} className="tl-run">
                Run {w.run.id} · <span className="num">{fmtInt(w.run.targets_scored)}</span> scored · <span className="num">{fmtInt(w.run.proposals)}</span> proposals
              </Link>
            ) : (
              <span className="faint">–</span>
            )}
          </dd>
        </div>
      </dl>

      {w.state === "next" && (
        <div className="tl-action">
          <button className="btn btn-primary" onClick={onOpen} disabled={busy}>
            <Play /> Open wave {w.n}
          </button>
          <span className="t-small faint">≈ $0.3–1.5 · a few minutes</span>
        </div>
      )}
    </article>
  );
}

/* ---------------------------------------------------------------- what a wave does */

const FLOW: { who: "AI" | "System" | "You"; text: string }[] = [
  { who: "AI", text: "Reads the new evidence" },
  { who: "AI", text: "Drafts requirements, merges repeats" },
  { who: "AI", text: "Links evidence, re-checks fit" },
  { who: "System", text: "Re-scores every car · market" },
  { who: "You", text: "Decide in the queue" },
];

function Flow() {
  return (
    <div className="tl-flow">
      <span className="tl-flow-h">Each wave</span>
      <ol>
        {FLOW.map((f, i) => (
          <li key={i}>
            <span className={`tl-who tl-who-${f.who.toLowerCase()}`}>{f.who}</span>
            <span>{f.text}</span>
            {i < FLOW.length - 1 && <ArrowRight aria-hidden className="tl-flow-arrow" />}
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ---------------------------------------------------------------- open-wave drawer + job progress */

function OpenWaveDrawer({
  wave,
  open,
  onClose,
  jobId,
  job,
  onStarted,
  spend,
  hardStop,
}: {
  wave: WaveRow;
  open: boolean;
  onClose: () => void;
  jobId: string | null;
  job: Job | null;
  onStarted: (id: string) => void;
  spend: number | null;
  hardStop: number;
}) {
  const [why, setWhy] = useState("");
  const toast = useToast();
  const nav = useNavigate();
  const start = useMutation({
    mutationFn: () => api.post<{ job_id: string }>(`/api/waves/${wave.n}/open`, { rationale: why }),
    onSuccess: (r) => {
      onStarted(r.job_id);
      invalidateAll();
    },
    onError: (e: Error) => toast({ tone: "error", title: `Wave ${wave.n} not opened`, body: e.message }),
  });

  const status = job?.status;
  useEffect(() => {
    if (status === "done") {
      invalidateAll();
      toast({ tone: "ok", title: `Wave ${wave.n} is open`, body: "New proposals are waiting in Decide. Recorded in the audit trail." });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const title = jobId ? (status === "done" ? `Wave ${wave.n} is open` : status === "error" ? `Wave ${wave.n} failed` : `Opening wave ${wave.n}`) : `Open wave ${wave.n}`;
  const sub = jobId ? stripWave(wave.label) : `${stripWave(wave.label)} · simulated ${fmtSimDate(wave.simulated_date)}`;

  return (
    <Drawer open={open} onClose={onClose} title={title} sub={sub} width={600}>
      {!jobId && (
        <div className="col" style={{ gap: 20 }}>
          {wave.description && <p className="t-lead">{wave.description}</p>}
          <div>
            <div className="px-label">What happens</div>
            <ol className="ow-steps">
              <li><b>The AI reads the new evidence</b> of this wave — feedback, study, sales or web research.</li>
              <li><b>It drafts new requirements</b> and proposes merging repeated needs into existing ones instead of duplicating them.</li>
              <li><b>It links study and web evidence</b> and re-checks brand, segment, market and plant fit.</li>
              <li><b>Every car · market target is re-scored</b> — deterministic, no AI. Band changes become suggestions.</li>
              <li><b>Nothing is approved or re-prioritized for you.</b> Everything lands in Decide.</li>
            </ol>
          </div>
          <dl className="ow-cost">
            <div>
              <dt>Cost</dt>
              <dd>≈ $0.30–1.50 if uncached; replays hit the cache and are nearly free</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>A few minutes; it runs in the background</dd>
            </div>
            <div>
              <dt>Budget</dt>
              <dd>
                {spend == null ? "–" : <><span className="num">{fmtUsd(spend)}</span> spent · hard stop at ${hardStop}</>}
              </dd>
            </div>
          </dl>
          <ReasonField id="ow-why" value={why} onChange={setWhy} placeholder="Why now — e.g. the six-month evidence refresh is in" autoFocus />
          <div className="row">
            <button className="btn btn-primary" disabled={!reasonOk(why) || start.isPending} onClick={() => start.mutate()}>
              <Play /> {start.isPending ? "Starting…" : `Open wave ${wave.n}`}
            </button>
            <button className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {jobId && !job && <SkeletonBlock lines={5} />}
      {jobId && job && <JobProgress job={job} onDecide={() => nav("/decide")} onRuns={() => { onClose(); nav("/process?tab=runs"); }} />}
    </Drawer>
  );
}

function JobProgress({ job, onDecide, onRuns }: { job: Job; onDecide: () => void; onRuns: () => void }) {
  const running = job.status === "running";
  const now = useNow(running);
  const started = new Date(job.started_at).getTime();
  const ended = job.finished_at ? new Date(job.finished_at).getTime() : now;
  const listRef = useRef<HTMLOListElement>(null);
  const lines = useMemo(
    () =>
      job.log.map((l) => {
        const m = /^(info|warning|warn|error|debug):\s*/i.exec(l);
        const lvl = m ? m[1].toLowerCase() : "";
        return { text: m ? l.slice(m[0].length) : l, tone: lvl.startsWith("warn") ? "warn" : lvl === "error" ? "error" : "" };
      }),
    [job.log],
  );
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);
  const res = (job.result ?? null) as { new_requirements?: string[]; run_id?: number | null } | null;

  return (
    <div className="col" style={{ gap: 18 }}>
      <div className="job-head">
        {running && <span className="telltale blue pulse">The AI is working through the new evidence</span>}
        {job.status === "done" && <span className="telltale green">Done</span>}
        {job.status === "error" && <span className="telltale red">Stopped with an error</span>}
        <span className="job-clock num" title="Elapsed">{fmtElapsed(ended - started)}</span>
      </div>
      {running && <div className="job-bar" aria-hidden><i /></div>}

      {job.status === "done" && (
        <div className="job-done">
          <div className="job-done-n">
            <span className="instrument">{res?.new_requirements?.length ?? 0}</span>
            <span className="muted">new requirement{(res?.new_requirements?.length ?? 0) === 1 ? "" : "s"} to review</span>
          </div>
          <p className="muted t-small">
            {res?.run_id ? <>Prioritization run {res.run_id} re-scored every target. </> : null}
            Merges, new requirements and priority changes are suggestions — they wait for you in Decide.
          </p>
          <div className="row wrap">
            <button className="btn btn-primary" onClick={onDecide}>
              Go to Decide <ArrowRight />
            </button>
            <button className="btn btn-ghost" onClick={onRuns}>
              See what changed
            </button>
          </div>
        </div>
      )}
      {job.status === "error" && (
        <div className="errnote" role="alert">
          <span className="errnote-msg">{job.error ?? "The job failed."}</span>
        </div>
      )}

      <div>
        <div className="px-label">
          Pipeline log <span className="faint num">· {plural(lines.length, "line")}</span>
        </div>
        <ol className="job-log" ref={listRef} aria-live="polite">
          {lines.length === 0 && <li className="faint">Waiting for the first step…</li>}
          {lines.map((l, i) => (
            <li key={i} className={`${l.tone}${i === lines.length - 1 && running ? " latest" : ""}`}>
              {l.text}
            </li>
          ))}
        </ol>
        {running && <p className="t-small faint" style={{ marginTop: 10 }}>You can close this — the job keeps running and the top band shows its progress.</p>}
      </div>
    </div>
  );
}
