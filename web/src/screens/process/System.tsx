// System: OpenAI spend against the $100 budget (with the warn / block / hard-stop markers the LLM wrapper enforces),
// what the pipeline has processed so far, and demo snapshots to rewind the simulation.
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, History, TriangleAlert } from "lucide-react";
import { api, invalidateAll } from "@/lib/api";
import type { BudgetPayload, DemoSnapshot, PipelineStats, Status } from "@/lib/types";
import { useAppState } from "@/lib/hooks";
import { FIT_TYPE, STATUS } from "@/lib/labels";
import { fmtInt, fmtUsd } from "@/lib/format";
import { Drawer } from "@/components/Drawer";
import { ReasonField, reasonOk } from "@/components/actions";
import { useToast } from "@/components/toast";
import { Empty, ErrorNote, Skeleton, SkeletonBlock, StatusLight } from "@/components/ui";

const GROUP_LABEL: Record<string, string> = {
  extract: "Extract signals from feedback",
  derive: "Draft requirements",
  consolidate: "Consolidate across lines",
  match_existing: "Match to existing",
  link: "Link study & web evidence",
  fit: "Fit checks",
  web: "Web research",
  web_research: "Web research",
  challenge: "PM challenges",
  findings: "Build findings",
  scope: "Scope re-checks",
  recheck: "Scope re-checks",
  pilot: "Pilot runs",
  research: "Web research",
  reconciliation: "Budget reconciliation",
  bench: "Model benchmarks",
  "websearch-smoke": "Web-search smoke test",
  ingest: "Ingest",
  embed: "Embeddings",
};
const groupLabel = (g: string) => GROUP_LABEL[g] ?? g.replace(/[_-]/g, " ");

const SOURCE_LABEL: Record<string, string> = {
  feedback: "Feedback verbatims",
  study: "Study items",
  sales: "Sales rows",
  web: "Web sources",
  option_list: "Option-list items",
  reference: "Reference sources",
};
const FINDING_LABEL: Record<string, string> = { verbatim: "From feedback", study: "From the study", web: "From the web" };
const STATUSES: Status[] = ["proposed", "challenged", "approved", "deferred", "rejected"];
const STATUS_FILL: Record<Status, string> = {
  proposed: "var(--blue-hi)",
  challenged: "var(--violet)",
  approved: "var(--green)",
  deferred: "var(--amber)",
  rejected: "var(--red)",
};
const RESULTS = ["pass", "warn", "fail", "overridden"] as const;

const SNAP_HINT: Record<string, string> = {
  evidence: "Evidence loaded, no wave opened — replays all three waves",
  wave1: "After wave 1 — waves 2 and 3 can be opened again",
  demo: "The full demo state, all waves open",
  pre_dedup: "Before duplicate requirements were merged",
  pre_validation: "Before requirement validation",
};
const snapName = (s: DemoSnapshot) => (typeof s === "string" ? s : s.name);

export function System() {
  return (
    <div className="system">
      <BudgetPanel />
      <PipelinePanel />
      <SnapshotsPanel />
    </div>
  );
}

/* ---------------------------------------------------------------- budget */

