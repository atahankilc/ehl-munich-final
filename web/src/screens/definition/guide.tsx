// Guide content for page 3, drawn with the page's own marks (pins, link arcs, ladder marks). Rendered inside the
// shared Dock (components/Guide.tsx) through its `guide` slot; reuses the dock's guide.css classes.
import type { Requirement } from "@/lib/definition";
import { DOMAIN_COLOR, domainColor } from "./data";
import { useView } from "./store";
import type { DefStage } from "./stages";

type MarkKind = "held" | "new" | "changed" | "weakened" | "domains" | "synergy" | "enables" | "conflicts"
  | "cited" | "projected" | "assumption" | "gap" | "pm" | "ai" | "area" | "area-new" | "tag" | "rival" | "group";
const INK = "#f2f4f7", AMBER = "#f5a524", BLUE = "#4d94ff";
const C = DOMAIN_COLOR.interior;

function Mark({ kind }: { kind: MarkKind }) {
  const s = { width: 18, height: 18, viewBox: "0 0 18 18", "aria-hidden": true, className: "gmark" } as const;
  switch (kind) {
    case "held": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill={C} /></svg>;
    case "new": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill="none" stroke={C} strokeWidth="1.6" /></svg>;
    case "changed": return <svg {...s}><circle cx="9" cy="9" r="6" fill="none" stroke={C} strokeWidth="1.3" /><circle cx="9" cy="9" r="2.8" fill={C} /></svg>;
    case "weakened": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill={AMBER} /><path d="M6.5 6.5l5 5M11.5 6.5l-5 5" stroke="#000" strokeWidth="1.3" /></svg>;
    case "domains": return <svg {...s}>{Object.values(DOMAIN_COLOR).slice(0, 6).map((c, i) => <circle key={c} cx={3 + (i % 3) * 6} cy={i < 3 ? 6 : 12} r="2.2" fill={c} />)}</svg>;
    case "synergy": return <svg {...s}><path d="M2 15Q9 0 16 15" fill="none" stroke={INK} strokeWidth="1.4" /></svg>;
    case "enables": return <svg {...s}><path d="M2 15Q9 0 16 15" fill="none" stroke={INK} strokeWidth="1.4" /><path d="M16.5 15.5l-1-5-3.5 3.2z" fill={INK} /></svg>;
    case "conflicts": return <svg {...s}><path d="M2 15Q9 0 16 15" fill="none" stroke={INK} strokeWidth="1.4" strokeDasharray="2.2 2" /></svg>;
    case "cited": return <svg {...s}><circle cx="9" cy="9" r="4" fill={INK} /></svg>;
    case "projected": return <svg {...s}><circle cx="9" cy="9" r="4" fill="none" stroke={INK} strokeWidth="1.5" /></svg>;
    case "assumption": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill="none" stroke={INK} strokeWidth="1.3" strokeDasharray="2 1.8" /></svg>;
    case "gap": return <svg {...s}><text x="9" y="13" textAnchor="middle" fontSize="11" fontWeight="600" fill={INK}>?</text></svg>;
    case "pm": return <svg {...s}><circle cx="9" cy="9" r="7" fill="rgba(28,105,212,0.25)" /><circle cx="9" cy="9" r="4" fill={BLUE} /></svg>;
    case "area": return <svg {...s}><path d="M9 3l5 6-5 6-5-6z" fill={INK} /></svg>;
    case "area-new": return <svg {...s}><path d="M9 3l5 6-5 6-5-6z" fill="none" stroke={INK} strokeWidth="1.2" /></svg>;
    case "group": return <svg {...s}><ellipse cx="9" cy="12" rx="7" ry="2.6" fill="none" stroke="#868d99" strokeWidth="0.9" />{[5, 9, 13].map((x) => <circle key={x} cx={x} cy="9.5" r="1.9" fill={C} />)}</svg>;
    case "tag": return <svg {...s}><circle cx="4" cy="9" r="2.6" fill={C} /><rect x="8" y="5.5" width="9" height="7" rx="1.5" fill="none" stroke="#868d99" strokeWidth="0.8" /><text x="12.5" y="11" textAnchor="middle" fontSize="5.5" fill="#b4bac4">≥</text></svg>;
    case "rival": return <svg {...s}><path d="M1 10h16" stroke="#5b616b" strokeWidth="1" /><path d="M7 5v10" stroke="#868d99" strokeWidth="1" /><circle cx="12.5" cy="10" r="2.6" fill={INK} /></svg>;
    case "ai": return <svg {...s}><rect x="2.5" y="4.5" width="13" height="9" rx="2" fill="none" stroke="#868d99" /><text x="9" y="11.5" textAnchor="middle" fontSize="6.5" fontWeight="600" fill="#b4bac4">AI</text></svg>;
  }
}

