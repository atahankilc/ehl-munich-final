// Page 3's stages in the shared canvas, continuing the Evidence → Structure morph as one object story:
// drafted: arriving from page 2, the requirement-area diamonds rise from their Structure ring (exact page-2 spots)
//        towards a plane above the volume, which sinks away below them; still rising, each diamond swells and bursts
//        into its requirements (domain hue, track-state mark) in a sweep around the ring, and they settle into one
//        group per vehicle domain; emptied diamonds fade;
// specified: every requirement shows its recommended target, "?" where a gap is open;
// linked: the couplings run as arcs between the requirements on the plane;
// car: today's car rises (DefinitionLayer) and every requirement flies down to its zone, where the pins take over.
// Arriving, the funnel runs through the stages to the car with every move at double speed (view.fast); stepping back
// by hand then peels the layers off one at a time at full length.
// Every move is a scalar that runs toward its goal, so stepping back plays the same move in reverse; leaving for
// page 2 folds the requirements back into their diamonds, which then sink into the ring.
import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import * as THREE from "three";
import type { NavInput } from "../scan/navigate";
import { api } from "@/lib/api";
import { useCheckpoint } from "@/state/checkpoint";
import type { AreaNode, StructurePayload } from "@/lib/types";
import type { DefinitionPayload, DefLink, Requirement } from "@/lib/definition";
import { zoneToWorld, type CarFrame, type Vec3 } from "@/three/frame";
import { AREA_Y, areaLayout } from "../structure/StructureLayer";
import { domainColor, fmtLevel, isDashed, linkVerdict, rowFor } from "./data";
import { select, setView, useView } from "./store";
import { defAtLeast, type DefStage } from "./stages";

export const RISE_DY = 0.85;                         // how far the diamonds rise above their Structure ring
export const PLANE_Y = AREA_Y + RISE_DY;
const RC = 1.3, SPACING = 0.062;                     // domain groups: ring radius, phyllotaxis step
const RISE_S = 1.2, SPLIT_S = 2.0, SPLIT_AT = 0.62, SWEEP = 0.35, LINK_S = 0.6, FLY_S = 1.3, FLY_DELAY = 0.25;
const INK = "#f2f4f7";

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const smooth = (a: number, b: number, x: number) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeIO = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const toward = (v: number, goal: number, step: number) => (goal > v ? Math.min(goal, v + step) : Math.max(goal, v - step));
const hash = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return Math.abs(h); };
const AREA_COLOR = (a: AreaNode) => (a.kind === "quality" ? "#f5a524" : a.kind === "keep" ? "#eef1f5" : a.kind === "emerging" ? "#d95926" : "#3987e5");

/** One scalar per move; the stage sets the goals. rise: diamonds up · split: diamonds → domain groups ·
 *  link: arcs on the plane · fly: groups → car zones. */
export interface StageAnim { rise: number; split: number; link: number; fly: number; flyWait: number }
/** A diamond's own share of the split: the bursts sweep around the ring (lag 0..SWEEP), each runs over 1 − SWEEP. */
const localSplit = (split: number, lag: number) => clamp01((split - lag) / (1 - SWEEP));

type Orbit = { target: THREE.Vector3; update: () => void };

/* ------------------------------------------------------------------------------------------- label collisions */
type Register = (key: string, prio: number) => (el: HTMLElement | null) => void;
const LabelCtx = createContext<Register>(() => () => {});
const FOCUS = 1e9;
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
      const hit = prio < FOCUS && placed.some((q) => r.left < q.right + 3 && r.right > q.left - 3 && r.top < q.bottom + 2 && r.bottom > q.top - 2);
      el.toggleAttribute("data-collide", hit);
      if (!hit) placed.push(r);
    }
  });
  return register;
}

/* ------------------------------------------------------------------------------------------- layer */
interface Props {
  active: boolean;                       // page 3 is showing
  data: DefinitionPayload;
  reqs: Requirement[];                   // on the chosen car line
  line: string;
  frame: CarFrame;
  carScale: number;
  spread: number;                        // the scan's layout scale (the diamonds start where page 2 drew them)
  nav?: MutableRefObject<NavInput>;      // the nav pad: its Reset re-plans this page's plane view
  anim: MutableRefObject<StageAnim>;
  onLanded: (landed: boolean) => void;
  reduced: boolean;
}

