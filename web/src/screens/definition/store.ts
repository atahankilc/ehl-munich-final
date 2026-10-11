// Page-3 view state, shared by the HUD (DOM) and the definition layer inside the canvas without threading props
// through Scan/Scene. A tiny external store read with useSyncExternalStore.
import { useSyncExternalStore } from "react";
import type { ChoosableRung, LineName } from "@/lib/definition";
import type { DefStage } from "./stages";

export type LinkMode = "strong" | "all" | "off";

export interface DefView {
  selected: string | null;        // requirement key
  hover: string | null;           // requirement key under the pointer (pin or list row)
  hoverPos: { x: number; y: number } | null;
  line: LineName;
  domains: string[];              // empty = all
  links: LinkMode;
  bundle: string | null;          // highlighted bundle id
  /** optimistic PM choices, key `${req}|${line}|${market}` → rung (cleared when the server state arrives) */
  pending: Record<string, ChoosableRung>;
  /** optimistic link reviews, link id → verdict */
  pendingLinks: Record<string, "confirmed" | "removed">;
  /** the definition stage in view (stages.ts); set by the funnel, read by the 3D stage layer */
  stage: DefStage;
  /** true while the arrival play steps through the stages on its own */
  auto: boolean;
  /** the arrival's fast run-through (the 3D moves play at double speed) until the PM steps by hand */
  fast: boolean;
  /** area diamond / domain group under the pointer (lights up their requirements) */
  hoverArea: string | null;
  hoverDomain: string | null;
}

const LINE_KEY = "definition.line";
const readLine = (): LineName => {
  try { const v = localStorage.getItem(LINE_KEY); return v === "1 Series" || v === "7 Series" ? v : "5 Series"; } catch { return "5 Series"; }
};

let state: DefView = {
  selected: null, hover: null, hoverPos: null, line: readLine(), domains: [], links: "strong", bundle: null, pending: {}, pendingLinks: {},
  stage: "drafted", auto: false, fast: false, hoverArea: null, hoverDomain: null,
};
const subs = new Set<() => void>();

export function setView(patch: Partial<DefView> | ((s: DefView) => Partial<DefView>)) {
  const p = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...p };
  if (p.line) { try { localStorage.setItem(LINE_KEY, p.line); } catch { /* private mode */ } }
  subs.forEach((f) => f());
}
export const getView = () => state;
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };

export function useView<T>(pick: (s: DefView) => T): T {
  return useSyncExternalStore(subscribe, () => pick(state));
}

export const select = (key: string | null) => setView({ selected: key, hover: null, hoverPos: null });
