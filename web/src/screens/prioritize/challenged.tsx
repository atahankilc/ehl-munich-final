// "Your decisions are challenged": a compact, non-modal line in the top-left HUD when the selected checkpoint has OPEN
// proposals against PM-confirmed bands (factor_delta.against = "pm"). Proposals against the AI's own earlier band stay
// passive marks. On arrival at a checkpoint the list is open and the line pulses once (white = attention; none under
// reduced motion); folded it stays a small count until every challenged decision is accepted or rejected. A row opens
// that target's inspector, where the proposal's Accept / Reject box sits.
import { useEffect, useMemo, useState } from "react";
import type { Proposal } from "@/lib/prioritize";
import type { LineName } from "@/lib/definition";
import { useCheckpoint } from "@/state/checkpoint";
import { setView } from "../definition/store";
import { BandMark } from "./marks";
import { CAUSE_LABEL, CP_LABEL, openProposals, type PrioData } from "./data";
import { selectTarget, setP, useP } from "./store";

export function Challenged({ pd }: { pd: PrioData }) {
  const { cp } = useCheckpoint();
  useP((s) => s.pendingProposals);   // an optimistic verdict removes its row at once
  const list = pd.sample ? [] : openProposals(pd.data).filter((p) => p.against === "pm");
  const title = useMemo(() => new Map(pd.data.targets.map((t) => [t.key, t.title])), [pd.data.targets]);
  const [open, setOpen] = useState(true);
  useEffect(() => { setOpen(true); }, [cp]);   // arriving at a checkpoint opens the list again
  if (!list.length) return null;
  const at = CP_LABEL[cp] ?? cp;
  const go = (p: Proposal) => {
    setView({ line: p.line as LineName });
    setP((s) => ({ market: { ...s.market, [p.line]: p.market }, view: "skyline" }));
    selectTarget(p.key);
  };
  return (
    <section className="pchal" key={cp} aria-label="Challenged decisions" aria-live="polite">
      <button className="pchal-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <i className="pchal-dot" aria-hidden />
        <span className="num">{list.length}</span>
        <span>{list.length === 1 ? "of your decisions is" : "of your decisions are"} challenged at {at}</span>
      </button>
      {open && (
        <ul className="pchal-list">
          {list.map((p) => (
            <li key={p.id}>
              <button onClick={() => go(p)} title="Open: accept or reject">
                <span className="pchal-title">{title.get(p.key) ?? p.key}</span>
                <span className="label">{p.line} · {p.market}</span>
                <span className="pchal-move">
                  <BandMark band={p.old_band} color="var(--ink-2)" size="sm" pm />{p.old_band ?? "–"}
                  <span aria-hidden>→</span>
                  <BandMark band={p.proposed_band} color="var(--ink)" size="sm" />{p.proposed_band}
                </span>
                <span className="label">{CAUSE_LABEL[p.cause] ?? p.cause}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
