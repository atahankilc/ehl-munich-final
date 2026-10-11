// The checkpoint is app-wide state: every screen reads what is visible at the current checkpoint, and every screen
// can animate the change from the previous one (the sweep). The URL (?cp=) is the source of truth so a view can be
// linked; ← / → step between checkpoints anywhere in the app.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import type { Checkpoint, CheckpointId } from "@/lib/types";

const ORDER: CheckpointId[] = ["cp1", "cp2"];
const isCp = (v: string | null): v is CheckpointId => v === "cp1" || v === "cp2";

interface Ctx {
  cp: CheckpointId;
  from: CheckpointId;        // checkpoint before the latest switch (equals cp when settled)
  sweepId: number;           // increments on every switch; screens restart their sweep on change
  setCp: (cp: CheckpointId) => void;
  checkpoints: Checkpoint[] | undefined;
  current: Checkpoint | undefined;
  position: number;          // 1 | 2
}

const CheckpointCtx = createContext<Ctx | null>(null);

export function CheckpointProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const urlCp = params.get("cp");
  // No checkpoint in the URL: open at the first one and play the sweep to the latest once (the signature moment).
  const arrival = useRef(!isCp(urlCp));
  const cp: CheckpointId = isCp(urlCp) ? urlCp : "cp1";
  const prev = useRef<CheckpointId>(cp);
  const [from, setFrom] = useState<CheckpointId>(cp);
  const [sweepId, setSweepId] = useState(0);
  const { data: checkpoints } = useQuery({ queryKey: ["checkpoints"], queryFn: () => api.get<Checkpoint[]>("/api/checkpoints") });

  useEffect(() => {
    if (prev.current !== cp) {
      setFrom(prev.current);
      setSweepId((n) => n + 1);
      prev.current = cp;
    }
  }, [cp]);

  const setCp = useCallback(
    (next: CheckpointId) => {
      setParams((p) => { const q = new URLSearchParams(p); q.set("cp", next); return q; }, { replace: true });
    },
    [setParams],
  );

  useEffect(() => {
    if (!arrival.current || !checkpoints) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const t = window.setTimeout(() => { arrival.current = false; setCp(ORDER[ORDER.length - 1]); }, reduced ? 0 : 1200);
    return () => window.clearTimeout(t);
  }, [checkpoints, setCp]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && e.target.closest("input, textarea, [contenteditable]")) return;
      const i = ORDER.indexOf(cp);
      if (e.key === "ArrowRight" && i < ORDER.length - 1) setCp(ORDER[i + 1]);
      if (e.key === "ArrowLeft" && i > 0) setCp(ORDER[i - 1]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cp, setCp]);

  const value = useMemo<Ctx>(() => {
    const current = checkpoints?.find((c) => c.id === cp);
    return { cp, from, sweepId, setCp, checkpoints, current, position: ORDER.indexOf(cp) + 1 };
  }, [cp, from, sweepId, setCp, checkpoints]);

  return <CheckpointCtx.Provider value={value}>{children}</CheckpointCtx.Provider>;
}

export function useCheckpoint(): Ctx {
  const c = useContext(CheckpointCtx);
  if (!c) throw new Error("useCheckpoint outside CheckpointProvider");
  return c;
}

export const CHECKPOINT_ORDER = ORDER;
