// Page 4 inside the shared canvas: the requirement pins lift off today's car and stand on a ring around it as a
// priority skyline. One column per requirement on the car line, grouped by vehicle domain; its HEIGHT is the target's
// score in the selected market, its MARK the band (Must solid, Should outlined, Could a thin line), its hue the domain.
// Two faint planes at the band thresholds (Should 45, Must 60). Switching market morphs the heights, so the PM sees
// where markets disagree (D-011). At JUL a ghost tick keeps JAN's height and movers pulse once. Bundles join their
// bases with a faint chord; two Musts that must be chosen jointly carry a dashed white arc labelled with the resource.
// A PM-confirmed band is the PM's position: the one blue mark, a dot with its wash at the column's base.
// Rendered inside DefinitionLayer's car group (same frame, same rise); leaving runs the move back onto the car.
import { memo, useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import type { Band, Target } from "@/lib/prioritize";
import type { ZoneDef } from "@/three/frame";
import { zoneToWorld, type CarFrame, type Vec3 } from "@/three/frame";
import { useCheckpoint } from "@/state/checkpoint";
import type { NavInput } from "../scan/navigate";
import { domainColor } from "../definition/data";
import { glide } from "../definition/StageLayer";
import { useView } from "../definition/store";
import { bandsAt, isBlocked, marketsOf, openProposals, parseFlags, pmBand, shownBand, usePrioritize } from "./data";
import { getP, selectTarget, setP, useP } from "./store";
import { usePreview } from "./weights";
import { CAUSE_LABEL } from "./data";
import { BAND_RANK, bandMove, dirOf, type Challenge, type Dir } from "./pm";
import "./pm.css";

export const RING_R = 2.45;          // world units; the car's half-length is ≈ 1.73
export const H_MAX = 2.0;            // height of a score of 100
const LIFT_S = 2.3, STAGGER = 0.38, WAIT = 0.25;
const INK = "#f2f4f7", SWEEP_HI = "#4d94ff";
// Rise / Fall (tokens.css --rise / --fall): only for a PM-confirmed band the AI now places higher / lower
const RF_COLOR: Record<Dir, string> = { up: "#2fbf71", down: "#ff3b30" };
const CONE = new THREE.ConeGeometry(1, 2.2, 14).translate(0, 1.1, 0);   // tip at y = 2.2, base at 0
const W = { Must: 0.064, Should: 0.064, Could: 0.016 };

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const smooth = (a: number, b: number, x: number) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeIO = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const hOf = (score: number) => (Math.max(0, Math.min(100, score)) / 100) * H_MAX;
const DOMAIN_ORDER = ["exterior", "interior", "powertrain", "chassis", "assist", "digital", "variants", "quality"];

type Orbit = { target: THREE.Vector3; update: () => void };

interface Col { key: string; title: string; domain: string; zone: string | null; angle: number; slot: Vec3; from: Vec3; order: number }

/* unit geometries, shared: base at y = 0, height 1 */
const BOX = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
const EDGES = new THREE.EdgesGeometry(BOX);
const DOT = new THREE.SphereGeometry(1, 16, 12);
const DISC = new THREE.CircleGeometry(1, 32).rotateX(-Math.PI / 2);
const HALO = new THREE.RingGeometry(0.62, 1, 40).rotateX(-Math.PI / 2);
const SLOT = new THREE.RingGeometry(0.7, 1, 24).rotateX(-Math.PI / 2);

export function Skyline({ active, frame, zones, carScale, reduced, nav, sweepId }: {
  active: boolean; frame: CarFrame; zones: Record<string, ZoneDef>; carScale: number; reduced: boolean;
  nav?: MutableRefObject<NavInput>; sweepId: number;
}) {
  const pd = usePrioritize();
  const { data } = pd;
  const { position } = useCheckpoint();
  const line = useView((s) => s.line);
  const markets = useMemo(() => marketsOf(data, line), [data, line]);
  const stored = useP((s) => s.market[line]);
  const market = stored && markets.includes(stored) ? stored : markets[0] ?? "";
  const selected = useP((s) => s.selected);
  const hover = useP((s) => s.hover);
  const bundle = useP((s) => s.bundle);
  const flat = useP((s) => s.view === "matrix");   // the matrix is in front: the skyline steps back
  const pendingBands = useP((s) => s.pending);
  const pendingProps = useP((s) => s.pendingProposals);
  // the weights panel's preview: proposed thresholds and per-target score / AI band, in memory only
  const pv = usePreview();
  const at = pv?.bands ?? bandsAt(data);

  /* the ring: every requirement on this line (any market) keeps its slot, so switching market only moves heights */
  const cols = useMemo<Col[]>(() => {
    const by = new Map<string, { t: Target; max: number }>();
    for (const t of data.targets) if (t.line === line) {
      const cur = by.get(t.key);
      if (!cur || t.score > cur.max) by.set(t.key, { t, max: Math.max(t.score, cur?.max ?? 0) });
    }
    const list = [...by.values()].sort((a, b) => (DOMAIN_ORDER.indexOf(a.t.domain) + 99) % 99 - (DOMAIN_ORDER.indexOf(b.t.domain) + 99) % 99 || b.max - a.max);
    const groups = new Set(list.map((x) => x.t.domain)).size;
    const GAP = 1.4;
    const units = list.length + groups * GAP;
    const step = (Math.PI * 2) / Math.max(units, 8);
    let u = GAP / 2, prev = "";
    // start at the back so the first domain group sits at the far left and the ring reads clockwise toward the camera
    const a0 = Math.PI * 0.62;
    return list.map(({ t }, i) => {
      if (prev && t.domain !== prev) u += GAP;
      prev = t.domain;
      const angle = a0 + (u + 0.5) * step;
      u += 1;
      const z = t.zones.find((k) => zones[k]) ?? null;
      const from = z ? zoneToWorld(zones[z].pos, frame).map((v) => v * carScale) as Vec3 : [0, 0.5, 0] as Vec3;
      return { key: t.key, title: t.title, domain: t.domain, zone: z, angle, order: i,
               slot: [RING_R * Math.cos(angle), 0, RING_R * Math.sin(angle)] as Vec3, from };
    });
  }, [data.targets, line, zones, frame, carScale]);
  const colOf = useMemo(() => new Map(cols.map((c) => [c.key, c])), [cols]);
  const inMarket = useMemo(() => new Map(data.targets.filter((t) => t.line === line && t.market === market).map((t) => {
    const p = pv?.by.get(`${t.key}|${t.line}|${t.market}`);
    return [t.key, p ? { ...t, score: p.score, band: p.band } : t];
  })), [data.targets, line, market, pv]);
  const proposals = useMemo(() => new Map(openProposals(data).filter((p) => p.line === line && p.market === market).map((p) => [p.key, p])), [data, line, market]); // eslint-disable-line react-hooks/exhaustive-deps
  /* rise / fall: a PM-confirmed band the AI now places higher or lower (open proposal against "pm"). The column stays at
     the PM's level (JAN's score, clamped into the PM's band) — it is still the PM's position until they act — and the
     AI's score becomes a coloured ghost with a rise / drop line. Not in the weights preview (hypothetical, stays white). */
  const rfs = useMemo(() => {
    const m = new Map<string, RF>();
    if (pv) return m;
    for (const [k, p] of proposals) {
      const tg = inMarket.get(k);
      if (!tg || p.against !== "pm" || pendingProps[String(p.id)]) continue;
      const from = pendingBands[`${tg.key}|${tg.line}|${tg.market}`] ?? tg.confirmed?.priority ?? null;
      const dir = from ? dirOf(p.proposed_band, from) : null;
      if (!from || !dir) continue;
      const lo = from === "Must" ? at.Must : from === "Should" ? at.Should : 0, hi = from === "Must" ? 100 : from === "Should" ? at.Must : at.Should;
      const pmScore = Math.max(lo + 1, Math.min(hi - 1, tg.prev?.score ?? (lo + hi) / 2));
      m.set(k, { dir, from, to: p.proposed_band, cause: CAUSE_LABEL[p.cause] ?? p.cause, pmScore, aiScore: tg.score });
    }
    return m;
  }, [proposals, inMarket, pv, at.Must, at.Should, pendingBands, pendingProps]);

  /* domain group labels on the ground, outside the ring */
  const groups = useMemo(() => {
    const m = new Map<string, Col[]>();
    for (const c of cols) m.set(c.domain, [...(m.get(c.domain) ?? []), c]);
    return [...m].map(([d, cs]) => {
      const a = (cs[0].angle + cs[cs.length - 1].angle) / 2;
      return { d, n: cs.filter((c) => inMarket.has(c.key)).length, at: [(RING_R + 0.62) * Math.cos(a), 0, (RING_R + 0.62) * Math.sin(a)] as Vec3 };
    });
  }, [cols, inMarket]);

  /* the lift: one scalar, staggered per column; reversed it lowers the columns back onto the car */
  const t = useRef(0);
  const wait = useRef(WAIT);
  const [present, setPresent] = useState(active);
  useEffect(() => { if (active) { setPresent(true); wait.current = reduced ? 0 : WAIT; } }, [active, reduced]);
  const heights = useRef(new Map<string, number>());
  const refs = useRef(new Map<string, ColRefs>());
  const planes = useRef<THREE.Group>(null);
  const ground = useRef<THREE.Group>(null);
  const overlay = useRef<THREE.Group>(null);
  const chords = useRef<THREE.Group>(null);
  // DOM labels that fade with the planes (fade) or appear once every column has landed (late)
  const fade = useRef(new Set<HTMLElement>());
  const late = useRef(new Set<HTMLElement>());
  const fadeRef = useCallback((el: HTMLElement | null) => { if (el) fade.current.add(el); }, []);
  const lateRef = useCallback((el: HTMLElement | null) => { if (el) late.current.add(el); }, []);
  const v = useMemo(() => ({ m: new THREE.Vector3(), a: new THREE.Vector3(), b: new THREE.Vector3(), c: new THREE.Vector3(), q: new THREE.QuadraticBezierCurve3() }), []);
  useFrame((_, dt) => {
    const goal = active ? 1 : 0;
    if (active && wait.current > 0) wait.current -= dt;
    else if (t.current !== goal) {
      const k = reduced ? 1 : dt / LIFT_S;
      t.current = goal > t.current ? Math.min(1, t.current + k) : Math.max(0, t.current - k * 1.25);
    }
    const out = t.current > 0;
    if (out !== getP().out) setP({ out });
    if (!active && t.current === 0 && present) setPresent(false);
    const T = t.current;
    const n = Math.max(1, cols.length);
    const morph = reduced ? 1 : 1 - Math.exp(-dt * 4.5);
    for (const c of cols) {
      const r = refs.current.get(c.key);
      if (!r?.group) continue;
      const tg = inMarket.get(c.key);
      const goalH = tg ? hOf(rfs.get(c.key)?.pmScore ?? tg.score) : 0;
      const h0 = heights.current.get(c.key) ?? goalH;
      const h = Math.abs(goalH - h0) < 0.0005 ? goalH : h0 + (goalH - h0) * morph;
      heights.current.set(c.key, h);
      const d = (c.order / n) * STAGGER;
      const ti = clamp01((T - d) / (1 - STAGGER));
      const fly = easeIO(clamp01(ti / 0.55));
      const grow = smooth(0.5, 1, ti);
      v.a.set(...c.from); v.c.set(...c.slot);
      v.b.lerpVectors(v.a, v.c, 0.5); v.b.y = Math.max(v.a.y, 0) + 0.85;
      v.q.v0.copy(v.a); v.q.v1.copy(v.b); v.q.v2.copy(v.c);
      v.q.getPoint(fly, v.m);
      r.group.position.copy(v.m);
      r.group.visible = T > 0.001;
      const shownH = Math.max(0.0001, h * grow);
      if (r.scale) r.scale.scale.y = shownH;
      if (r.cap) r.cap.position.y = shownH;
      if (r.pin) { const s = (1 - grow) * 0.05; r.pin.visible = s > 0.002; r.pin.scale.setScalar(Math.max(0.0001, s)); }
      if (r.base) r.base.visible = grow > 0.6;
      if (r.ghost) r.ghost.visible = grow > 0.98;
      if (r.rf) r.rf.visible = grow > 0.98;
      if (r.label) { const o = smooth(0.85, 1, ti); r.label.style.opacity = o.toFixed(3); r.label.style.visibility = o > 0.02 ? "" : "hidden"; }
    }
    const show = smooth(0.55, 1, T);
    if (planes.current) { planes.current.visible = show > 0.01; planes.current.position.y = 0; planes.current.scale.setScalar(0.92 + 0.08 * show); setOpacity(planes.current, show); }
    if (ground.current) { ground.current.visible = show > 0.01; setOpacity(ground.current, show); }
    if (overlay.current) overlay.current.visible = T >= 0.999;
    if (chords.current) chords.current.visible = T >= 0.9;
    for (const el of fade.current) { if (!el.isConnected) { fade.current.delete(el); continue; } el.style.opacity = show.toFixed(3); el.style.visibility = show > 0.02 ? "" : "hidden"; }
    for (const el of late.current) { if (!el.isConnected) { late.current.delete(el); continue; } el.style.visibility = T >= 0.999 ? "" : "hidden"; }
  });

  useSkylineCamera(active, reduced, nav);
  useEffect(() => () => { setP({ out: false }); document.body.style.cursor = ""; }, []);

  /* bundles present in this market: chords between their bases, through the inside of the ring */
  const bundleChords = useMemo(() => {
    const out: { id: string; pts: THREE.Vector3[]; keys: string[] }[] = [];
    for (const b of data.bundles) {
      const members = b.keys.filter((k) => inMarket.has(k) && colOf.has(k)).map((k) => colOf.get(k)!).sort((a, c) => a.angle - c.angle);
      if (members.length < 2) continue;
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i < members.length - 1; i++) {
        const A = new THREE.Vector3(...members[i].slot), C = new THREE.Vector3(...members[i + 1].slot);
        const B = A.clone().lerp(C, 0.5).multiplyScalar(0.62);
        const seg = new THREE.QuadraticBezierCurve3(A, B, C).getPoints(28);
        pts.push(...(i ? seg.slice(1) : seg));
      }
      pts.forEach((p) => { p.y = 0.006; });
      out.push({ id: b.id, pts, keys: members.map((m) => m.key) });
    }
    return out;
  }, [data.bundles, inMarket, colOf]);

  /* two Musts to choose jointly: a dashed arc between their tops, the shared resource at the apex */
  const joint = useMemo(() => {
    const seen = new Set<string>();
    const out: { id: string; a: string; b: string; via: string; pts: THREE.Vector3[]; apex: THREE.Vector3 }[] = [];
    for (const tg of inMarket.values()) for (const f of parseFlags(tg)) {
      if (f.kind !== "choose_jointly" || !f.partner) continue;
      const id = [tg.key, f.partner].sort().join("~");
      const other = inMarket.get(f.partner);
      if (seen.has(id) || !other || !colOf.has(tg.key) || !colOf.has(f.partner)) continue;
      seen.add(id);
      const A = new THREE.Vector3(...colOf.get(tg.key)!.slot).setY(hOf(tg.score) + 0.05);
      const C = new THREE.Vector3(...colOf.get(f.partner)!.slot).setY(hOf(other.score) + 0.05);
      const B = A.clone().lerp(C, 0.5).multiplyScalar(0.78); B.y = Math.max(A.y, C.y) + 0.55 + A.distanceTo(C) * 0.12;
      const q = new THREE.QuadraticBezierCurve3(A, B, C);
      out.push({ id, a: tg.key, b: f.partner, via: f.via ?? "", pts: q.getPoints(40), apex: q.getPoint(0.5) });
    }
    return out;
  }, [inMarket, colOf]);

  const register = useCollisions();
  const onRef = useCallback((key: string, r: ColRefs) => { refs.current.set(key, r); }, []);

  if (!present) return null;
  const selCol = selected && inMarket.has(selected) ? selected : null;
  const bundleKeys = new Set(data.bundles.find((b) => b.id === bundle)?.keys ?? []);
  const focusBundle = selCol ? inMarket.get(selCol)?.bundle_id ?? null : null;
  const facing = new THREE.Vector3(0.67, 0, -0.74);

  return (
    <group>
      {/* the band thresholds: two faint planes over the ring */}
      <group ref={planes}>
        <Plane y={hOf(at.Should)} label={`Should · ${at.Should}`} strength={0.09} facing={facing} labelRef={fadeRef} />
        <Plane y={hOf(at.Must)} label={`Must · ${at.Must}`} strength={0.14} facing={facing} labelRef={fadeRef} />
      </group>
      {/* the ground ring and the domain groups */}
      <group ref={ground}>
        <RingLine r={RING_R} y={0.003} opacity={0.12} />
        {groups.map((g) => (
          <Html key={g.d} position={g.at} center zIndexRange={[12, 10]}>
            <span ref={fadeRef} className="psky-group" style={{ ["--c" as string]: domainColor(g.d) }}><i aria-hidden />{DOMAIN_LABEL[g.d] ?? g.d}<b>{g.n}</b></span>
          </Html>
        ))}
      </group>
      <group ref={chords}>
        {bundleChords.map((b) => {
          const hot = bundle === b.id || focusBundle === b.id || (!!hover && b.keys.includes(hover));
          return <Line key={b.id} points={b.pts} color={INK} lineWidth={hot ? 1.6 : 1} transparent opacity={hot ? 0.62 : 0.16} depthWrite={false} />;
        })}
      </group>
      {cols.map((c) => {
        const tg = inMarket.get(c.key) ?? null;
        const band = tg ? shownBand(tg) : null;
        const on = selCol === c.key;
        const hot = on || hover === c.key || bundleKeys.has(c.key);
        // a shown bundle wins over the selection's focus, so "Show bundle" from the inspector lights its members
        const dim = flat || (bundleKeys.size > 0 ? !bundleKeys.has(c.key) : !!selCol && !on);
        const delta = tg?.prev && position > 1 ? tg.score - tg.prev.score : 0;
        const moved = !!tg?.prev && position > 1 && (Math.abs(delta) >= 3 || tg.prev.band !== tg.band);
        // a challenged PM decision: an open proposal against the PM's band (or, in the weights preview, one it would get)
        const pmb = tg ? pmBand(tg) : null;
        const pr = proposals.get(c.key);
        const rf = rfs.get(c.key) ?? null;
        const challenge: Challenge | null = !tg || !pmb || rf ? null
          : pv ? (pmb !== tg.band ? { band: tg.band, from: pmb, cause: "weights preview" } : null)
          : pr && pr.against === "pm" ? { band: pr.proposed_band, from: pmb, cause: CAUSE_LABEL[pr.cause] ?? pr.cause } : null;
        return (
          <Column key={c.key} c={c} t={tg} band={band} hot={hot} on={on} dim={dim} pm={pmb} blocked={tg ? isBlocked(tg) : false}
                  proposal={challenge || rf ? null : pv ? null : pr?.proposed_band ?? null} challenge={challenge} rf={rf}
                  move={!pv && tg && position > 1 && !rf ? bandMove(tg) : null}
                  prevH={tg?.prev && position > 1 && Math.abs(delta) >= 1 ? hOf(tg.prev.score) : null}
                  pulse={moved || rf || (challenge && !pv) ? `${sweepId}:${market}` : null} delta={delta} register={register} onRef={onRef} />
        );
      })}
      <group ref={overlay}>
        {joint.map((j) => {
          const hot = selCol === j.a || selCol === j.b || hover === j.a || hover === j.b;
          return (
            <group key={j.id}>
              <Line points={j.pts} color={INK} lineWidth={hot ? 1.8 : 1.3} dashed dashSize={0.07} gapSize={0.06} transparent opacity={hot ? 0.95 : 0.7} depthWrite={false} renderOrder={6} />
              <Html position={j.apex} center zIndexRange={[13, 11]}>
                <div ref={lateRef} className="dlink-label" data-dashed="">choose jointly · {j.via}</div>
              </Html>
            </group>
          );
        })}
      </group>
    </group>
  );
}

