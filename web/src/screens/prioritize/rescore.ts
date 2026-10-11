// The automatic re-score after a PM action (api/rescore.py): every PM write on pages 3–4 hands its response to
// `trackRescore`; when the server queued a re-score, poll until it is idle, then refetch page 4 (every checkpoint) so
// new proposals and ▲▼ show without a reload. `useRescoring` drives the HUD's quiet "re-scoring…" state.
import { useSyncExternalStore } from "react";
import { api, queryClient } from "@/lib/api";

let busy = false;
const subs = new Set<() => void>();
const setBusy = (v: boolean) => { if (v !== busy) { busy = v; subs.forEach((f) => f()); } };
export const useRescoring = () => useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, () => busy);

let polling = 0;
export async function trackRescore(resp: unknown) {
  const rs = (resp as { rescore?: string } | null)?.rescore;
  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["prioritize"] }),
    queryClient.invalidateQueries({ queryKey: ["prioritize-target"] }),
    queryClient.invalidateQueries({ queryKey: ["prioritize-whatif"] }),
  ]);
  if (rs !== "queued") { if (rs === "sync") await refresh(); return; }
  const me = ++polling;
  setBusy(true);
  const end = Date.now() + 30_000;
  try {
    while (Date.now() < end && me === polling) {
      await new Promise((r) => setTimeout(r, 400));
      const s = await api.get<{ state: string }>("/api/prioritize/rescore").catch(() => ({ state: "idle" }));
      if (s.state === "idle") break;
    }
  } finally {
    if (me === polling) { await refresh(); setBusy(false); }
  }
}
