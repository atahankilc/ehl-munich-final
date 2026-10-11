// Bottom-left dock: the Guide explains the screen (a legend drawn with the scene's own marks) and, once something is
// opened, what that kind of item is and how the AI uses it. On Structure the Agent panel sits next to it. Each is a
// pill like the Audit button; clicking one opens its panel above the pills and closes the other, clicking the open one
// closes it. Which one is open (or none) is remembered per browser.
import { useEffect, useState, type ReactNode } from "react";
import { BookOpen, Bot } from "lucide-react";
import type { Selection } from "@/lib/types";
import { TYPE_COLOR } from "@/screens/scan/colors";
import "./guide.css";

type Mode = "scan" | "structure" | "definition" | "prioritize" | "document";
type MarkKind =
  | "comment" | "research" | "study" | "option" | "sales" | "sales-fc" | "public" | "held" | "new"
  | "improve" | "keep" | "strengthened" | "weakened" | "lost" | "theme" | "area-improve" | "area-keep"
  | "area-emerging" | "area-quality" | "area-new" | "arc" | "arc-contra" | "sector";
interface Row { mark: MarkKind; name: string; text: string }
interface Page { title: string; lead?: string; rows?: Row[]; uses?: string; notes?: string[] }

const BLUE = "#3987e5", INK = "#f2f4f7", AMBER = "#f5a524";

/** The scene's marks in miniature, so the legend looks exactly like what it explains. */
function Mark({ kind }: { kind: MarkKind }) {
  const s = { width: 18, height: 18, viewBox: "0 0 18 18", "aria-hidden": true, className: "gmark" } as const;
  switch (kind) {
    case "comment": return <svg {...s}><circle cx="5" cy="7" r="2" fill={BLUE} /><circle cx="11.5" cy="5" r="2" fill={BLUE} opacity=".7" /><circle cx="10" cy="12" r="2.4" fill={BLUE} /></svg>;
    case "research": return <svg {...s}><path d="M2 12a8 8 0 0 1 14 0" fill="none" stroke="#fff" strokeOpacity=".35" strokeDasharray="1.5 2" /><circle cx="9" cy="6" r="2.4" fill={TYPE_COLOR.research} /></svg>;
    case "study": return <svg {...s}><path d="M2 11h14" stroke="#fff" strokeOpacity=".2" /><path d="M5 11V6M9 11v4M13 11V4" stroke={TYPE_COLOR.study} strokeWidth="1.5" /></svg>;
    case "option": return <svg {...s}>{[3.5, 7, 10.5, 14].map((x) => <circle key={x} cx={x} cy="9" r="1.3" fill={TYPE_COLOR.option} />)}</svg>;
    case "sales": return <svg {...s}><rect x="5" y="6" width="2.5" height="9" fill={TYPE_COLOR.sales} /><rect x="10.5" y="3" width="2.5" height="12" fill={TYPE_COLOR.sales} /></svg>;
    case "sales-fc": return <svg {...s}><rect x="7.5" y="3.5" width="3" height="11" fill="none" stroke={TYPE_COLOR.sales} /></svg>;
    case "public": return <svg {...s}><circle cx="9" cy="9" r="4" fill="none" stroke={TYPE_COLOR.study} strokeWidth="1.5" /></svg>;
    case "held": return <svg {...s}><circle cx="9" cy="9" r="4" fill={INK} /></svg>;
    case "new": return <svg {...s}><circle cx="9" cy="9" r="4" fill="none" stroke={INK} strokeWidth="1.5" /></svg>;
    case "improve": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill="none" stroke={BLUE} strokeWidth="2" /></svg>;
    case "keep": return <svg {...s}><circle cx="9" cy="9" r="4.5" fill="none" stroke={INK} strokeWidth="2" /></svg>;
    case "strengthened": return <svg {...s}><circle cx="9" cy="9" r="6" fill="none" stroke={INK} strokeWidth="1.3" /><circle cx="9" cy="9" r="2.8" fill="none" stroke={INK} strokeWidth="1.3" /></svg>;
    case "weakened": return <svg {...s}><circle cx="9" cy="9" r="4" fill={AMBER} /></svg>;
    case "lost": return <svg {...s}><path d="M5.5 5.5l7 7M12.5 5.5l-7 7" stroke={AMBER} strokeWidth="1.6" /></svg>;
    case "theme": return <svg {...s}><circle cx="9" cy="9" r="6.5" fill="none" stroke="#fff" strokeOpacity=".55" /></svg>;
    case "area-improve": case "area-keep": case "area-emerging": case "area-quality": case "area-new": {
      const c = kind === "area-keep" ? "#eef1f5" : kind === "area-emerging" ? TYPE_COLOR.research : kind === "area-quality" ? AMBER : BLUE;
      const wire = kind === "area-new" || kind === "area-quality";
      return <svg {...s}><path d="M9 2.5l5 6.5-5 6.5-5-6.5z" fill={wire ? "none" : c} stroke={c} strokeWidth="1.2" /></svg>;
    }
    case "arc": return <svg {...s}><path d="M3 15Q9 1 15 15" fill="none" stroke={TYPE_COLOR.research} strokeWidth="1.4" /></svg>;
    case "arc-contra": return <svg {...s}><path d="M3 15Q9 1 15 15" fill="none" stroke={TYPE_COLOR.study} strokeWidth="1.4" strokeDasharray="2 2" /></svg>;
    case "sector": return <svg {...s}><path d="M3 13A8 8 0 0 1 9 5" fill="none" stroke="#fff" strokeOpacity=".5" /><path d="M10.5 5A8 8 0 0 1 15 9" fill="none" stroke="#fff" strokeOpacity=".5" /></svg>;
  }
}

