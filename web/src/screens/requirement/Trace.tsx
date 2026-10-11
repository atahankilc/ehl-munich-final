// Trace: follow one requirement for one car · market from a single customer comment to the PM's decision.
// Each stop shows the rule applied to ALL data (left) beside what it did HERE (right). ← → to step.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { api, qs } from "@/lib/api";
import { FIT_TYPE, HORIZON, KANO, MARKET } from "@/lib/labels";
import { fmtInt, fmtUsd, fmtWhen } from "@/lib/format";
import { Drawer } from "@/components/Drawer";
import { ErrorNote, Kbd, PriorityMark, SkeletonBlock } from "@/components/ui";
import "./trace.css";

type Spend = { calls: number; usd: number };
type TraceData = {
  requirement: { id: string; title: string };
  target: { key: string; label: string };
  steps: {
    collect: { global: { sources_by_kind: Record<string, number> }; example: null | { external_id: string; text: string; country: string | null; market: string | null; channel: string | null; wave: number }; example_from_other_market: boolean };
    read: { global: { extractor_version: string; extracted: number; in_scope: number; signals: number; unverified_quotes: number; spend: Spend }; signals: { signal_id: number; category: string; feedback_type: string; severity: string | null; need_statement: string | null; quote: string | null; quote_verified: number }[] };
    group: { global: { findings_by_kind: Record<string, number>; spend: Spend }; finding: null | { id: number; title: string; summary: string | null; n_signals: number; markets: { market: string; verbatims: number | null; share: number | null }[] }; link_counts: { kind: string; relation: string; n: number }[] };
    draft: { global: { requirements: number; duplicates_caught: number; spend: Spend }; title: string; description: string | null; horizon: string | null; kano_class: string | null; n_supporting: number; product_decision: string | null; evidence_summary: string | null; assumptions: string[] };
    fit: { global: { matrix: { check_type: string; result: string; n: number }[]; spend: Spend }; checks: { check_type: string; result: string; rationale: string }[] };
    score: { global: { priority_bands: Record<string, number> }; waterfall: { step: string; kind: string; start: number; end: number; delta: number }[]; score: number | null; ai_priority: string | null; cap_note?: string | null; priority_note?: string | null; gaps: string[] };
    decide: { global: { by_actor_type: Record<string, number> }; status: string; pm_priority: string | null; ai_priority: string | null; human_events: { ts: string; actor_id: string; action: string; rationale: string | null; new_value: string | null }[] };
    repeat: { global: { proposal_status_counts: Record<string, number> }; snapshots: { run_id: number; score: number | null; priority: string; ts: string; cause: string | null }[] };
  };
};

const STOPS = [
  { k: "collect", t: "A customer speaks", who: "Data" },
  { k: "read", t: "The AI reads it", who: "AI" },
  { k: "group", t: "Comments become a theme", who: "AI" },
  { k: "draft", t: "The theme becomes a requirement", who: "AI" },
  { k: "fit", t: "Brand, market and plant fit", who: "AI" },
  { k: "score", t: "The score, as arithmetic", who: "System" },
  { k: "decide", t: "The PM decides", who: "You" },
  { k: "repeat", t: "New evidence, new proposals", who: "AI → You" },
] as const;

export function TraceDrawer({ reqId, target, open, onClose }: { reqId: string; target: string | null; open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [dir, setDir] = useState(1);
  const q = useQuery({ queryKey: ["trace", reqId, target], queryFn: () => api.get<TraceData>(`/api/requirements/${reqId}/trace${qs({ target })}`), enabled: open });
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });
  useEffect(() => { if (open) setI(0); }, [open]);
  const step = (d: number) => {
    setDir(d);
    setI((x) => Math.max(0, Math.min(STOPS.length - 1, x + d)));
  };
  const s = STOPS[i];
  return (
    <Drawer open={open} onClose={onClose} width={980} title={q.data ? `Trace · ${q.data.requirement.title}` : "Trace"} sub={q.data ? `Following ${q.data.target.label} — left: the rule for all data · right: what happened here` : undefined}>
      {q.isLoading && <SkeletonBlock lines={8} />}
      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <div className="trace">
          <ol className="trace-route" aria-label="Steps">
            {STOPS.map((x, j) => (
              <li key={x.k}>
                <button className={`trace-stop${j === i ? " on" : j < i ? " past" : ""}`} onClick={() => { setDir(j > i ? 1 : -1); setI(j); }} aria-current={j === i}>
                  <span className="trace-dot" />
                  <span className="trace-stop-t">{x.t}</span>
                </button>
              </li>
            ))}
          </ol>
          <AnimatePresence mode="wait" initial={false} custom={dir}>
            <motion.section
              key={s.k}
              className="trace-step"
              custom={dir}
              initial={{ opacity: 0, x: dir * 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: dir * -16, transition: { duration: 0.14 } }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <header className="trace-head">
                <span className={`chip ${s.who === "You" ? "up" : s.who === "AI" || s.who === "AI → You" ? "blue" : ""}`}>{s.who}</span>
                <h3 className="t-title">{s.t}</h3>
                <span className="faint t-small num">{i + 1} / {STOPS.length}</span>
              </header>
              <div className="trace-cols">
                <div className="trace-rule">{rule(q.data, s.k)}</div>
                <div className="trace-here">{here(q.data, s.k)}</div>
              </div>
            </motion.section>
          </AnimatePresence>
          <footer className="trace-nav">
            <button className="btn" disabled={i === 0} onClick={() => step(-1)}><ArrowLeft /> Previous</button>
            <span className="faint t-micro"><Kbd>←</Kbd> <Kbd>→</Kbd></span>
            <button className="btn btn-primary" disabled={i === STOPS.length - 1} onClick={() => step(1)}>Next <ArrowRight /></button>
          </footer>
        </div>
      )}
    </Drawer>
  );
}

