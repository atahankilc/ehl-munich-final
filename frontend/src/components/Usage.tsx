// The Audit panel's Usage tab (the panel widens for it): every model call the app made, from `llm_usage`
// (GET /api/usage). The key and spend limits on top (BudgetSettings, D-054), then three instrument figures (spend against
// the stop, calls, tokens) with the spend
// split by model; one bar per pipeline sized by its spend, the open one listing its steps in plain words with model,
// calls, tokens and cost; the latest single calls and the price table behind a toggle.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BudgetSettings } from "./BudgetSettings";
import "./usage.css";

interface Step {
  pipeline: string; step: string; model: string; flex_calls: number; calls: number; failed: number; reserved: number;
  input_tokens: number; cached_tokens: number; output_tokens: number; reasoning_tokens: number; search_calls: number;
  usd: number; failed_usd: number; first: string; last: string; by_checkpoint: Record<string, number>; manual: boolean;
}
interface Pipeline { key: string; label: string; usd: number; calls: number; failed: number; steps: Step[] }
interface Call {
  id: number; at: string; job: string; pipeline: string; model: string; tier: string | null; status: string; usd: number;
  input_tokens: number | null; output_tokens: number | null; response_id: string | null; error: string | null;
}
interface Usage {
  budget: { spent: number; committed: number; confirm_above: number; stop_at: number };
  by_model: Record<string, number>;
  totals: { calls: number; failed: number; input_tokens: number; cached_tokens: number; output_tokens: number; first: string | null; last: string | null };
  prices: Record<string, { input: number; cached_input: number; output: number }>;
  flex_factor: number; pipelines: Pipeline[]; recent: Call[]; method: string;
}

const usd = (v: number) => (v >= 1 ? `$${v.toFixed(2)}` : v >= 0.01 ? `$${v.toFixed(3)}` : v > 0 ? `$${v.toFixed(4)}` : "$0");
const tok = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n));
const when = (ts: string) => new Date(ts).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

const MODEL: Record<string, { name: string; role: string }> = {
  "gpt-6.1-sol": { name: "GPT-6.1 Sol", role: "reasoning" },
  "gpt-6-luna": { name: "GPT-6 Luna", role: "bulk" },
  "text-embedding-3-small": { name: "Embedding 3 small", role: "vectors" },
};
const modelName = (m: string) => MODEL[m]?.name ?? m;
const SHORT: Record<string, string> = { "gpt-6.1-sol": "Sol", "gpt-6-luna": "Luna", "text-embedding-3-small": "Embedding" };

const PIPE_NAME: Record<string, { name: string; sub: string }> = {
  definition: { name: "Requirement definition", sub: "D-048 · define, specify, couple" },
  structure: { name: "Structure & context", sub: "D-043 · classify, cluster, link evidence, areas" },
  sources: { name: "Sources", sub: "D-026, D-031 · web research agents, price lists" },
  legacy: { name: "Earlier pipeline", sub: "D-022 – D-033 · superseded, history only" },
};
const STEP: Record<string, string> = {
  "structure.benchmarks": "Extract benchmarks", define: "Define requirements", "research:benchmarks": "Research gaps on the web",
  specify: "Specify metrics and targets", couple: "Couple requirements", "couple:recheck": "Re-check couplings",
  "embed:comments:galaxy": "Embed comments for the 3D layout", "classify:extract-v4:ab": "Classifier A/B test",
  "classify:extract-v4": "Classify comments into signals", "embed:signals:v4": "Embed signals", "embed:nodes": "Embed evidence items",
  "contextualize:standardize": "Write findings per cluster", "embed:insights": "Embed findings", "contextualize:duplicates": "Judge duplicate findings",
  "contextualize:themes": "Name themes", "embed:themes": "Embed themes", "contextualize:link": "Link themes to evidence",
  areas: "Group themes into areas", "classify:study-aspects": "Map study items", "classify:option-aspects": "Map options",
  "classify:research": "Read research items", "websearch-smoke": "Web search test", "ingest:options": "Read the price lists",
  "research:review_miner": "Review miner agent", "research:trend_scout": "Trend scout agent", "research:competitor_scout": "Competitor scout agent",
  "research:market_analyst": "Market analyst agent", "research:market_profile_scout": "Market profile agent", "research:findings": "Summarise research findings",
  "pilot:extract": "Pilot: extract", "pilot:derive": "Pilot: derive", "extract:extract-v2": "Extract signals (v2)", "extract:extract-v3": "Extract signals (v3)",
  "recheck:extract-v2": "Re-check out-of-scope (v2)", "embed:signals": "Embed signals", "findings:label": "Label findings", derive: "Derive requirements",
  consolidate: "Consolidate requirements", link: "Link evidence (old linker)", "fit:luna": "Fit checks", "fit:sol": "Fit re-checks",
  "bench:judge": "Benchmark judge", challenge: "Challenge requirements", "challenge:embed": "Embed for challenge", match_existing: "Match to existing requirements",
  "reconciliation:lost-usage-rows": "Lost usage rows (manual estimate)",
};
const stepName = (s: string) => STEP[s] ?? s.replace(/[:_.]/g, " ");