const DOMAIN_LABEL: Record<string, string> = {
  exterior: "Exterior", interior: "Interior & comfort", powertrain: "Powertrain & charging", chassis: "Chassis & dynamics",
  assist: "Driver assistance", digital: "Infotainment & digital", variants: "Variants & packages", quality: "Design & quality",
};

function setOpacity(g: THREE.Object3D, k: number) {
  g.traverse((o) => {
    const m = (o as THREE.Mesh).material as (THREE.Material & { opacity: number; userData: { base?: number } }) | undefined;
    if (!m || Array.isArray(m)) return;
    if (m.userData.base == null) m.userData.base = m.opacity;
    m.opacity = m.userData.base * k;
  });
}

/* ------------------------------------------------------------------------------------------- planes */
function RingLine({ r, y, opacity }: { r: number; y: number; opacity: number }) {
  const geom = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 180; i++) { const a = (i / 180) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r)); }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [r, y]);
  return <lineLoop geometry={geom}><lineBasicMaterial color="#ffffff" transparent opacity={opacity} depthWrite={false} /></lineLoop>;
}

function Plane({ y, label, strength, facing, labelRef }: { y: number; label: string; strength: number; facing: THREE.Vector3; labelRef: (el: HTMLElement | null) => void }) {
  const annulus = useMemo(() => new THREE.RingGeometry(RING_R - 0.34, RING_R + 0.34, 120).rotateX(-Math.PI / 2), []);
  const at: Vec3 = [facing.x * (RING_R + 0.5), y, facing.z * (RING_R + 0.5)];
  return (
    <group>
      <mesh geometry={annulus} position={[0, y, 0]} renderOrder={1}>
        <meshBasicMaterial color="#ffffff" transparent opacity={strength * 0.28} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <RingLine r={RING_R} y={y} opacity={strength} />
      <RingLine r={RING_R + 0.34} y={y} opacity={strength * 0.45} />
      <Html position={at} center zIndexRange={[11, 10]}>
        <span ref={labelRef} className="psky-plane">{label}</span>
      </Html>
    </group>
  );
}