interface Row { mark: MarkKind; name: string; text: string }
interface Page { title: string; lead?: string; rows?: Row[]; uses?: string; made?: string; notes?: string[] }

const PAGE: Page = {
  title: "Definition",
  lead: "Each requirement gets one measurable target, defined on today's car. Pins sit where the customer feels it; arcs show which requirements pull on the same resource.",
  rows: [
    { mark: "domains", name: "Pin colour", text: "The vehicle domain: exterior, interior, powertrain, chassis, assistance, digital, variants." },
    { mark: "held", name: "Held", text: "Defined at the earlier checkpoint, target unchanged." },
    { mark: "new", name: "New", text: "Defined at this checkpoint." },
    { mark: "changed", name: "Target moved", text: "The recommended target changed since the earlier checkpoint." },
    { mark: "weakened", name: "Weakened", text: "Less evidence than before." },
    { mark: "synergy", name: "Synergy", text: "Solid arc: working on one helps the other. Thicker = stronger." },
    { mark: "enables", name: "Enables", text: "Solid arc with a cone: one makes the other possible." },
    { mark: "conflicts", name: "Conflicts / competes", text: "Dashed arc: they pull on the same resource, named at the top of the arc (mass, energy, thermal …)." },
    { mark: "cited", name: "Cited number", text: "Backed by a source; click its id to see it." },
    { mark: "projected", name: "Projected", text: "Extrapolated from a named trend." },
    { mark: "assumption", name: "Assumption", text: "No evidence; the reasoning is given." },
    { mark: "gap", name: "Gap", text: "No data. Never filled with an invented number; it becomes a research task." },
    { mark: "ai", name: "AI", text: "The rung the AI recommends." },
    { mark: "pm", name: "PM", text: "The rung the PM chose, with a rationale." },
  ],
  notes: ["Click a pin or a list row to open it; the camera flies to its zone.", "Switch the car line and filter domains top-left.", "← → change the checkpoint; new pins and links pulse once."],
};

