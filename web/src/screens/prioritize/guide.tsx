// Guide content for page 4, drawn with the page's own marks (columns by band, threshold planes, ghost tick, bundle
// chord, choose-jointly arc, the PM's blue base). Rendered inside the shared Dock through its `guide` slot.
import type { Target } from "@/lib/prioritize";
import { DOMAIN_COLOR, domainColor } from "../definition/data";
import type { PrioView } from "./store";

type MarkKind = "must" | "should" | "could" | "planes" | "ghost" | "pulse" | "bundle" | "joint" | "pm" | "pmcap" | "challenged" | "fall" | "rise" | "moved" | "blocked" | "slot" | "waterfall" | "matrix" | "domains";
const INK = "#f2f4f7", BLUE = "#4d94ff", C = DOMAIN_COLOR.digital;
const RISE = "#2fbf71", FALL = "#ff3b30";   // tokens --rise / --fall: only for priority-level changes after a checkpoint

function Mark({ kind }: { kind: MarkKind }) {
  const s = { width: 18, height: 18, viewBox: "0 0 18 18", "aria-hidden": true, className: "gmark" } as const;
  switch (kind) {
    case "must": return <svg {...s}><rect x="7" y="3" width="4" height="13" fill={C} /></svg>;
    case "should": return <svg {...s}><rect x="7" y="6.5" width="4" height="9.5" fill={C} fillOpacity=".15" stroke={C} strokeWidth="1" /></svg>;
    case "could": return <svg {...s}><rect x="8.4" y="10" width="1.2" height="6" fill={C} /><circle cx="9" cy="9.6" r="1.3" fill={C} /></svg>;
    case "planes": return <svg {...s}><path d="M1 7h16M1 11h16" stroke="#fff" strokeOpacity=".35" /><text x="17" y="6" fontSize="4" textAnchor="end" fill="#b4bac4">60</text></svg>;
    case "ghost": return <svg {...s}><rect x="7" y="8" width="4" height="8" fill={C} /><path d="M5 5h8" stroke={INK} strokeOpacity=".6" /></svg>;
    case "pulse": return <svg {...s}><circle cx="9" cy="9" r="6" fill="none" stroke={INK} strokeOpacity=".7" /><circle cx="9" cy="9" r="2" fill={INK} /></svg>;
    case "bundle": return <svg {...s}><path d="M3 14Q9 8 15 14" fill="none" stroke={INK} strokeOpacity=".5" /><rect x="2" y="6" width="2" height="8" fill={C} /><rect x="14" y="8" width="2" height="6" fill={DOMAIN_COLOR.interior} /></svg>;
    case "joint": return <svg {...s}><path d="M3 9Q9 0 15 9" fill="none" stroke={INK} strokeDasharray="2 1.8" /><rect x="2" y="9" width="2.4" height="7" fill={C} /><rect x="13.6" y="9" width="2.4" height="7" fill={DOMAIN_COLOR.powertrain} /></svg>;
    case "pm": return <svg {...s}><rect x="8" y="3" width="2.4" height="10" fill={C} /><ellipse cx="9.2" cy="14.5" rx="6" ry="2.2" fill="rgba(28,105,212,0.35)" /><ellipse cx="9.2" cy="14.5" rx="2.6" ry="1" fill={BLUE} /></svg>;
    case "pmcap": return <svg {...s}><rect x="7" y="7" width="4" height="10" fill={C} stroke={BLUE} strokeWidth="1" /><rect x="2.5" y="1" width="13" height="5" rx="1" fill={BLUE} /><text x="9" y="5" fontSize="4" textAnchor="middle" fill="#fff" fontWeight="700">M ✓</text></svg>;
    case "challenged": return <svg {...s}><rect x="5" y="8" width="3.6" height="9" fill={C} stroke={BLUE} strokeWidth="1" /><ellipse cx="6.8" cy="8" rx="4" ry="1.4" fill="none" stroke={INK} /><circle cx="14" cy="5" r="3.4" fill={INK} /><text x="14" y="6.8" fontSize="5" textAnchor="middle" fill="#000" fontWeight="700">!</text></svg>;
    case "fall": return <svg {...s}><rect x="4" y="4" width="4" height="13" fill={C} stroke={BLUE} strokeWidth="1" /><rect x="2.6" y="9" width="6.8" height="5" fill={FALL} fillOpacity=".3" stroke={FALL} strokeWidth=".8" /><path d="M12.5 3v8.5" stroke={FALL} strokeWidth="2" /><path d="M10.3 10.5l2.2 3.2 2.2-3.2z" fill={FALL} /></svg>;
    case "rise": return <svg {...s}><rect x="4" y="9" width="4" height="8" fill={C} stroke={BLUE} strokeWidth="1" /><rect x="3" y="2.5" width="6" height="6.5" fill={RISE} fillOpacity=".18" stroke={RISE} strokeWidth=".8" /><path d="M12.5 15V6" stroke={RISE} strokeWidth="1.5" /><path d="M10.6 6.8l1.9-2.9 1.9 2.9z" fill={RISE} /></svg>;
    case "moved": return <svg {...s}><text x="5" y="9" fontSize="7" fill={RISE} textAnchor="middle">▲</text><text x="13" y="15" fontSize="7" fill={FALL} textAnchor="middle">▼</text></svg>;
    case "blocked": return <svg {...s}><circle cx="9" cy="9" r="5" fill="none" stroke={INK} strokeWidth="1.3" /><path d="M5.5 12.5l7-7" stroke={INK} strokeWidth="1.3" /></svg>;
    case "slot": return <svg {...s}><ellipse cx="9" cy="12" rx="4" ry="1.6" fill="none" stroke="#868d99" /></svg>;
    case "waterfall": return <svg {...s}><rect x="2" y="3" width="5" height="2.4" fill="#b4bac4" /><rect x="7" y="7" width="4" height="2.4" fill="#b4bac4" /><rect x="9" y="11" width="2" height="2.4" fill="#868d99" /><rect x="2" y="14.6" width="9" height="2" fill={INK} /></svg>;
    case "matrix": return <svg {...s}>{[3, 8, 13].map((x, i) => <rect key={x} x={x} y={4 + i * 2} width="2.6" height={10 - i * 2} fill={i === 1 ? "none" : C} stroke={C} strokeWidth=".8" />)}</svg>;
    case "domains": return <svg {...s}>{Object.values(DOMAIN_COLOR).slice(0, 6).map((c, i) => <circle key={c} cx={3 + (i % 3) * 6} cy={i < 3 ? 6 : 12} r="2.2" fill={c} />)}</svg>;
  }
}

