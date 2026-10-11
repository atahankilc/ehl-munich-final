// Page 4 data: the live prioritize payload when the stage has run at this checkpoint, the sample fixture until then
// (polled, so the page switches to live data on its own), plus the PM's writes (decision, proposal verdict).
import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, getActor, queryClient } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import type { Rung } from "@/lib/definition";
import type { Band, PrioritizePayload, Proposal, Target, TargetDetail, WhatIf } from "@/lib/prioritize";
import { BAND_AT, FACTORS, fixtureDetail, fixtureFor, fixtureWhatIf } from "./fixture";
import { getP, setP } from "./store";
import { trackRescore } from "./rescore";

export interface PrioData { data: PrioritizePayload; sample: boolean; why: string | null; pending: boolean }

/** DEV / DEMO ONLY: `?sample=1` in the URL forces the page-4 sample fixture (fixture.ts: PM decisions and proposals,
 *  incl. challenged ones) even while the live API is ready, e.g. for screenshots of the rise / fall marks before any
 *  real PM decision exists. Writes stay local in sample mode (no decision or proposal reaches the API). */
export const sampleForced = () => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("sample") === "1";

export function usePrioritize(): PrioData {
  const { cp } = useCheckpoint();
  const q = useQuery({
    queryKey: ["prioritize", cp],
    queryFn: () => api.get<PrioritizePayload>(`/api/prioritize?cp=${cp}`),
    retry: false, staleTime: 15_000, placeholderData: (prev) => prev,
    refetchInterval: (s) => (s.state.data?.ready && s.state.data.checkpoint === cp ? false : 10_000),
  });
  const fx = useMemo(() => fixtureFor(cp), [cp]);
  return useMemo(() => {
    if (sampleForced()) return { data: fx, sample: true, why: "Forced by ?sample=1 (dev / demo only)", pending: false };
    const live = q.data?.ready && q.data.checkpoint === cp && q.data.targets?.length ? q.data : null;
    if (live) return { data: live, sample: false, why: null, pending: false };
    const why = q.isError ? "Prioritize API not available" : q.data && !q.data.ready ? "The prioritize stage has not run at this checkpoint" : "Waiting for the API";
    return { data: fx, sample: true, why, pending: q.isPending };
  }, [q.data, q.isError, q.isPending, cp, fx]);
}

/* --------------------------------------------------------------------------------------------- derived */
export const bandsAt = (d: PrioritizePayload) => ({ Must: d.weights?.bands?.Must ?? BAND_AT.Must, Should: d.weights?.bands?.Should ?? BAND_AT.Should });
const MARKET_ORDER = ["US", "EU", "CN", "JP", "RoW"];
export function marketsOf(d: PrioritizePayload, line: string): string[] {
  const given = Array.isArray(d.markets) ? null : d.markets?.[line];
  const found = [...new Set(d.targets.filter((t) => t.line === line).map((t) => t.market))];
  const list = given?.length ? [...given, ...found.filter((m) => !given.includes(m))] : found;
  return list.sort((a, b) => (MARKET_ORDER.indexOf(a) + 99) % 99 - (MARKET_ORDER.indexOf(b) + 99) % 99);
}
export function linesOf(d: PrioritizePayload): string[] {
  const found = new Set(d.targets.map((t) => t.line));
  return ["1 Series", "5 Series", "7 Series"].filter((l) => found.has(l));
}
export const tid = (t: Pick<Target, "key" | "line" | "market">) => `${t.key}|${t.line}|${t.market}`;

/** The band the page shows: the PM's (optimistic first), else the AI's proposed band. */
export function shownBand(t: Target): Band {
  return getP().pending[tid(t)] ?? t.confirmed?.priority ?? t.band;
}
/** The PM's band, if decided (optimistic first). */
export function pmBand(t: Target): Band | null {
  return getP().pending[tid(t)] ?? t.confirmed?.priority ?? null;
}

export interface Flag { kind: string; via?: string; partner?: string; band?: string; raw: string }
export function parseFlags(t: Target): Flag[] {
  return t.flags.map((raw) => {
    const [kind, a, b] = raw.split("|");
    if (kind === "choose_jointly") return { kind, via: a, partner: b, raw };
    if (kind === "bundle_band") return { kind, band: a, raw };
    return { kind, raw };
  });
}
export const isBlocked = (t: Target) => t.flags.includes("brand_blocked") || (typeof t.gates?.brand === "string" ? t.gates.brand === "fail" : t.gates?.brand?.result === "fail");

export const FLAG_LABEL: Record<string, string> = {
  choose_jointly: "Choose jointly", brand_blocked: "Brand fit blocks approval", borrowed_voice: "Borrowed customer voice",
  volume_conflict: "BMW vs. public volume conflict", bundle_band: "Band shared with its bundle",
};
export const flagLabel = (k: string) => FLAG_LABEL[k] ?? k.replace(/_/g, " ");
export const CAUSE_LABEL: Record<string, string> = {
  new_fact: "New benchmark fact", area_strengthened: "Customer evidence moved", market_trend: "Market trend",
  link_changed: "Linked requirement moved", pm_rung: "PM changed the rung", weights_changed: "PM changed the weights",
};
export const FACTOR_LABEL: Record<string, string> = Object.fromEntries(FACTORS.map((f) => [f.key, f.label]));
export const factorLabel = (k: string) => FACTOR_LABEL[k] ?? k.replace(/_/g, " ");
export const DIM_LABEL = { customer: "Customer", business: "Business", future: "Future" } as const;
export const CP_LABEL: Record<string, string> = { cp1: "JAN 26", cp2: "JUL 26" };

