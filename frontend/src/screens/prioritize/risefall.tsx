// Rise / Fall in the inspector (PM request 2026-10-11): when the open target is a challenged PM decision, a coloured
// banner at the top — red when the AI now places it below the PM's band, green when above — in plain words, with the
// proposal's Accept / Reject (required rationale) right there. It replaces the lower proposal box for that target.
import { useState } from "react";
import { useCheckpoint } from "@/state/checkpoint";
import { BandMark } from "./marks";
import { CP_LABEL, factorLabel, useProposalVerdict } from "./data";
import { rfSentence, type RiseFall } from "./pm";

export function RiseFallBanner({ rf }: { rf: RiseFall }) {
  const { cp } = useCheckpoint();
  const verdict = useProposalVerdict();
  const [open, setOpen] = useState<"accept" | "reject" | null>(null);
  const [why, setWhy] = useState("");
  const p = rf.proposal;
  const down = rf.dir === "down";
  const deltas = Object.entries(p.factor_delta ?? {}).filter(([, v]) => v);
  return (
    <section className="prf-banner" data-rf={rf.dir} role="alert" aria-label={down ? "Your decision is contradicted" : "Upgrade opportunity"}>
      <p className="prf-kicker"><b aria-hidden>{down ? "▼" : "▲"}</b>{down ? "Downgrade — your decision is contradicted" : "Upgrade opportunity"}</p>
      <p className="prf-move">
        <BandMark band={rf.from} color="var(--sweep-hi)" size="md" pm /><span className="prf-pm">Your {rf.from}</span>
        <span className="prf-arrow" aria-hidden>→</span>
        <BandMark band={rf.to} color={down ? "var(--fall-hi)" : "var(--rise-hi)"} size="md" /><b>AI: {rf.to}</b>
      </p>
      <p className="prf-text">{rfSentence(rf, CP_LABEL[cp] ?? cp)}</p>
      {deltas.length > 0 && (
        <p className="prf-deltas label">{deltas.map(([k, v]) => `${factorLabel(k)} ${v > 0 ? "+" : "−"}${Math.abs(v)} pts`).join(" · ")}</p>
      )}
      {open ? (
        <form className="ladder-choose" onSubmit={(e) => { e.preventDefault(); if (why.trim().length >= 5) { verdict.mutate({ p, verdict: open, rationale: why.trim() }); setOpen(null); setWhy(""); } }}>
          <textarea rows={2} value={why} onChange={(e) => setWhy(e.target.value)} autoFocus aria-label="Rationale"
                    placeholder={open === "accept" ? `Why change to ${rf.to}? (required)` : `Why keep ${rf.from}? (required)`} />
          <div className="ladder-actions">
            <button type="submit" className="dbtn primary" disabled={why.trim().length < 5 || verdict.isPending}>{open === "accept" ? `Accept → ${rf.to}` : `Keep ${rf.from}`}</button>
            <button type="button" className="dbtn" onClick={() => setOpen(null)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="prf-actions">
          <button className="prf-btn" data-kind="accept" onClick={() => setOpen("accept")}>Accept {rf.to}</button>
          <button className="prf-btn" onClick={() => setOpen("reject")}>Reject · keep {rf.from}</button>
        </div>
      )}
      {verdict.isError && <p className="derror">Not saved: {(verdict.error as Error).message}</p>}
    </section>
  );
}
