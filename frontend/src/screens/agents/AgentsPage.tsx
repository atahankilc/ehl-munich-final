// The AI agents page (D-055): the one place that says which model does what, how hard it thinks, how much it may
// spend, and what it actually spent. GET/PUT /api/agents is the source of truth the LLM wrapper reads on every call.
// Top: the OpenAI key and the spend limits (D-054). Then the model tiers, one table per pipeline (model, reasoning
// effort, cap, on/off, spend), the priced models (add a new OpenAI model with its prices), and the usage details.
// Every change saves at once and is an audit event.
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { BudgetSettings } from "@/components/BudgetSettings";
import { UsageView, modelName } from "@/components/Usage";
import "@/components/sheet.css";
import "@/components/usage.css";
import "./agents.css";

interface Usage { usd: number; calls: number; failed: number; running: number; input_tokens: number; output_tokens: number; last: string | null; by_checkpoint: Record<string, number> }
interface Config { model: string | null; reasoning_effort: string | null; enabled: boolean; cap_usd: number | null }
interface Agent {
  key: string; name: string; description: string; kind: "responses" | "embeddings"; tier: "fast" | "smart" | "embed"; web_search: boolean;
  default_effort: string | null; default_model: string; model: string; effort: string | null; config: Config; usage: Usage;
}
interface Pipeline { key: string; label: string; about: string; agents: Agent[]; usd: number }
interface Model { id: string; kind: "responses" | "embeddings"; input: number; cached_input: number; output: number; builtin: boolean; used_by: string[]; tier: string[] }
interface State {
  pipelines: Pipeline[]; tiers: Record<"fast" | "smart" | "embed", { model: string; default: string; set_in_app: boolean }>;
  models: Model[]; efforts: string[]; legacy: Usage; flex_factor: number;
}

const usd = (v: number) => (v >= 1 ? `$${v.toFixed(2)}` : v >= 0.01 ? `$${v.toFixed(3)}` : v > 0 ? `$${v.toFixed(4)}` : "$0");
const when = (ts: string | null) => (ts ? new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "never");
const TIER: Record<string, string> = { fast: "Fast", smart: "Reasoning", embed: "Embeddings" };
const TIER_ABOUT: Record<string, string> = { fast: "bulk reading and classifying", smart: "reasoning-heavy steps", embed: "vectors for clustering and search" };
const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Saving failed.");

export function AgentsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["agents"], queryFn: () => api.get<State>("/api/agents"), refetchInterval: 15_000 });
  const [error, setError] = useState<string | null>(null);
  const s = q.data;

  async function save(call: () => Promise<State>) {
    setError(null);
    try {
      qc.setQueryData(["agents"], await call());
      await qc.invalidateQueries({ queryKey: ["usage"] });
    } catch (e) {
      setError(errText(e));
    }
  }

  return (
    <section className="pagesheet agentspage" aria-label="AI agents">
      <header className="ps-top">
        <div className="ps-title">
          <h1>AI agents</h1>
          <p className="ps-lede">Which model each agent uses, how hard it reasons, how much it may spend, and what it spent. Changes apply to the
            next call and are recorded in the audit trail. A changed model or effort is a new request, so cached answers no longer apply.</p>
        </div>
        {error && <p className="ag-error" role="alert">{error}</p>}
      </header>

      <div className="ps-section"><BudgetSettings /></div>

      {!s ? <p className="ps-label">{q.isError ? "The agents could not be loaded." : "Loading…"}</p> : <>
        <Tiers state={s} onSave={(body) => save(() => api.put<State>("/api/agents/tiers", body))} />

        {s.pipelines.map((p) => (
          <section key={p.key} className="ps-section">
            <h2>{p.label} <span className="ag-h-usd">{usd(p.usd)}</span></h2>
            <p className="ps-lede">{p.about}</p>
            <div className="ag-table" role="table" aria-label={p.label}>
              <div className="ag-row ag-head" role="row">
                <span>Agent</span><span>Model</span><span>Effort</span><span>Spend cap</span><span className="ag-r">Spent</span><span>On</span>
              </div>
              {p.agents.map((a) => (
                <AgentRow key={a.key} a={a} state={s} onSave={(cfg) => save(() => api.put<State>(`/api/agents/${a.key}`, cfg))} />
              ))}
            </div>
          </section>
        ))}

        <Models state={s} onAdd={(m) => save(() => api.post<State>("/api/agents/models", m))}
                onRemove={(id) => save(() => api.delete<State>(`/api/agents/models/${encodeURIComponent(id)}`))} />

        <section className="ps-section">
          <h2>Usage details</h2>
          <p className="ps-lede">Earlier wave pipeline (history only, not configurable): {usd(s.legacy.usd)} over {s.legacy.calls.toLocaleString("en-US")} calls.</p>
          <UsageView />
        </section>
      </>}
    </section>
  );
}

