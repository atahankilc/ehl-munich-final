// Requirement building blocks reused by Decide and the Requirement page, so a requirement reads the same
// wherever the PM meets it.
import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ChevronDown, Quote as QuoteIcon, ShieldAlert } from "lucide-react";
import type { FitRow, Priority, RequirementDetail } from "@/lib/types";
import { FIT_TYPE, HORIZON, KANO, MARKET, PRIORITIES, REALIZATION } from "@/lib/labels";
import { fmtPct } from "@/lib/format";
import { EvidenceMeter, PriorityMark, ScoreBar } from "./ui";
import "./req.css";

export function ReqTags({ r }: { r: Pick<RequirementDetail, "category" | "kano_class" | "horizon" | "effort" | "must_not_lose"> }) {
  return (
    <div className="row wrap" style={{ gap: 6 }}>
      <span className="chip outline">{r.category}</span>
      {r.kano_class && <span className="chip">{KANO[r.kano_class] ?? r.kano_class}</span>}
      {r.horizon && <span className="chip">{HORIZON[r.horizon] ?? r.horizon}</span>}
      {r.effort && <span className="chip outline" title="Rough effort">Effort {r.effort}</span>}
      {r.must_not_lose && <span className="chip blue">Protects a strength</span>}
    </div>
  );
}

export function DecisionAsk({ r }: { r: RequirementDetail }) {
  const ask = r.derivation?.product_decision;
  return (
    <div className="ask">
      {ask ? (
        <>
          <div className="ask-label">The decision this asks for</div>
          <p className="ask-text">{ask}</p>
          {r.description && <p className="ask-need">{r.description}</p>}
        </>
      ) : (
        <>
          <div className="ask-label">What customers need</div>
          <p className="ask-text ask-text-sm">{r.description}</p>
        </>
      )}
    </div>
  );
}

/** "What customers say": share of in-scope comments per market; silent markets are labelled, not hidden. */
export function VoiceByMarket({ r }: { r: RequirementDetail }) {
  const rows = r.targets
    .filter((t) => t.voice)
    .map((t) => ({ key: t.target.key, label: t.target.label, ...t.voice! }))
    .sort((a, b) => (b.share ?? -1) - (a.share ?? -1));
  const max = Math.max(0.01, ...rows.map((x) => x.share ?? 0));
  return (
    <div className="voice">
      {rows.map((v) => (
        <div key={v.key} className="voice-row">
          <span className="voice-label">{v.label}</span>
          {v.own && v.verbatims > 0 ? (
            <>
              <span className="voice-track">
                <span style={{ width: `${((v.share ?? 0) / max) * 100}%` }} />
              </span>
              <span className="voice-num num">
                {v.verbatims.toLocaleString()}
                <span className="faint"> of {v.base?.toLocaleString() ?? "–"}</span>
                <span className="muted"> · {fmtPct(v.share)}</span>
                {v.verbatims < 5 && <span className="chip warn" style={{ marginLeft: 6 }}>small sample</span>}
              </span>
            </>
          ) : (
            <span className="voice-silent">No own customer comments — rests on study and web evidence</span>
          )}
        </div>
      ))}
    </div>
  );
}

export function Quotes({ r, limit = 3 }: { r: RequirementDetail; limit?: number }) {
  const [all, setAll] = useState(false);
  const qs = all ? r.quotes : r.quotes.slice(0, limit);
  if (!r.quotes.length) return <p className="muted t-small">No direct customer quotes for this requirement.</p>;
  return (
    <div className="quotes">
      {qs.map((q) => (
        <figure key={`${q.external_id}${q.quote.slice(0, 12)}`} className="quote">
          <QuoteIcon className="quote-mark" aria-hidden />
          <blockquote>{q.quote}</blockquote>
          <figcaption>
            {MARKET[q.market] ?? q.market}
            {q.country ? ` · ${q.country}` : ""} · <span className="id">{q.external_id}</span>
          </figcaption>
        </figure>
      ))}
      {r.quotes.length > limit && (
        <button className="btn btn-ghost btn-sm" onClick={() => setAll(!all)}>
          {all ? "Fewer quotes" : `All ${r.quotes.length} quotes`}
        </button>
      )}
    </div>
  );
}

