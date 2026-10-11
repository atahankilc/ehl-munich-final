// The agent at work, bottom-left on page 2, frameless like the checkpoint timeline opposite it: a status line with the
// running stage's count as an instrument numeral, the four stages as one segmented bar (done segments filled, the running
// one filling with its progress), and the agent's latest steps in plain words (one line per AI call, from the audit
// trail), older lines fading. Polls every 2 s while something runs. Hovering (or focusing) a stage swaps the feed for a
// two-line explanation of what that stage does.
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

const STAGE_NAME: Record<string, string> = { classify: "Classify", cluster: "Cluster", contextualize: "Contextualize", areas: "Requirement areas",
  define: "Define", specify: "Specify", couple: "Couple", gate: "Fit gate", prioritize: "Prioritize" };
export type Layer = "structure" | "definition" | "prioritize";
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
    case "start": return e.stage === "areas" ? `Grouping ${n(p.themes)} themes into requirement areas`
      : e.stage === "define" ? `Drafting requirements for ${n(p.to_draft)} areas (${n(p.carried)} carried)`
      : e.stage === "specify" ? `Specifying ${n(p.to_specify)} requirements (${n(p.carried)} carried)`
      : e.stage === "couple" ? `Judging ${n(p.to_judge)} candidate links` : `Reading ${n(p.clusters)} clusters`;
    case "draft": return `Drafted ${n(p.requirements)} requirements from ${n(p.areas)} areas${ex(p)}`;
    case "spec": return `Specified ${n(p.requirements)} requirements${ex(p)}`;
    case "repair": return `Re-asked ${n((p.requirements as unknown[] | undefined)?.length)} requirements that failed checks`;
    case "judge": return `Judged ${n(p.pairs)} pairs → ${n(p.links)} links`;
    case "recheck": return `Re-checked ${n(p.links)} strong links → ${n(p.kept)} kept`;
    case "finish": return e.stage === "define" ? `Wrote ${n(p.requirements)} requirements` : e.stage === "couple" ? `Wrote ${n(p.links)} links` : `Finished ${e.stage}`;
    case "batch_failed": return `A ${e.stage} batch failed; continuing`;
    case "extracted": return `Extracted ${n(p.stored)} benchmark facts`;
    case "gap_research": return `Researched missing benchmarks`;
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

export function useActivity(layer: Layer = "structure") {
  const { cp } = useCheckpoint();
  return useQuery({
    queryKey: ["activity", cp, layer],
    queryFn: () => api.get<Activity>(`/api/structure/activity?cp=${cp}&layer=${layer}`),
    refetchInterval: (q) => (q.state.data?.running ? 2000 : 15000),
  });
}

const SHORT: Record<string, string> = { classify: "Classify", cluster: "Cluster", contextualize: "Context", areas: "Areas",
  define: "Define", specify: "Specify", couple: "Couple", gate: "Gate", prioritize: "Score" };
const DOING: Record<string, string> = { classify: "classified", cluster: "Clustering signals", contextualize: "Adding context", areas: "Finding requirement areas",
  define: "drafted", specify: "specified", couple: "judged", gate: "checked", prioritize: "Scoring targets" };

// what each stage does, condensed (D-043); the visible mark it makes in the volume is named in the second sentence
const EXPLAIN: Record<string, string> = {
  classify: "Reads every comment and splits it into signals: one point about one topic, tagged with one of ~45 shared aspects, gap, like or wish, a strength 1–3 and a quote. Study, research and options get the same aspects.",
  cluster: "Groups signals that say nearly the same thing, across all car lines; likes and complaints never mix. No AI here, just text similarity. Each cluster is a dot: blue to improve, white to keep.",
  contextualize: "Writes one clean need per cluster, merges look-alikes and groups them into themes (the halos). Then links each theme to the research, study and option items that support or contradict it (the arcs).",
  areas: "Groups themes into requirement areas a PM would recognise (the diamonds): the need, improve, keep or emerging, why now, open questions. Pure quality defects go to a separate list. Not requirements yet.",
  define: "Drafts 1–3 requirements per area, each one product decision, with the car lines and markets its evidence supports. Domain and car zone come from the aspects, not the AI. The pins on the car.",
  specify: "Makes each requirement measurable: one metric the customer experiences, acceptance criteria under market conditions, and a ladder per line × market: baseline, threshold, target, stretch. Every number cited, projected or marked a gap.",
  gate: "Checks every requirement for brand and segment fit, and every target for market fit and feasibility (luna, sol re-checks a fail). A brand fail blocks approval unless the PM overrides it.",
  prioritize: "Scores every requirement × line × market target from the evidence (no AI): six weighted factors, × confidence, + effort and market fit; bundles share a band, a moved band becomes a proposal. The skyline.",
  couple: "Finds requirements that draw on the same resource (energy, mass, heat, space, attention…) and judges whether they conflict, compete, enable or help each other. The arcs through the car.",
};

export function AgentPanel({ layer = "structure" }: { layer?: Layer }) {
  const [hot, setHot] = useState<string | null>(null);
  const q = useActivity(layer);
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
          : idle ? <span className="agent-doing">{layer === "definition" ? "Not defined at this checkpoint yet" : layer === "prioritize" ? "Not prioritized at this checkpoint yet" : "Not structured at this checkpoint yet"}</span>
          : <><span className="num">{done}</span><span className="agent-of">/ {a.stages.length} stages done</span></>}
      </p>

      <ol className="agent-stages">
        {a.stages.map((s) => {
          const p = s.progress;
          // a running stage without a count shows a short travelling segment instead of a fill
          const f = s.status === "completed" ? 1 : s.status === "running" ? (p?.total ? p.done / p.total : 0.3) : 0;
          return (
            <li key={s.stage} data-status={s.status} data-hot={hot === s.stage ? "" : undefined} tabIndex={0}
                aria-describedby={hot === s.stage ? "agent-explain" : undefined}
                onPointerEnter={() => setHot(s.stage)} onPointerLeave={() => setHot(null)} onFocus={() => setHot(s.stage)} onBlur={() => setHot(null)}>
              <span className="agent-seg" data-indeterminate={s.status === "running" && !p ? "" : undefined}><i style={{ transform: `scaleX(${f})` }} /></span>
              <span className="agent-name">{SHORT[s.stage] ?? s.stage}</span>
            </li>
          );
        })}
      </ol>

      {/* feed and explanation share one grid cell, so the panel keeps its height and the bar stays under the pointer */}
      <div className="agent-swap">
        {!idle && (
          <ul className="agent-feed" aria-hidden={hot ? true : undefined} data-hidden={hot ? "" : undefined}>
            {a.events.slice(0, 4).map((e) => (
              <li key={e.id}><span>{line(e)}</span><span className="agent-ago">{ago(e.ts, now)}</span></li>
            ))}
          </ul>
        )}
        {hot && <p className="agent-explain" id="agent-explain"><b>{STAGE_NAME[hot] ?? hot}</b> {EXPLAIN[hot] ?? ""}</p>}
      </div>
    </section>
  );
}
