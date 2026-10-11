// Process: the ~2-year requirements process and its governance — evidence waves, prioritization runs and weights,
// the append-only audit trail, the BMW deliverable and the system's budget. The AI proposes; the PM decides.
import { useSearchParams } from "react-router-dom";
import { PageHead } from "@/components/Shell";
import { Seg } from "@/components/ui";
import { Timeline } from "./process/Timeline";
import { Runs } from "./process/Runs";
import { Audit } from "./process/Audit";
import { Deliver } from "./process/Deliver";
import { System } from "./process/System";
import "./process.css";

const TABS = [
  { value: "timeline", label: "Timeline", lede: "The two-year requirements process, replayed as three evidence waves. Each wave brings new evidence; the AI re-drafts and re-scores; you decide." },
  { value: "runs", label: "Runs & weights", lede: "Every prioritization run is kept. Compare any two, see what moved and why, and tune how the score is weighted." },
  { value: "audit", label: "Audit trail", lede: "Every change by you, the AI and the system — who, when, what, and why." },
  { value: "deliver", label: "Deliver", lede: "The deliverable for BMW: prioritized, evidence-linked customer requirements per car and market." },
  { value: "system", label: "System", lede: "OpenAI spend against the $100 budget, what the pipeline has processed, and demo snapshots." },
] as const;
type Tab = (typeof TABS)[number]["value"];

export default function Process() {
  const [sp, setSp] = useSearchParams();
  const raw = sp.get("tab");
  const tab: Tab = TABS.some((t) => t.value === raw) ? (raw as Tab) : "timeline";
  const meta = TABS.find((t) => t.value === tab)!;
  return (
    <main className="page process">
      <PageHead
        title="Process"
        lede={meta.lede}
        actions={
          <div className="px-tabs">
            <Seg
              label="Process view"
              value={tab}
              options={TABS.map((t) => ({ value: t.value, label: t.label }))}
              onChange={(v) => setSp(v === "timeline" ? {} : { tab: v }, { replace: true })}
            />
          </div>
        }
      />
      {tab === "timeline" && <Timeline />}
      {tab === "runs" && <Runs />}
      {tab === "audit" && <Audit />}
      {tab === "deliver" && <Deliver />}
      {tab === "system" && <System />}
    </main>
  );
}
