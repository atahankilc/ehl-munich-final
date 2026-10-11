// PM write actions with their guard rails: every one needs a reason (≥5 characters, server-enforced too),
// and long AI jobs run in the background with visible progress.
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api, invalidateAll } from "@/lib/api";
import type { ChallengeAnswer, Job } from "@/lib/types";
import { VERDICT } from "@/lib/labels";
import { Drawer } from "./Drawer";
import { useToast } from "./toast";

export const MIN_REASON = 5;
export const reasonOk = (s: string) => s.trim().length >= MIN_REASON;

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => api.get<Job>(`/api/jobs/${id}`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && q.state.data.status !== "running" ? false : 1500),
  });
}

export function ReasonField({ value, onChange, placeholder, id, autoFocus }: { value: string; onChange: (s: string) => void; placeholder: string; id: string; autoFocus?: boolean }) {
  const short = value.length > 0 && !reasonOk(value);
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        Reason <span className="faint">— recorded with your name in the audit trail</span>
      </label>
      <textarea id={id} className="textarea" rows={2} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} />
      {short && <div className="t-small" style={{ color: "var(--amber-ink)", marginTop: 4 }}>A few more words, please — at least {MIN_REASON} characters.</div>}
    </div>
  );
}

export function OverrideDrawer({ reqId, target, label, onClose }: { reqId: string; target: string | null; label: string; onClose: () => void }) {
  const [why, setWhy] = useState("");
  const toast = useToast();
  const m = useMutation({
    mutationFn: () => api.post(`/api/requirements/${reqId}/override`, { target, rationale: why }),
    onSuccess: () => {
      toast({ tone: "ok", title: "Gate overridden", body: `${label} — recorded in the audit trail.` });
      invalidateAll();
      onClose();
    },
    onError: (e: Error) => toast({ tone: "error", title: "Not overridden", body: e.message }),
  });
  return (
    <Drawer open={!!target} onClose={onClose} title={`Override the brand gate · ${label}`} sub="The AI found a brand-fit problem. You can approve anyway, but only with a reason.">
      <div className="col" style={{ gap: 14 }}>
        <ReasonField id="ov-why" value={why} onChange={setWhy} placeholder="Why this still fits the brand for this car and market…" autoFocus />
        <div className="row">
          <button className="btn btn-danger" disabled={!reasonOk(why) || m.isPending} onClick={() => m.mutate()}>
            Override gate
          </button>
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Drawer>
  );
}

/** "Ask the AI": the PM challenges a requirement; the answer can propose edits and evidence links (proposals). */
export function ChallengeDrawer({ reqId, open, onClose }: { reqId: string; open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const toast = useToast();
  const start = useMutation({
    mutationFn: () => api.post<{ job_id: string }>(`/api/requirements/${reqId}/challenge`, { question: q }),
    onSuccess: (r) => setJobId(r.job_id),
    onError: (e: Error) => toast({ tone: "error", title: "Couldn't ask the AI", body: e.message }),
  });
  useEffect(() => {
    if (job.data?.status === "done") invalidateAll();
  }, [job.data?.status]);
  useEffect(() => {
    if (!open) {
      setJobId(null);
      setQ("");
    }
  }, [open]);
  const res = (job.data?.result ?? null) as { answer?: ChallengeAnswer; cost?: number } | null;
  const a = res?.answer;
  return (
    <Drawer open={open} onClose={onClose} title="Ask the AI" sub="Challenge the requirement. The status becomes Challenged; any edits the AI suggests arrive as proposals you decide on.">
      {!jobId && (
        <div className="col" style={{ gap: 14 }}>
          <div>
            <label className="field-label" htmlFor="ch-q">Your question</label>
            <textarea id="ch-q" className="textarea" rows={4} value={q} onChange={(e) => setQ(e.target.value)} autoFocus placeholder="e.g. Is there evidence that Chinese customers want this, or is it a US pain point?" />
          </div>
          <div className="row">
            <button className="btn btn-primary" disabled={!reasonOk(q) || start.isPending} onClick={() => start.mutate()}>
              <Sparkles /> Ask · costs a few cents
            </button>
            <span className="t-small faint">Takes 20–60 seconds.</span>
          </div>
        </div>
      )}
      {jobId && job.data?.status === "running" && (
        <div className="col" style={{ gap: 12 }}>
          <span className="telltale blue pulse">The AI is re-reading the evidence…</span>
          <div className="skel" style={{ height: 4 }} />
        </div>
      )}
      {job.data?.status === "error" && <div className="errnote"><span className="errnote-msg">{job.data.error}</span></div>}
      {a && (
        <div className="col" style={{ gap: 16 }}>
          <span className={`chip ${a.verdict === "upheld" ? "up" : a.verdict === "partially_upheld" ? "warn" : "blue"}`} style={{ alignSelf: "flex-start" }}>
            {VERDICT[a.verdict] ?? a.verdict}
          </span>
          <p className="t-lead">{a.answer}</p>
          {a.evidence_for.length > 0 && (
            <div>
              <div className="sec-label">Evidence for</div>
              <ul className="sw-list">{a.evidence_for.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
          )}
          {a.evidence_against.length > 0 && (
            <div>
              <div className="sec-label">Evidence against</div>
              <ul className="sw-list">{a.evidence_against.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
          )}
          {(a.proposed_edits.length > 0 || a.link_finding_ids.length > 0) && (
            <p className="t-small muted">
              {a.proposed_edits.length} edit(s) and {a.link_finding_ids.length} evidence link(s) were proposed — they are in your Decide queue.
            </p>
          )}
        </div>
      )}
    </Drawer>
  );
}