/* ------------------------------------------------------------------------------------------- columns */
interface ColRefs { group: THREE.Group | null; scale: THREE.Group | null; cap: THREE.Group | null; pin: THREE.Mesh | null; base: THREE.Group | null; ghost: THREE.Mesh | null; rf?: THREE.Group | null; label: HTMLElement | null }
/** a challenged PM decision on the skyline: direction, the PM's band → the AI's, the PM's level and the AI's score */
interface RF { dir: Dir; from: Band; to: Band; cause: string; pmScore: number; aiScore: number }
/* the rise / drop line runs beside the column on the camera's side (perpendicular to the overview's view direction) */
const RF_OFF: Vec3 = [0.768 * 0.075, 0, 0.64 * 0.075];

const Column = memo(function Column({ c, t, band, hot, on, dim, pm, blocked, proposal, challenge, rf = null, move = null, prevH, pulse, delta, register, onRef }: {
  c: Col; t: Target | null; band: Band | null; hot: boolean; on: boolean; dim: boolean; pm: Band | null; blocked: boolean;
  proposal: Band | null; challenge: Challenge | null; rf?: RF | null; move?: Dir | null; prevH: number | null; pulse: string | null; delta: number; register: Register; onRef: (k: string, r: ColRefs) => void;
}) {
  const r = useRef<ColRefs>({ group: null, scale: null, cap: null, pin: null, base: null, ghost: null, label: null });
  useEffect(() => { onRef(c.key, r.current); }, [c.key, onRef]);
  const color = hot ? INK : domainColor(c.domain);
  const k = dim ? 0.28 : 1;
  const w = band ? W[band] : W.Could;
  const enter = (e: { stopPropagation: () => void; clientX?: number; clientY?: number; nativeEvent?: PointerEvent }) => {
    e.stopPropagation();
    if (!t) return;
    const ne = e.nativeEvent;
    setP({ hover: c.key, hoverPos: ne ? { x: ne.clientX, y: ne.clientY } : null });
    document.body.style.cursor = "pointer";
  };
  // the PM's columns keep their chips; a challenged one wins every collision (a downgrade is never hidden)
  const labelRef = register(c.key, on || hot || rf?.dir === "down" ? 1e9 : rf ? 9e8 + (t?.score ?? 0) : t ? t.score + (challenge ? 2000 : pm ? 1000 : 0) : -1);
  return (
    <group ref={(g) => { r.current.group = g; }}>
      {/* the column, by band: Must solid, Should outlined over a faint fill, Could a thin line */}
      <group ref={(g) => { r.current.scale = g; }}>
        {band === "Must" && <mesh geometry={BOX} scale={[w, 1, w]}><meshBasicMaterial color={color} transparent opacity={0.95 * k} /></mesh>}
        {band === "Should" && (
          <>
            <mesh geometry={BOX} scale={[w, 1, w]}><meshBasicMaterial color={color} transparent opacity={0.13 * k} depthWrite={false} /></mesh>
            <lineSegments geometry={EDGES} scale={[w, 1, w]}><lineBasicMaterial color={color} transparent opacity={0.95 * k} /></lineSegments>
          </>
        )}
        {band === "Could" && <mesh geometry={BOX} scale={[w, 1, w]}><meshBasicMaterial color={color} transparent opacity={0.85 * k} /></mesh>}
        {/* the PM's confirmed band: the column's edge in sweep blue over the domain fill (the one blue on page 4) */}
        {pm && <lineSegments geometry={EDGES} scale={[Math.max(0.03, w * 1.3), 1, Math.max(0.03, w * 1.3)]}><lineBasicMaterial color={SWEEP_HI} transparent opacity={k} /></lineSegments>}
        {t && (
          <mesh geometry={BOX} scale={[0.22, 1, 0.22]} onPointerOver={enter}
                onPointerMove={(e) => setP({ hoverPos: { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY } })}
                onPointerOut={() => { if (getP().hover === c.key) setP({ hover: null, hoverPos: null }); document.body.style.cursor = ""; }}
                onClick={(e) => { e.stopPropagation(); selectTarget(on ? null : c.key); }}>
            <meshBasicMaterial visible={false} />
          </mesh>
        )}
      </group>
      {/* the pin in flight (domain hue), shrinking into the column as it grows */}
      <mesh ref={(m) => { r.current.pin = m; }} geometry={DOT}><meshBasicMaterial color={domainColor(c.domain)} /></mesh>
      {/* ground: the slot (hollow when this market has no target here) and the PM's position */}
      <group ref={(g) => { r.current.base = g; }}>
        <mesh geometry={SLOT} position={[0, 0.004, 0]} scale={t ? 0.05 : 0.04}><meshBasicMaterial color={t ? domainColor(c.domain) : "#868d99"} transparent opacity={t ? 0.55 * k : 0.6} depthWrite={false} /></mesh>
        {pm && (
          <>
            <mesh geometry={DISC} position={[0, 0.006, 0]} scale={0.055}><meshBasicMaterial color={SWEEP_HI} depthWrite={false} /></mesh>
            <mesh geometry={HALO} position={[0, 0.005, 0]} scale={0.12}><meshBasicMaterial color="#1c69d4" transparent opacity={0.45} depthWrite={false} /></mesh>
          </>
        )}
      </group>
      {/* JAN's height at JUL: a ghost tick */}
      {prevH != null && (
        <mesh ref={(m) => { r.current.ghost = m; }} position={[0, prevH, 0]} scale={[0.13, 0.005, 0.13]} geometry={BOX}>
          <meshBasicMaterial color={INK} transparent opacity={0.38 * k} depthWrite={false} />
        </mesh>
      )}
      {/* rise / fall: the AI's level as a coloured ghost, a ring at the AI's score and a line from the PM's cap to it */}
      {rf && (() => {
        const hp = hOf(rf.pmScore), ha = hOf(rf.aiScore), col = RF_COLOR[rf.dir], down = rf.dir === "down";
        const lo = Math.min(hp, ha), span = Math.max(0.004, Math.abs(hp - ha)), gw = Math.max(0.05, w * (down ? 1.9 : 1.6));
        return (
          <group ref={(g) => { r.current.rf = g; }} visible={false}>
            <mesh geometry={BOX} position={[0, lo, 0]} scale={[gw, span, gw]} renderOrder={4}><meshBasicMaterial color={col} transparent opacity={(down ? 0.26 : 0.18) * k} depthWrite={false} /></mesh>
            <lineSegments geometry={EDGES} position={[0, lo, 0]} scale={[gw, span, gw]} renderOrder={4}><lineBasicMaterial color={col} transparent opacity={0.95 * k} depthWrite={false} /></lineSegments>
            <mesh geometry={HALO} position={[0, ha, 0]} scale={down ? 0.16 : 0.12} renderOrder={5}><meshBasicMaterial color={col} transparent opacity={k} depthWrite={false} side={THREE.DoubleSide} /></mesh>
            <Line points={[[RF_OFF[0], hp, RF_OFF[2]], [RF_OFF[0], down ? ha + 0.05 : ha - 0.05, RF_OFF[2]]]} color={col} lineWidth={down ? 4 : 2.6} transparent opacity={k} depthWrite={false} renderOrder={6} />
            <mesh geometry={CONE} position={[RF_OFF[0], down ? ha + 0.055 : ha - 0.055, RF_OFF[2]]} rotation={[down ? Math.PI : 0, 0, 0]} scale={[down ? 0.028 : 0.022, 0.025, down ? 0.028 : 0.022]} renderOrder={6}>
              <meshBasicMaterial color={col} transparent opacity={k} depthWrite={false} />
            </mesh>
          </group>
        );
      })()}
      {/* the top: Could's cap dot, and the score numeral */}
      <group ref={(g) => { r.current.cap = g; }}>
        {band === "Could" && <mesh geometry={DOT} scale={0.024}><meshBasicMaterial color={color} transparent opacity={k} /></mesh>}
        {/* challenged: a white ring at the AI's score (the column's top) — the AI now places it elsewhere than the PM */}
        {challenge && <mesh geometry={HALO} scale={0.1}><meshBasicMaterial color={INK} transparent opacity={0.85 * k} depthWrite={false} /></mesh>}
        {t && (
          <Html position={[0, 0.07, 0]} center zIndexRange={[13, 11]}>
            <div ref={(el) => { r.current.label = el; labelRef(el); }} className="psky-cap" data-hot={hot ? "" : undefined} data-on={on ? "" : undefined}
                 data-dim={dim ? "" : undefined} data-band={band ?? undefined} data-rf={rf?.dir}>
              {rf && (
                <span className="psky-rf" data-rf={rf.dir} role="status"
                      aria-label={rf.dir === "down" ? `Downgrade: AI now places it ${rf.to}, below your ${rf.from}. ${rf.cause}` : `Upgrade suggested: AI now places it ${rf.to}, above your ${rf.from}. ${rf.cause}`}>
                  <b aria-hidden>{rf.dir === "down" ? "▼" : "▲"}</b>{rf.from} → {rf.to}<span className="psky-rf-why"> · {rf.dir === "down" ? rf.cause : "upgrade suggested"}</span>
                </span>
              )}
              {pulse && <i key={pulse} className="psky-pulse" data-rf={rf?.dir} aria-hidden />}
              {pulse && rf?.dir === "down" && <i key={`${pulse}:2`} className="psky-pulse psky-pulse-2" data-rf="down" aria-hidden />}
              {blocked && <span className="psky-blocked" title="Brand fit fails: approval blocked" aria-label="blocked by brand fit" />}
              <span className="psky-num">{Math.round(t.score)}</span>
              {delta !== 0 && Math.abs(delta) >= 1 && <span className="psky-delta">{delta > 0 ? "+" : "−"}{Math.abs(Math.round(delta))}</span>}
              {move ? <span className="psky-prop" data-rf={move} aria-label={move === "up" ? "AI band rose since JAN" : "AI band fell since JAN"}>{move === "up" ? "▲" : "▼"}</span>
                : proposal && <span className="psky-prop" aria-label={`AI proposes ${proposal}`}>{proposal === "Must" || (proposal === "Should" && band === "Could") ? "▲" : "▼"}</span>}
              {pm && <span className="psky-pm" aria-label={`PM confirmed ${pm}`}>{pm[0]} ✓</span>}
              {challenge && (
                <span className="psky-chal" aria-label={`AI proposes ${challenge.band}, ${challenge.cause}`}>
                  <b>!</b>AI: {challenge.band} {BAND_RANK[challenge.band] < BAND_RANK[challenge.from] ? "▲" : "▼"} · {challenge.cause}
                </span>
              )}
            </div>
          </Html>
        )}
      </group>
    </group>
  );
});