interface NodeP { r: Requirement; d: number; burst: Vec3; slot: Vec3; zone: Vec3 | null }

export function StageLayer(p: Props) {
  const stage = useView((s) => s.stage);
  const fast = useView((s) => s.fast);
  const selected = useView((s) => s.selected);
  const hover = useView((s) => s.hover);
  const hoverDomain = useView((s) => s.hoverDomain);
  const domains = useView((s) => s.domains);
  const linkMode = useView((s) => s.links);
  const bundle = useView((s) => s.bundle);
  const pendingLinks = useView((s) => s.pendingLinks);
  const { cp } = useCheckpoint();
  const sq = useQuery({ queryKey: ["structure", cp], queryFn: () => api.get<StructurePayload>(`/api/structure?cp=${cp}`),
                        staleTime: 30_000, placeholderData: (prev) => prev });
  const st = sq.data?.ready ? sq.data : null;

  /* the diamonds: page-2 ring (× spread, as the universe draws it) → the plane, straight up */
  const diamonds = useMemo(() => {
    if (!st) return [];
    const themeOf = Object.fromEntries(st.themes.map((t) => [t.key, t]));
    return areaLayout(st, themeOf).map(({ a, at }) => {
      const turn = (Math.atan2(at[2], at[0]) / (Math.PI * 2) + 1.25) % 1;   // from the back of the ring, clockwise
      return { a, ring: [at[0] * p.spread, at[1] * p.spread, at[2] * p.spread] as Vec3, plane: [at[0], at[1] + RISE_DY, at[2]] as Vec3,
               lag: turn * SWEEP };
    });
  }, [st, p.spread]);
  const areaIdx = useMemo(() => new Map(diamonds.map((d, i) => [d.a.key, i])), [diamonds]);

  /* domain groups on a ring at plane height, one phyllotaxis disc each, in the payload's domain order */
  const groups = useMemo(() => {
    const order = [...p.data.domains.map((d) => d.key), ...new Set(p.reqs.map((r) => r.domain))].filter((k, i, xs) => xs.indexOf(k) === i);
    const present = order.filter((k) => p.reqs.some((r) => r.domain === k));
    const n = present.length || 1;
    return present.map((key, i) => {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2 + Math.PI / n;
      const c: Vec3 = [RC * Math.cos(ang), PLANE_Y, RC * Math.sin(ang)];
      const members = p.reqs.filter((r) => r.domain === key);
      const rad = SPACING * Math.sqrt(members.length);
      return { key, label: p.data.domains.find((d) => d.key === key)?.label ?? key, c, ang, members,
               labelAt: [c[0], PLANE_Y, c[2] - rad - 0.12] as Vec3 };   // just behind the disc: above it on screen
    });
  }, [p.data.domains, p.reqs]);

  /* one node per requirement: its diamond, a burst offset out of it, its slot in the domain group, its car zone */
  const nodes = useMemo<NodeP[]>(() => {
    const byArea = new Map<number, Requirement[]>();
    const dOf = (r: Requirement) => areaIdx.get(r.area_key) ?? (diamonds.length ? hash(r.area_key) % diamonds.length : -1);
    for (const r of p.reqs) { const d = dOf(r); byArea.set(d, [...(byArea.get(d) ?? []), r]); }
    const slot = new Map<string, Vec3>();
    for (const g of groups) {
      const ms = [...g.members].sort((a, b) => dOf(a) - dOf(b) || a.title.localeCompare(b.title));   // siblings stay close
      ms.forEach((r, m) => {
        const rr = SPACING * Math.sqrt(m + 0.5), th = m * 2.39996 + g.ang;
        slot.set(r.key, [g.c[0] + rr * Math.cos(th), PLANE_Y, g.c[2] + rr * Math.sin(th)]);
      });
    }
    const out: NodeP[] = [];
    for (const [d, list] of byArea) {
      const at = d >= 0 ? diamonds[d].plane : ([0, PLANE_Y, 0] as Vec3);
      const a0 = Math.atan2(at[2], at[0]);
      list.forEach((r, j) => {
        const ang = a0 + (list.length > 1 ? (j / (list.length - 1) - 0.5) * 1.6 : 0);
        const z = r.zones.find((k) => p.data.zones[k]);
        const zw = z ? zoneToWorld(p.data.zones[z].pos, p.frame).map((v) => v * p.carScale) as Vec3 : null;
        out.push({ r, d, burst: [Math.cos(ang) * 0.15, 0.09, Math.sin(ang) * 0.15], slot: slot.get(r.key) ?? at, zone: zw });
      });
    }
    return out;
  }, [p.reqs, p.data.zones, p.frame, p.carScale, groups, diamonds, areaIdx]);

  /* the moves */
  useEffect(() => { if (stage === "car") p.anim.current.flyWait = p.reduced ? 0 : FLY_DELAY; }, [stage, p.reduced, p.anim]);
  // whatever was under the pointer moves away with the stage change
  useEffect(() => { setView({ hover: null, hoverPos: null, hoverArea: null, hoverDomain: null }); }, [stage]);
  const landed = useRef(false);
  const dGroups = useRef<(THREE.Group | null)[]>([]);
  const dMats = useRef<(THREE.MeshBasicMaterial | null)[]>([]);
  const dLabels = useRef<(HTMLElement | null)[]>([]);
  const nGroups = useRef<(THREE.Group | null)[]>([]);
  const nEls = useRef<(HTMLElement | null)[]>([]);
  const gLabels = useRef<(HTMLElement | null)[]>([]);
  const arcsRef = useRef<THREE.Group>(null);
  const v = useMemo(() => ({ a: new THREE.Vector3(), b: new THREE.Vector3(), c: new THREE.Vector3(), m: new THREE.Vector3(), q: new THREE.QuadraticBezierCurve3() }), []);
  useFrame((_, dt) => {
    const a = p.anim.current;
    const k = (dur: number) => (p.reduced ? 1 : (dt * (fast ? 2 : 1)) / dur);
    // leaving from the car the requirements just go; from the plane they fold back into their diamonds first
    if (!p.active && a.fly > 0) { a.split = 0; a.link = 0; a.fly = 0; }
    if (p.active || a.split <= 0) a.rise = toward(a.rise, p.active ? 1 : 0, k(RISE_S));
    // forward in order (rise → split → link / fly), backward in reverse (fly → link → split)
    const gSplit = p.active && defAtLeast(stage, "drafted") ? 1 : 0;
    const gLink = p.active && stage === "linked" ? 1 : 0;
    const gFly = p.active && stage === "car" ? 1 : 0;
    if (a.fly > gFly) a.fly = toward(a.fly, 0, k(FLY_S));
    else if (a.link > gLink) a.link = toward(a.link, 0, k(0.35));
    else if (a.split > gSplit) a.split = toward(a.split, 0, k(SPLIT_S * (p.active ? 1 : 0.4)));
    else if (a.rise >= SPLIT_AT && a.split < gSplit) a.split = toward(a.split, 1, k(SPLIT_S));
    else if (a.split >= 1 && a.link < gLink) a.link = toward(a.link, 1, k(LINK_S));
    else if (a.split >= 1 && a.fly < gFly) { if (a.flyWait > 0) a.flyWait -= dt; else a.fly = toward(a.fly, 1, k(FLY_S)); }
    const isLanded = a.fly >= 1;
    if (isLanded !== landed.current) { landed.current = isLanded; p.onLanded(isLanded); }

    const eR = easeIO(a.rise);
    const leaving = p.active ? 1 : smooth(0, 0.3, a.rise);            // the copies hand back to page 2's diamonds
    diamonds.forEach((d, i) => {
      const g = dGroups.current[i];
      if (!g) return;
      g.position.set(d.ring[0] + (d.plane[0] - d.ring[0]) * eR, d.ring[1] + (d.plane[1] - d.ring[1]) * eR, d.ring[2] + (d.plane[2] - d.ring[2]) * eR);
      // swell (charge), then burst: the diamond shrinks away as its requirements fly out of it
      const ls = localSplit(a.split, d.lag);
      const dShow = 1 - smooth(0.12, 0.4, ls);
      const swell = 1 + 0.7 * smooth(0, 0.12, ls) * dShow;
      const s = dShow * leaving;
      g.visible = s > 0.01;
      g.scale.setScalar(Math.max(0.001, (0.35 + 0.65 * s) * swell));
      const m = dMats.current[i];
      if (m) m.opacity = Math.min(1, 0.9 * s + 0.1 * (swell - 1) / 0.7);
      const el = dLabels.current[i];
      if (el) { const o = p.active ? 1 - smooth(0, 0.15, ls) : 0; el.style.opacity = o.toFixed(3); el.style.display = o > 0.02 ? "" : "none"; }
    });

    const gShow = smooth(0.6, 1, a.split) * (1 - smooth(0, 0.3, a.fly));
    groups.forEach((_, i) => {
      const el = gLabels.current[i];
      if (el) { el.style.opacity = gShow.toFixed(3); el.style.display = gShow > 0.02 ? "" : "none"; }
    });
    if (arcsRef.current) arcsRef.current.visible = a.link > 0.005;

    nodes.forEach((n, i) => {
      const g = nGroups.current[i], el = nEls.current[i];
      if (!g || !el) return;
      const sp = n.d >= 0 && diamonds[n.d] ? localSplit(a.split, diamonds[n.d].lag) : a.split;
      const show = sp > 0.12 && a.fly < 1;                            // out of the diamond once it has swelled
      el.style.display = show ? "" : "none";
      if (!show) return;
      const ns = (sp - 0.12) / 0.88;                                  // this node's own split, 0..1
      const dp = n.d >= 0 ? dGroups.current[n.d]?.position : null;
      v.a.set(...(dp ? [dp.x, dp.y, dp.z] as Vec3 : n.slot));
      v.b.copy(v.a).add(v.c.set(...n.burst));
      let scale = 1;
      if (ns < 0.3) { const t = easeOut(ns / 0.3); v.m.lerpVectors(v.a, v.b, t); scale = 0.3 + 0.7 * t; }
      else {
        const t = easeIO((ns - 0.3) / 0.7);
        v.c.set(...n.slot);
        v.q.v0.copy(v.b); v.q.v2.copy(v.c); v.q.v1.lerpVectors(v.b, v.c, 0.5); v.q.v1.y += 0.22;
        v.q.getPoint(t, v.m);
      }
      if (a.fly > 0 && n.zone) {
        const t = easeIO(a.fly);
        v.q.v0.set(...n.slot); v.q.v2.set(...n.zone); v.q.v1.lerpVectors(v.q.v0, v.q.v2, 0.5); v.q.v1.y = Math.max(v.q.v0.y, v.q.v2.y) + 0.35;
        v.q.getPoint(t, v.m);
      }
      g.position.copy(v.m);
      el.style.setProperty("--s", scale.toFixed(3));
      el.style.setProperty("--v", (1 - smooth(0.05, 0.4, a.fly)).toFixed(3));   // targets fold away in flight
    });
  });

  useLandedReset(p.active, landed, p.onLanded);
  usePlaneFlight(p.active && stage !== "car", p.reduced, p.nav);

  /* links between requirements on this line, drawn on the plane between their slots */
  const slotOf = useMemo(() => new Map(nodes.map((n) => [n.r.key, n.slot])), [nodes]);
  const bundleKeys = useMemo(() => new Set(p.data.bundles.find((b) => b.id === bundle)?.keys ?? []), [p.data.bundles, bundle]);
  const passes = useCallback((r: Requirement) => !domains.length || domains.includes(r.domain), [domains]);
  const byKey = useMemo(() => new Map(p.reqs.map((r) => [r.key, r])), [p.reqs]);
  const arcs = useMemo(() => {
    const out: { l: DefLink; a: Vec3; b: Vec3; level: "hot" | "warm" | "faint" }[] = [];
    for (const l of p.data.links) {
      const a = slotOf.get(l.a), b = slotOf.get(l.b);
      if (!a || !b) continue;
      const mine = !!selected && (l.a === selected || l.b === selected);
      if (linkVerdict(l) === "removed" && !mine) continue;
      const inBundle = bundleKeys.size > 0 && bundleKeys.has(l.a) && bundleKeys.has(l.b) && l.strength >= 2;
      const hovered = !!hover && (l.a === hover || l.b === hover);
      let level: "hot" | "warm" | "faint" | null;
      if (mine || inBundle) level = "hot";
      else if (hovered) level = "warm";
      else if (selected || bundleKeys.size || linkMode === "off" || (linkMode === "strong" && l.strength < 2)) level = null;
      else level = passes(byKey.get(l.a)!) && passes(byKey.get(l.b)!) ? "faint" : null;
      if (level) out.push({ l, a, b, level });
    }
    return out;
  }, [p.data.links, slotOf, selected, hover, bundleKeys, linkMode, passes, byKey, pendingLinks]);   // eslint-disable-line react-hooks/exhaustive-deps

  const linked = useMemo(() => {
    if (!selected) return null;
    const s = new Set<string>([selected]);
    for (const l of p.data.links) if (linkVerdict(l) !== "removed") { if (l.a === selected) s.add(l.b); if (l.b === selected) s.add(l.a); }
    return s;
  }, [selected, p.data.links, pendingLinks]);   // eslint-disable-line react-hooks/exhaustive-deps
  const hoverArea = hover ? byKey.get(hover)?.area_key ?? null : null;
  const register = useCollisions();
  const spec = defAtLeast(stage, "specified");

  return (
    <LabelCtx.Provider value={register}>
      {diamonds.map((d, i) => (
        <group key={d.a.key} ref={(g) => { dGroups.current[i] = g; }} position={d.ring}>
          <StageDiamond a={d.a} children_={p.reqs.filter((r) => r.area_key === d.a.key).length}
                        matRef={(m) => { dMats.current[i] = m; }} labelRef={(el) => { dLabels.current[i] = el; }} />
        </group>
      ))}
      {groups.map((g, i) => (
        <Html key={g.key} position={g.labelAt} center zIndexRange={[13, 11]}>
          <button type="button" className="dgroup" ref={(el) => { gLabels.current[i] = el; register(`g:${g.key}`, FOCUS)(el); }}
                  style={{ ["--c" as string]: domainColor(g.key), display: "none" }}
                  data-on={domains.includes(g.key) ? "" : undefined}
                  onPointerEnter={() => setView({ hoverDomain: g.key })} onPointerLeave={() => setView({ hoverDomain: null })}
                  onClick={(e) => { e.stopPropagation(); setView((s) => ({ domains: s.domains.includes(g.key) ? s.domains.filter((x) => x !== g.key) : [...s.domains, g.key] })); }}>
            <i aria-hidden />{g.label}<b>{g.members.length}</b>
          </button>
        </Html>
      ))}
      <group ref={arcsRef} visible={false}>
        {arcs.map((x) => <PlaneArc key={String(x.l.id)} {...x} anim={p.anim} label={x.level === "hot" && stage === "linked"} />)}
      </group>
      {nodes.map((n, i) => {
        const r = n.r;
        const dim = !passes(r) ? "off" : linked && !linked.has(r.key) ? "dim" : bundleKeys.size && !bundleKeys.has(r.key) ? "dim"
          : hoverDomain && r.domain !== hoverDomain ? "dim" : undefined;
        return (
          <group key={r.key} ref={(g) => { nGroups.current[i] = g; }}>
            <Html center zIndexRange={[14, 12]}>
              <StageNode r={r} line={p.line} spec={spec} elRef={(el) => { nEls.current[i] = el; }} register={register}
                         on={selected === r.key} isLinked={!!linked?.has(r.key) && selected !== r.key}
                         sib={!!hoverArea && hover !== r.key && r.area_key === hoverArea} hot={hoverDomain === r.domain} dim={dim} />
            </Html>
          </group>
        );
      })}
    </LabelCtx.Provider>
  );
}