function BudgetPanel() {
  const q = useQuery({ queryKey: ["budget"], queryFn: () => api.get<BudgetPayload>("/api/budget") });
  const b = q.data;
  const groups = useMemo(() => {
    if (!b) return [];
    if (b.by_group?.length) return b.by_group.map((g) => ({ group: g.job_group || "other", calls: g.calls, usd: g.usd }));
    const m = new Map<string, { group: string; calls: number; usd: number }>();
    for (const j of b.by_job) {
      const g = (j.job ?? "other").split(":")[0] || "other";
      const cur = m.get(g) ?? { group: g, calls: 0, usd: 0 };
      cur.calls += j.calls;
      cur.usd += j.usd;
      m.set(g, cur);
    }
    return [...m.values()].sort((a, c) => c.usd - a.usd);
  }, [b]);
  const maxUsd = Math.max(0.0001, ...groups.map((g) => g.usd));

  return (
    <section className="panel sys-budget" aria-labelledby="bud-h">
      <div className="panel-head">
        <h2 id="bud-h">OpenAI budget</h2>
        <span className="t-small faint">Every call goes through the budget-guarded wrapper</span>
      </div>
      {q.isError && (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.isLoading && (
        <div className="panel-body">
          <Skeleton h={44} w={180} />
          <div style={{ height: 22 }} />
          <Skeleton h={8} />
          <div style={{ height: 26 }} />
          <SkeletonBlock lines={5} />
        </div>
      )}
      {b && (
        <div className="panel-body bud-body">
          <div className="bud-read">
            <div className="bud-big">
              <span className="instrument">{fmtUsd(b.spent)}</span>
              <span className="muted">of ${b.total ?? 100} spent</span>
            </div>
            <dl className="bud-facts">
              <div>
                <dt>Headroom to hard stop</dt>
                <dd className="num">{fmtUsd(Math.max(0, b.thresholds.hard_stop - b.committed))}</dd>
              </div>
              <div>
                <dt>Committed</dt>
                <dd className="num" title="Spent plus calls currently reserved">{fmtUsd(b.committed)}</dd>
              </div>
              <div>
                <dt>Calls</dt>
                <dd className="num">{fmtInt(b.calls)}</dd>
              </div>
              <div>
                <dt>Cached responses</dt>
                <dd className="num" title="Replays of these prompts cost nothing">{fmtInt(b.cache_entries)}</dd>
              </div>
            </dl>
          </div>
          <BudgetGauge b={b} />

          <div className="bud-groups">
            <div className="px-label">Spend by job</div>
            {groups.length === 0 ? (
              <p className="muted t-small">No OpenAI calls yet.</p>
            ) : (
              <ol>
                {groups.slice(0, 9).map((g) => (
                  <li key={g.group}>
                    <span className="bg-name">{groupLabel(g.group)}</span>
                    <span className="bg-bar" aria-hidden>
                      <i style={{ width: `${(g.usd / maxUsd) * 100}%` }} />
                    </span>
                    <span className="bg-usd num">{fmtUsd(g.usd)}</span>
                    <span className="bg-calls num faint">{fmtInt(g.calls)} calls</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
          {b.by_model.length > 0 && (
            <div className="px-scroll">
              <table className="table bud-models">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Kind</th>
                    <th className="r">Calls</th>
                    <th className="r">Input tokens</th>
                    <th className="r">Cached</th>
                    <th className="r">Output</th>
                    <th className="r">Spend</th>
                  </tr>
                </thead>
                <tbody>
                  {b.by_model.map((m) => (
                    <tr key={`${m.model}${m.kind}`}>
                      <td>{m.model}</td>
                      <td className="muted">{m.kind}</td>
                      <td className="r">{fmtInt(m.calls)}</td>
                      <td className="r muted">{fmtInt(m.input_tokens)}</td>
                      <td className="r muted">{fmtInt(m.cached_tokens)}</td>
                      <td className="r muted">{fmtInt(m.output_tokens)}</td>
                      <td className="r">{fmtUsd(m.usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function BudgetGauge({ b }: { b: BudgetPayload }) {
  const total = b.total ?? 100;
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / total) * 100))}%`;
  const t = b.thresholds;
  const zone = b.spent >= t.hard_stop ? "stop" : b.spent >= t.block_non_demo ? "block" : b.spent >= t.warn ? "warn" : "ok";
  const marks = [
    { v: t.warn, label: "Warn", cls: "warn" },
    { v: t.block_non_demo, label: "Non-demo calls blocked", cls: "block" },
    { v: t.hard_stop, label: "Hard stop", cls: "stop" },
  ];
  return (
    <div className="gauge" role="img" aria-label={`Spent ${fmtUsd(b.spent)} of $${total}. Warning at $${t.warn}, non-demo calls blocked at $${t.block_non_demo}, hard stop at $${t.hard_stop}.`}>
      <div className="gauge-track">
        <span className="gauge-zone" style={{ left: pct(t.warn), width: `calc(${pct(t.block_non_demo)} - ${pct(t.warn)})` }} data-z="warn" />
        <span className="gauge-zone" style={{ left: pct(t.block_non_demo), width: `calc(${pct(t.hard_stop)} - ${pct(t.block_non_demo)})` }} data-z="block" />
        <span className="gauge-zone" style={{ left: pct(t.hard_stop), right: 0 }} data-z="stop" />
        <span className="gauge-committed" style={{ width: pct(b.committed) }} />
        <span className={`gauge-fill gz-${zone}`} style={{ width: pct(b.spent) }} />
        {marks.map((m) => (
          <i key={m.cls} className={`gauge-mark gm-${m.cls}`} style={{ left: pct(m.v) }} />
        ))}
      </div>
      <div className="gauge-scale">
        <span style={{ left: 0 }} className="num">$0</span>
        {marks.map((m) => (
          <span key={m.cls} style={{ left: pct(m.v) }} className={`gm-${m.cls}`}>
            <b className="num">${m.v}</b> {m.label}
          </span>
        ))}
        <span style={{ left: "100%" }} className="num end">${total}</span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- pipeline stats */

function PipelinePanel() {
  const q = useQuery({ queryKey: ["pipeline", "stats"], queryFn: () => api.get<PipelineStats>("/api/pipeline/stats") });
  const s = q.data;
  return (
    <section className="panel sys-pipe" aria-labelledby="pipe-h">
      <div className="panel-head">
        <h2 id="pipe-h">Pipeline</h2>
        {s?.extractor_version && <span className="t-small faint">Extractor {s.extractor_version}</span>}
      </div>
      {q.isError && (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.isLoading && (
        <div className="panel-body">
          <SkeletonBlock lines={9} />
        </div>
      )}
      {s && <PipelineBody s={s} />}
    </section>
  );
}

function PipelineBody({ s }: { s: PipelineStats }) {
  const findings = Object.values(s.findings_by_kind).reduce((a, b) => a + b, 0);
  const reqs = STATUSES.reduce((a, k) => a + (s.requirements_by_status[k] ?? 0), 0);
  const funnel = [
    { n: s.sources_by_kind.feedback ?? 0, l: "feedback verbatims" },
    { n: s.extracted, l: "read by the AI" },
    { n: s.in_scope, l: "in scope" },
    { n: s.signals, l: "signals" },
    { n: findings, l: "findings" },
    { n: reqs, l: "requirements" },
  ];
  const fit = useMemo(() => {
    const m = new Map<string, Record<string, number>>();
    for (const r of s.fit_matrix) {
      const row = m.get(r.check_type) ?? {};
      row[r.result] = (row[r.result] ?? 0) + r.n;
      m.set(r.check_type, row);
    }
    const order = ["brand", "segment", "market", "feasibility", "compliance"];
    return [...m.entries()].sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
  }, [s.fit_matrix]);

  return (
    <div className="panel-body col" style={{ gap: 22 }}>
      <ol className="funnel" aria-label="From feedback to requirements">
        {funnel.map((f, i) => (
          <li key={f.l}>
            <span className="instrument funnel-n">{fmtInt(f.n)}</span>
            <small>{f.l}</small>
            {i < funnel.length - 1 && <ArrowRight className="funnel-arrow" aria-hidden />}
          </li>
        ))}
      </ol>
      {s.unverified_quotes ? <p className="t-small faint">{fmtInt(s.unverified_quotes)} signal quotes could not be matched word-for-word to the verbatim and are flagged.</p> : null}

      <div className="pipe-split">
        <div>
          <div className="px-label">Sources</div>
          <dl className="kv">
            {Object.entries(s.sources_by_kind)
              .sort((a, b) => b[1] - a[1])
              .map(([k, n]) => (
                <div key={k}>
                  <dt>{SOURCE_LABEL[k] ?? k.replace(/_/g, " ")}</dt>
                  <dd className="num">{fmtInt(n)}</dd>
                </div>
              ))}
          </dl>
        </div>
        <div>
          <div className="px-label">Findings</div>
          <dl className="kv">
            {Object.entries(s.findings_by_kind).map(([k, n]) => (
              <div key={k}>
                <dt>{FINDING_LABEL[k] ?? k}</dt>
                <dd className="num">{fmtInt(n)}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <p className="t-small faint num">
        {fmtInt(s.runs)} prioritization runs · {fmtInt(s.open_proposals)} open AI suggestions · {fmtInt(s.audit_events)} audit events
      </p>

      <div>
        <div className="px-label">Requirements by status</div>
        <div className="st-bar" aria-hidden>
          {STATUSES.map((k) => (
            <i key={k} style={{ width: `${reqs ? ((s.requirements_by_status[k] ?? 0) / reqs) * 100 : 0}%`, background: STATUS_FILL[k] }} title={`${STATUS[k]}: ${s.requirements_by_status[k] ?? 0}`} />
          ))}
        </div>
        <div className="st-legend">
          {STATUSES.map((k) => (
            <span key={k}>
              <StatusLight s={k} /> <b className="num">{fmtInt(s.requirements_by_status[k] ?? 0)}</b>
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="px-label">
          Fit checks <span className="faint">· {fmtInt(s.reqs_with_fit)} requirements checked</span>
        </div>
        {fit.length === 0 ? (
          <p className="muted t-small">No fit checks yet.</p>
        ) : (
          <div className="px-scroll">
            <table className="table fit-matrix">
              <thead>
                <tr>
                  <th>Check</th>
                  {RESULTS.map((r) => (
                    <th key={r} className="r">
                      {r === "overridden" ? "Overridden" : r[0].toUpperCase() + r.slice(1)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fit.map(([type, row]) => (
                  <tr key={type}>
                    <td>
                      <span>{FIT_TYPE[type]?.label ?? type}</span>
                      <span className="faint t-small"> · {FIT_TYPE[type]?.effect ?? ""}</span>
                    </td>
                    {RESULTS.map((r) => (
                      <td key={r} className={`r fm-${r}${row[r] ? "" : " zero"}`}>
                        {row[r] ? fmtInt(row[r]) : "·"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- demo snapshots */

function SnapshotsPanel() {
  const q = useQuery({ queryKey: ["demo", "snapshots"], queryFn: () => api.get<DemoSnapshot[]>("/api/demo/snapshots") });
  const [pick, setPick] = useState<string | null>(null);
  return (
    <section className="panel sys-snaps" aria-labelledby="snap-h">
      <div className="panel-head">
        <h2 id="snap-h">Demo snapshots</h2>
        <span className="t-small faint">Rewind the simulation</span>
      </div>
      {q.isLoading && (
        <div className="panel-body">
          <SkeletonBlock lines={3} />
        </div>
      )}
      {q.isError && (
        <div className="panel-body">
          <ErrorNote error={q.error} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.data && q.data.length === 0 && <Empty title="No snapshots saved">Save one with `uv run python scripts/demo_state.py save &lt;name&gt;`.</Empty>}
      {q.data && q.data.length > 0 && (
        <ol className="snaps">
          {q.data.map((s) => {
            const n = snapName(s);
            return (
              <li key={n}>
                <History aria-hidden className="faint" />
                <span className="snap-main">
                  <span className="snap-name">{n}</span>
                  <span className="t-small muted">{SNAP_HINT[n] ?? (typeof s === "string" ? "Saved database state" : s.description ?? "Saved database state")}</span>
                </span>
                <button className="btn btn-sm" onClick={() => setPick(n)}>
                  Restore…
                </button>
              </li>
            );
          })}
        </ol>
      )}
      <RestoreDrawer name={pick} onClose={() => setPick(null)} />
    </section>
  );
}

function RestoreDrawer({ name, onClose }: { name: string | null; onClose: () => void }) {
  const [why, setWhy] = useState("");
  const toast = useToast();
  const { data: st } = useAppState();
  const busy = !!st?.running_job;
  const m = useMutation({
    mutationFn: () => api.post<{ restored: string; current_wave: number }>("/api/demo/restore", { snapshot: name, rationale: why }),
    onSuccess: (r) => {
      toast({ tone: "ok", title: `Restored “${r.restored}”`, body: `The simulation is at wave ${r.current_wave}. Recorded in the audit trail.` });
      setWhy("");
      invalidateAll();
      onClose();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Not restored", body: e.message }),
  });
  return (
    <Drawer open={!!name} onClose={onClose} title={`Restore “${name ?? ""}”`} sub={name ? SNAP_HINT[name] : undefined}>
      <div className="col" style={{ gap: 18 }}>
        <div className="warnnote">
          <TriangleAlert aria-hidden />
          <div>
            <b>This replaces the working database with the snapshot.</b> Requirements, decisions, runs and audit events made after the snapshot are no longer
            in the working state. OpenAI spend and cached answers are kept — the budget never loses a cent, and replays stay free.
          </div>
        </div>
        <p className="t-small muted">Use it to rewind the demo, for example to open waves 2 and 3 again. The restore itself is recorded with your name.</p>
        {busy && <p className="t-small" style={{ color: "var(--amber-ink)" }}>A pipeline job is running — restore when it has finished.</p>}
        <ReasonField id="rs-why" value={why} onChange={setWhy} placeholder="Why — e.g. rewind for the jury demo" autoFocus />
        <div className="row">
          <button className="btn btn-danger" disabled={!reasonOk(why) || m.isPending || busy} onClick={() => m.mutate()}>
            {m.isPending ? "Restoring…" : `Restore “${name ?? ""}”`}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Drawer>
  );
}
