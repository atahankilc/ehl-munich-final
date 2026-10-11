export const fmtScore = (s: number | null | undefined) => (s == null ? "–" : Math.round(s).toString());
export const fmtDelta = (d: number | null | undefined) => (d == null ? "–" : `${d > 0 ? "+" : d < 0 ? "−" : "±"}${Math.abs(d).toFixed(1)}`);
export const fmtUsd = (n: number) => `$${n.toFixed(2)}`;
export const fmtInt = (n: number | null | undefined) => (n == null ? "–" : n.toLocaleString("en-US"));
export const fmtPct = (n: number | null | undefined, digits = 1) => (n == null ? "–" : `${(n * 100).toFixed(digits)}%`);

export function fmtWhen(ts: string | null | undefined): string {
  if (!ts) return "–";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fmtSimDate(s: string | null | undefined): string {
  if (!s) return "";
  const [y, m] = s.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return m ? `${months[Number(m) - 1]} ${y}` : s;
}

/** Split a markdown bullet string ("- a\n- b") into items. */
export function bullets(s: string | null | undefined): string[] {
  if (!s) return [];
  return s
    .split(/\n+/)
    .map((l) => l.replace(/^\s*[-*•]\s*/, "").trim())
    .filter(Boolean);
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