/** A stage change back from the car must hide the pins at once, before the next frame runs. */
function useLandedReset(active: boolean, landed: MutableRefObject<boolean>, onLanded: (l: boolean) => void) {
  const stage = useView((s) => s.stage);
  useEffect(() => {
    if ((!active || stage !== "car") && landed.current) { landed.current = false; onLanded(false); }
  }, [active, stage, landed, onLanded]);
}

/* ------------------------------------------------------------------------------------------- camera */
const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _q = new THREE.Quaternion(), _q0 = new THREE.Quaternion();
/** One camera glide: the orbit centre moves straight, the view direction turns (slerp) and the distance eases, so the
 *  camera swings around what it looks at instead of cutting through it (a straight line can pass through the plane or
 *  the car when the two views face different ways). */
export function glide(fromP: THREE.Vector3, fromT: THREE.Vector3, toP: THREE.Vector3, toT: THREE.Vector3, e: number,
                      outP: THREE.Vector3, outT: THREE.Vector3) {
  outT.lerpVectors(fromT, toT, e);
  _a.subVectors(fromP, fromT); _b.subVectors(toP, toT);
  const d = _a.length() + (_b.length() - _a.length()) * e;
  _q.setFromUnitVectors(_a.normalize(), _b.normalize());
  _q0.identity().slerp(_q, e);
  outP.copy(_a).applyQuaternion(_q0).multiplyScalar(d).add(outT);
}

