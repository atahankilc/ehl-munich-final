// Geometry of the scan volume. The comment galaxy sits in the unit ball. Just outside it runs the research time ring
// (angle = publication date, so the sweep that reveals the second checkpoint passes newer research in date order).
// Beyond that the car-specific rings (study, options, sales) run in one sector per car line, right under the car's
// name. The 5 Series sector holds the G60 and, in its last part, the China long-wheelbase G68 (D-042).

export const TAU = Math.PI * 2;

export const CARS = ["F70", "G60", "G68", "G70"] as const;           // derivatives in the data
export const LINES = ["F70", "G60", "G70"] as const;                 // one sector per car line
export const CAR_NAME: Record<string, string> = { F70: "1 Series", G60: "5 Series", G68: "5 Series LWB", G70: "7 Series" };
export const LINE_CODES: Record<string, string> = { F70: "F70", G60: "G60 · G68", G70: "G70" };
export const MARKET_NAME: Record<string, string> = { EU: "Europe", US: "USA", CN: "China", RoW: "Rest of world" };

export const R = { time: 1.32, study: 1.6, options: 1.8, sales: 2.02, labels: 2.42 } as const;

const START = Math.PI / 2;   // sectors start at the front, so the gap between the 7 and 1 Series faces the viewer
const GAP = 0.08;            // radians between sectors
const LWB_SHARE = 0.28;      // share of the 5 Series sector given to the China long-wheelbase G68

export function lineSector(line: string): [number, number] {
  const i = Math.max(0, LINES.indexOf(line as (typeof LINES)[number]));
  const a0 = START + (i * TAU) / LINES.length + GAP / 2;
  return [a0, a0 + TAU / LINES.length - GAP];
}

/** Angular span for one derivative's items on the car rings. */
export function sector(car: string): [number, number] {
  if (car === "G60" || car === "G68") {
    const [a0, a1] = lineSector("G60");
    const split = a1 - (a1 - a0) * LWB_SHARE;
    return car === "G60" ? [a0, split - GAP / 4] : [split + GAP / 4, a1];
  }
  return lineSector(car);
}

// Time ring: Jul 2025 → Jul 2026 over 300°, the JAN cut-off at bearing 0 (viewer's right). Older items collect just
// before the start.
const T0 = Date.parse("2025-07-01");
const T1 = Date.parse("2026-07-31");
const SPAN = (300 / 360) * TAU;
export const TIME_START = -SPAN * ((Date.parse("2026-01-31") - T0) / (T1 - T0));
export function timeAngle(iso: string | null): number {
  const t = iso ? Date.parse(iso.length === 7 ? `${iso}-28` : iso.length === 4 ? `${iso}-12-31` : iso) : NaN;
  if (Number.isNaN(t) || t < T0) return TIME_START - 0.08;
  return TIME_START + SPAN * Math.min(1, (t - T0) / (T1 - T0));
}
export const SWEEP_START = timeAngle("2026-01-31"); // the sweep to JUL starts at the JAN cut-off

export const polar = (r: number, a: number, y = 0): [number, number, number] => [r * Math.cos(a), y, r * Math.sin(a)];

/** Study ticks: one per item, grouped by car in input order; tip offset outward/inward by the item's z-score. */
export function studyLayout<T extends { car: string; z: number | null }>(list: T[]) {
  const byCar = new Map<string, T[]>();
  for (const s of list) byCar.set(s.car, [...(byCar.get(s.car) ?? []), s]);
  const out: { item: T; base: [number, number, number]; tip: [number, number, number] }[] = [];
  for (const [car, rows] of byCar) {
    const [a0, a1] = sector(car);
    rows.forEach((s, i) => {
      const a = a0 + ((a1 - a0) * (i + 0.5)) / rows.length;
      out.push({ item: s, base: polar(R.study, a), tip: polar(R.study + Math.max(-2.5, Math.min(2.5, s.z ?? 0)) * 0.05, a) });
    });
  }
  return out;
}

/** Option dots: one per equipment option, grouped by car in input order, in three slightly offset lanes. */
export function optionLayout<T extends { car: string }>(list: T[]) {
  const byCar = new Map<string, T[]>();
  for (const o of list) byCar.set(o.car, [...(byCar.get(o.car) ?? []), o]);
  const out: { item: T; at: [number, number, number] }[] = [];
  for (const [car, rows] of byCar) {
    const [a0, a1] = sector(car);
    rows.forEach((o, i) => out.push({ item: o, at: polar(R.options + ((i % 3) - 1) * 0.018, a0 + ((a1 - a0) * (i + 0.5)) / rows.length) }));
  }
  return out;
}