interface Row { mark: MarkKind; name: string; text: string }
interface Page { title: string; lead?: string; rows?: Row[]; made?: string; uses?: string; notes?: string[] }

const SKYLINE: Page = {
  title: "Prioritize",
  lead: "The requirements lift off the car into a skyline: one column per requirement, its height the score in the market you picked. Switch the market and watch the heights move: markets are different customers.",
  made: "No AI in the score: six weighted factors from the evidence, × confidence, + effort and market fit (prio-v1). The AI only checks brand, segment and market fit, and proposes bands.",
  rows: [
    { mark: "domains", name: "Colour", text: "Vehicle domain; columns are grouped by domain round the ring." },
    { mark: "must", name: "Solid column", text: "Must (score ≥ 60)." },
    { mark: "should", name: "Outlined column", text: "Should (≥ 45)." },
    { mark: "could", name: "Thin line", text: "Could." },
    { mark: "planes", name: "Faint planes", text: "The two band thresholds." },
    { mark: "slot", name: "Empty slot", text: "Not targeted in this market." },
    { mark: "ghost", name: "Ghost tick", text: "JAN's score, shown at JUL; movers pulse once." },
    { mark: "bundle", name: "Chord", text: "A bundle: strongly linked requirements share one band." },
    { mark: "joint", name: "Dashed arc", text: "Two Musts competing for one resource: choose their ladder levels jointly." },
    { mark: "blocked", name: "Barred circle", text: "Brand fit fails: approval needs a PM override." },
    { mark: "pm", name: "Blue base", text: "The PM confirmed this band. Blue is only ever the PM." },
    { mark: "pmcap", name: "Blue edge + M ✓", text: "PM-confirmed column: blue outline and the confirmed band's letter." },
    { mark: "fall", name: "Red ▼ badge + drop line", text: "Downgrade: new evidence puts a band you confirmed lower (\"Must → Should · cause\"). The column stays at your band; the red ghost and line show where the AI now puts it. Review it first." },
    { mark: "rise", name: "Green ▲ badge + ghost", text: "Upgrade opportunity: the AI now puts a band you confirmed higher (\"Should → Must\"). Consider upgrading." },
    { mark: "moved", name: "Small green ▲ / red ▼", text: "Not confirmed by you: the AI's own band rose or fell since the last checkpoint." },
    { mark: "challenged", name: "White ! + ring", text: "Weights preview only: the previewed weights would put a decision of yours in another band." },
  ],
  notes: ["Click a column or list row to open its score.", "[ and ] step through the line's markets; ← → change the checkpoint.", "Back to Definition lowers the columns onto the car."],
};

