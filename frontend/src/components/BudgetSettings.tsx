// Usage tab → "Budget and API key" (D-054, GET/PUT /api/settings): the OpenAI key the AI runs use and the two spend
// limits. Above "ask before spending" every new run must be confirmed first (a y/N prompt in the terminal); at "stop"
// no call is made. The key is never sent back by the API, only a masked form.
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";

interface Settings {
  openai: { configured: boolean; source: "app" | "env" | null; masked: string | null };
  budget: { confirm_above_usd: number; stop_at_usd: number; spent_usd: number; committed_usd: number; asking: boolean; stopped: boolean };
}

const money = (v: number) => `$${v.toFixed(2)}`;

export function BudgetSettings() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api.get<Settings>("/api/settings") });
  const [key, setKey] = useState("");
  const [confirmAbove, setConfirmAbove] = useState("");
  const [stopAt, setStopAt] = useState("");
  const [busy, setBusy] = useState<null | "key" | "budget">(null);
  const [msg, setMsg] = useState<{ on: "key" | "budget"; text: string; error?: boolean } | null>(null);
  const s = q.data;

  useEffect(() => {
    if (!s) return;
    setConfirmAbove(String(s.budget.confirm_above_usd));
    setStopAt(String(s.budget.stop_at_usd));
  }, [s?.budget.confirm_above_usd, s?.budget.stop_at_usd]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!s) return null;

  async function run(on: "key" | "budget", call: () => Promise<Settings>, ok: string) {
    setBusy(on);
    setMsg(null);
    try {
      qc.setQueryData(["settings"], await call());
      await qc.invalidateQueries({ queryKey: ["usage"] });
      setMsg({ on, text: ok });
      if (on === "key") setKey("");
    } catch (e) {
      setMsg({ on, text: e instanceof ApiError ? e.message : "Saving failed.", error: true });
    } finally {
      setBusy(null);
    }
  }

  const saveKey = () => run("key", () => api.put<Settings>("/api/settings/openai-key", { key }), "Key checked with OpenAI and saved.");
  const removeKey = () => run("key", () => api.delete<Settings>("/api/settings/openai-key"), "Key removed from the app.");
  const ca = Number(confirmAbove), st = Number(stopAt);
  const limitsValid = confirmAbove !== "" && stopAt !== "" && st > 0 && ca >= 0 && ca <= st;
  const limitsDirty = ca !== s.budget.confirm_above_usd || st !== s.budget.stop_at_usd;
  const saveBudget = () => run("budget", () => api.put<Settings>("/api/settings/budget", { confirm_above_usd: ca, stop_at_usd: st }), "Limits saved.");
  const b = s.budget;

  return (
    <section className="u-settings" aria-label="Budget and API key">
      <div className="u-set">
        <span className="label">OpenAI API key</span>
        <p className="u-set-state">
          {s.openai.configured
            ? <><b>{s.openai.masked}</b> {s.openai.source === "app" ? "saved in the app" : "from .env"}</>
            : <b>Not set: AI runs can't start.</b>}
        </p>
        <form className="u-set-row" onSubmit={(e) => { e.preventDefault(); if (key.trim()) saveKey(); }}>
          <input className="u-input" type="password" autoComplete="off" spellCheck={false} placeholder={s.openai.configured ? "Replace with a new key" : "sk-…"}
                 value={key} onChange={(e) => setKey(e.target.value)} aria-label="New OpenAI API key" />
          <button type="submit" className="u-btn primary" disabled={!key.trim() || busy !== null}>{busy === "key" ? "Checking…" : "Save"}</button>
          {s.openai.source === "app" && <button type="button" className="u-btn" disabled={busy !== null} onClick={removeKey}>Remove</button>}
        </form>
        {msg?.on === "key" && <p className="u-sub" data-error={msg.error || undefined} role="status">{msg.text}</p>}
      </div>

      <div className="u-set">
        <span className="label">Spend limits</span>
        <p className="u-set-state">
          {b.stopped ? <b>Stopped at {money(b.committed_usd)}: no AI call runs until you raise the stop.</b>
            : b.asking ? <b>Past {money(b.confirm_above_usd)}: every new AI run asks before it spends.</b>
            : <>{money(b.committed_usd)} committed. Runs ask first above {money(b.confirm_above_usd)} and stop at {money(b.stop_at_usd)}.</>}
        </p>
        <form className="u-set-row" onSubmit={(e) => { e.preventDefault(); if (limitsValid && limitsDirty) saveBudget(); }}>
          <label className="u-field"><span>Ask before spending above $</span>
            <input className="u-input u-money" type="number" min={0} step={1} value={confirmAbove} onChange={(e) => setConfirmAbove(e.target.value)} /></label>
          <label className="u-field"><span>Stop at $</span>
            <input className="u-input u-money" type="number" min={1} step={1} value={stopAt} onChange={(e) => setStopAt(e.target.value)} /></label>
          <button type="submit" className="u-btn primary" disabled={!limitsValid || !limitsDirty || busy !== null}>{busy === "budget" ? "Saving…" : "Save"}</button>
        </form>
        {!limitsValid && <p className="u-sub" data-error>"Ask before" must be between $0 and the stop.</p>}
        {msg?.on === "budget" && <p className="u-sub" data-error={msg.error || undefined} role="status">{msg.text}</p>}
      </div>
    </section>
  );
}
