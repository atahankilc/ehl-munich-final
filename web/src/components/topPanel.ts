// Which top-right panel is open: the audit trail or (on Definition) the requirements. They share the corner, so
// opening one closes the other. A tiny external store, read with useSyncExternalStore.
import { useSyncExternalStore } from "react";

export type TopPanel = "audit" | "requirements" | "priorities" | null;   // priorities: page 4

let open: TopPanel = null;
const subs = new Set<() => void>();
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };

export function setTopPanel(next: TopPanel | ((cur: TopPanel) => TopPanel)) {
  const v = typeof next === "function" ? next(open) : next;
  if (v === open) return;
  open = v;
  subs.forEach((f) => f());
}
export const getTopPanel = () => open;
export const useTopPanel = () => useSyncExternalStore(subscribe, () => open);
/** open `p`, or close it when it is already open */
export const toggleTopPanel = (p: Exclude<TopPanel, null>) => setTopPanel((cur) => (cur === p ? null : p));