const spend = (s?: Spend) => (s ? `${fmtInt(s.calls)} AI calls · ${fmtUsd(s.usd)}` : "");

function rule(d: TraceData, k: string) {
  const s = d.steps;
  switch (k) {
    case "collect":
      return (<><p>Every source is stored with its provenance: file, sheet and row, or URL with date and trust tier.</p><dl className="trace-dl">{Object.entries(s.collect.global.sources_by_kind).map(([kk, n]) => <div key={kk}><dt>{kk.replace("_", " ")}</dt><dd className="num">{fmtInt(n)}</dd></div>)}</dl></>);
    case "read":
      return (<><p>A small model reads each comment, drops what's out of scope and extracts customer signals with an exact quote.</p><dl className="trace-dl"><div><dt>comments read</dt><dd className="num">{fmtInt(s.read.global.extracted)}</dd></div><div><dt>in scope</dt><dd className="num">{fmtInt(s.read.global.in_scope)}</dd></div><div><dt>signals</dt><dd className="num">{fmtInt(s.read.global.signals)}</dd></div><div><dt>quotes not verbatim</dt><dd className="num">{fmtInt(s.read.global.unverified_quotes)}</dd></div></dl><p className="faint t-small">{spend(s.read.global.spend)}</p></>);
    case "group":
      return (<><p>Similar signals are clustered into findings per car and market; study items and cited web research become findings too.</p><dl className="trace-dl">{Object.entries(s.group.global.findings_by_kind).map(([kk, n]) => <div key={kk}><dt>{kk}</dt><dd className="num">{fmtInt(n)}</dd></div>)}</dl><p className="faint t-small">{spend(s.group.global.spend)}</p></>);
    case "draft":
      return (<><p>The reasoning model drafts requirements that are product decisions — not restated defects — citing their findings. Repeats are merged, not duplicated.</p><dl className="trace-dl"><div><dt>requirements</dt><dd className="num">{s.draft.global.requirements}</dd></div><div><dt>duplicates caught</dt><dd className="num">{s.draft.global.duplicates_caught}</dd></div></dl><p className="faint t-small">{spend(s.draft.global.spend)}</p></>);
    case "fit":
      return (<><p>Four checks per car · market. Brand fit is a gate; market fit adjusts the score; plant & platform is context only.</p><dl className="trace-dl">{["brand", "market", "segment", "feasibility"].map((t) => <div key={t}><dt>{FIT_TYPE[t]?.label ?? t}</dt><dd className="num">{s.fit.global.matrix.filter((m) => m.check_type === t).map((m) => `${m.n} ${m.result}`).join(" · ")}</dd></div>)}</dl></>);
    case "score":
      return (<><p>Six weighted factors, scaled by evidence confidence, adjusted for market fit and effort. Must ≥ {s.score.global.priority_bands.Must ?? 60}, Should ≥ {s.score.global.priority_bands.Should ?? 45}. Deterministic — no AI.</p></>);
    case "decide":
      return (<><p>Only a named person can approve, reject or defer — always with a reason. The AI's priority stays a suggestion until confirmed.</p><dl className="trace-dl">{Object.entries(s.decide.global.by_actor_type).map(([a, n]) => <div key={a}><dt>{a === "ai" ? "AI events" : a === "human" ? "human events" : "system events"}</dt><dd className="num">{n}</dd></div>)}</dl></>);
    case "repeat":
      return (<><p>Each evidence wave re-scores everything. When a confirmed priority no longer matches, the AI proposes a change with its cause — it never changes a decision itself.</p><dl className="trace-dl">{Object.entries(s.repeat.global.proposal_status_counts).map(([a, n]) => <div key={a}><dt>{a} proposals</dt><dd className="num">{n}</dd></div>)}</dl></>);
  }
  return null;
}

function here(d: TraceData, k: string) {
  const s = d.steps;
  switch (k) {
    case "collect": {
      const ex = s.collect.example;
      if (!ex) return <p className="muted">No customer comment supports this requirement directly — it rests on study and web evidence.</p>;
      return (
        <>
          {s.collect.example_from_other_market && <p className="t-small" style={{ color: "var(--amber-ink)" }}>No comment from this market — showing one from {MARKET[ex.market ?? ""] ?? ex.market}.</p>}
          <blockquote className="trace-quote">{ex.text}</blockquote>
          <p className="faint t-small"><span className="id">{ex.external_id}</span> · {ex.country} · {ex.channel} · arrived in wave {ex.wave}</p>
        </>
      );
    }
    case "read":
      return s.read.signals.length ? (
        <ol className="signals">{s.read.signals.map((g) => <li key={g.signal_id} className="signal"><div className="row wrap" style={{ gap: 6 }}><span className="chip warn">{g.feedback_type.replace(/_/g, " ")}</span>{g.severity && <span className="chip outline">{g.severity}</span>}<span className="t-micro faint">{g.category}</span></div>{g.need_statement && <p className="signal-need">{g.need_statement}</p>}{g.quote && <blockquote className="signal-quote">“{g.quote}”</blockquote>}</li>)}</ol>
      ) : <p className="muted">No extracted signals for this example.</p>;
    case "group": {
      const f = s.group.finding;
      return f ? (<><div className="t-title" style={{ fontSize: 17 }}>{f.title}</div>{f.summary && <p className="muted" style={{ marginTop: 6 }}>{f.summary}</p>}<p className="t-small" style={{ marginTop: 10 }}>{fmtInt(f.n_signals)} signals · {f.markets.filter((m) => m.verbatims).map((m) => `${MARKET[m.market] ?? m.market} ${m.verbatims}`).join(" · ")}</p><p className="faint t-small" style={{ marginTop: 6 }}>This requirement cites {s.group.link_counts.map((l) => `${l.n} ${l.kind} (${l.relation})`).join(", ")}.</p></>) : <p className="muted">No comment theme behind this requirement.</p>;
    }
    case "draft":
      return (<><div className="t-title" style={{ fontSize: 17 }}>{s.draft.title}</div>{s.draft.product_decision && <p className="trace-ask">{s.draft.product_decision}</p>}<p className="muted" style={{ marginTop: 8 }}>{s.draft.description}</p><div className="row wrap" style={{ gap: 6, marginTop: 10 }}>{s.draft.kano_class && <span className="chip">{KANO[s.draft.kano_class]}</span>}{s.draft.horizon && <span className="chip">{HORIZON[s.draft.horizon]}</span>}<span className="chip outline">{s.draft.n_supporting} supporting findings</span></div>{s.draft.assumptions.length > 0 && <div style={{ marginTop: 12 }}><span className="telltale amber">Assumption</span><ul className="sw-list" style={{ marginTop: 6 }}>{s.draft.assumptions.slice(0, 3).map((a) => <li key={a}>{a}</li>)}</ul></div>}</>);
    case "fit":
      return <div className="col" style={{ gap: 10 }}>{s.fit.checks.map((c) => <div key={c.check_type}><span className={`telltale ${c.result === "pass" ? "green" : c.result === "warn" ? "amber" : "red"}`}>{FIT_TYPE[c.check_type]?.label ?? c.check_type} · {c.result}</span><p className="t-small muted" style={{ marginTop: 4 }}>{c.rationale}</p></div>)}</div>;
    case "score":
      return (<><div className="wf">{s.score.waterfall.map((w) => <div key={w.step} className={`wf-row ${w.kind === "total" ? "wf-t" : w.kind === "minus" ? "wf-c" : w.kind === "plus" ? "wf-m" : ""}`}><span className="wf-label">{w.step}</span><span className="wf-track"><span className="wf-bar" style={{ left: `${Math.max(0, w.start)}%`, width: `${Math.max(0, w.end - w.start)}%` }} /></span><span className="wf-val num">{w.kind === "total" ? w.delta.toFixed(1) : `${w.delta >= 0 ? "+" : "−"}${Math.abs(w.delta).toFixed(1)}`}</span></div>)}</div><p className="t-small" style={{ marginTop: 10 }}>AI suggests <PriorityMark p={s.score.ai_priority as never} ai size="sm" />{s.score.gaps.length ? ` · no data for ${s.score.gaps.join(", ")}` : ""}</p>{s.score.cap_note && <p className="faint t-small">{s.score.cap_note}</p>}</>);
    case "decide":
      return (<><p className="t-small">PM priority <PriorityMark p={s.decide.pm_priority as never} size="sm" /> · AI suggests <PriorityMark p={s.decide.ai_priority as never} ai size="sm" /></p><ol className="trace-events">{s.decide.human_events.length ? s.decide.human_events.map((e, j) => <li key={j}><b>{e.actor_id}</b> {e.action.replace(/_/g, " ")}{e.new_value && e.new_value.length < 30 ? ` → ${e.new_value}` : ""}<span className="faint"> · {fmtWhen(e.ts)}</span>{e.rationale && <div className="muted t-small">{e.rationale}</div>}</li>) : <li className="muted">No human decision yet.</li>}</ol></>);
    case "repeat":
      return <ol className="trace-events">{s.repeat.snapshots.map((h) => <li key={h.run_id}><b>Run {h.run_id}</b> · <span className="num">{h.score?.toFixed(1)}</span> <PriorityMark p={h.priority as never} ai size="sm" />{h.cause && <div className="muted t-small">{h.cause}</div>}</li>)}</ol>;
  }
  return null;
}
