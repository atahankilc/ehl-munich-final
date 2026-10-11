// Decide: ONE queue for everything that needs the PM — AI priority changes on decided items, merges, new
// requirements to review, AI edits from challenges. Step through it like a rotary controller (J/K), decide with
// a reason, and the next item rolls in. The AI never applies anything itself.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Check, Clock, ExternalLink, GitMerge, MessageCircleQuestion, PencilLine, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { api, invalidateAll, logView, qs } from "@/lib/api";
import type { Meta, Priority, Proposal, QueueItem, RequirementDetail } from "@/lib/types";
import { PROPOSAL_KIND, targetLabel } from "@/lib/labels";
import { fmtWhen } from "@/lib/format";
import { useMeta } from "@/lib/hooks";
import { Empty, ErrorNote, Kbd, PriorityMark, ScoreBar, SkeletonBlock, StatusLight } from "@/components/ui";
import { HistoryChart } from "@/components/charts";
import { AssumptionsBlock, Conflict, DecisionAsk, FitGates, MarketTable, Quotes, ReqTags, StudyAndWeb, VoiceByMarket } from "@/components/req";
import { ChallengeDrawer, OverrideDrawer, ReasonField, reasonOk } from "@/components/actions";
import { useToast } from "@/components/toast";
import "./decide.css";

type Queue = { items: QueueItem[]; counts: Record<string, number> };

const GROUPS: { id: string; label: string; kinds: QueueItem["kind"][]; icon: typeof Clock }[] = [
  { id: "changes", label: "Changes to your decisions", kinds: ["priority"], icon: SlidersHorizontal },
  { id: "merge", label: "Merge into existing", kinds: ["extend"], icon: GitMerge },
  { id: "review", label: "To review", kinds: ["review", "challenged", "new_requirement"], icon: Clock },
  { id: "edits", label: "AI edits & evidence", kinds: ["content", "link_finding"], icon: PencilLine },
];

const isTyping = (e: KeyboardEvent) => {
  const t = e.target as HTMLElement;
  return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
};

