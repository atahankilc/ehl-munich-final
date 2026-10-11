// Page 3 data: the live definition payload when the pipeline has run at this checkpoint, the sample fixture until then.
import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, getActor, queryClient } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import type {
  ChoiceBody, ChoosableRung, DefinitionPayload, DefLink, LadderRow, LineName, LinkReviewBody, Requirement, RequirementDetail,
} from "@/lib/definition";
import { bundlesOf, fixtureDetail, fixtureFor } from "./fixture";
import { getView, setView } from "./store";
import { trackRescore } from "../prioritize/rescore";

export const LINES: LineName[] = ["1 Series", "5 Series", "7 Series"];

/** One categorical hue per vehicle domain, validated on black; never sweep blue, never loss amber. */
export const DOMAIN_COLOR: Record<string, string> = {
  exterior: "#d95926",   // vermilion
  interior: "#199e70",   // aqua green
  powertrain: "#c98500", // ochre
  chassis: "#d55181",    // magenta
  assist: "#9b72e8",     // violet
  digital: "#1fa8b8",    // teal
  variants: "#a08a78",   // taupe
  quality: "#8f9a5a",    // olive
};
export const domainColor = (d: string) => DOMAIN_COLOR[d] ?? "#b4bac4";

export const RELATION_NAME: Record<string, string> = {
  conflicts: "Conflicts", competes_for: "Competes for", enables: "Enables", synergy: "Synergy",
};
export const isDashed = (r: string) => r === "conflicts" || r === "competes_for";

export interface DefData {
  data: DefinitionPayload;
  sample: boolean;            // true: fixture (API missing or not ready at this checkpoint)
  why: string | null;         // why the sample is shown
  pending: boolean;
}

export function useDefinition(): DefData {
  const { cp } = useCheckpoint();
  const q = useQuery({
    queryKey: ["definition", cp],
    queryFn: () => api.get<DefinitionPayload>(`/api/definition?cp=${cp}`),
    retry: false, staleTime: 15_000, placeholderData: (prev) => prev,
    // keep asking while the pipeline is still filling it, so the page switches to live data on its own
    refetchInterval: (s) => (s.state.data?.ready && s.state.data.checkpoint === cp ? false : 10_000),
  });
  return useMemo(() => {
    const live = q.data?.ready && q.data.checkpoint === cp ? q.data : null;
    if (live) return { data: { ...live, bundles: live.bundles ?? bundlesOf(live.links) }, sample: false, why: null, pending: false };
    const fx = fixtureFor(cp);
    // the zones and models of the live payload are real even before the pipeline has run
    if (q.data?.zones && Object.keys(q.data.zones).length) fx.zones = q.data.zones;
    if (q.data?.models && Object.keys(q.data.models).length) fx.models = { ...fx.models, ...q.data.models };
    const why = q.isError ? "Definition API not available" : q.data && !q.data.ready ? "Pipeline has not run at this checkpoint" : "Waiting for the API";
    return { data: fx, sample: true, why, pending: q.isPending };
  }, [q.data, q.isError, q.isPending, cp]);
}

export function useRequirementDetail(key: string | null, def: DefData) {
  const { cp } = useCheckpoint();
  const live = !def.sample;
  const q = useQuery({
    queryKey: ["definition-req", key, cp],
    queryFn: () => api.get<RequirementDetail>(`/api/definition/requirement/${encodeURIComponent(key!)}?cp=${cp}`),
    enabled: !!key && live, retry: false, staleTime: 15_000,
  });
  return useMemo(() => {
    if (!key) return null;
    if (live && q.data) return q.data;
    const r = def.data.requirements.find((x) => x.key === key);
    return r ? (live ? { ...r, evidence: [], facts: [], area: null, history: [] } as RequirementDetail : fixtureDetail(r)) : null;
  }, [key, live, q.data, def.data]);
}

/* --------------------------------------------------------------------------------------------- derived */
export const rowKey = (req: string, r: Pick<LadderRow, "line" | "market">) => `${req}|${r.line}|${r.market}`;

/** The rung the PM chose (optimistic first), or null. */
export function chosenRung(req: string, r: LadderRow): ChoosableRung | null {
  return getView().pending[rowKey(req, r)] ?? r.choice?.level ?? null;
}

export function linkVerdict(l: DefLink): "confirmed" | "removed" | "added" | null {
  return getView().pendingLinks[String(l.id)] ?? l.review?.verdict ?? null;
}

/** First ladder row for the line (the one shown on the pin and in the list). */
export const rowFor = (r: Requirement, line: string) => r.ladder.find((x) => x.line === line) ?? null;

export function fmtLevel(v: number | null | undefined, unit: string | undefined) {
  if (v == null) return "?";
  const n = Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en-US") : String(Math.round(v * 10) / 10);
  if (!unit) return n;
  return unit.startsWith("%") || unit === "/ 10" ? `${n}${unit === "/ 10" ? "" : "%"}` : `${n} ${unit}`;
}

/* --------------------------------------------------------------------------------------------- writes */
export function useChoice(def: DefData) {
  const { cp } = useCheckpoint();
  return useMutation({
    mutationFn: async (b: Omit<ChoiceBody, "actor">) => {
      setView((s) => ({ pending: { ...s.pending, [`${b.key}|${b.line}|${b.market}`]: b.level } }));
      if (def.sample) return { sample: true };
      return api.post("/api/definition/choice", { ...b, actor: getActor() });
    },
    onError: (_e, b) => setView((s) => { const p = { ...s.pending }; delete p[`${b.key}|${b.line}|${b.market}`]; return { pending: p }; }),
    onSuccess: async (r, b) => {
      if (def.sample) return;
      await queryClient.invalidateQueries({ queryKey: ["definition", cp] });
      await queryClient.invalidateQueries({ queryKey: ["definition-req", b.key] });
      void trackRescore(r);   // a new rung re-scores page 4 in the background
      setView((s) => { const p = { ...s.pending }; delete p[`${b.key}|${b.line}|${b.market}`]; return { pending: p }; });
    },
  });
}

export function useLinkReview(def: DefData) {
  const { cp } = useCheckpoint();
  return useMutation({
    mutationFn: async ({ link, ...b }: Omit<LinkReviewBody, "actor"> & { link: DefLink }) => {
      if (b.verdict !== "added") setView((s) => ({ pendingLinks: { ...s.pendingLinks, [String(link.id)]: b.verdict as "confirmed" | "removed" } }));
      if (def.sample) return { sample: true };
      return api.post("/api/definition/link-review", { ...b, actor: getActor() });
    },
    onError: (_e, { link }) => setView((s) => { const p = { ...s.pendingLinks }; delete p[String(link.id)]; return { pendingLinks: p }; }),
    onSuccess: async (r, { link }) => {
      if (def.sample) return;
      await queryClient.invalidateQueries({ queryKey: ["definition", cp] });
      void trackRescore(r);
      setView((s) => { const p = { ...s.pendingLinks }; delete p[String(link.id)]; return { pendingLinks: p }; });
    },
  });
}
