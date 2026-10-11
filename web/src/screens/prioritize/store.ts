// Page-4 view state, shared by the HUD (DOM) and the skyline inside the canvas. The car line is page 3's (the car
// on stage is the same object), so it lives in the definition store; the market, selection and view live here.
import { useSyncExternalStore } from "react";
import type { Band } from "@/lib/prioritize";

export type PrioView = "skyline" | "matrix";

export interface PView {
  /** market per car line (each line has its own markets) */
  market: Record<string, string>;
  selected: string | null;            // requirement key (the target is key × line × market)
  hover: string | null;
  hoverPos: { x: number; y: number } | null;
  view: PrioView;
  bundle: string | null;              // highlighted bundle id
  /** optimistic PM decisions, `${key}|${line}|${market}` → band */
  pending: Record<string, Band>;
  /** optimistic proposal verdicts, proposal id → verdict */
  pendingProposals: Record<string, "accept" | "reject">;
  /** the skyline is (partly) off the car: page 3 keeps its pins hidden until the columns have landed back */
  out: boolean;
}

const MARKET_KEY = "prioritize.market";
const readMarket = (): Record<string, string> => {
  try { const v = JSON.parse(localStorage.getItem(MARKET_KEY) ?? "{}"); return v && typeof v === "object" ? v : {}; } catch { return {}; }
};

let state: PView = {
  market: readMarket(), selected: null, hover: null, hoverPos: null, view: "skyline", bundle: null, pending: {}, pendingProposals: {}, out: false,
};
const subs = new Set<() => void>();

export function setP(patch: Partial<PView> | ((s: PView) => Partial<PView>)) {
  const p = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...p };
  if (p.market) { try { localStorage.setItem(MARKET_KEY, JSON.stringify(p.market)); } catch { /* private mode */ } }
  subs.forEach((f) => f());
}
export const getP = () => state;
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };
export function useP<T>(pick: (s: PView) => T): T {
  return useSyncExternalStore(subscribe, () => pick(state));
}
export const selectTarget = (key: string | null) => setP({ selected: key, hover: null, hoverPos: null });