const MATRIX: Page = {
  title: "Market × requirement",
  lead: "The same priorities flat: one row per requirement, one column per market of the line. Rows with a white tick disagree between markets.",
  rows: [
    { mark: "matrix", name: "Cells", text: "Band mark (solid / outlined / line) and score; ▲▼ moved since JAN; P an open AI proposal." },
    { mark: "pm", name: "Blue underline + ✓", text: "Confirmed by the PM." },
    { mark: "fall", name: "Red cell ▼", text: "Downgrade: the AI now puts a band you confirmed lower; the proposed band's letter follows." },
    { mark: "rise", name: "Green cell ▲", text: "Upgrade opportunity: the AI now puts a band you confirmed higher." },
    { mark: "moved", name: "Small green ▲ / red ▼", text: "An unconfirmed AI band moved since the last checkpoint." },
  ],
  notes: ["Click a cell to open that market's score.", "Esc returns to the skyline."],
};

function forTarget(t: Target): Page {
  return {
    title: "Target priority",
    lead: `${t.title}, in ${t.line} · ${t.market}. A score with every step visible, so the band can be argued with.`,
    uses: "The AI recomputes scores at every checkpoint and proposes a band; a band that moves becomes a proposal with its cause. The PM confirms Must, Should or Could with a rationale, which goes to the audit trail. The AI never sets a priority.",
    rows: [
      { mark: "waterfall", name: "Waterfall", text: "Customer, Business and Future factors add up to the base, × confidence, then effort and market fit." },
      { mark: "planes", name: "Dashed lines", text: "The band thresholds on the same scale." },
      { mark: "blocked", name: "Gates", text: "Brand fit fail blocks approval; feasibility is context only." },
    ],
    notes: ["What-if moves the ladder rung without storing anything; it names linked requirements that get exposed."],
  };
}

export function PrioritizeGuide({ sel, view }: { sel: Target | null; view: PrioView }) {
  const page = sel ? forTarget(sel) : view === "matrix" ? MATRIX : SKYLINE;
  return (
    <div className="guide">
      <p className="guide-title">{sel && <i className="dguide-dot" style={{ background: domainColor(sel.domain) }} aria-hidden />}{page.title}</p>
      {page.lead && <p className="guide-lead">{page.lead}</p>}
      {page.made && <div className="guide-uses"><span className="label">How the score is made</span><p>{page.made}</p></div>}
      {page.uses && <div className="guide-uses"><span className="label">How the AI uses it</span><p>{page.uses}</p></div>}
      {page.rows && <ul className="guide-rows">{page.rows.map((r) => <li key={r.name}><Mark kind={r.mark} /><span><b>{r.name}</b> {r.text}</span></li>)}</ul>}
      {page.notes && <ul className="guide-notes">{page.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </div>
  );
}
