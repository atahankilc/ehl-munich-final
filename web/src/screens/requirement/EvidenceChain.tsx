// Requirement → findings → customer signals → the original comment. Findings are grouped by where they come
// from; opening one lists the signals the AI extracted and the verbatim each came from.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import { MARKET } from "@/lib/labels";
import { ErrorNote, SkeletonBlock } from "@/components/ui";

type Card = {
  id: number;
  source_kind: "verbatim" | "study" | "web" | string;
  type: string;
  title: string;
  summary: string | null;
  relation: "supports" | "contradicts" | string;
  n_sources: number;
  n_signals: number;
  verbatims?: number | null;
  markets?: Record<string, { verbatims?: number; share?: number }>;
  metrics?: { tiers?: Record<string, number>; publishers?: string[]; mean?: number; z?: number };
};
type Signal = {
  signal_id: number;
  feedback_type: string;
  severity: string | null;
  need_statement: string | null;
  quote: string | null;
  quote_verified: number | boolean;
  source?: { external_id?: string; market?: string; country?: string; channel?: string };
};

const KIND: Record<string, string> = { verbatim: "Customer comments", study: "Customer study", web: "Competitors, reviews & trends" };
const FT: Record<string, string> = { like: "Likes", complaint: "Complaint", want: "Wants", defect: "Defect", difficult_to_use: "Hard to use" };

export function EvidenceChain({ reqId }: { reqId: string }) {
  const q = useQuery({ queryKey: ["requirement", reqId, "evidence"], queryFn: () => api.get<{ findings: Card[] }>(`/api/requirements/${reqId}/evidence`) });
  const [kind, setKind] = useState<string>("verbatim");
  if (q.isLoading) return <div className="panel panel-body"><SkeletonBlock lines={6} /></div>;
  if (q.isError) return <ErrorNote error={q.error} onRetry={() => q.refetch()} />;
  const fs = q.data?.findings ?? [];
  const kinds = ["verbatim", "study", "web"].filter((k) => fs.some((f) => f.source_kind === k));
  const active = kinds.includes(kind) ? kind : kinds[0];
  const list = fs.filter((f) => f.source_kind === active).sort((a, b) => (a.relation === b.relation ? (b.verbatims ?? b.n_sources) - (a.verbatims ?? a.n_sources) : a.relation === "contradicts" ? 1 : -1));
  return (
    <div className="panel chain">
      <div className="panel-head">
        <div className="seg" role="group" aria-label="Evidence type">
          {kinds.map((k) => (
            <button key={k} aria-pressed={k === active} onClick={() => setKind(k)}>
              {KIND[k] ?? k} <span className="count">{fs.filter((f) => f.source_kind === k).length}</span>
            </button>
          ))}
        </div>
        <span className="t-micro faint">{fs.filter((f) => f.relation === "contradicts").length} contradicting</span>
      </div>
      <ol className="chain-list">
        {list.map((f) => (
          <FindingRow key={f.id} f={f} />
        ))}
      </ol>
    </div>
  );
}

function FindingRow({ f }: { f: Card }) {
  const [open, setOpen] = useState(false);
  const mk = Object.entries(f.markets ?? {}).filter(([, m]) => (m.verbatims ?? 0) > 0);
  return (
    <li className={`chain-item${f.relation === "contradicts" ? " contra" : ""}`}>
      <button className="chain-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="grow">
          <span className="chain-title">
            {f.relation === "contradicts" && <span className="chip warn">contradicts</span>} {f.title}
          </span>
          {f.summary && <span className="chain-sum">{f.summary}</span>}
        </span>
        <span className="chain-meta">
          {f.source_kind === "verbatim" ? (
            <>
              <span className="num">{(f.verbatims ?? 0).toLocaleString()}</span> comments
              <span className="chain-mk">{mk.map(([m, x]) => <span key={m}>{MARKET[m] ?? m} {x.verbatims}</span>)}</span>
            </>
          ) : f.source_kind === "web" ? (
            <>
              <span className="num">{f.n_sources}</span> sources {Object.keys(f.metrics?.tiers ?? {}).sort()[0] && <span className="chip up">{Object.keys(f.metrics!.tiers!).sort()[0]}</span>}
            </>
          ) : (
            <>study item</>
          )}
        </span>
        <ChevronDown className={`gate-chev${open ? " up" : ""}`} aria-hidden />
      </button>
      {open && <FindingDetail f={f} />}
    </li>
  );
}

function FindingDetail({ f }: { f: Card }) {
  const isVerbatim = f.source_kind === "verbatim";
  const sig = useQuery({ queryKey: ["finding", f.id, "signals"], queryFn: () => api.get<Signal[]>(`/api/findings/${f.id}/signals?limit=12`), enabled: isVerbatim });
  const src = useQuery({
    queryKey: ["finding", f.id, "sources"],
    queryFn: () => api.get<{ kind: string; external_id: string | null; quote: string | null; text: string | null; url: string | null; trust_tier: string | null; meta: Record<string, unknown> }[]>(`/api/findings/${f.id}/sources?limit=8`),
    enabled: !isVerbatim,
  });
  if (isVerbatim) {
    if (sig.isLoading) return <div className="chain-body"><SkeletonBlock lines={3} /></div>;
    return (
      <div className="chain-body">
        <div className="t-micro faint" style={{ marginBottom: 8 }}>
          {f.n_signals.toLocaleString()} customer signals in this theme · showing the strongest
        </div>
        <ol className="signals">
          {(sig.data ?? []).map((s) => (
            <li key={s.signal_id} className="signal">
              <div className="row wrap" style={{ gap: 6 }}>
                <span className={`chip ${s.feedback_type === "like" ? "up" : s.feedback_type === "defect" ? "down" : "warn"}`}>{FT[s.feedback_type] ?? s.feedback_type}</span>
                {s.severity && <span className="chip outline">{s.severity}</span>}
                <span className="t-micro faint">
                  {s.source?.market ? MARKET[s.source.market] ?? s.source.market : ""} {s.source?.country ? `· ${s.source.country}` : ""} {s.source?.channel ? `· ${s.source.channel}` : ""} · <span className="id">{s.source?.external_id}</span>
                </span>
              </div>
              {s.need_statement && <p className="signal-need">{s.need_statement}</p>}
              {s.quote && <blockquote className="signal-quote">“{s.quote}”{!s.quote_verified && <span className="chip warn" style={{ marginLeft: 6 }}>quote not verbatim</span>}</blockquote>}
            </li>
          ))}
        </ol>
      </div>
    );
  }
  if (src.isLoading) return <div className="chain-body"><SkeletonBlock lines={3} /></div>;
  return (
    <div className="chain-body">
      <ol className="signals">
        {(src.data ?? []).map((s, i) => (
          <li key={i} className="signal">
            <div className="row wrap" style={{ gap: 6 }}>
              {s.trust_tier && <span className={`chip ${s.trust_tier === "T1" ? "up" : s.trust_tier === "T2" ? "warn" : "down"}`}>{s.trust_tier}</span>}
              <span className="t-micro faint">{String(s.meta?.publisher ?? s.external_id ?? s.kind)}</span>
              {s.url && <a className="t-micro" href={s.url} target="_blank" rel="noreferrer">source</a>}
            </div>
            <blockquote className="signal-quote">{s.quote ?? s.text}</blockquote>
          </li>
        ))}
      </ol>
    </div>
  );
}