/* ------------------------------------------------------------------------------------------- content */
const SCAN: Page = {
  title: "Raw evidence",
  lead: "Everything the system holds at this checkpoint, before any AI interpretation. Each colour is one kind of data.",
  rows: [
    { mark: "comment", name: "Customer comments", text: "The cloud in the middle. Placed by meaning: comments that say similar things sit close together." },
    { mark: "research", name: "Web research", text: "The dashed ring. Cited sources, placed by publication date from JUL 25 round to JUL 26." },
    { mark: "study", name: "Customer study", text: "One tick per survey question. Outward: rated above that car's average in that market; inward: below." },
    { mark: "option", name: "Equipment options", text: "Today's car, one dot per option from the German price list." },
    { mark: "sales", name: "Sales volumes", text: "BMW figures per market and year." },
    { mark: "sales-fc", name: "Forecast", text: "Outlined bars are the 2030 forecast." },
    { mark: "public", name: "Public research on a car", text: "Hollow rings beside BMW's data: cited ratings, product news and sales figures about that car." },
    { mark: "sector", name: "Car slices", text: "Each car line owns one slice of the outer rings: 1 Series, 5 Series (with the China long-wheelbase part), 7 Series." },
    { mark: "held", name: "Held", text: "Known at the earlier checkpoint." },
    { mark: "new", name: "New", text: "Acquired by this checkpoint's sweep." },
  ],
  notes: ["Drag to turn the view, scroll to zoom.", "Click anything to open it; Esc closes.", "Filters sit under the numbers; ← → change the checkpoint."],
};

