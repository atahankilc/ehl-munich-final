// Page 3's stage funnel and stepper, built like page 2's (same classes, same [ and ] keys): requirements (the
// page-2 areas split) → specified → links → on the car. Arriving on the page runs through the stages quickly to the
// last one, like the page 1 → 2 morph (skippable); stepping back then peels them off one by one at full length.
// The 3D side reads the stage from the store (StageLayer).
import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { StructurePayload } from "@/lib/types";
import { useCheckpoint } from "@/state/checkpoint";
import { StateMark } from "../structure/panels";
import { linkVerdict, type DefData } from "./data";
import { setView, useView } from "./store";
import { DEF_STAGE_LABEL, defAtLeast, defDoneStages, type DefStage } from "./stages";
import { getP } from "../prioritize/store";

const fmt = (n: number | undefined | null) => (n == null ? "–" : n.toLocaleString("en-US"));

const STEP_NOTE: Record<DefStage, string> = {
  drafted: "Each requirement area from Structure split into requirements, grouped by vehicle domain",
  specified: "Each requirement gets a measurable target; ? marks an open gap",
  linked: "Requirements that help or compete with each other",
  car: "Every requirement where the customer feels it on today's car",
};
// how long the arrival run-through holds each stage before the next (ms): just long enough for its (double-speed)
// move to read; drafted includes the rise out of page 2's ring
const HOLD: Record<DefStage, number> = { drafted: 1500, specified: 550, linked: 900, car: 0 };

export function useStructure() {
  const { cp } = useCheckpoint();
  return useQuery({ queryKey: ["structure", cp], queryFn: () => api.get<StructurePayload>(`/api/structure?cp=${cp}`),
                    staleTime: 30_000, placeholderData: (prev) => prev });
}