// On arrival (and when stepping back from the car) the camera glides up to look down on the plane; it is never
// moved between plane stages, so the PM's own orbit stays put while stepping.
function usePlaneFlight(on: boolean, reduced: boolean, nav?: MutableRefObject<NavInput>) {
  const controls = useThree((s) => s.controls) as unknown as Orbit | null;
  const camera = useThree((s) => s.camera);
  const aspect = useThree((s) => s.size.width / Math.max(1, s.size.height));
  const flight = useRef<{ t0: number; fromP: THREE.Vector3; fromT: THREE.Vector3; toP: THREE.Vector3; toT: THREE.Vector3; dur: number } | null>(null);
  const lastReset = useRef(nav?.current.reset ?? 0);
  const plan = () => {
    if (!controls) return;
    const pull = aspect < 1.25 ? Math.min(2.1, Math.pow(1.25 / aspect, 0.85)) : 1;
    const t = new THREE.Vector3(0, PLANE_Y + 0.15, 0);   // centred on the screen, like pages 1 and 2
    const p = new THREE.Vector3(0, 0.7, 0.72).normalize().multiplyScalar(4.5 * pull).add(t);
    flight.current = { t0: -1, fromP: camera.position.clone(), fromT: controls.target.clone(), toP: p, toT: t, dur: reduced ? 0 : 1.4 };
  };
  useEffect(() => {
    if (!on || !controls) { flight.current = null; return; }
    plan();
  }, [on, controls, camera, aspect, reduced]); // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(({ clock }) => {
    if (nav && nav.current.reset !== lastReset.current) { lastReset.current = nav.current.reset; if (on) plan(); }
    const f = flight.current;
    if (!f || !controls) return;
    if (f.t0 < 0) f.t0 = clock.elapsedTime;
    const k = f.dur ? Math.min(1, (clock.elapsedTime - f.t0) / f.dur) : 1;
    const e = easeIO(k);
    glide(f.fromP, f.fromT, f.toP, f.toT, e, camera.position, controls.target);
    controls.update();
    if (k >= 1) flight.current = null;
  });
}