/** Requirements whose shown band differs between the markets of one line (D-011: markets are different customers). */
export function disagreements(d: PrioritizePayload, line: string): Set<string> {
  const by = new Map<string, Set<Band>>();
  for (const t of d.targets) if (t.line === line) by.set(t.key, (by.get(t.key) ?? new Set()).add(shownBand(t)));
  return new Set([...by].filter(([, s]) => s.size > 1).map(([k]) => k));
}

export function openProposals(d: PrioritizePayload): Proposal[] {
  const pend = getP().pendingProposals;
  return d.proposals.filter((p) => p.status === "open" && !pend[String(p.id)]);
}

/* --------------------------------------------------------------------------------------------- reads */
export function useTargetDetail(t: Target | null, pd: PrioData) {
  const { cp } = useCheckpoint();
  const live = !pd.sample;
  const q = useQuery({
    queryKey: ["prioritize-target", t?.key, t?.line, t?.market, cp],
    queryFn: () => api.get<TargetDetail>(`/api/prioritize/target/${encodeURIComponent(t!.key)}?line=${encodeURIComponent(t!.line)}&market=${encodeURIComponent(t!.market)}&cp=${cp}`),
    enabled: !!t && live, retry: false, staleTime: 15_000,
  });
  return useMemo<TargetDetail | null>(() => {
    if (!t) return null;
    if (live) return q.data ? { ...t, ...q.data } : { ...t, history: [], evidence: {} };
    return fixtureDetail(t);
  }, [t, live, q.data]);
}

export function useWhatIf(t: Target | null, level: Rung | null, pd: PrioData) {
  const { cp } = useCheckpoint();
  const live = !pd.sample;
  const q = useQuery({
    queryKey: ["prioritize-whatif", t?.key, t?.line, t?.market, level, cp],
    queryFn: () => api.get<WhatIf>(`/api/prioritize/what-if?key=${encodeURIComponent(t!.key)}&line=${encodeURIComponent(t!.line)}&market=${encodeURIComponent(t!.market)}&level=${level}&cp=${cp}`),
    enabled: !!t && !!level && live, retry: false, staleTime: 60_000,
  });
  return useMemo(() => {
    if (!t || !level) return { data: null as WhatIf | null, error: null as Error | null, pending: false };
    if (live) return { data: q.data ?? null, error: (q.error as Error) ?? null, pending: q.isPending };
    const title = (k: string) => pd.data.targets.find((x) => x.key === k)?.title;
    return { data: fixtureWhatIf(t, level, title), error: null, pending: false };
  }, [t, level, live, q.data, q.error, q.isPending, pd.data]);
}

/* --------------------------------------------------------------------------------------------- writes */
export function useDecision(pd: PrioData) {
  const { cp } = useCheckpoint();
  return useMutation({
    mutationFn: async (b: { key: string; line: string; market: string; priority: Band; rationale: string }) => {
      setP((s) => ({ pending: { ...s.pending, [`${b.key}|${b.line}|${b.market}`]: b.priority } }));
      if (pd.sample) return { sample: true };
      return api.post("/api/prioritize/decision", { ...b, actor: getActor(), cp });
    },
    onError: (_e, b) => setP((s) => { const p = { ...s.pending }; delete p[`${b.key}|${b.line}|${b.market}`]; return { pending: p }; }),
    onSuccess: async (r, b) => {
      if (pd.sample) return;
      await queryClient.invalidateQueries({ queryKey: ["prioritize", cp] });
      await queryClient.invalidateQueries({ queryKey: ["prioritize-target", b.key] });
      void trackRescore(r);   // the server re-scores the later checkpoints against this band
      setP((s) => { const p = { ...s.pending }; delete p[`${b.key}|${b.line}|${b.market}`]; return { pending: p }; });
    },
  });
}

export function useProposalVerdict(pd: PrioData) {
  const { cp } = useCheckpoint();
  return useMutation({
    mutationFn: async ({ p, verdict, rationale }: { p: Proposal; verdict: "accept" | "reject"; rationale: string }) => {
      setP((s) => ({
        pendingProposals: { ...s.pendingProposals, [String(p.id)]: verdict },
        // accepting a proposal is a PM decision on that band
        pending: verdict === "accept" ? { ...s.pending, [`${p.key}|${p.line}|${p.market}`]: p.proposed_band } : s.pending,
      }));
      if (pd.sample) return { sample: true };
      return api.post(`/api/prioritize/proposal/${encodeURIComponent(String(p.id))}`, { verdict, rationale, actor: getActor() });
    },
    onError: (_e, { p }) => setP((s) => {
      const pp = { ...s.pendingProposals }; delete pp[String(p.id)];
      const pend = { ...s.pending }; delete pend[`${p.key}|${p.line}|${p.market}`];
      return { pendingProposals: pp, pending: pend };
    }),
    onSuccess: async (r, { p }) => {
      if (pd.sample) return;
      await queryClient.invalidateQueries({ queryKey: ["prioritize", cp] });
      void trackRescore(r);
      setP((s) => {
        const pp = { ...s.pendingProposals }; delete pp[String(p.id)];
        const pend = { ...s.pending }; delete pend[`${p.key}|${p.line}|${p.market}`];
        return { pendingProposals: pp, pending: pend };
      });
    },
  });
}
