// Shared bits for the Process screen: PM wording for audit actions and run triggers, the who-chip, small clocks.
import { useEffect, useState } from "react";
import { Bot, Cog, User } from "lucide-react";
import type { ActorType, AuditFacet } from "@/lib/types";

export const ACTION: Record<string, string> = {
  open_wave: "opened a wave",
  start_run: "started a prioritization run",
  finish_run: "finished a run",
  rescore: "re-scored",
  update_evidence_level: "updated the evidence level",
  set_priority: "set a priority",
  set_status: "set the status",
  accept_proposal: "accepted a suggestion",
  reject_proposal: "rejected a suggestion",
  change_weights: "changed the scoring weights",
  override_gate: "overrode a gate",
  challenge: "challenged",
  challenge_response: "answered a challenge",
  edit: "edited",
  edit_evidence: "edited evidence",
  create: "created",
  add_target: "added a car · market",
  link_findings: "linked evidence",
  fit_check: "ran a fit check",
  match_existing: "matched to existing",
  extract_signals: "extracted signals",
  recheck_scope: "re-checked scope",
  web_research: "researched the web",
  build_findings: "built findings",
  build_web_findings: "built web findings",
  ingest: "ingested data",
  restore_snapshot: "restored a demo snapshot",
  assign_waves: "assigned evidence waves",
  budget_reconciliation: "reconciled the budget",
  delete_web_findings: "deleted web findings",
  load_reference: "loaded reference data",
  reverify_quotes: "re-verified quotes",
  view: "viewed",
  export: "exported",
};
export const actionLabel = (a: string) => ACTION[a] ?? a.replace(/_/g, " ");

export const TRIGGER: Record<string, string> = {
  new_evidence: "New evidence",
  weight_change: "Weights changed",
  manual: "Manual",
  initial: "Initial",
  rebuild: "Rebuild",
  demo: "Demo build",
};
export const triggerLabel = (t: string | null | undefined) => (t ? TRIGGER[t] ?? t.replace(/_/g, " ") : "–");

export const ACTOR_TYPE: Record<ActorType, string> = { human: "Product manager", ai: "AI", system: "System · no AI" };

const WHO_ICON = { human: User, ai: Bot, system: Cog } as const;
export function Who({ type, name, size = 26 }: { type: ActorType; name?: string | null; size?: number }) {
  const Icon = WHO_ICON[type] ?? Cog;
  const title = type === "human" ? name || "Product manager" : type === "ai" ? `AI${name ? ` · ${name}` : ""}` : `System${name ? ` · ${name}` : ""}`;
  return (
    <span className={`px-who px-who-${type}`} style={{ width: size, height: size }} title={title}>
      <Icon aria-hidden />
    </span>
  );
}

/** Normalise a facet list from the API (plain values, {value,n} rows or a value→count map). */
export function facetList(f: AuditFacet | undefined): { value: string; n: number | null }[] {
  if (!f) return [];
  if (Array.isArray(f)) {
    return (f as (string | { value: string; n?: number })[]).map((x) => (typeof x === "string" ? { value: x, n: null } : { value: x.value, n: x.n ?? null }));
  }
  return Object.entries(f).map(([value, n]) => ({ value, n: typeof n === "number" ? n : null }));
}

/** Re-renders every `ms` while `on` — for elapsed clocks. */
export function useNow(on: boolean, ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [on, ms]);
  return now;
}

export function fmtElapsed(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

/** Month index for "YYYY-MM" (for placing waves on the timeline). */
export const monthIdx = (s: string) => {
  const [y, m] = s.split("-").map(Number);
  return y * 12 + ((m || 1) - 1);
};

export const clip = (s: string | null | undefined, n = 80) => (s == null ? "" : s.length > n ? `${s.slice(0, n - 1)}…` : s);