/* ------------------------------------------------------------------------------------------- diamond */
// Page 2's diamond (same colour, size and spin), with its label; hovering names how many requirements it became.
function StageDiamond({ a, children_, matRef, labelRef }: {
  a: AreaNode; children_: number; matRef: (m: THREE.MeshBasicMaterial | null) => void; labelRef: (el: HTMLElement | null) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const register = useContext(LabelCtx);
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.y += dt * 0.4; });
  const size = 0.028 + Math.min(0.03, Math.sqrt(a.metrics.comments ?? 1) * 0.0012);
  const quality = a.kind === "quality";
  return (
    <>
      <mesh ref={ref}
            onPointerMove={(e) => { e.stopPropagation(); setView({ hoverArea: a.key, hoverPos: { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY } }); }}
            onPointerOut={() => setView({ hoverArea: null, hoverPos: null })}>
        <octahedronGeometry args={[size, 0]} />
        <meshBasicMaterial ref={matRef} color={AREA_COLOR(a)} wireframe={a.state === "new" || quality} transparent opacity={0.9} depthWrite={false} />
      </mesh>
      {(a.metrics.comments ?? 0) > 0 && (
        <Html position={[0, size + 0.05, 0]} center zIndexRange={[12, 0]}>
          <div className="dstage-area" ref={(el) => { labelRef(el); register(`a:${a.key}`, 1e6 + (a.metrics.comments ?? 0))(el); }}>
            {a.title}{children_ > 0 && <b>{children_}</b>}
          </div>
        </Html>
      )}
    </>
  );
}

