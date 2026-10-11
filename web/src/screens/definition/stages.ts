// Stepping through the definition layer on page 3 (frontend only: every stage's output is already in /api/definition).
// drafted: arriving from page 2, the requirement-area diamonds rise from their Structure ring as the volume sinks away
//          and, still rising, burst into their requirements, which settle into one group per vehicle domain.
// specified: each requirement shows its recommended target; a "?" marks open gaps.
// linked: the couplings between requirements appear as arcs between the groups.
// car: today's car rises and every requirement flies to its zone on it.
import type { DefData } from "./data";

export const DEF_STAGES = ["drafted", "specified", "linked", "car"] as const;
export type DefStage = (typeof DEF_STAGES)[number];
export const DEF_STAGE_LABEL: Record<DefStage, string> = {
  drafted: "Drafted", specified: "Specified", linked: "Linked", car: "On the car",
};

export const defAtLeast = (s: DefStage, t: DefStage) => DEF_STAGES.indexOf(s) >= DEF_STAGES.indexOf(t);

/** Stages whose output this checkpoint has, in order; all of them need drafted requirements. */
export function defDoneStages(def: DefData): DefStage[] {
  const d = def.data;
  const has = d.requirements.length > 0;
  return DEF_STAGES.filter((s) => {
    if (!has) return false;
    if (s === "specified") return def.sample || !!d.runs.specify || d.requirements.some((r) => r.ladder.length > 0);
    if (s === "linked") return def.sample || !!d.runs.couple || d.links.length > 0;
    return true;
  });
}
