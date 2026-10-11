// Guide content for page 5 (Document), rendered inside the shared Dock through its `guide` slot.
import { BandMark, GateMark } from "../prioritize/marks";
import { DOMAIN_COLOR } from "../definition/data";

const C = DOMAIN_COLOR.digital;

export function DocumentGuide({ open }: { open: boolean }) {
  return (
    <div className="guide">
      <p className="guide-title">{open ? "Requirement record" : "Document"}</p>
      <p className="guide-lead">
        {open
          ? "The full deliverable for one requirement in this car line × market: what, how it is measured, why this priority, and every source behind it."
          : "The deliverable: every requirement for one car line × market at this checkpoint, grouped by band, each traceable to its sources."}
      </p>
      <div className="guide-uses"><span className="label">Who decides</span>
        <p>The band is the PM's where confirmed, else the AI's proposal. The AI never sets a priority; exports are logged in the audit trail.</p></div>
      <ul className="guide-rows">
        <li><BandMark band="Must" color={C} /><span><b>Band mark</b> Must solid, Should outlined, Could a thin line; hue = vehicle domain.</span></li>
        <li><BandMark band="Should" color={C} pm /><span><b>Blue underline · PM ✓</b> confirmed by the PM (the only blue).</span></li>
        <li><span className="doc-gtag doc-gmark">→</span><span><b>Arrow tag</b> an open AI proposal to change the band.</span></li>
        <li><GateMark result="warn" /><span><b>Gate</b> brand, segment, market, feasibility: pass, warn, fail.</span></li>
        <li><span className="doc-gtag doc-gmark">E2</span><span><b>Evidence level</b> E1 strongest … E4 weakest.</span></li>
      </ul>
      <ul className="guide-notes">
        <li>Click a row to open its record; “Changes since JAN” shows what moved.</li>
        <li>Export writes Markdown or CSV for the selected line × market.</li>
      </ul>
    </div>
  );
}