/* ------------------------------------------------------------------------------------------- requirement node */
// (drei <Html> renders into its own React root, so the collision register comes in as a prop, not from context)
const StageNode = memo(function StageNode({ r, line, spec, elRef, register, on, isLinked, sib, hot, dim }: {
  r: Requirement; line: string; spec: boolean; elRef: (el: HTMLElement | null) => void; register: Register;
  on: boolean; isLinked: boolean; sib: boolean; hot: boolean; dim: string | undefined;
}) {
  const row = rowFor(r, line);
  const lvl = row ? row[row.recommended] : null;
  const gap = r.gaps.length > 0 || !!row && [row.baseline, row.threshold, row.target, row.stretch].some((l) => l?.basis === "gap");
  const dir = r.metric?.direction;
  // compact: a long unit ("mean points on a 7-point scale") stays in the inspector, the plane shows the number
  const unit = r.metric?.unit && r.metric.unit.length <= 6 ? r.metric.unit : undefined;
  const val = !lvl || lvl.basis === "gap" ? null
    : dir === "binary" ? "yes" : lvl.value == null ? null : `${dir === "lower" ? "≤ " : dir === "higher" ? "≥ " : ""}${fmtLevel(lvl.value, unit)}`;
  return (
    <div className="dnode" ref={elRef} style={{ display: "none" }}>
      <button type="button" className="dpin" data-state={r.state ?? "held"} data-on={on ? "" : undefined}
              data-linked={isLinked || sib || hot ? "" : undefined} data-dim={dim} style={{ ["--c" as string]: domainColor(r.domain) }}
              aria-label={r.title} aria-pressed={on}
              onPointerEnter={(e) => setView({ hover: r.key, hoverPos: { x: e.clientX, y: e.clientY } })}
              onPointerMove={(e) => setView({ hoverPos: { x: e.clientX, y: e.clientY } })}
              onPointerLeave={() => setView({ hover: null, hoverPos: null })}
              onClick={(e) => { e.stopPropagation(); select(on ? null : r.key); }}>
        <i aria-hidden />
      </button>
      {spec && (val || gap) && (
        <span className="dnode-val" data-dim={dim} ref={register(`n:${r.key}`, on ? FOCUS : r.evidence_count)}>
          {val}{gap && <b title="Open gap">?</b>}
        </span>
      )}
    </div>
  );
});

