// Stepping through the structure pipeline on page 2 (frontend only: every stage's output is already in /api/structure).
// classify: comments stay where they are; the ones the agent turned into signals light up, the rest dim.
// cluster: comments fly into their clusters (no names yet: those come from context).
// contextualize: themes, their halos and evidence arcs appear. areas: requirement areas float above them.
import type { StructurePayload } from "@/lib/types";

export const STAGES = ["classify", "cluster", "contextualize", "areas"] as const;
export type Stage = (typeof STAGES)[number];
export const STAGE_LABEL: Record<Stage, string> = { classify: "Classify", cluster: "Cluster", contextualize: "Context", areas: "Areas" };

export const atLeast = (s: Stage, t: Stage) => STAGES.indexOf(s) >= STAGES.indexOf(t);

/** Stages whose output this checkpoint has, in order. A ready payload always has classify and cluster. */
export function doneStages(d: StructurePayload | undefined): Stage[] {
  if (!d?.ready) return [];
  return STAGES.filter((s) => s === "classify" || s === "cluster" || !!d.funnel[s]);
}

/** classify view: 1 for comments the agent turned into in-scope signals, 0 for the rest (aligned to the points ids). */
export function classifiedMask(ids: number[], d: StructurePayload): Uint8Array {
  const done = new Set(d.member.ids);
  return Uint8Array.from(ids, (id) => (done.has(id) ? 1 : 0));
}
