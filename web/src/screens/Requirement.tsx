// Requirement: one number, fully opened. Headline score per car · market → its arithmetic → its history →
// the findings, signals and customer words underneath → fit gates → every decision ever taken on it.
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Car, ChevronRight, Footprints, MessageCircleQuestion, PencilLine, Scale } from "lucide-react";
import { api, invalidateAll, logView } from "@/lib/api";
import type { AuditEvent, Meta, RequirementDetail } from "@/lib/types";
import { CAR, HORIZON, KANO, VERDICT, targetLabel } from "@/lib/labels";
import { fmtInt, fmtWhen } from "@/lib/format";
import { useMeta } from "@/lib/hooks";
import { ErrorNote, EvidenceMeter, PriorityMark, ScoreArc, SkeletonBlock, StatusLight } from "@/components/ui";
import { AssumptionsBlock, Conflict, DecisionAsk, FitGates, MarketTable, Quotes, ReqTags, StudyAndWeb, VoiceByMarket } from "@/components/req";
import { ChallengeDrawer, OverrideDrawer, ReasonField, reasonOk } from "@/components/actions";
import { HistoryChart, Waterfall, type Series } from "@/components/charts";
import { Drawer } from "@/components/Drawer";
import { useToast } from "@/components/toast";
import { EvidenceChain } from "./requirement/EvidenceChain";
import { TraceDrawer } from "./requirement/Trace";
import "./requirement.css";

type History = { series: { target: { key: string; label: string }; points: { run_id: number; ts: string; trigger: string; wave: number | null; score: number; rank: number; priority: string }[] }[]; causes: { run_id: number; target_key: string; rationale: string }[] };

const SECTIONS = [
  ["overview", "Overview"],
  ["score", "Score"],
  ["evidence", "Evidence"],
  ["fit", "Fit"],
  ["history", "Decisions & audit"],
] as const;