const STRUCTURE: Page = {
  title: "Structure",
  lead: "What the AI made of the evidence. The comments flew into clusters: signals from many comments with the same need. Clusters form themes, themes form requirement areas.",
  rows: [
    { mark: "improve", name: "Cluster to improve", text: "Many comments asking for the same fix. Bigger = more comments." },
    { mark: "keep", name: "Cluster to keep", text: "Many comments praising the same thing." },
    { mark: "new", name: "New", text: "Appeared at this checkpoint." },
    { mark: "strengthened", name: "Strengthened", text: "Clearly more comments than at the earlier checkpoint (tested, not just noise)." },
    { mark: "weakened", name: "Weakened", text: "Clearly fewer comments than before." },
    { mark: "lost", name: "Lost", text: "No longer supported at this checkpoint." },
    { mark: "theme", name: "Theme", text: "A halo around related clusters, named by the AI." },
    { mark: "area-improve", name: "Requirement area", text: "The diamonds on the ring above the cloud, with stems down to the themes they group. Blue improve, white keep, orange emerging." },
    { mark: "area-quality", name: "Quality hand-over", text: "Defects rather than product decisions: passed on, not prioritised here." },
    { mark: "area-new", name: "Outlined diamond", text: "A new area at this checkpoint." },
    { mark: "arc", name: "Evidence", text: "Hover or open a theme: arcs run to the items that back it, coloured by source (orange research, green study, yellow options)." },
    { mark: "arc-contra", name: "Contradicting evidence", text: "Dashed arcs: the source argues against the theme." },
  ],
  notes: ["The numbers on top follow the funnel: signals → clusters → themes → areas.", "The Agent tab shows the AI working live."],
};

const TIERS = "Trust: T1 official (BMW, OEMs, registration statistics), T2 reputable press and analysts, T3 forums and social media.";

// On Evidence the inspector shows the source only; the AI's reading of it sits on Structure, one link away
const ON_STRUCTURE = "If the AI used it at this checkpoint, \"View in Structure\" shows how.";

function forSelection(sel: Selection, mode: Mode): Page {
  const ai = mode === "structure";
  switch (sel.kind) {
    case "comment": return {
      title: "Customer comment",
      lead: "One verbatim from a BMW feedback channel, with its car, market, channel and BMW's own label.",
      uses: "The AI reads it and writes signals: the aspect (e.g. seat comfort), whether it is a like, a gap or a wish, how strongly it is said, and the customer's words as proof. Signals from many comments form the clusters on the Structure page.",
      notes: [ai ? "\"What the AI found\" lists this comment's signals." : "\"View in Structure\" opens the cluster its signals joined.",
              "Its place in the cloud comes from its meaning; neighbours say similar things."],
    };
    case "research": return sel.item.ring ? {
      title: { study: "Public rating", options: "Product news", sales: "Public sales figure" }[sel.item.ring],
      lead: "Cited, published information about one car line, kept beside BMW's own data and never mixed into it.",
      uses: "Linked to themes as evidence when it supports, contradicts or adds context to them.",
      notes: [TIERS, ai ? "\"Not classified yet\" means the per-item AI reading has not run for research; links to themes are made in a later step." : ON_STRUCTURE],
    } : {
      title: "Web research",
      lead: "A cited source found by the research agents: the claim, its URL, publication date and trust tier. Placed on the dashed ring by date.",
      uses: "Not split into signals like comments. When the AI builds themes it searches these sources and links the relevant ones as evidence: supports, contradicts, competitor, trend or context.",
      notes: [TIERS, ai ? "\"Not classified yet\" means the per-item AI reading has not run for research; the links to themes are made in a later step." : ON_STRUCTURE],
    };
    case "study": return {
      title: "Customer study",
      lead: "One question from BMW's 2025 customer study for one car in one market.",
      uses: "Linked to themes as evidence: a topic rated well supports a \"keep\", a topic rated poorly supports an \"improve\".",
      notes: ["Tick direction: outward = above this car's average in this market, inward = below.",
              "USA: share of the top two answers on a 7-point scale. Europe and China: mean rating out of 10.", ...(ai ? [] : [ON_STRUCTURE])],
    };
    case "option": return {
      title: "Equipment option",
      lead: "One option of today's car from the German price list: standard, optional or part of a package.",
      uses: "Linked to themes when customers ask for something the car already offers (\"available as option\"), a hint that it is hard to find or poorly packaged rather than missing.",
      notes: ai ? undefined : [ON_STRUCTURE],
    };
    case "sales": return {
      title: "BMW sales volume",
      lead: "BMW's units for one car, market and year; the outlined bar is the 2030 forecast.",
      uses: "Not used in the analysis yet. These figures look stylized and conflict with public data (open question Q-015), so they are shown but never mixed in. Their natural role is weighting priorities by market size.",
    };
    case "cluster": return {
      title: "Cluster",
      lead: "Signals from many comments that express the same need, across cars and markets.",
      uses: "The AI writes one finding per cluster (title, statement, need type) and groups related clusters into themes.",
      notes: ["Blue: something to improve. White: something to keep.", "Its mark shows how it changed since the earlier checkpoint."],
    };
    case "theme": return {
      title: "Theme",
      lead: "Related clusters the AI grouped under one name.",
      uses: "The AI searches research, study and options for evidence and links what it finds; the arcs show those links. Themes are grouped into requirement areas.",
      notes: ["Dashed arc: evidence against the theme."],
    };
    case "area": return {
      title: "Requirement area",
      lead: "A product decision area: themes that belong together, with why it matters now and open questions.",
      uses: "Drafting concrete requirements from an area is the next step; the PM decides, never the AI.",
      notes: ["Blue improve, white keep, orange emerging, amber quality hand-over. Outlined = new at this checkpoint."],
    };
  }
}

