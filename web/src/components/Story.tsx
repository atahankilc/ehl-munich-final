// Story mode: the pitch path through the real app. A small presenter card walks BMW's judges from "what changed"
// to "the deliverable"; every step is a live screen, nothing is mocked.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, Presentation, X } from "lucide-react";

type Step = { to: string; title: string; say: string };
export const STORY: Step[] = [
  { to: "/", title: "What should the next BMW offer?", say: "10k customer comments, a study, sales and cited web research become ranked requirements per car and market. Three simulated waves stand for ~2 years. This briefing shows what the last wave changed — compiled from the data, no AI call." },
  { to: "/decide", title: "The AI proposes, the PM decides", say: "Everything that needs a human sits in one queue. Here the AI suggests lowering a priority the PM set earlier — with its cause. It never changes a decision itself." },
  { to: "/decide/req:REQ-0006", title: "One decision, with a reason", say: "The need, the decision it asks for, what customers say per market, study and competitor evidence, fit gates, the AI's priority per car and market. Approve, defer or reject — the reason goes into the audit trail." },
  { to: "/cars/G60?market=US", title: "The car is the canvas", say: "Today's 5 Series in 3D. Every recommendation is pinned where customers experience it; click a zone and the car opens up. Next to it: what today's car already offers there." },
  { to: "/cars/G68?market=CN&zone=cockpit", title: "Markets are different customers", say: "Same car line, China long-wheelbase. Digital reliability is a Must here and a Could elsewhere. China has no comments of its own — the app says so instead of hiding it." },
  { to: "/markets/CN", title: "Who these customers are", say: "Climate, usage, expectations, charging — and where China disagrees with the rest of the world, with cited competitor and trend signals." },
  { to: "/requirements/REQ-0001", title: "One number, fully opened", say: "The score per market, its arithmetic, its history across waves, and the chain down to the original comment. 'Trace step by step' walks one comment to the decision." },
  { to: "/evidence?tab=gaps", title: "What isn't covered yet", say: "Customer themes no requirement cites yet — the honest backlog for the next wave. Defects go to quality, not into requirements." },
  { to: "/process", title: "A process, not a one-shot list", say: "Each wave brings new evidence; the AI re-scores and proposes changes; the PM decides. Weights are a PM lever and re-scoring is free and deterministic." },
  { to: "/process?tab=audit", title: "Every action, audited", say: "Who, when, why, which model — AI and people alike. Append-only: the database rejects edits and deletions." },
  { to: "/process?tab=deliver", title: "The deliverable", say: "The requirement list BMW asked for: ID, description, findings and sources, score and rationale, evidence level, assumptions, decision status — as JSON, CSV or a report." },
];

type Ctx = { on: boolean; i: number; start: () => void; stop: () => void; go: (i: number) => void };
const StoryCtx = createContext<Ctx>({ on: false, i: 0, start: () => {}, stop: () => {}, go: () => {} });
const KEY = "successor.story";

function load(): { on: boolean; i: number } {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "") as { on: boolean; i: number };
  } catch {
    return { on: false, i: 0 };
  }
}

export function StoryProvider({ children }: { children: ReactNode }) {
  const [st, setSt] = useState(load);
  const nav = useNavigate();
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(st));
    } catch {
      /* fine without persistence */
    }
  }, [st]);
  const go = useCallback(
    (i: number) => {
      const j = Math.max(0, Math.min(STORY.length - 1, i));
      setSt({ on: true, i: j });
      nav(STORY[j].to);
    },
    [nav],
  );
  const value = useMemo<Ctx>(
    () => ({ ...st, start: () => go(0), stop: () => setSt((s) => ({ ...s, on: false })), go }),
    [st, go],
  );
  return <StoryCtx.Provider value={value}>{children}</StoryCtx.Provider>;
}

export const useStory = () => useContext(StoryCtx);

export function StoryCard() {
  const { on, i, go, stop } = useStory();
  const loc = useLocation();
  const s = STORY[i];
  const here = `${loc.pathname}${loc.search}` === s?.to || loc.pathname === s?.to.split("?")[0];
  useEffect(() => {
    if (!on) return;
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (e.key === "]" ) go(i + 1);
      if (e.key === "[") go(i - 1);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [on, i, go]);
  return (
    <AnimatePresence>
      {on && s && (
        <motion.aside
          className="story"
          aria-label="Demo story"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="story-top">
            <span className="story-step num">
              <Presentation size={14} /> {i + 1} / {STORY.length}
            </span>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={stop} aria-label="End story mode">
              <X />
            </button>
          </div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.22 }}>
              <div className="story-title">{s.title}</div>
              <p className="story-say">{s.say}</p>
            </motion.div>
          </AnimatePresence>
          <div className="story-dots" aria-hidden>
            {STORY.map((_, j) => (
              <i key={j} className={j === i ? "on" : j < i ? "past" : ""} />
            ))}
          </div>
          <div className="story-nav">
            <button className="btn btn-sm" disabled={i === 0} onClick={() => go(i - 1)}>
              <ArrowLeft /> Back
            </button>
            {!here && (
              <button className="btn btn-sm btn-ghost" onClick={() => go(i)}>
                Return to this step
              </button>
            )}
            <button className="btn btn-sm btn-primary" disabled={i === STORY.length - 1} onClick={() => go(i + 1)}>
              Next <ArrowRight />
            </button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
