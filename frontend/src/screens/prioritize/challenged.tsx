// "Your decisions are challenged": a non-modal block in the top-left HUD when the selected checkpoint has OPEN proposals
// against PM-confirmed bands (against = "pm"). Proposals against the AI's own earlier band stay passive marks.
// Rise / Fall (PM request 2026-10-11): two groups, downgrades first in red ("▼ N downgrades — review": the AI now places
// a confirmed target BELOW the PM's band), then upgrade opportunities in green ("▲ N upgrade opportunities"). On arrival
// at a checkpoint the list is open and the head pulses once (none under reduced motion); folded it stays a count until
// every challenged decision is accepted or rejected. A row opens that target's inspector, whose top banner carries the
// Accept / Reject box.
import { useEffect, useMemo, useState } from "react";
import type { LineName } from "@/lib/definition";
import { useCheckpoint } from "@/state/checkpoint";
import { setView } from "../definition/store";
import { BandMark } from "./marks";
import { CP_LABEL, type PrioData } from "./data";
import { challengedAll, type RiseFall } from "./pm";
import { selectTarget, setP, useP } from "./store";
import type { Target } from "@/lib/prioritize";

type Row = RiseFall & { t: Target };

export function Challenged({ pd }: { pd: PrioData }) {
  const { cp } = useCheckpoint();
  useP((s) => s.pendingProposals);   // an optimistic verdict removes its row at once
  useP((s) => s.pending);
  const list = challengedAll(pd.data);
  const downs = useMemo(() => list.filter((r) => r.dir === "down"), [list]);
  const ups = useMemo(() => list.filter((r) => r.dir === "up"), [list]);
  const [openState, setOpen] = useState(true);
  // the matrix hangs under the HUD: while it is up the groups fold to their counts (▼ n ▲ n) to leave it the room
  const matrix = useP((s) => s.view === "matrix");
  const open = openState && !matrix;
  useEffect(() => { setOpen(true); }, [cp]);   // arriving at a checkpoint opens the list again
  if (!list.length) return null;
  const at = CP_LABEL[cp] ?? cp;
  const go = (r: Row) => {
    setView({ line: r.t.line as LineName });
    setP((s) => ({ market: { ...s.market, [r.t.line]: r.t.market }, view: "skyline" }));
    selectTarget(r.t.key);
  };
  return (
    <section className="pchal" key={cp} aria-label="Challenged decisions" aria-live="polite" data-rf={downs.length ? "down" : "up"}>
      <button className="pchal-head" aria-expanded={open} onClick={() => { if (matrix) { setP({ view: "skyline" }); setOpen(true); } else setOpen((o) => !o); }}>
        <i className="pchal-dot" data-rf={downs.length ? "down" : "up"} aria-hidden />
        <span className="num">{list.length}</span>
        <span>{list.length === 1 ? "of your decisions is" : "of your decisions are"} challenged at {at}</span>
        {!open && <span className="pchal-fold">{downs.length > 0 && <b data-rf="down">▼ {downs.length}</b>}{ups.length > 0 && <b data-rf="up">▲ {ups.length}</b>}</span>}
      </button>
      {open && (
        <>
          {downs.length > 0 && <Group dir="down" rows={downs} go={go}
                                      head={<><b>▼ {downs.length}</b> {downs.length === 1 ? "downgrade" : "downgrades"} — review</>} />}
          {ups.length > 0 && <Group dir="up" rows={ups} go={go}
                                    head={<><b>▲ {ups.length}</b> upgrade {ups.length === 1 ? "opportunity" : "opportunities"}</>} />}
        </>
      )}
    </section>
  );
}

function Group({ dir, rows, head, go }: { dir: "up" | "down"; rows: Row[]; head: React.ReactNode; go: (r: Row) => void }) {
  return (
    <div className="pchal-group" data-rf={dir}>
      <p className="pchal-ghead">{head}</p>
      <ul className="pchal-list">
        {rows.map((r) => (
          <li key={String(r.proposal.id)}>
            <button onClick={() => go(r)} title="Open: accept or reject" data-rf={dir}>
              <span className="pchal-title">{r.t.title}</span>
              <span className="label">{r.t.line} · {r.t.market}</span>
              <span className="pchal-move">
                <BandMark band={r.from} color="var(--sweep-hi)" size="sm" pm />{r.from}
                <span aria-hidden className="pchal-arrow">{dir === "down" ? "▼" : "▲"}</span>
                <BandMark band={r.to} color={dir === "down" ? "var(--fall-hi)" : "var(--rise-hi)"} size="sm" /><b>{r.to}</b>
              </span>
              <span className="label">{r.cause}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
