// Deliver: the BMW deliverable — prioritized, evidence-linked requirements per car · market, as JSON, CSV or Markdown.
// Counts come from the requirement list (free); only the download itself is logged as an export.
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Braces, FileText, Sheet } from "lucide-react";
import { api, qs, queryClient, getActor } from "@/lib/api";
import type { RequirementSummary, Status } from "@/lib/types";
import { fmtInt } from "@/lib/format";
import { Empty, ErrorNote, PriorityMark, Skeleton, SkeletonBlock, StatusLight } from "@/components/ui";

const ALL: Status[] = ["approved", "proposed", "challenged", "deferred", "rejected"];
const DEFAULT: Status[] = ["approved", "proposed", "challenged", "deferred"];

const FORMATS = [
  { f: "json", label: "JSON", icon: Braces, file: "requirements.json", note: "Full and nested: every target with its score breakdown, every finding with up to 25 sources." },
  { f: "csv", label: "CSV", icon: Sheet, file: "requirements.csv", note: "One row per car · market target — opens in Excel." },
  { f: "md", label: "Markdown", icon: FileText, file: "requirements.md", note: "A readable report: per requirement, its targets, rationale, evidence and assumptions." },
] as const;

const CONTENTS: { group: string; fields: string[] }[] = [
  {
    group: "Requirement",
    fields: ["ID, title, description, category", "Target metric & acceptance criteria", "Status & version", "Horizon, Kano class & drift, must-not-lose", "Rough effort (S / M / L)", "Evidence level (E1–E4)", "Assumptions, uncertainties, conflicting evidence"],
  },
  {
    group: "Per car · market",
    fields: ["Realization (carry-over, platform-wide, …)", "Score 0–100 with factor breakdown", "AI-proposed and PM-confirmed priority", "Evidence level for this market", "Prioritization rationale & market note"],
  },
  {
    group: "Evidence trail",
    fields: ["Linked findings — supports or contradicts", "Source kind, car and market", "Sample sources: feedback IDs, study items, web URLs with trust tier", "Quotes where the source has one"],
  },
];

