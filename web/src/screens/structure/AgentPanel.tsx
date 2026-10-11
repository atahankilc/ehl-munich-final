// The agent at work, bottom-left on page 2, frameless like the checkpoint timeline opposite it: a status line with the
// running stage's count as an instrument numeral, the four stages as one segmented bar (done segments filled, the running
// one filling with its progress), and the agent's latest steps in plain words (one line per AI call, from the audit
// trail), older lines fading. Polls every 2 s while something runs.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";

interface Activity {
  running: boolean;
  stages: { stage: string; status: string; progress?: { done: number; total: number; unit: string } }[];
  events: { id: number; ts: string; stage: string; action: string; payload: Record<string, unknown>; model: string | null }[];
  recent: number[];
}

const STAGE_NAME: Record<string, string> = { classify: "Classify", cluster: "Cluster", contextualize: "Contextualize", areas: "Requirement areas" };
const n = (v: unknown) => (typeof v === "number" ? v.toLocaleString("en-US") : "");
const ex = (p: Record<string, unknown>) => {
  const e = (p.examples as string[] | undefined)?.[0];
  return e ? ` · “${e}”` : "";
};

export function line(e: { action: string; stage: string; payload: Record<string, unknown> }): string {
  const p = e.payload;
  switch (e.action) {
    case "classify_comments": return `Classified ${n(p.comments)} comments → ${n(p.signals)} signals`;
    case "map_study": return `Mapped ${n(p.items)} study items onto aspects`;
    case "map_options": return `Mapped ${n(p.items)} equipment options onto aspects`;
    case "map_research": return `Read ${n(p.items)} research items`;
    case "clustered": return `Grouped ${n(p.signals)} signals into ${n(p.clusters)} clusters`;
    case "start": return e.stage === "areas" ? `Grouping ${n(p.themes)} themes into requirement areas` : `Reading ${n(p.clusters)} clusters`;
    case "grouped": return `Found ${n(p.areas)} requirement areas${ex(p)}`;
    case "standardize": return `Wrote ${n(p.clusters)} findings${ex(p)}`;
    case "duplicates": return `Checked ${n(p.pairs)} look-alike pairs → ${n(p.merged)} duplicates`;
    case "themes": return `Named ${n(p.themes)} themes${ex(p)}`;
    case "link": return `Linked “${p.theme}” to ${n(p.linked)} of ${n(p.candidates)} sources`;
    default: return e.action.replace(/_/g, " ");
  }
}

function ago(ts: string, now: number) {
  const s = Math.max(0, Math.round((now - Date.parse(ts)) / 1000));
  return s < 60 ? `${s}s` : s < 3600 ? `${Math.round(s / 60)}m` : `${Math.round(s / 3600)}h`;
}

export function useActivity() {
  const { cp } = useCheckpoint();
  return useQuery({
    queryKey: ["activity", cp],
    queryFn: () => api.get<Activity>(`/api/structure/activity?cp=${cp}`),
    refetchInterval: (q) => (q.state.data?.running ? 2000 : 15000),
  });
}

const SHORT: Record<string, string> = { classify: "Classify", cluster: "Cluster", contextualize: "Context", areas: "Areas" };
const DOING: Record<string, string> = { classify: "classified", cluster: "Clustering signals", contextualize: "Adding context", areas: "Finding requirement areas" };

export function AgentPanel() {
  const q = useActivity();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  const a = q.data;
  if (!a) return null;
  const idle = a.stages.every((s) => s.status === "pending");
  const run = a.stages.find((s) => s.status === "running");
  const failed = a.stages.find((s) => s.status === "failed");
  const done = a.stages.filter((s) => s.status === "completed").length;
  const state = run ? "Working" : failed ? "Stopped" : idle ? "Idle" : done === a.stages.length ? "Done" : "Paused";

  return (
    <section className="agent" aria-label="Agent activity" aria-live="polite" data-running={a.running ? "" : undefined}>
      <div className="agent-top">
        <span className="agent-title">Agent</span>
        <span className="agent-state" data-state={state.toLowerCase()}><i aria-hidden />{state}</span>
      </div>

      <p className="agent-now">
        {run?.progress ? (
          <><span className="num">{n(run.progress.done)}</span><span className="agent-of">/ {n(run.progress.total)} {run.progress.unit} {DOING[run.stage] ?? ""}</span></>
        ) : run ? <span className="agent-doing">{DOING[run.stage] ?? STAGE_NAME[run.stage] ?? run.stage}…</span>
          : failed ? <span className="agent-doing">Stopped at {STAGE_NAME[failed.stage] ?? failed.stage}</span>
          : idle ? <span className="agent-doing">Not structured at this checkpoint yet</span>
          : <><span className="num">{done}</span><span className="agent-of">/ {a.stages.length} stages done</span></>}
      </p>

      <ol className="agent-stages">
        {a.stages.map((s) => {
          const p = s.progress;
          // a running stage without a count shows a short travelling segment instead of a fill
          const f = s.status === "completed" ? 1 : s.status === "running" ? (p?.total ? p.done / p.total : 0.3) : 0;
          return (
            <li key={s.stage} data-status={s.status} title={STAGE_NAME[s.stage] ?? s.stage}>
              <span className="agent-seg" data-indeterminate={s.status === "running" && !p ? "" : undefined}><i style={{ transform: `scaleX(${f})` }} /></span>
              <span className="agent-name">{SHORT[s.stage] ?? s.stage}</span>
            </li>
          );
        })}
      </ol>

      {!idle && (
        <ul className="agent-feed">
          {a.events.slice(0, 4).map((e) => (
            <li key={e.id}><span>{line(e)}</span><span className="agent-ago">{ago(e.ts, now)}</span></li>
          ))}
        </ul>
      )}
    </section>
  );
}