export function StudyAndWeb({ r }: { r: RequirementDetail }) {
  if (!r.study.length && !r.web.length) return null;
  return (
    <div className="sw">
      {r.study.length > 0 && (
        <div>
          <div className="sec-label">Customer study</div>
          <ul className="sw-list">
            {r.study.map((s) => (
              <li key={s.finding_id}>{s.title}</li>
            ))}
          </ul>
        </div>
      )}
      {r.web.length > 0 && (
        <div>
          <div className="sec-label">Competitors, reviews and trends</div>
          <ul className="sw-list">
            {r.web.map((w) => (
              <li key={w.finding_id}>
                {w.title} {w.best_tier && <span className={`chip ${w.best_tier === "T1" ? "up" : w.best_tier === "T2" ? "warn" : "down"}`} title="Source trust tier">{w.best_tier}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function Conflict({ r }: { r: RequirementDetail }) {
  const text = r.conflicting_evidence && !/^none( found)?\.?$/i.test(r.conflicting_evidence.trim()) ? r.conflicting_evidence : null;
  if (!text && !r.contradicting.length) return null;
  return (
    <div className="conflict" role="note">
      <AlertTriangle aria-hidden />
      <div>
        <div className="conflict-title">Evidence points the other way too</div>
        {text && <p>{text}</p>}
        {r.contradicting.length > 0 && (
          <p className="muted t-small">
            {r.contradicting.length} contradicting finding{r.contradicting.length === 1 ? "" : "s"}: {r.contradicting.slice(0, 3).map((c) => c.title).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}

/** Per car · market: AI score + suggested priority, evidence, and the PM's own priority (editable). */
export function MarketTable({
  r,
  draft,
  setDraft,
  focusKey,
  compact,
}: {
  r: RequirementDetail;
  draft?: Record<string, Priority | null>;
  setDraft?: (d: Record<string, Priority | null>) => void;
  focusKey?: string | null;
  compact?: boolean;
}) {
  const rows = [...r.targets].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  return (
    <table className="table mt">
      <thead>
        <tr>
          <th>Car · market</th>
          {compact ? <th>AI suggests</th> : (<><th>AI score</th><th>AI suggests</th></>)}
          <th>Evidence</th>
          <th>{setDraft ? "Your priority" : "PM priority"}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((t) => {
          const key = t.target.key;
          const cur = draft && key in draft ? draft[key] : t.pm_priority;
          return (
            <tr key={key} className={focusKey === key ? "mt-focus" : undefined}>
              <td>
                <div className="mt-target">{t.target.label}</div>
                {t.realization && <div className="t-micro faint">{REALIZATION[t.realization] ?? t.realization}</div>}
              </td>
              {compact ? (
                <td>
                  <div className="mt-ai">
                    <PriorityMark p={t.ai_priority} ai size="sm" />
                    <ScoreBar score={t.score} width={44} />
                  </div>
                </td>
              ) : (
                <>
                  <td>
                    <ScoreBar score={t.score} width={72} />
                  </td>
                  <td>
                    <PriorityMark p={t.ai_priority} ai size="sm" />
                  </td>
                </>
              )}
              <td>
                <EvidenceMeter level={t.evidence_level} />
              </td>
              <td>
                {setDraft ? (
                  <div className="pchoice" role="radiogroup" aria-label={`Your priority for ${t.target.label}`}>
                    {PRIORITIES.map((p) => (
                      <button
                        key={p}
                        role="radio"
                        aria-checked={cur === p}
                        className={`pchoice-b pc-${p.toLowerCase()}`}
                        title={p}
                        aria-label={p}
                        onClick={() => setDraft({ ...(draft ?? {}), [key]: cur === p ? null : p })}
                      >
                        {compact ? p[0] : p}
                      </button>
                    ))}
                  </div>
                ) : (
                  <PriorityMark p={t.pm_priority} size="sm" />
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const ORDER = ["brand", "compliance", "market", "segment", "feasibility"];
export function FitGates({ fit, overridden = [], onOverride }: { fit: FitRow[]; overridden?: string[]; onOverride?: (targetKey: string) => void }) {
  const types = ORDER.filter((t) => fit.some((f) => f.check_type === t)).concat(
    [...new Set(fit.map((f) => f.check_type))].filter((t) => !ORDER.includes(t)),
  );
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="gates">
      {types.map((t) => {
        const rows = fit.filter((f) => f.check_type === t);
        const fails = rows.filter((f) => f.result === "fail" && !overridden.includes(f.target.key));
        const warns = rows.filter((f) => f.result === "warn");
        const tone = fails.length ? "red" : warns.length ? "amber" : "green";
        const word = fails.length ? `${fails.length} fail` : warns.length ? `${warns.length} warn` : "pass";
        const meta = FIT_TYPE[t] ?? { label: t, effect: "" };
        return (
          <div key={t} className="gate">
            <button className="gate-head" onClick={() => setOpen(open === t ? null : t)} aria-expanded={open === t}>
              <span className={`telltale ${tone}`}>{meta.label}</span>
              <span className="gate-word">{word}</span>
              <span className="gate-effect faint">{meta.effect}</span>
              <ChevronDown className={`gate-chev${open === t ? " up" : ""}`} aria-hidden />
            </button>
            {open === t && (
              <div className="gate-body">
                {dedupe(rows).map((g) => (
                  <div key={g.rationale + g.result} className="gate-item">
                    <div className="row wrap" style={{ gap: 6 }}>
                      <span className={`chip ${g.result === "pass" ? "up" : g.result === "warn" ? "warn" : "down"}`}>{g.result}</span>
                      <span className="t-small muted">{g.keys.join(", ")}</span>
                    </div>
                    <p className="gate-why">{g.rationale}</p>
                  </div>
                ))}
              </div>
            )}
            {fails.length > 0 && onOverride && (
              <div className="gate-fail">
                <ShieldAlert aria-hidden />
                <span>
                  {meta.label} fails for {fails.map((f) => f.target.label).join(", ")} — approval is blocked until you override with a reason.
                </span>
                {fails.map((f) => (
                  <button key={f.target.key} className="btn btn-sm btn-danger" onClick={() => onOverride(f.target.key)}>
                    Override {f.target.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function dedupe(rows: FitRow[]) {
  const m = new Map<string, { result: string; rationale: string; keys: string[] }>();
  for (const r of rows) {
    const k = `${r.result}|${r.rationale}`;
    const e = m.get(k) ?? { result: r.result, rationale: r.rationale, keys: [] };
    e.keys.push(r.target.label);
    m.set(k, e);
  }
  return [...m.values()];
}

export function AssumptionsBlock({ r }: { r: RequirementDetail }) {
  const a = r.assumptions_list;
  const u = r.uncertainties_list;
  if (!a.length && !u.length) return null;
  return (
    <div className="au">
      {a.length > 0 && (
        <div className="au-col">
          <div className="au-label"><span className="telltale amber">Assumption</span> <span className="faint t-micro">forward-looking, not evidence</span></div>
          <ul>{a.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      {u.length > 0 && (
        <div className="au-col">
          <div className="au-label"><span className="telltale red">Uncertainty</span></div>
          <ul>{u.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

export function ReqLink({ id, children }: { id: string; children?: React.ReactNode }) {
  return <Link to={`/requirements/${id}`}>{children ?? id}</Link>;
}