export default function Decide() {
  const { uid } = useParams();
  const nav = useNavigate();
  const { data: meta } = useMeta();
  const [scope, setScope] = useState<string>("");
  const q = useQuery({ queryKey: ["queue", scope], queryFn: () => api.get<Queue>(`/api/queue${qs({ target: scope })}`) });
  const items = q.data?.items ?? [];
  const ordered = useMemo(() => GROUPS.flatMap((g) => items.filter((i) => g.kinds.includes(i.kind))).concat(items.filter((i) => !GROUPS.some((g) => g.kinds.includes(i.kind)))), [items]);
  const idx = Math.max(0, ordered.findIndex((i) => i.uid === uid));
  const current = ordered.find((i) => i.uid === uid) ?? ordered[0] ?? null;
  const [dir, setDir] = useState(1);
  const lastUid = useRef<string | null>(null);

  const goTo = (i: number) => {
    const it = ordered[Math.max(0, Math.min(ordered.length - 1, i))];
    if (!it) return;
    setDir(i >= idx ? 1 : -1);
    nav(`/decide/${encodeURIComponent(it.uid)}`, { replace: true });
  };

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        goTo(idx + 1);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        goTo(idx - 1);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  // after a decision the item leaves the queue: roll to whatever now sits at the same position
  const afterDecision = (decidedUid: string) => {
    lastUid.current = decidedUid;
    setDir(1);
    const rest = ordered.filter((i) => i.uid !== decidedUid);
    const next = rest[Math.min(idx, rest.length - 1)];
    nav(next ? `/decide/${encodeURIComponent(next.uid)}` : "/decide", { replace: true });
  };

  return (
    <main className="page decide">
      <aside className="qrail" aria-label="Decision queue">
        <div className="qrail-head">
          <div>
            <h1 className="t-title">Decide</h1>
            <p className="muted t-small">{ordered.length ? `${idx + 1} of ${ordered.length} waiting` : "Queue empty"}</p>
          </div>
          <select className="select qscope" value={scope} onChange={(e) => setScope(e.target.value)} aria-label="Limit the queue to one car · market">
            <option value="">All cars & markets</option>
            {meta?.targets.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        {q.isLoading && <SkeletonBlock lines={8} />}
        {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
        <div className="qrail-list">
          {GROUPS.map((g) => {
            const gi = ordered.filter((i) => g.kinds.includes(i.kind));
            if (!gi.length) return null;
            return (
              <section key={g.id} className="qgroup">
                <h2 className="qgroup-h">
                  <g.icon aria-hidden /> {g.label} <span className="num faint">{gi.length}</span>
                </h2>
                {gi.map((it) => (
                  <button
                    key={it.uid}
                    className={`qitem${current?.uid === it.uid ? " on" : ""}`}
                    onClick={() => {
                      setDir(ordered.indexOf(it) >= idx ? 1 : -1);
                      nav(`/decide/${encodeURIComponent(it.uid)}`, { replace: true });
                    }}
                    aria-current={current?.uid === it.uid}
                    ref={current?.uid === it.uid ? (el) => el?.scrollIntoView({ block: "nearest" }) : undefined}
                  >
                    <span className="qitem-title">{it.title}</span>
                    <span className="qitem-sub">
                      {it.kind === "priority" && it.target ? (
                        <>
                          {it.target.label} · <PriorityMark p={it.priority} size="sm" ai />
                        </>
                      ) : (
                        <>
                          {it.is_new_in_wave && <span className="chip blue">new</span>}
                          {it.kind === "challenged" && <span className="chip violet">challenged</span>}
                          <span className="ellipsis">{it.subtitle}</span>
                        </>
                      )}
                      {it.score != null && it.kind !== "priority" && <ScoreBar score={it.score} width={36} />}
                    </span>
                  </button>
                ))}
              </section>
            );
          })}
        </div>
        <div className="qrail-keys faint t-micro">
          <Kbd>J</Kbd> <Kbd>K</Kbd> step · <Kbd>⌘</Kbd>
          <Kbd>↵</Kbd> record
        </div>
      </aside>

      <section className="workspace" aria-live="polite">
        {!q.isLoading && !current && (
          <div className="panel ws-empty">
            <Empty title="Nothing waiting for you">
              Every requirement has a decision and every AI suggestion is answered. New evidence arrives with the next wave — see <Link to="/process">Process</Link>.
            </Empty>
          </div>
        )}
        <AnimatePresence mode="popLayout" initial={false} custom={dir}>
          {current && (
            <motion.div
              key={current.uid}
              custom={dir}
              variants={{
                enter: (d: number) => ({ opacity: 0, y: d * 28, filter: "blur(3px)" }),
                center: { opacity: 1, y: 0, filter: "blur(0px)" },
                exit: (d: number) => ({ opacity: 0, y: d * -22, filter: "blur(3px)", transition: { duration: 0.18 } }),
              }}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.36, ease: [0.16, 1, 0.3, 1] }}
            >
              {current.type === "requirement" ? (
                <ReviewItem item={current} meta={meta} onDone={() => afterDecision(current.uid)} />
              ) : (
                <ProposalItem item={current} onDone={() => afterDecision(current.uid)} siblings={ordered.filter((i) => i.kind === current.kind)} />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </main>
  );
}

/* ================================================================ review a requirement */

type Choice = "approved" | "deferred" | "rejected";
const CHOICES: { v: Choice; label: string; done: string; key: string; icon: typeof Check; tone: string }[] = [
  { v: "approved", label: "Approve", done: "Approved", key: "A", icon: Check, tone: "approve" },
  { v: "deferred", label: "Defer", done: "Deferred", key: "D", icon: Clock, tone: "defer" },
  { v: "rejected", label: "Reject", done: "Rejected", key: "R", icon: X, tone: "reject" },
];

function ReviewItem({ item, onDone }: { item: QueueItem; meta?: Meta; onDone: () => void }) {
  const q = useQuery({ queryKey: ["requirement", item.req_id], queryFn: () => api.get<RequirementDetail>(`/api/requirements/${item.req_id}`) });
  const r = q.data;
  const toast = useToast();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [why, setWhy] = useState("");
  const [draft, setDraft] = useState<Record<string, Priority | null>>({});
  const [acceptAi, setAcceptAi] = useState(true);
  const [override, setOverride] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);
  const reasonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logView(item.req_id);
  }, [item.req_id]);

  const blocked = r?.brand_blocked ?? [];
  const unset = r ? r.targets.filter((t) => !t.pm_priority && t.ai_priority && !(t.target.key in draft)).length : 0;
  const changed = Object.entries(draft).filter(([k, v]) => r?.targets.find((t) => t.target.key === k)?.pm_priority !== v);
  const canSubmit = !!choice && reasonOk(why) && !(choice === "approved" && blocked.length > 0);

  const submit = useMutation({
    mutationFn: async () => {
      if (changed.length) await api.put(`/api/requirements/${item.req_id}/priorities`, { priorities: Object.fromEntries(changed), rationale: why });
      return api.post<{ priorities_set: string[] }>(`/api/requirements/${item.req_id}/status`, {
        status: choice,
        rationale: why,
        accept_ai_priorities: acceptAi && choice !== "rejected",
      });
    },
    onSuccess: (res) => {
      const n = changed.length + (res?.priorities_set?.length ?? 0);
      toast({
        tone: "ok",
        title: `${CHOICES.find((c) => c.v === choice)!.done} · ${item.req_id}`,
        body: n ? `With ${n} market priorit${n === 1 ? "y" : "ies"} confirmed. Recorded in the audit trail.` : "Recorded in the audit trail.",
      });
      invalidateAll();
      onDone();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Not recorded", body: e.message }),
  });

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (canSubmit && !submit.isPending) submit.mutate();
        return;
      }
      if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return;
      const c = CHOICES.find((x) => x.key.toLowerCase() === e.key.toLowerCase());
      if (c) {
        e.preventDefault();
        setChoice(c.v);
        setTimeout(() => reasonRef.current?.querySelector("textarea")?.focus(), 0);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  if (q.isLoading) return <div className="panel ws-pad"><SkeletonBlock lines={10} /></div>;
  if (q.isError || !r) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;

  return (
    <article className="ws">
      <header className="ws-head">
        <div className="row wrap" style={{ gap: 10 }}>
          <span className="id">{r.id}</span>
          <StatusLight s={r.status} />
          {item.is_new_in_wave && <span className="chip blue">New in this wave</span>}
          <Link to={`/requirements/${r.id}`} className="ws-open t-small">
            Full trace <ExternalLink size={13} />
          </Link>
        </div>
        <h2 className="ws-title">{r.title}</h2>
        <ReqTags r={r} />
      </header>

      <div className="ws-grid">
        <div className="ws-main">
          <div className="panel ws-pad">
            <DecisionAsk r={r} />
          </div>
          <div className="panel ws-pad">
            <div className="sec-label">What customers say</div>
            <VoiceByMarket r={r} />
            <div style={{ height: 16 }} />
            <Quotes r={r} />
          </div>
          {(r.study.length > 0 || r.web.length > 0) && (
            <div className="panel ws-pad">
              <StudyAndWeb r={r} />
            </div>
          )}
          <Conflict r={r} />
          <div className="panel ws-pad">
            <AssumptionsBlock r={r} />
          </div>
        </div>

        <div className="ws-side">
          <div className="panel decision" ref={reasonRef}>
            <div className="decision-choices" role="radiogroup" aria-label="Decision">
              {CHOICES.map((c) => (
                <button key={c.v} role="radio" aria-checked={choice === c.v} className={`dchoice dc-${c.tone}`} onClick={() => setChoice(c.v)}>
                  <c.icon aria-hidden />
                  <span>{c.label}</span>
                  <Kbd>{c.key}</Kbd>
                </button>
              ))}
            </div>
            {choice === "approved" && blocked.length > 0 && (
              <p className="decision-block">Brand-fit fails for {blocked.map(targetLabel).join(", ")}. Override the gate above with a reason first.</p>
            )}
            <ReasonField id="dec-why" value={why} onChange={setWhy} placeholder={choice === "rejected" ? "Why this shouldn't go into the successor…" : "Why — evidence, trade-off, market…"} />
            <p className="t-micro faint">Adjust any market's priority in the table below before recording — your choices are saved with the same reason.</p>
            {choice !== "rejected" && unset > 0 && (
              <label className="check">
                <input type="checkbox" checked={acceptAi} onChange={(e) => setAcceptAi(e.target.checked)} />
                <span>Also confirm the AI's priority for the {unset} market{unset === 1 ? "" : "s"} you haven't set</span>
              </label>
            )}
            <div className="row" style={{ justifyContent: "space-between" }}>
              <button className="btn btn-ghost" onClick={() => setAsk(true)}>
                <MessageCircleQuestion /> Ask the AI
              </button>
              <button className="btn btn-primary" disabled={!canSubmit || submit.isPending} onClick={() => submit.mutate()}>
                {submit.isPending ? "Recording…" : "Record decision"} <Kbd>⌘↵</Kbd>
              </button>
            </div>
          </div>
          <div className="panel">
            <div className="panel-head">
              <h3>Priority by car & market</h3>
              <span className="t-micro faint">Must ≥ 60 · Should ≥ 45</span>
            </div>
            <div className="ws-table">
              <MarketTable r={r} draft={draft} setDraft={setDraft} compact />
            </div>
          </div>
          <div className="panel ws-pad">
            <div className="sec-label">Fit checks</div>
            <FitGates fit={r.fit} overridden={r.overridden} onOverride={setOverride} />
          </div>

        </div>
      </div>
      <OverrideDrawer reqId={r.id} target={override} label={override ? targetLabel(override) : ""} onClose={() => setOverride(null)} />
      <ChallengeDrawer reqId={r.id} open={ask} onClose={() => setAsk(false)} />
    </article>
  );
}

/* ================================================================ answer an AI proposal */

function ProposalItem({ item, onDone, siblings }: { item: QueueItem; onDone: () => void; siblings: QueueItem[] }) {
  const all = useQuery({ queryKey: ["proposals", "open"], queryFn: () => api.get<Proposal[]>("/api/proposals?status=open") });
  const p = all.data?.find((x) => x.id === item.proposal_id || `prop:${x.id}` === item.uid);
  const toast = useToast();
  const [why, setWhy] = useState("");
  const [bulk, setBulk] = useState(false);
  const decide = useMutation({
    mutationFn: async (accept: boolean) => {
      if (bulk && siblings.length > 1) {
        const ids = siblings.map((s) => s.proposal_id ?? Number(s.uid.replace("prop:", "")));
        return api.post<{ done: number[]; failed: { id: number; detail: string }[] }>("/api/proposals/bulk-decision", { ids, accept, rationale: why });
      }
      return api.post(`/api/proposals/${p!.id}/decision`, { accept, rationale: why });
    },
    onSuccess: (_r, accept) => {
      toast({ tone: "ok", title: `${accept ? "Accepted" : "Rejected"}${bulk ? ` ${siblings.length} suggestions` : ""}`, body: "Recorded in the audit trail." });
      invalidateAll();
      onDone();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Not recorded", body: e.message }),
  });

  if (all.isLoading) return <div className="panel ws-pad"><SkeletonBlock lines={6} /></div>;
  if (!p) return <ErrorNote error={new Error("This suggestion is no longer open.")} onRetry={() => all.refetch()} />;

  return (
    <article className="ws">
      <header className="ws-head">
        <div className="row wrap" style={{ gap: 10 }}>
          <span className="chip blue">
            <Sparkles /> AI suggests · {PROPOSAL_KIND[p.kind] ?? p.kind}
          </span>
          <span className="id">#{p.id}</span>
          {p.run && <span className="t-small faint">from run {p.run.id} · {fmtWhen(p.run.ts)}</span>}
          <Link to={`/requirements/${p.requirement_id}`} className="ws-open t-small">
            {p.requirement_id} <ExternalLink size={13} />
          </Link>
        </div>
        <h2 className="ws-title">{p.requirement_title}</h2>
      </header>

      <div className="panel ws-pad prop-body">
        {p.kind === "priority" && (
          <div className="prop-priority">
            <div className="prop-target">{p.target?.label}</div>
            <div className="prop-change">
              <div className="col" style={{ gap: 6, alignItems: "center" }}>
                <span className="t-micro faint">Your priority</span>
                <PriorityMark p={(p.old_value as Priority) ?? null} />
              </div>
              <ArrowRight className="prop-arrow" aria-hidden />
              <div className="col" style={{ gap: 6, alignItems: "center" }}>
                <span className="t-micro faint">AI proposes</span>
                <PriorityMark p={(p.proposed_value as Priority) ?? null} ai />
              </div>
              {typeof p.delta?.score === "number" && (
                <div className="col" style={{ gap: 6, alignItems: "center", marginLeft: 18 }}>
                  <span className="t-micro faint">New score</span>
                  <ScoreBar score={p.delta.score as number} width={110} />
                </div>
              )}
            </div>
          </div>
        )}
        {p.kind === "priority" && p.target && <TargetHistory reqId={p.requirement_id} targetKey={p.target.key} />}
        {p.kind === "extend" && <ExtendView p={p} />}
        {p.kind === "content" && (
          <div className="diff">
            <div className="sec-label">Field · {p.field.replace(/_/g, " ")}</div>
            <div className="diff-grid">
              <div className="diff-old">
                <div className="t-micro faint">Current</div>
                <p>{p.old_value || "—"}</p>
              </div>
              <div className="diff-new">
                <div className="t-micro" style={{ color: "var(--blue-ink)" }}>Proposed</div>
                <p>{p.proposed_value}</p>
              </div>
            </div>
          </div>
        )}
        {p.kind === "link_finding" && p.finding && (
          <div>
            <div className="sec-label">Link this finding as “{p.proposed_value}”</div>
            <div className="t-title" style={{ fontSize: 16 }}>{p.finding.title}</div>
            <p className="muted" style={{ marginTop: 6 }}>{p.finding.summary}</p>
          </div>
        )}
        {p.kind === "new_requirement" && <p className="t-lead">Accept to keep this new requirement in review; reject to drop it.</p>}
        {p.reason && (
          <div className="prop-cause">
            <div className="sec-label">Why the AI suggests this</div>
            <p>{p.reason}</p>
          </div>
        )}
      </div>

      <div className="panel decision">
        <ReasonField id="prop-why" value={why} onChange={setWhy} placeholder="Why you accept or reject this suggestion…" />
        {siblings.length > 1 && (
          <label className="check">
            <input type="checkbox" checked={bulk} onChange={(e) => setBulk(e.target.checked)} />
            <span>Apply this answer to all {siblings.length} {PROPOSAL_KIND[p.kind]?.toLowerCase()}s in the queue</span>
          </label>
        )}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-danger" disabled={!reasonOk(why) || decide.isPending} onClick={() => decide.mutate(false)}>
            <X /> Reject
          </button>
          <button className="btn btn-primary" disabled={!reasonOk(why) || decide.isPending} onClick={() => decide.mutate(true)}>
            <Check /> Accept
          </button>
        </div>
      </div>
    </article>
  );
}

function ExtendView({ p }: { p: Proposal }) {
  const d = (p.delta ?? {}) as { draft_title?: string; draft_description?: string; targets?: { vehicle_model_id: string; market_code: string; market_note?: string }[] };
  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="extend">
        <div>
          <div className="t-micro faint">Raised again this wave as</div>
          <div className="extend-draft">“{d.draft_title}”</div>
          {d.draft_description && <p className="muted t-small" style={{ marginTop: 6 }}>{d.draft_description}</p>}
        </div>
        <GitMerge className="extend-icon" aria-hidden />
        <div>
          <div className="t-micro faint">Merge into existing</div>
          <div className="extend-draft">{p.requirement_title}</div>
        </div>
      </div>
      {d.targets && d.targets.length > 0 && (
        <div>
          <div className="sec-label">Adds car · market targets</div>
          <div className="row wrap" style={{ gap: 6 }}>
            {d.targets.map((t) => (
              <span key={t.vehicle_model_id + t.market_code} className="chip outline" title={t.market_note}>
                {targetLabel(`${t.vehicle_model_id}×${t.market_code}`)}
              </span>
            ))}
          </div>
        </div>
      )}
      {p.findings && p.findings.length > 0 && (
        <div>
          <div className="sec-label">Brings {p.findings.length} finding(s)</div>
          <ul className="sw-list">{p.findings.slice(0, 6).map((f) => <li key={f.id}>{f.title}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

type Hist = { series: { target: { key: string; label: string }; points: { run_id: number; wave: number | null; score: number }[] }[]; causes: { run_id: number; target_key: string; rationale: string }[] };

function TargetHistory({ reqId, targetKey }: { reqId: string; targetKey: string }) {
  const q = useQuery({ queryKey: ["requirement", reqId, "history"], queryFn: () => api.get<Hist>(`/api/requirements/${reqId}/history`) });
  if (!q.data) return null;
  const series = q.data.series.map((s) => ({
    key: s.target.key,
    label: s.target.label,
    points: s.points.map((p) => ({
      x: p.run_id,
      xLabel: p.wave ? `Run ${p.run_id} · W${p.wave}` : `Run ${p.run_id}`,
      y: p.score,
      note: q.data!.causes.find((c) => c.run_id === p.run_id && c.target_key === s.target.key)?.rationale ?? null,
    })),
  }));
  return (
    <div>
      <div className="sec-label">This score across runs — the other markets in grey</div>
      <HistoryChart series={series} focus={targetKey} height={170} />
    </div>
  );
}