function AgentRow({ a, state, onSave }: { a: Agent; state: State; onSave: (c: Config) => void }) {
  const cfg = a.config;
  const [cap, setCap] = useState(cfg.cap_usd == null ? "" : String(cfg.cap_usd));
  useEffect(() => setCap(cfg.cap_usd == null ? "" : String(cfg.cap_usd)), [cfg.cap_usd]);
  const models = state.models.filter((m) => m.kind === a.kind);
  const put = (c: Partial<Config>) => onSave({ ...cfg, ...c });
  const saveCap = () => {
    const v = cap.trim() === "" ? null : Number(cap);
    if (v !== cfg.cap_usd && (v === null || (Number.isFinite(v) && v >= 0))) put({ cap_usd: v });
  };
  const capPct = cfg.cap_usd ? Math.min(100, (a.usage.usd / cfg.cap_usd) * 100) : 0;
  const u = a.usage;
  return (
    <div className="ag-row" role="row" data-off={cfg.enabled ? undefined : ""}>
      <span className="ag-name">
        <b>{a.name}{a.web_search && <Globe size={12} aria-label="uses web search" />}</b>
        <em>{a.description}</em>
      </span>
      <select className="u-input ag-select" value={cfg.model ?? ""} onChange={(e) => put({ model: e.target.value || null })} aria-label={`${a.name} model`}>
        <option value="">{TIER[a.tier]} tier · {modelName(a.default_model)}</option>
        {models.map((m) => <option key={m.id} value={m.id}>{modelName(m.id)}</option>)}
      </select>
      {a.kind === "responses"
        ? <select className="u-input ag-select" value={cfg.reasoning_effort ?? ""} onChange={(e) => put({ reasoning_effort: e.target.value || null })} aria-label={`${a.name} reasoning effort`}>
            <option value="">Default · {a.default_effort}</option>
            {state.efforts.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
        : <span className="ag-dim">–</span>}
      <span className="ag-cap">
        <input className="u-input u-money" type="number" min={0} step={0.5} placeholder="no cap" value={cap} aria-label={`${a.name} spend cap in dollars`}
               onChange={(e) => setCap(e.target.value)} onBlur={saveCap} onKeyDown={(e) => { if (e.key === "Enter") saveCap(); }} />
        {cfg.cap_usd != null && <i className="ag-capbar" aria-hidden><b style={{ width: `${capPct}%` }} data-full={capPct >= 100 ? "" : undefined} /></i>}
      </span>
      <span className="ag-r ag-spent" title={`${u.calls.toLocaleString("en-US")} calls${u.failed ? `, ${u.failed} failed` : ""} · last ${when(u.last)}${Object.keys(u.by_checkpoint).length ? `\n${Object.entries(u.by_checkpoint).map(([k, v]) => `${k === "cp1" ? "JAN 26" : k === "cp2" ? "JUL 26" : "no checkpoint"} ${usd(v)}`).join(" · ")}` : ""}`}>
        <b>{usd(u.usd)}</b><em>{u.calls ? `${u.calls.toLocaleString("en-US")} calls · ${when(u.last)}` : "not run"}{u.running ? ` · ${u.running} running` : ""}</em>
      </span>
      <label className="ag-switch" title={cfg.enabled ? "On: this agent may call its model" : "Off: calls are refused and the stage stops"}>
        <input type="checkbox" role="switch" checked={cfg.enabled} onChange={(e) => put({ enabled: e.target.checked })} aria-label={`${a.name} on`} />
        <i aria-hidden />
      </label>
    </div>
  );
}

function Tiers({ state, onSave }: { state: State; onSave: (b: Record<string, string | null>) => void }) {
  const cur = { fast: state.tiers.fast.model, smart: state.tiers.smart.model, embed: state.tiers.embed.model };
  const [draft, setDraft] = useState(cur);
  useEffect(() => setDraft(cur), [cur.fast, cur.smart, cur.embed]);   // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = draft.fast !== cur.fast || draft.smart !== cur.smart || draft.embed !== cur.embed;
  return (
    <section className="ps-section">
      <h2>Model tiers</h2>
      <p className="ps-lede">The model behind each tier. Every agent uses its tier's model unless it names its own below.</p>
      <form className="ag-tiers" onSubmit={(e) => { e.preventDefault(); if (dirty) onSave(draft); }}>
        {(["fast", "smart", "embed"] as const).map((t) => (
          <label key={t} className="u-field">
            <span>{TIER[t]} · {TIER_ABOUT[t]}{state.tiers[t].set_in_app ? "" : " (from .env)"}</span>
            <select className="u-input ag-select" value={draft[t]} onChange={(e) => setDraft({ ...draft, [t]: e.target.value })}>
              {state.models.filter((m) => m.kind === (t === "embed" ? "embeddings" : "responses")).map((m) => <option key={m.id} value={m.id}>{modelName(m.id)}</option>)}
            </select>
          </label>
        ))}
        <button type="submit" className="u-btn primary" disabled={!dirty}>Save</button>
      </form>
    </section>
  );
}

function Models({ state, onAdd, onRemove }: { state: State; onAdd: (m: Omit<Model, "builtin" | "used_by" | "tier">) => void; onRemove: (id: string) => void }) {
  const [m, setM] = useState({ id: "", kind: "responses" as Model["kind"], input: "", cached_input: "", output: "" });
  const nums = [m.input, m.cached_input, m.output].map(Number);
  const ok = m.id.trim() && [m.input, m.cached_input, m.output].every((v) => v.trim() !== "") && nums.every((v) => Number.isFinite(v) && v >= 0);
  return (
    <section className="ps-section">
      <h2>Models and prices</h2>
      <p className="ps-lede">USD per 1M tokens · input / cached input / output. The budget guard prices every call with these; a model without a price
        is refused. Built-in prices are kept in code (D-014); add a new OpenAI model here with its list prices.</p>
      <div className="ag-models" role="table" aria-label="Priced models">
        {state.models.map((x) => (
          <div key={x.id} className="ag-mrow" role="row">
            <span className="ag-name"><b>{modelName(x.id)}</b><em>{x.id}{x.builtin ? "" : " · added in the app"}</em></span>
            <span className="ag-dim">{x.kind === "embeddings" ? "embeddings" : "text"}</span>
            <span className="u-num">${x.input} / ${x.cached_input} / ${x.output}</span>
            <span className="ag-dim">{[...x.tier.map((t) => `${TIER[t]} tier`), ...x.used_by].join(", ") || "unused"}</span>
            {x.builtin ? <span /> : <button className="u-btn ag-icon" onClick={() => onRemove(x.id)} aria-label={`Remove ${x.id}`} title="Remove (only when unused)"><Trash2 size={13} /></button>}
          </div>
        ))}
      </div>
      <form className="ag-add" onSubmit={(e) => { e.preventDefault(); if (ok) { onAdd({ id: m.id.trim(), kind: m.kind, input: nums[0], cached_input: nums[1], output: nums[2] }); setM({ ...m, id: "", input: "", cached_input: "", output: "" }); } }}>
        <input className="u-input" placeholder="Model id, e.g. gpt-6.2-sol" value={m.id} onChange={(e) => setM({ ...m, id: e.target.value })} aria-label="Model id" />
        <select className="u-input ag-select" value={m.kind} onChange={(e) => setM({ ...m, kind: e.target.value as Model["kind"] })} aria-label="Kind">
          <option value="responses">text</option><option value="embeddings">embeddings</option>
        </select>
        {(["input", "cached_input", "output"] as const).map((k) => (
          <input key={k} className="u-input u-money" type="number" min={0} step={0.01} placeholder={k === "cached_input" ? "cached" : k} value={m[k]}
                 onChange={(e) => setM({ ...m, [k]: e.target.value })} aria-label={`${k.replace("_", " ")} price per 1M tokens`} />
        ))}
        <button type="submit" className="u-btn primary" disabled={!ok}>Add model</button>
      </form>
    </section>
  );
}