export function DefinitionFunnel({ def }: { def: DefData }) {
  const { position } = useCheckpoint();
  const structure = useStructure().data;
  const st = structure?.ready ? structure : undefined;
  const line = useView((s) => s.line);
  const stored = useView((s) => s.stage);
  const auto = useView((s) => s.auto);
  useView((s) => s.pendingLinks);
  const doneKey = defDoneStages(def).join(",");
  // keyed by its contents: a refetch of the same payload must not restart the arrival play's timer
  const done = useMemo(() => (doneKey ? doneKey.split(",") as DefStage[] : []), [doneKey]);
  const stage: DefStage = done.includes(stored) ? stored : done[done.length - 1] ?? "car";
  const doneRef = useRef(done);
  doneRef.current = done;
  // the story moves play like page 2's morph, which ignores reduced motion too: the motion is the explanation
  // (only the decorative CSS pulses honour it)
  const reduced = false;

  // keep the store on a stage this checkpoint has
  useEffect(() => { if (done.length && stored !== stage) setView({ stage }); }, [done, stored, stage]);

  // arrival: run through the stages from the split to the last one
  const ready = done.length > 0;
  useEffect(() => {
    if (!ready) return;
    const ds = doneRef.current;
    // coming back from page 4 (its skyline is still landing on the car) the page stays on the car: no replay
    if (reduced || ds.length < 2 || getP().out) setView({ stage: ds[ds.length - 1], auto: false });
    else setView({ stage: ds[0], auto: true, fast: true });
    return () => setView({ auto: false, fast: false, hoverArea: null, hoverDomain: null });
  }, [ready, reduced]);
  useEffect(() => {
    if (!auto) return;
    const i = done.indexOf(stage);
    if (i < 0 || i >= done.length - 1) { setView({ auto: false }); return; }
    const t = window.setTimeout(() => setView({ stage: done[i + 1], auto: i + 1 < done.length - 1 }), HOLD[stage]);
    return () => window.clearTimeout(t);
  }, [auto, stage, done]);

  // a hand step ends the run-through: from here every move plays at full length
  const go = (s: DefStage) => setView({ stage: s, auto: false, fast: false });
  const step = (d: -1 | 1) => { const i = done.indexOf(stage) + d; if (i >= 0 && i < done.length) go(done[i]); else setView({ auto: false }); };
  // [ and ] step back and forward on page 3 too (the arrow keys belong to the checkpoints)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && (e.target as HTMLInputElement).type !== "range")) return;
      if (e.key === "[") step(-1);
      if (e.key === "]") step(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* the numbers */
  const reqs = def.data.requirements.filter((r) => r.lines.includes(line));
  const keys = new Set(reqs.map((r) => r.key));
  const rows = reqs.flatMap((r) => r.ladder.filter((x) => x.line === line));
  const levels = rows.flatMap((x) => [x.baseline, x.threshold, x.target, x.stretch]);
  const gaps = levels.filter((l) => l?.basis === "gap").length;
  const cited = levels.filter((l) => l?.basis === "cited").length;
  const links = def.data.links.filter((l) => keys.has(l.a) && keys.has(l.b) && linkVerdict(l) !== "removed");
  const bundles = def.data.bundles.filter((b) => b.keys.some((k) => keys.has(k))).length;
  const placed = reqs.filter((r) => r.zones.some((z) => def.data.zones[z]));
  const zones = new Set(placed.map((r) => r.zones.find((z) => def.data.zones[z]))).size;
  const later = position > 1;
  const nu = (xs: { state: string | null }[]) => (later ? xs.filter((x) => x.state === "new").length : 0);
  const moved = (xs: { state: string | null }[]) => (later ? xs.filter((x) => x.state === "changed" || x.state === "strengthened").length : 0);
  const cells: { stage: DefStage; label: string; n: number | undefined; nu?: number; ch?: number; note?: string[] }[] = [
    { stage: "drafted", label: "Requirements", n: reqs.length, nu: nu(reqs),
      note: st ? [`from ${fmt(new Set(reqs.map((r) => r.area_key)).size)} areas`] : undefined },
    { stage: "specified", label: "Specified", n: reqs.filter((r) => r.ladder.some((x) => x.line === line)).length, ch: moved(reqs),
      note: [`${fmt(gaps)} gaps`, `${fmt(cited)} cited`] },
    { stage: "linked", label: "Links", n: links.length, nu: nu(links), note: [`${fmt(bundles)} bundles`] },
    { stage: "car", label: "On the car", n: placed.length, note: [`${fmt(zones)} zones`] },
  ];
  const at = done.indexOf(stage);

  return (
    <div className="funnel-wrap dfunnel">
      <dl className="funnel" aria-label="How the requirement areas became requirements on the car">
        {cells.map((c, i) => (
          <div key={c.stage} className="funnel-cell" data-ahead={!defAtLeast(stage, c.stage) ? "" : undefined} data-current={c.stage === stage ? "" : undefined}>
            <dt className="label">
              <button type="button" className="funnel-pick" disabled={!done.includes(c.stage)} aria-pressed={c.stage === stage}
                      onClick={() => go(c.stage)} title={`Show the requirements after ${DEF_STAGE_LABEL[c.stage]}`}>{c.label}</button>
            </dt>
            <dd>
              <span className="num">{done.includes(c.stage) ? fmt(c.n) : "–"}</span>
              {((c.nu ?? 0) > 0 || (c.ch ?? 0) > 0) && (
                <span className="funnel-delta">
                  {(c.nu ?? 0) > 0 && <span><StateMark state="new" />{c.nu}</span>}
                  {(c.ch ?? 0) > 0 && <span><StateMark state="strengthened" />{c.ch}</span>}
                </span>
              )}
            </dd>
            {c.note && done.includes(c.stage) && <dd className="dfunnel-note">{c.note.map((t) => <span key={t}>{t}</span>)}</dd>}
            {i < cells.length - 1 && <svg className="funnel-arrow" width="18" height="10" viewBox="0 0 18 10" aria-hidden><path d="M0 5h15M11 1l4 4-4 4" fill="none" stroke="currentColor" /></svg>}
          </div>
        ))}
      </dl>
      <div className="funnel-step" role="group" aria-label="Step through the stages">
        <button type="button" onClick={() => step(-1)} disabled={at <= 0} aria-label="Previous stage" title="Previous stage ([)"><ChevronLeft size={14} /></button>
        <span className="funnel-step-n num">{at + 1}/{done.length}</span>
        <button type="button" onClick={() => step(1)} disabled={at >= done.length - 1} aria-label="Next stage" title="Next stage (])"><ChevronRight size={14} /></button>
        <span className="funnel-step-name">{DEF_STAGE_LABEL[stage]}</span>
        <span className="funnel-step-note" aria-live="polite">{STEP_NOTE[stage]}</span>
        {auto && <button type="button" className="dfunnel-skip" onClick={() => setView({ stage: done[done.length - 1], auto: false })}>Skip</button>}
      </div>
      <AreaHover def={def} structure={st} />
    </div>
  );
}

/** Hovering a diamond while it rises and splits: its title and what it became. */
function AreaHover({ def, structure }: { def: DefData; structure: StructurePayload | undefined }) {
  const key = useView((s) => s.hoverArea);
  const pos = useView((s) => s.hoverPos);
  const line = useView((s) => s.line);
  if (!key || !pos || !structure) return null;
  const a = structure.areas.find((x) => x.key === key);
  if (!a) return null;
  const kids = def.data.requirements.filter((r) => r.area_key === key && r.lines.includes(line));
  const left = Math.min(pos.x + 16, window.innerWidth - 336), top = Math.min(pos.y + 16, window.innerHeight - 160);
  return (
    <div className="hovercard" style={{ left, top }} role="tooltip">
      <p>{a.title}</p>
      <div className="hovercard-meta">
        <span>{a.kind === "quality" ? "Quality hand-over" : `Requirement area · ${a.kind}`}</span>
        <span>{kids.length ? `→ ${kids.length} requirement${kids.length > 1 ? "s" : ""}` : "no requirement drafted"}</span>
      </div>
    </div>
  );
}

