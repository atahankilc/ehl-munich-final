// Page 4's marks in DOM, drawn like the skyline's columns: Must solid, Should outlined, Could a thin line. Hue is the
// domain (or ink in neutral contexts); the band is the shape, never the hue.
import type { Band, GateResult } from "@/lib/prioritize";

export function BandMark({ band, color, size = "md", pm = false }: { band: Band | null; color?: string; size?: "sm" | "md" | "lg"; pm?: boolean }) {
  if (!band) return <i className="pband" data-band="none" data-size={size} aria-label="not targeted" />;
  return <i className="pband" data-band={band} data-size={size} data-pm={pm ? "" : undefined} style={color ? { ["--c" as string]: color } : undefined} aria-label={band} />;
}

/** gate result by shape: pass a filled dot, warn a half-filled ring, fail a ring with a bar through it */
export function GateMark({ result }: { result: GateResult }) {
  return <i className="pgate" data-r={result} aria-label={result} />;
}

export function Arrow({ d }: { d: number }) {
  if (!d) return null;
  return <span className="parrow" data-d={d > 0 ? "up" : "down"} aria-label={d > 0 ? "rose" : "fell"}>{d > 0 ? "▲" : "▼"}</span>;
}