/* ------------------------------------------------------------------------------------------- label collisions */
type Register = (key: string, prio: number) => (el: HTMLElement | null) => void;
function useCollisions(): Register {
  const labels = useRef(new Map<string, { el: HTMLElement; prio: number }>());
  const tick = useRef(0);
  const register = useCallback<Register>((key, prio) => (el) => {
    if (el) labels.current.set(key, { el, prio }); else labels.current.delete(key);
  }, []);
  useFrame(() => {
    if (tick.current++ % 6) return;
    const placed: DOMRect[] = [];
    for (const { el, prio } of [...labels.current.values()].sort((a, b) => b.prio - a.prio)) {
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const hit = prio < 1e9 && placed.some((q) => r.left < q.right + 2 && r.right > q.left - 2 && r.top < q.bottom + 1 && r.bottom > q.top - 1);
      el.toggleAttribute("data-collide", hit);
      if (!hit) placed.push(r);
    }
  });
  return register;
}

/* ------------------------------------------------------------------------------------------- camera */
// An elevated three-quarter view of the whole ring, centred on screen; opening a priority or the panel leaves it
// where it is. The nav pad's Reset re-plans the same flight.

function useSkylineCamera(active: boolean, reduced: boolean, nav?: MutableRefObject<NavInput>) {
  const controls = useThree((s) => s.controls) as unknown as Orbit | null;
  const camera = useThree((s) => s.camera);
  const aspect = useThree((s) => s.size.width / Math.max(1, s.size.height));
  const flight = useRef<{ t0: number; fromP: THREE.Vector3; fromT: THREE.Vector3; toP: THREE.Vector3; toT: THREE.Vector3; dur: number } | null>(null);
  const lastReset = useRef(nav?.current.reset ?? 0);
  const plan = useCallback((dur = 1.6) => {
    if (!controls) return;
    const pull = aspect < 1.3 ? Math.min(2.2, Math.pow(1.3 / aspect, 0.9)) : 1;
    const tgt = new THREE.Vector3(0, 0.35, 0);
    const dir = new THREE.Vector3(0.6, 0.72, -0.72).normalize();
    const p = tgt.clone().add(dir.multiplyScalar(10.2 * pull));
    flight.current = { t0: -1, fromP: camera.position.clone(), fromT: controls.target.clone(), toP: p, toT: tgt, dur: reduced ? 0 : dur };
  }, [controls, camera, aspect, reduced]);
  useEffect(() => {
    if (!active) { flight.current = null; return; }
    plan();
  }, [active, plan]);
  useFrame(({ clock }) => {
    if (nav && nav.current.reset !== lastReset.current) { lastReset.current = nav.current.reset; if (active) plan(); }
    const f = flight.current;
    if (!f || !controls) return;
    if (f.t0 < 0) f.t0 = clock.elapsedTime;
    const p = f.dur ? Math.min(1, (clock.elapsedTime - f.t0) / f.dur) : 1;
    glide(f.fromP, f.fromT, f.toP, f.toT, easeOut(p), camera.position, controls.target);
    controls.update();
    if (p >= 1) flight.current = null;
  });
}