/* ------------------------------------------------------------------------------------------- arcs on the plane */
const WIDTH: Record<number, number> = { 1: 1, 2: 1.7, 3: 2.6 };
const OPACITY = { hot: 0.92, warm: 0.6, faint: 0.22 };
function PlaneArc({ l, a, b, level, label, anim }: {
  l: DefLink; a: Vec3; b: Vec3; level: "hot" | "warm" | "faint"; label: boolean; anim: MutableRefObject<StageAnim>;
}) {
  const { pts, apex } = useMemo(() => {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
    const mid = A.clone().lerp(B, 0.5);
    mid.y += 0.1 + A.distanceTo(B) * 0.22;
    const c = new THREE.QuadraticBezierCurve3(A, mid, B);
    return { pts: c.getPoints(40), apex: c.getPoint(0.5) };
  }, [a, b]);
  const ref = useRef<{ material: THREE.Material & { opacity: number } } | null>(null);
  const base = OPACITY[level] * (l.strength >= 3 ? 1 : l.strength === 2 ? 0.9 : 0.75);
  useFrame(() => { const m = ref.current?.material; if (m) m.opacity = base * anim.current.link; });
  const dashed = isDashed(l.relation);
  return (
    <group>
      <Line ref={ref as never} points={pts} color={INK} lineWidth={(WIDTH[l.strength] ?? 1.4) * (level === "hot" ? 1.15 : 1)} transparent opacity={0}
            dashed={dashed} dashSize={0.05} gapSize={0.04} depthWrite={false} renderOrder={level === "hot" ? 6 : 4} />
      {label && (
        <Html position={apex} center zIndexRange={[13, 11]}>
          <div className="dlink-label" data-dashed={dashed ? "" : undefined}>{l.via}</div>
        </Html>
      )}
    </group>
  );
}

export type { DefStage };