export function Deliver() {
  const [sel, setSel] = useState<Status[]>(DEFAULT);
  const status = ALL.filter((s) => sel.includes(s)).join(",");
  const q = useQuery({
    queryKey: ["requirements", "deliver", status],
    queryFn: () => api.get<RequirementSummary[]>(`/api/requirements${qs({ status, include_rejected: sel.includes("rejected") })}`),
    enabled: sel.length > 0,
  });
  const all = useQuery({ queryKey: ["requirements", "deliver", "all"], queryFn: () => api.get<RequirementSummary[]>(`/api/requirements${qs({ include_rejected: true })}`) });
  const byStatus = useMemo(() => {
    const c: Partial<Record<Status, number>> = {};
    for (const r of all.data ?? []) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [all.data]);

  const rows = useMemo(() => (sel.length ? (q.data ?? []).filter((r) => sel.includes(r.status)) : []), [q.data, sel]);
  const counts = useMemo(() => {
    let targets = 0;
    let pm = 0;
    for (const r of rows) {
      targets += r.targets.length;
      pm += r.targets.filter((t) => t.pm_priority).length;
    }
    return { reqs: rows.length, targets, approved: rows.filter((r) => r.status === "approved").length, pm };
  }, [rows]);
  const toggle = (s: Status) => setSel((xs) => (xs.includes(s) ? xs.filter((x) => x !== s) : [...xs, s]));
  const loading = sel.length > 0 && q.isLoading;
  const empty = sel.length === 0 || (!loading && rows.length === 0);

  return (
    <div className="deliver">
      <section className="panel dl-main" aria-labelledby="dl-h">
        <div className="panel-head">
          <h2 id="dl-h">Requirements deliverable</h2>
          <span className="t-small faint">Every download is logged in the audit trail</span>
        </div>
        <div className="panel-body col" style={{ gap: 20 }}>
          <div>
            <div className="px-label">Include requirements that are</div>
            <div className="dl-status" role="group" aria-label="Statuses to include">
              {ALL.map((s) => (
                <button key={s} type="button" className="dl-st" aria-pressed={sel.includes(s)} onClick={() => toggle(s)}>
                  <StatusLight s={s} />
                  <span className="num faint">{all.data ? fmtInt(byStatus[s] ?? 0) : ""}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="dl-counts" aria-live="polite">
            {[
              { n: counts.reqs, l: "requirements" },
              { n: counts.targets, l: "car · market targets" },
              { n: counts.approved, l: "approved" },
              { n: counts.pm, l: "PM-confirmed priorities" },
            ].map((c) => (
              <div key={c.l}>
                {loading ? <Skeleton h={30} w={56} /> : <span className="instrument dl-n">{fmtInt(sel.length ? c.n : 0)}</span>}
                <small>{c.l}</small>
              </div>
            ))}
          </div>
          {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}
          {!loading && counts.reqs > 0 && counts.pm < counts.targets && (
            <p className="t-small muted">
              {fmtInt(counts.targets - counts.pm)} of {fmtInt(counts.targets)} priorities are still the AI's suggestion — they're exported as <i>AI-proposed</i>, not as your decision.{" "}
              <Link to="/decide">Decide them</Link>.
            </p>
          )}

          <div className="dl-formats">
            {FORMATS.map((f) => (
              <div key={f.f} className="dl-format">
                <a
                  className={`btn${f.f === "json" ? " btn-primary" : ""}${empty ? " is-disabled" : ""}`}
                  href={empty ? undefined : `/api/export${qs({ status, format: f.f, as_actor: getActor() })}`}
                  download={f.file}
                  aria-disabled={empty}
                  onClick={(e) => {
                    if (empty) {
                      e.preventDefault();
                      return;
                    }
                    setTimeout(() => queryClient.invalidateQueries({ queryKey: ["audit"] }), 1200);
                  }}
                >
                  <f.icon /> {f.label}
                </a>
                <span className="t-small muted">{f.note}</span>
              </div>
            ))}
          </div>
          <p className="t-small faint">Option-list prices are never part of the deliverable. Customer quotes are included — the file is confidential.</p>
        </div>
      </section>

      <section className="panel dl-side" aria-labelledby="dl-c">
        <div className="panel-head">
          <h2 id="dl-c">What the deliverable contains</h2>
        </div>
        <div className="panel-body dl-contents">
          {CONTENTS.map((g) => (
            <div key={g.group}>
              <h3>{g.group}</h3>
              <ul>
                {g.fields.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="panel dl-preview" aria-labelledby="dl-p">
        <div className="panel-head">
          <h2 id="dl-p">Preview</h2>
          <span className="t-small faint">{rows.length > 8 ? `First 8 of ${fmtInt(rows.length)}` : ""}</span>
        </div>
        {loading && (
          <div className="panel-body">
            <SkeletonBlock lines={5} />
          </div>
        )}
        {!loading && empty && (
          <Empty title="Nothing selected">{sel.length === 0 ? "Pick at least one status to include." : "No requirements have these statuses yet."}</Empty>
        )}
        {!loading && rows.length > 0 && (
          <div className="px-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Status</th>
                  <th>Best target</th>
                  <th className="r">Targets</th>
                  <th className="r">PM-confirmed</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 8).map((r) => {
                  const best = r.targets.find((t) => t.target.key === r.best_target?.key) ?? r.targets[0];
                  return (
                    <tr key={r.id}>
                      <td>
                        <Link to={`/requirements/${r.id}`} className="dl-req">
                          <span className="id">{r.id}</span>
                          <span className="ellipsis">{r.title}</span>
                        </Link>
                      </td>
                      <td>
                        <StatusLight s={r.status} />
                      </td>
                      <td>
                        {best ? (
                          <span className="row" style={{ gap: 8 }}>
                            <PriorityMark p={best.priority} size="sm" ai={best.ai_only} />
                            <span className="muted">{best.target.label}</span>
                          </span>
                        ) : (
                          <span className="faint">–</span>
                        )}
                      </td>
                      <td className="r">{r.targets.length}</td>
                      <td className="r">{r.targets.filter((t) => t.pm_priority).length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