export default function Requirement() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const { data: meta } = useMeta();
  const q = useQuery({ queryKey: ["requirement", id], queryFn: () => api.get<RequirementDetail>(`/api/requirements/${id}`) });
  const hist = useQuery({ queryKey: ["requirement", id, "history"], queryFn: () => api.get<History>(`/api/requirements/${id}/history`) });
  const r = q.data;
  const ranked = useMemo(() => (r ? [...r.targets].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)) : []), [r]);
  const focusKey = sp.get("t") ?? ranked[0]?.target.key ?? null;
  const focus = r?.targets.find((t) => t.target.key === focusKey) ?? ranked[0];
  const [override, setOverride] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);
  const [edit, setEdit] = useState(false);
  const [trace, setTrace] = useState(false);

  useEffect(() => {
    if (id) logView(id);
  }, [id]);

  if (q.isLoading) return <main className="page"><SkeletonBlock lines={12} /></main>;
  if (q.isError || !r) return <main className="page"><ErrorNote error={q.error} onRetry={() => q.refetch()} /></main>;

  const totalVoice = r.targets.reduce((s, t) => s + (t.voice?.own ? t.voice.verbatims : 0), 0);
  const series: Series[] = (hist.data?.series ?? []).map((s) => ({
    key: s.target.key,
    label: s.target.label,
    points: s.points.map((p) => ({
      x: p.run_id,
      xLabel: p.wave ? `Run ${p.run_id} · W${p.wave}` : `Run ${p.run_id}`,
      y: p.score,
      note: hist.data?.causes.find((c) => c.run_id === p.run_id && c.target_key === s.target.key)?.rationale ?? null,
    })),
  }));
  const [veh, mk] = (focusKey ?? "").split("×");

  return (
    <main className="page reqpage">
      <div className="req-crumbs">
        <button className="btn btn-ghost btn-sm" onClick={() => nav(-1)}>
          <ArrowLeft /> Back
        </button>
        <span className="id">{r.id} · v{r.version}</span>
        <StatusLight s={r.status} />
        <div className="req-actions">
          <button className="btn btn-sm" onClick={() => setTrace(true)} title="Follow this requirement from one customer comment to the decision">
            <Footprints /> Trace step by step
          </button>
          <button className="btn btn-sm" onClick={() => setAsk(true)}>
            <MessageCircleQuestion /> Ask the AI
          </button>
          <button className="btn btn-sm" onClick={() => setEdit(true)}>
            <PencilLine /> Edit
          </button>
          <Link className="btn btn-sm btn-primary" to={`/decide/req:${r.id}`}>
            <Scale /> Decide
          </Link>
        </div>
      </div>

      <section className="req-hero">
        <div className="req-hero-main">
          <h1 className="req-title">{r.title}</h1>
          <ReqTags r={r} />
          <div style={{ height: 18 }} />
          <DecisionAsk r={r} />
          <div className="req-hero-voice">
            <div className="sec-label">What customers say</div>
            <VoiceByMarket r={r} />
          </div>
        </div>
        <div className="req-hero-gauge panel">
          <ScoreArc score={focus?.score} size={176} caption={<PriorityMark p={focus?.priority} ai={focus?.ai_only} />} />
          <div className="req-gauge-label">{focus?.target.label}</div>
          <div className="req-targets" role="tablist" aria-label="Car and market">
            {ranked.map((t) => (
              <button
                key={t.target.key}
                role="tab"
                aria-selected={t.target.key === focusKey}
                className="req-tgt"
                onClick={() => setSp((p) => { p.set("t", t.target.key); return p; }, { replace: true })}
              >
                <span>{t.target.label}</span>
                <span className="num">{t.score == null ? "–" : Math.round(t.score)}</span>
              </button>
            ))}
          </div>
          {veh && (
            <Link className="req-oncar t-small" to={`/cars/${veh}?market=${mk}&zone=${r.zone}`}>
              <Car size={14} /> See it on the {CAR[veh] ?? veh} <ChevronRight size={14} />
            </Link>
          )}
        </div>
      </section>

      <section className="panel kpis" aria-label="Key facts">
        <Kpi label="Evidence" value={<EvidenceMeter level={r.evidence_level} label />} />
        <Kpi label="Customer comments" value={<span className="num">{fmtInt(totalVoice)}</span>} />
        <Kpi label="Cars × markets" value={<span className="num">{r.targets.length}</span>} />
        <Kpi label="Kano" value={r.kano_class ? KANO[r.kano_class] ?? r.kano_class : "–"} />
        <Kpi label="Horizon" value={r.horizon ? HORIZON[r.horizon] ?? r.horizon : "–"} />
        <Kpi label="Effort" value={r.effort ?? "–"} />
        <Kpi label="Brand fit" value={r.brand_blocked.length ? <span className="telltale red">Blocked</span> : <span className="telltale green">Clear</span>} />
        <Kpi label="Created" value={<span className="t-small">{r.created_by?.startsWith("ai:") ? "AI" : r.created_by} · {fmtWhen(r.created_at)}</span>} />
      </section>

      <nav className="req-secnav" aria-label="Sections">
        {SECTIONS.map(([k, l]) => (
          <a key={k} href={`#${k}`}>{l}</a>
        ))}
      </nav>

      <section id="overview" className="req-sec">
        <h2 className="t-title">Overview</h2>
        <div className="req-two">
          <div className="panel panel-body col" style={{ gap: 14 }}>
            <div className="sec-label">In their words</div>
            <Quotes r={r} limit={4} />
          </div>
          <div className="col" style={{ gap: 14 }}>
            {r.derivation?.evidence_summary && (
              <div className="panel panel-body">
                <div className="sec-label"><span className="telltale green">Evidence</span></div>
                <p className="req-prose">{r.derivation.evidence_summary}</p>
              </div>
            )}
            <div className="panel panel-body"><StudyAndWeb r={r} /></div>
            <Conflict r={r} />
          </div>
        </div>
        <div className="panel panel-body"><AssumptionsBlock r={r} /></div>
        {(r.target_metric || r.acceptance_criteria) && (
          <div className="panel panel-body req-measure">
            {r.target_metric && (<div><div className="sec-label">How we'd measure it</div><p className="req-prose">{r.target_metric}</p></div>)}
            {r.acceptance_criteria && (<div><div className="sec-label">Test</div><p className="req-prose">{r.acceptance_criteria}</p></div>)}
          </div>
        )}
      </section>

      <section id="score" className="req-sec">
        <h2 className="t-title">Score</h2>
        <div className="req-two">
          <div className="panel">
            <div className="panel-head">
              <h3>How {focus?.target.label} gets to {focus?.score == null ? "–" : Math.round(focus.score)}</h3>
              <span className="t-micro faint">{focus?.breakdown?.version}</span>
            </div>
            <div className="panel-body">
              {focus?.breakdown ? (
                <>
                  <Waterfall b={focus.breakdown} />
                  {focus.breakdown.cap_note && <p className="req-note">{focus.breakdown.cap_note}</p>}
                  {focus.breakdown.priority_note && <p className="req-note">{focus.breakdown.priority_note}</p>}
                  <FactorTable r={r} focusKey={focusKey} meta={meta} />
                </>
              ) : (
                <p className="muted">Not scored yet — it gets a score in the next prioritization run.</p>
              )}
            </div>
          </div>
          <div className="col" style={{ gap: 14 }}>
            <div className="panel">
              <div className="panel-head"><h3>Score across runs</h3><span className="t-micro faint">hover a point for the cause</span></div>
              <div className="panel-body">{series.length ? <HistoryChart series={series} focus={focusKey} /> : <SkeletonBlock lines={4} />}</div>
            </div>
            <div className="panel">
              <div className="panel-head"><h3>All cars & markets</h3></div>
              <div style={{ padding: "0 6px 8px", overflowX: "auto" }}><MarketTable r={r} focusKey={focusKey} /></div>
            </div>
          </div>
        </div>
      </section>

      <section id="evidence" className="req-sec">
        <h2 className="t-title">Evidence chain</h2>
        <p className="muted req-sub">Requirement → findings → customer signals → the original comment. Every link is stored with its source.</p>
        <EvidenceChain reqId={r.id} />
      </section>

      <section id="fit" className="req-sec">
        <h2 className="t-title">Fit checks</h2>
        <div className="panel panel-body"><FitGates fit={r.fit} overridden={r.overridden} onOverride={setOverride} /></div>
      </section>

      <section id="history" className="req-sec">
        <h2 className="t-title">Decisions & audit</h2>
        <AuditList reqId={r.id} challenges={r.challenges} />
      </section>

      <OverrideDrawer reqId={r.id} target={override} label={override ? targetLabel(override) : ""} onClose={() => setOverride(null)} />
      <ChallengeDrawer reqId={r.id} open={ask} onClose={() => setAsk(false)} />
      <EditDrawer r={r} meta={meta} open={edit} onClose={() => setEdit(false)} />
      <TraceDrawer reqId={r.id} target={focusKey} open={trace} onClose={() => setTrace(false)} />
    </main>
  );
}

function Kpi({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </div>
  );
}

function FactorTable({ r, focusKey, meta }: { r: RequirementDetail; focusKey: string | null; meta?: Meta }) {
  const b = r.targets.find((t) => t.target.key === focusKey)?.breakdown;
  if (!b) return null;
  return (
    <div className="table-scroll">
    <table className="table req-factors">
      <thead>
        <tr><th>Factor</th><th className="r">Weight</th><th className="r">Points</th><th>Why</th></tr>
      </thead>
      <tbody>
        {Object.entries(b.factors).map(([k, f]) => (
          <tr key={k} className={f.available ? undefined : "req-factor-na"}>
            <td>{meta?.scoring.factor_labels[k] ?? f.label}</td>
            <td className="r">{f.weight}</td>
            <td className="r">{f.points == null ? "no data" : f.points.toFixed(1)}</td>
            <td className="req-factor-why">{f.explanation}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function AuditList({ reqId, challenges }: { reqId: string; challenges: RequirementDetail["challenges"] }) {
  const [humanOnly, setHumanOnly] = useState(true);
  const q = useQuery({ queryKey: ["requirement", reqId, "audit", humanOnly], queryFn: () => api.get<AuditEvent[]>(`/api/requirements/${reqId}/audit?human_only=${humanOnly}`) });
  const items = [...(q.data ?? [])].reverse();
  return (
    <div className="req-two">
      <div className="panel">
        <div className="panel-head">
          <h3>Trail</h3>
          <label className="check t-small"><input type="checkbox" checked={humanOnly} onChange={(e) => setHumanOnly(e.target.checked)} /> People only</label>
        </div>
        <ol className="audit">
          {q.isLoading && <SkeletonBlock lines={5} />}
          {items.slice(0, 80).map((e) => (
            <li key={e.id} className="audit-row">
              <span className={`audit-dot who-${e.actor_type}`} aria-hidden />
              <div className="grow">
                <div className="audit-line">
                  <b>{e.actor_type === "human" ? e.actor_id : e.actor_type === "ai" ? "AI" : "System"}</b> {ACTION[e.action] ?? e.action.replace(/_/g, " ")}
                  {e.entity_id?.includes(":") && <span className="muted"> · {targetLabel(e.entity_id.split(":")[1])}</span>}
                  {e.field && e.new_value != null && e.new_value.length < 40 && (
                    <span className="muted"> · {e.old_value ?? "–"} → <span style={{ color: "var(--text)" }}>{e.new_value}</span></span>
                  )}
                </div>
                {e.rationale && <div className="audit-why">{e.rationale}</div>}
              </div>
              <span className="faint t-micro audit-ts">{fmtWhen(e.ts)}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className="panel">
        <div className="panel-head"><h3>Questions to the AI</h3></div>
        <div className="panel-body col" style={{ gap: 16 }}>
          {!challenges.length && <p className="muted t-small">No one has challenged this requirement yet.</p>}
          {challenges.map((c, i) => (
            <div key={i} className="challenge">
              <div className="t-small muted">{c.actor} asked · {fmtWhen(c.asked_at)}</div>
              <p className="challenge-q">“{c.question}”</p>
              {c.answer ? (
                <>
                  <span className={`chip ${c.answer.verdict === "upheld" ? "up" : c.answer.verdict === "partially_upheld" ? "warn" : "blue"}`}>{VERDICT[c.answer.verdict]}</span>
                  <p className="req-prose" style={{ marginTop: 8 }}>{c.answer.answer}</p>
                </>
              ) : (
                <p className="muted t-small">No answer recorded.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const ACTION: Record<string, string> = {
  set_status: "changed the status",
  set_priority: "set the priority",
  accept_proposal: "accepted an AI suggestion",
  reject_proposal: "rejected an AI suggestion",
  override_gate: "overrode a gate",
  edit: "edited",
  edit_evidence: "changed an evidence link",
  challenge: "challenged the AI",
  challenge_response: "answered the challenge",
  rescore: "re-scored",
  create: "drafted it",
  add_target: "added a car · market",
  link_findings: "linked findings",
  fit_check: "checked fit",
  view: "viewed it",
  update_evidence_level: "updated the evidence level",
};

const EDIT_FIELDS: { k: keyof RequirementDetail; label: string; rows?: number; enum?: "horizon" | "kano_class" | "effort" }[] = [
  { k: "title", label: "Title", rows: 1 },
  { k: "description", label: "Description", rows: 4 },
  { k: "target_metric", label: "How we'd measure it", rows: 3 },
  { k: "acceptance_criteria", label: "Test", rows: 3 },
  { k: "horizon", label: "Horizon", enum: "horizon" },
  { k: "kano_class", label: "Kano", enum: "kano_class" },
  { k: "effort", label: "Effort", enum: "effort" },
  { k: "assumptions", label: "Assumptions", rows: 4 },
  { k: "uncertainties", label: "Uncertainties", rows: 3 },
];

function EditDrawer({ r, meta, open, onClose }: { r: RequirementDetail; meta?: Meta; open: boolean; onClose: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>({});
  const [why, setWhy] = useState("");
  const toast = useToast();
  useEffect(() => {
    if (open) {
      setVals(Object.fromEntries(EDIT_FIELDS.map((f) => [f.k, String(r[f.k] ?? "")])));
      setWhy("");
    }
  }, [open, r]);
  const changes = Object.fromEntries(Object.entries(vals).filter(([k, v]) => v !== String(r[k as keyof RequirementDetail] ?? "")));
  const m = useMutation({
    mutationFn: () => api.patch<{ version: number }>(`/api/requirements/${r.id}`, { changes, rationale: why }),
    onSuccess: (res) => {
      toast({ tone: "ok", title: `Saved · now v${res.version}`, body: "Each changed field is in the audit trail." });
      invalidateAll();
      onClose();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Not saved", body: e.message }),
  });
  const enumLabel = (e: string, v: string) => (e === "horizon" ? HORIZON[v] : e === "kano_class" ? KANO[v] : v) ?? v;
  return (
    <Drawer open={open} onClose={onClose} title={`Edit ${r.id}`} sub="Your edit creates a new version. An approved requirement stays approved." width={620}>
      <div className="col" style={{ gap: 14 }}>
        {EDIT_FIELDS.map((f) => (
          <div key={f.k}>
            <label className="field-label" htmlFor={`ed-${f.k}`}>{f.label}</label>
            {f.enum ? (
              <select id={`ed-${f.k}`} className="select input" value={vals[f.k] ?? ""} onChange={(e) => setVals({ ...vals, [f.k]: e.target.value })}>
                {(meta?.enums[f.enum] ?? []).map((v) => <option key={v} value={v}>{enumLabel(f.enum!, v)}</option>)}
              </select>
            ) : f.rows === 1 ? (
              <input id={`ed-${f.k}`} className="input" value={vals[f.k] ?? ""} onChange={(e) => setVals({ ...vals, [f.k]: e.target.value })} />
            ) : (
              <textarea id={`ed-${f.k}`} className="textarea" rows={f.rows} value={vals[f.k] ?? ""} onChange={(e) => setVals({ ...vals, [f.k]: e.target.value })} />
            )}
          </div>
        ))}
        <ReasonField id="ed-why" value={why} onChange={setWhy} placeholder="Why you're changing it…" />
        <div className="row">
          <button className="btn btn-primary" disabled={!Object.keys(changes).length || !reasonOk(why) || m.isPending} onClick={() => m.mutate()}>
            Save {Object.keys(changes).length ? `${Object.keys(changes).length} change(s)` : ""}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Drawer>
  );
}

