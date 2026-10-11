// Small pieces shared by the Evidence tabs: kind chip, scope label, per-market mini bars, filter vocabulary.
import { ClipboardList, Globe2, MessageSquareText } from "lucide-react";
import type { FindingKind, MarketCode } from "@/lib/types";
import { MARKET, car, mkt } from "@/lib/labels";

export const MARKETS: MarketCode[] = ["US", "EU", "CN", "RoW"];

export const KIND: Record<FindingKind, { label: string; long: string; icon: typeof Globe2 }> = {
  verbatim: { label: "Comments", long: "Customer comments", icon: MessageSquareText },
  study: { label: "Study", long: "Customer study", icon: ClipboardList },
  web: { label: "Web", long: "Cited web research", icon: Globe2 },
};

export function KindChip({ kind }: { kind: FindingKind | string }) {
  const k = KIND[kind as FindingKind];
  if (!k) return <span className="chip outline">{kind}</span>;
  return (
    <span className={`chip outline ev-kind ev-kind-${kind}`} title={k.long}>
      <k.icon aria-hidden />
      {k.label}
    </span>
  );
}

/** "5 Series · USA"; a finding without a car is line-wide, without a market it spans all markets. */
export function scopeLabel(vehicle: string | null | undefined, market: string | null | undefined) {
  return `${vehicle ? car(vehicle) : "All cars"} · ${market ? mkt(market) : "All markets"}`;
}

export const humanize = (s: string | null | undefined) => (s ? (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ") : "–");

export const FEEDBACK_TYPE: Record<string, string> = {
  like: "Praise",
  complaint: "Complaint",
  want: "Wish",
  defect: "Defect",
  difficult_to_use: "Hard to use",
};
export const FEEDBACK_TONE: Record<string, string> = { like: "up", complaint: "warn", want: "blue", defect: "down", difficult_to_use: "violet" };
export const SEVERITY_TONE: Record<string, string> = { high: "red", medium: "amber", low: "" };
export const POLARITY: Record<string, string> = { pain_or_want: "Pain or wish", like: "Strength", context: "Context" };
export const TIER: Record<string, string> = {
  T1: "Official / primary source",
  T2: "Established press / analysts",
  T3: "Forums / blogs",
};

/** Four hairline columns, one per market, scaled to the row's own loudest market — reads as the market mix. */
export function MarketBars({ by }: { by: Partial<Record<MarketCode, number>> }) {
  const max = Math.max(1, ...MARKETS.map((m) => by[m] ?? 0));
  const tip = MARKETS.map((m) => `${MARKET[m]} ${(by[m] ?? 0).toLocaleString("en-US")}`).join(" · ");
  return (
    <span className="mbars" title={tip} aria-label={tip} role="img">
      {MARKETS.map((m) => {
        const n = by[m] ?? 0;
        return (
          <span key={m} className="mbar">
            <i className={n ? "on" : ""} style={{ height: n ? Math.max(3, Math.round((n / max) * 14)) : 2 }} />
            <b>{m === "RoW" ? "R" : m.charAt(0)}</b>
          </span>
        );
      })}
    </span>
  );
}

export const isTyping = (e: KeyboardEvent) => {
  const t = e.target as HTMLElement;
  return !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
};