export function UsageView() {
  const q = useQuery({ queryKey: ["usage"], queryFn: () => api.get<Usage>("/api/usage?limit=60"), refetchInterval: 10_000 });
  const [pipe, setPipe] = useState("structure");
  const [more, setMore] = useState(false);
  const d = q.data;
  if (!d) return <p className="usage-empty label">{q.isError ? "Usage could not be loaded." : "Loading…"}</p>;
  const b = d.budget;
  const pct = (v: number, of: number) => `${Math.max(0, Math.min(100, (v / Math.max(of, 1e-9)) * 100))}%`;
  const total = d.pipelines.reduce((s, p) => s + p.usd, 0);
  const models = Object.entries(d.by_model).sort((x, y) => y[1] - x[1]);
  const open = d.pipelines.find((p) => p.key === pipe) ?? d.pipelines[0];
  const steps = [...open.steps].sort((x, y) => y.usd - x.usd);
  const stepMax = Math.max(...steps.map((s) => s.usd), 1e-9);
  const worst = d.pipelines.reduce((s, p) => s + p.steps.reduce((t, x) => t + x.failed_usd, 0), 0);

  return (
    <div className="usage">
      <BudgetSettings />

      {/* ---------------------------------------------------------------- figures */}
      <section className="u-figures">
        <div className="u-fig u-fig-spend">
          <span className="label">Spent</span>
          <span className="num">{usd(b.spent)}</span>
          <div className="u-budget" role="img" aria-label={`${usd(b.spent)} of the $${b.stop_at} stop`}>
            <i style={{ width: pct(b.spent, b.stop_at) }} />
            <span style={{ left: pct(b.confirm_above, b.stop_at) }} />
          </div>
          <span className="u-sub">stops at ${b.stop_at.toFixed(0)} · asks before spending above ${b.confirm_above.toFixed(0)}</span>
        </div>
        <div className="u-fig">
          <span className="label">Calls</span>
          <span className="num">{d.totals.calls.toLocaleString("en-US")}</span>
          <span className="u-sub">{d.totals.failed} failed</span>
        </div>
        <div className="u-fig">
          <span className="label">Tokens</span>
          <span className="num">{tok(d.totals.input_tokens + d.totals.output_tokens)}</span>
          <span className="u-sub">{tok(d.totals.input_tokens)} in ({Math.round((d.totals.cached_tokens / Math.max(1, d.totals.input_tokens)) * 100)}% cached) · {tok(d.totals.output_tokens)} out</span>
        </div>
      </section>

      {/* ---------------------------------------------------------------- by model */}
      <section className="u-models" aria-label="Spend by model">
        <div className="u-stack">{models.map(([m, v], i) => <i key={m} data-i={i} style={{ width: pct(v, total) }} title={`${modelName(m)} ${usd(v)}`} />)}</div>
        <div className="u-legend">
          {models.map(([m, v], i) => (
            <span key={m}><i data-i={i} />{modelName(m)}<em>{MODEL[m]?.role}</em><b>{usd(v)}</b></span>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------- pipelines */}
      <section className="u-pipes" role="tablist" aria-label="Pipelines">
        {d.pipelines.map((p) => (
          <button key={p.key} role="tab" aria-selected={p.key === open.key} className="u-pipe" onClick={() => setPipe(p.key)}>
            <span className="u-pipe-top"><span className="u-pipe-name">{PIPE_NAME[p.key]?.name ?? p.label}</span><span className="u-pipe-usd">{usd(p.usd)}</span></span>
            <span className="u-pipe-bar"><i style={{ width: pct(p.usd, total) }} /></span>
            <span className="u-pipe-sub">{PIPE_NAME[p.key]?.sub} · {p.calls.toLocaleString("en-US")} calls</span>
          </button>
        ))}
      </section>

      {/* ---------------------------------------------------------------- steps of the open pipeline */}
      <section className="u-steps" role="table" aria-label={open.label}>
        <div className="u-row u-head" role="row"><span>Step</span><span>Model</span><span className="u-r">Calls</span><span className="u-r">Tokens in / out</span><span className="u-r">Cost</span></div>
        {steps.map((s) => (
          <div key={`${s.step}|${s.model}`} className="u-row" role="row"
               title={`${s.step}\n${when(s.first)} – ${when(s.last)}${s.flex_calls ? `\n${s.flex_calls} of ${s.calls} on Flex (−50 %)` : ""}${s.reasoning_tokens ? `\nreasoning tokens ${tok(s.reasoning_tokens)}` : ""}${s.search_calls ? `\nweb searches ${s.search_calls}` : ""}${Object.keys(s.by_checkpoint).some((k) => k !== "—") ? `\n${Object.entries(s.by_checkpoint).map(([k, v]) => `${k === "cp1" ? "JAN 26" : k === "cp2" ? "JUL 26" : "no checkpoint"} ${usd(v)}`).join(" · ")}` : ""}`}>
            <span className="u-step">{stepName(s.step)}</span>
            <span className="u-model" data-model={SHORT[s.model] ?? s.model}>{SHORT[s.model] ?? s.model}</span>
            <span className="u-r u-num">{s.calls}{s.failed > 0 && <em> · {s.failed} failed</em>}</span>
            <span className="u-r u-num">{s.manual ? "–" : `${tok(s.input_tokens)} / ${tok(s.output_tokens)}`}</span>
            <span className="u-r u-cost"><span className="u-cost-bar"><i style={{ width: pct(s.usd, stepMax) }} /></span><b>{usd(s.usd)}</b></span>
          </div>
        ))}
      </section>

      {/* ---------------------------------------------------------------- method, prices, latest calls */}
      <section className="u-foot">
        <p className="usage-note">
          Cost = OpenAI's reported tokens × list prices, computed when each call settles (Flex −{Math.round((1 - d.flex_factor) * 100)} %).
          {worst > 0 && <> {usd(worst)} of it is the worst-case estimate kept by failed calls.</>} Hover a step for checkpoints, time range and Flex share.
        </p>
        <button className="u-toggle" aria-expanded={more} onClick={() => setMore((m) => !m)}>{more ? "Hide" : "Show"} latest calls and prices</button>
        {more && (
          <div className="u-more">
            <ol className="u-calls">
              {d.recent.map((c) => (
                <li key={c.id} data-status={c.status} title={[c.response_id && `OpenAI response ${c.response_id}`, c.error].filter(Boolean).join("\n")}>
                  <span className="u-dim">{when(c.at)}</span><span className="u-step">{c.job}</span>
                  <span className="u-model" data-model={SHORT[c.model] ?? c.model}>{SHORT[c.model] ?? c.model}</span>
                  <span className="u-r u-num">{c.status === "failed" ? "failed" : c.status === "reserved" ? "running" : `${tok(c.input_tokens ?? 0)} / ${tok(c.output_tokens ?? 0)}`}</span>
                  <span className="u-r u-num">{usd(c.usd)}</span>
                </li>
              ))}
            </ol>
            <div className="u-prices">
              <span className="label">Per 1M tokens · input / cached / output</span>
              {Object.entries(d.prices).map(([m, p]) => <span key={m}>{modelName(m)} <b>${p.input} / ${p.cached_input} / ${p.output}</b></span>)}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