// One guide per page-3 stage (stages.ts), following the stepper. Labels, not paragraphs.
const PIN_ROWS: Row[] = [
  { mark: "held", name: "Held", text: "Same as the earlier checkpoint." },
  { mark: "new", name: "New", text: "New at this checkpoint." },
  { mark: "changed", name: "Target moved", text: "Recommended target changed." },
  { mark: "weakened", name: "Weakened", text: "Less evidence than before." },
];
const BASIS_ROWS: Row[] = [
  { mark: "cited", name: "Cited", text: "Number backed by a source." },
  { mark: "projected", name: "Projected", text: "Extrapolated from a named trend." },
  { mark: "assumption", name: "Assumption", text: "No evidence; reasoning given." },
  { mark: "gap", name: "Gap", text: "No data. Never an invented number; becomes a research task." },
];
const ARC_ROWS: Row[] = [
  { mark: "synergy", name: "Solid arc", text: "Synergy: one helps the other. Thicker = stronger." },
  { mark: "enables", name: "Arc with a cone", text: "Enables: one makes the other possible." },
  { mark: "conflicts", name: "Dashed arc", text: "Conflict: both pull on the same resource, named at the apex." },
];
const STAGE_PAGE: Record<DefStage, Page> = {
  drafted: {
    title: "Drafted",
    lead: "Page 2's requirement areas rise out of the evidence and split into the product decisions they call for, grouped by vehicle domain.",
    made: "sol drafts 1–3 product decisions per area; domain and zone come from aspect rules, not the AI.",
    rows: [
      { mark: "area", name: "Diamond", text: "A requirement area from page 2, colour as there; it bursts into its requirements." },
      { mark: "domains", name: "Colour", text: "Vehicle domain." },
      { mark: "group", name: "Group", text: "One disc per domain; click it to filter." },
      ...PIN_ROWS,
    ],
    notes: ["Hover a requirement: its siblings from the same area ring up.", "[ and ] step through the stages; click a stage name to jump."],
  },
  specified: {
    title: "Specified",
    lead: "Each requirement with one measurable target; the tag shows the recommended rung.",
    made: "A customer-experienced metric, acceptance criteria and a ladder (today, threshold, target, stretch); every number is cited, projected, an assumption or a gap.",
    rows: [
      { mark: "tag", name: "Target tag", text: "Recommended target, e.g. ≥ 540 km." },
      ...BASIS_ROWS,
      { mark: "rival", name: "Tick", text: "A rival's cited value on the ladder, same unit and cycle." },
    ],
    notes: ["Open a requirement for its full ladder and sources."],
  },
  linked: {
    title: "Linked",
    lead: "How requirements pull on each other: help, enable or compete for one resource.",
    made: "Candidate pairs come from shared resources; luna judges each pair, sol re-checks strong and conflict links.",
    rows: [...ARC_ROWS, { mark: "ai", name: "Proposed", text: "Links are proposals; the PM confirms or removes them." }],
    notes: ["The Links switch shows strong, all or none."],
  },
  car: {
    title: "On the car",
    lead: "Every requirement pinned where the customer feels it on today's car.",
    made: "Zones follow from the requirement's aspects; arcs are the links from the previous stage.",
    rows: [{ mark: "domains", name: "Pin colour", text: "Vehicle domain." }, ...PIN_ROWS, ...ARC_ROWS],
    notes: ["Click a pin or list row; the camera flies to its zone.", "← → change the checkpoint; new pins and links pulse once."],
  },
};

function forRequirement(r: Requirement): Page {
  return {
    title: "Requirement definition",
    lead: "One customer requirement with one primary metric, its acceptance criteria and a target ladder per car line and market.",
    uses: "The AI drafts the metric and ladder from the area's evidence and benchmarks, and recommends a rung. The PM chooses the rung with a rationale; the AI never decides. Linked requirements are proposals the PM confirms or removes.",
    rows: [
      { mark: "cited", name: "Ladder", text: "Today → threshold → target → stretch on one scale, better to the right." },
      { mark: "rival", name: "Tick", text: "A rival's cited value, same unit and cycle; hover for the name, click for the source." },
      { mark: "conflicts", name: "Links", text: `${r.title} draws on ${r.aspects.length ? "the same resources as the linked requirements below" : "shared resources"}.` },
    ],
    notes: ["Choosing a rung asks for a rationale; it goes into the audit trail.", "Gaps list the numbers still missing."],
  };
}

export function DefinitionGuide({ sel }: { sel: Requirement | null }) {
  const stage = useView((s) => s.stage);
  const page = sel ? forRequirement(sel) : STAGE_PAGE[stage] ?? PAGE;
  return (
    <div className="guide">
      <p className="guide-title">{sel && <i className="dguide-dot" style={{ background: domainColor(sel.domain) }} aria-hidden />}{page.title}</p>
      {page.lead && <p className="guide-lead">{page.lead}</p>}
      {page.made && <div className="guide-uses"><span className="label">How the AI made it</span><p>{page.made}</p></div>}
      {page.uses && <div className="guide-uses"><span className="label">How the AI uses it</span><p>{page.uses}</p></div>}
      {page.rows && (
        <ul className="guide-rows">
          {page.rows.map((r) => <li key={r.name}><Mark kind={r.mark} /><span><b>{r.name}</b> {r.text}</span></li>)}
        </ul>
      )}
      {page.notes && <ul className="guide-notes">{page.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </div>
  );
}
