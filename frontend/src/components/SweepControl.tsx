// Bottom-right checkpoint control: one timeline, JUL 25 → JUL 26, a tick per month, each checkpoint a labelled node at
// its cut-off date. The rail is filled up to the active checkpoint's cut-off ("known up to"); the fill travels there
// with the same timing as the 3D sweep. The block keeps one size at every checkpoint, so nothing shifts.
import { useLocation } from "react-router-dom";
import { useCheckpoint, CHECKPOINT_ORDER } from "@/state/checkpoint";
import type { Checkpoint, CheckpointId } from "@/lib/types";
import "./sweep.css";

const fmt = (n: number | undefined) => (n == null ? "–" : n.toLocaleString("en-US"));

const T0 = Date.parse("2025-07-01"), T1 = Date.parse("2026-07-31");   // the scene's date ring
const FALLBACK: Record<CheckpointId, string> = { cp1: "2026-01-31", cp2: "2026-07-31" };
const frac = (iso: string) => Math.min(1, Math.max(0, (Date.parse(iso) - T0) / (T1 - T0)));
const MONTHS = Array.from({ length: 13 }, (_, i) => frac(new Date(Date.UTC(2025, 6 + i, 1)).toISOString().slice(0, 10)));
const longDate = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** Full-screen 2D pages have no scene to sweep; they carry their own checkpoint switch (Document, Audit) or need none. */
export const FULL_PAGES = ["/document", "/agents", "/audit"];

export function SweepControl() {
  const { pathname } = useLocation();
  const { cp, setCp, checkpoints } = useCheckpoint();
  const byId = Object.fromEntries((checkpoints ?? []).map((c) => [c.id, c])) as Partial<Record<CheckpointId, Checkpoint>>;
  // Same groups as the readout totals, so held + new = everything visible now. The first checkpoint holds nothing yet.
  const sum = (c: Checkpoint | undefined, f: "visible" | "new") =>
    c ? (["feedback", "research", "study", "option_list", "sales"] as const).reduce((n, k) => n + c.sources[k][f], 0) : undefined;
  const cur = byId[cp], parent = cur?.parent_id ? byId[cur.parent_id] : undefined;
  const held = cur ? (parent ? sum(parent, "visible") : 0) : undefined;
  const added = parent ? sum(cur, "new") : sum(cur, "visible");
  const cutoff = (id: CheckpointId) => byId[id]?.cutoff ?? FALLBACK[id];
  const label = (id: CheckpointId) => byId[id]?.label ?? (id === "cp1" ? "JAN 26" : "JUL 26");
  const at = CHECKPOINT_ORDER.indexOf(cp);
  const known = frac(cutoff(cp));

  if (FULL_PAGES.includes(pathname)) return null;

  return (
    <div className="sweepctl">
      <div className="sweepctl-top">
        <span className="sweepctl-title">Checkpoint</span>
        <span className="label">Evidence known up to {longDate(cutoff(cp))}</span>
      </div>

      <div className="sweepctl-line" role="radiogroup" aria-label="Checkpoint">
        <span className="sweepctl-rail" aria-hidden />
        <span className="sweepctl-fill" aria-hidden style={{ transform: `scaleX(${known})` }} />
        {MONTHS.map((x, i) => <span key={i} className="sweepctl-tick" aria-hidden style={{ left: `${x * 100}%` }} />)}
        <span className="sweepctl-start label" aria-hidden>JUL 25</span>
        {CHECKPOINT_ORDER.map((id, i) => (
          <button key={id} role="radio" aria-checked={cp === id} className="sweepctl-node"
                  data-state={id === cp ? "active" : i < at ? "built" : "idle"} data-end={frac(cutoff(id)) > 0.9 ? "" : undefined}
                  style={{ left: `${frac(cutoff(id)) * 100}%` }} onClick={() => setCp(id)}>
            <span className="sweepctl-name">{label(id)}</span>
            <span className="sweepctl-dot" />
          </button>
        ))}
      </div>

      <div className="sweepctl-counts" aria-live="polite">
        <span><i className="mark held" aria-hidden /><span className="num">{fmt(held)}</span><span className="label">held</span></span>
        <span><i className="mark new" aria-hidden /><span className="num">{fmt(added)}</span><span className="label">new</span></span>
        <span className="label sweepctl-keys" aria-hidden>← →</span>
      </div>
    </div>
  );
}