function GuideBody({ mode, sel }: { mode: Mode; sel: Selection | null }) {
  const page = sel ? forSelection(sel, mode) : mode === "structure" ? STRUCTURE : SCAN;
  return (
    <div className="guide">
      <p className="guide-title">{page.title}</p>
      {page.lead && <p className="guide-lead">{page.lead}</p>}
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

/* ------------------------------------------------------------------------------------------- dock */
type Panel = "guide" | "agent";
const OPEN_KEY = "dock.open";
const readOpen = (): Panel | null => {
  try { const v = localStorage.getItem(OPEN_KEY); return v === "" ? null : v === "agent" ? "agent" : "guide"; } catch { return "guide"; }
};

/** `guide` replaces the built-in Guide content (page 3 brings its own, screens/definition/guide.tsx). */
export function Dock({ mode, sel, agent, running = false, guide }: { mode: Mode; sel: Selection | null; agent?: ReactNode; running?: boolean; guide?: ReactNode }) {
  // on Structure the live agent opens first while it works; otherwise whatever was open last (the Guide by default)
  const start = (): Panel | null => (mode !== "scan" && agent && running ? "agent" : readOpen());
  const [open, setOpen] = useState<Panel | null>(start);
  useEffect(() => { try { localStorage.setItem(OPEN_KEY, open ?? ""); } catch { /* private mode */ } }, [open]);
  useEffect(() => { setOpen(start()); }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (sel) setOpen((o) => (o ? "guide" : o)); }, [sel]);   // opening something explains it, if the dock is in use
  const shown = open === "agent" && !agent ? "guide" : open;
  const toggle = (p: Panel) => setOpen((o) => (o === p ? null : p));
  return (
    <section className="dock" data-open={shown ?? undefined} aria-label="Guide">
      {shown && (
        <div className="dock-body" id="dock-panel" key={shown}>
          {shown === "agent" ? agent : guide ?? <GuideBody mode={mode} sel={sel} />}
        </div>
      )}
      <div className="dock-pills">
        <button className="dock-pill" aria-expanded={shown === "guide"} aria-controls="dock-panel" onClick={() => toggle("guide")}>
          <BookOpen size={14} aria-hidden /> Guide
        </button>
        {agent && (
          <button className="dock-pill" aria-expanded={shown === "agent"} aria-controls="dock-panel" onClick={() => toggle("agent")}
                  data-running={running ? "" : undefined}>
            <Bot size={14} aria-hidden /> Agent{running && <i className="dock-live" aria-label="working" />}
          </button>
        )}
      </div>
    </section>
  );
}
