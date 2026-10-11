// The scan volume (react-three-fiber). One shader decides, per contact, whether the current sweep has acquired it.
// Each raw data type has its own colour (TYPE_COLOR); track state is the mark's shape: held contacts (known at the
// earlier checkpoint) are dots, contacts this sweep acquired are rings. The flare as the sweep passes, hover and the
// lock reticle turn white; blue is the sweep blade itself.
// The same rule drives the comments and the dated research on the time ring. Every ring element can be opened.
// Opening one focuses its layer (the cluster or one ring): that layer rises, the others sink and fade out of the way.
import { useEffect, useMemo, useRef, type MutableRefObject, type ReactNode } from "react";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Billboard, Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { PointsPayload, ResearchItem, Selection, SourcesPayload, StructurePayload } from "@/lib/types";
import { StructureLayer } from "../structure/StructureLayer";
import { ClassifyPulse } from "../structure/ClassifyPulse";
import { VolumeSink } from "../definition/VolumeSink";
import { passOption, passResearch, passSales, passStudy, type Filter } from "./filter";
import type { Stage } from "../structure/stages";
import { Navigator, SpreadCtx, spreadOf, useSpread, type NavInput } from "./navigate";
import { CARS, CAR_NAME, LINES, LINE_CODES, MARKET_NAME, R, SWEEP_START, TAU, TIME_START, lineSector, optionLayout, polar, sector, studyLayout, timeAngle } from "./layout";

const VERT = /* glsl */ `
attribute float aCp; attribute float aSel; attribute float aAz; attribute float aSize; attribute float aIdx;
attribute vec3 aTarget; attribute float aClustered;
uniform float uCp, uFrom, uSweep, uStart, uScale, uHover, uDim, uMorph, uGrow, uDepth;
varying float vAlpha; varying float vRing; varying float vFlare; varying float vHov;
const float TAU = 6.2831853;
void main() {
  float lo = min(uCp, uFrom), hi = max(uCp, uFrom);
  float d = mod(aAz - uStart + 2.0 * TAU, TAU) / TAU;
  float passed = step(d, uSweep);
  float vis = aCp <= lo ? 1.0 : (aCp <= hi ? (uCp > uFrom ? passed : 1.0 - passed) : 0.0);
  vFlare = (uCp > uFrom && aCp > lo && aCp <= hi) ? passed * exp(-max(uSweep - d, 0.0) * 14.0) * (1.0 - pow(uSweep, 12.0)) : 0.0;
  vRing = abs(aCp - uCp) < 0.5 ? 1.0 : 0.0;          // acquired by the current sweep
  vHov = abs(aIdx - uHover) < 0.5 ? 1.0 : 0.0;
  vec3 pp = mix(position, aTarget, uMorph);            // page 2: comments fly into their cluster
  vec4 mv = modelViewMatrix * vec4(pp, 1.0);
  float depth = smoothstep(3.2 * uDepth, 7.5 * uDepth, -mv.z);  // far contacts recede (scaled with the spread)
  vAlpha = vis * mix(uDim, 1.0, aSel) * mix(0.95, 0.4, depth) * mix(1.0, mix(0.08, 0.4, aClustered), uMorph);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = aSize * uScale * uGrow * (1.0 + vRing * 0.25 + vFlare * 2.0 + vHov * 2.2) / -mv.z;
}`;
const FRAG = /* glsl */ `
uniform vec3 uColor; uniform float uFade;
varying float vAlpha; varying float vRing; varying float vFlare; varying float vHov;
void main() {
  float r = length(gl_PointCoord - 0.5);
  if (r > 0.5) discard;
  float dot = smoothstep(0.5, 0.3, r);
  float ring = smoothstep(0.5, 0.42, r) * smoothstep(0.24, 0.32, r);
  float a = mix(dot, ring, vRing * (1.0 - vFlare));
  vec3 col = mix(uColor, vec3(1.0), max(vFlare, vHov));
  gl_FragColor = vec4(col, min(1.0, vAlpha + vHov) * a * uFade);
}`;

import { TYPE_COLOR } from "./colors";
export { TYPE_COLOR };

function contactMaterial(scale: number, color: string) {
  return new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
    uniforms: {
      uCp: { value: 2 }, uFrom: { value: 2 }, uSweep: { value: 1 }, uStart: { value: SWEEP_START },
      uScale: { value: scale }, uHover: { value: -1 }, uDim: { value: 0.06 }, uFade: { value: 1 }, uMorph: { value: 0 }, uGrow: { value: 1 }, uDepth: { value: 1 },
      uColor: { value: new THREE.Color(color) },
    },
  });
}

function attrGeometry(pos: Float32Array, attrs: Record<string, Float32Array>) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  for (const [k, v] of Object.entries(attrs)) g.setAttribute(k, new THREE.BufferAttribute(v, 1));
  g.computeBoundingSphere();
  return g;
}

/* ------------------------------------------------------------------------------------------- focus layers */
// One layer per raw data type: the comment cluster and the four rings. Public research sits on its car's ring.
export type LayerId = "comment" | "research" | "study" | "option" | "sales";
export const layerOf = (s: Selection): LayerId | null =>
  s.kind === "cluster" || s.kind === "theme" || s.kind === "area" ? null
    : s.kind !== "research" ? s.kind : s.item.ring === "options" ? "option" : (s.item.ring ?? "research");

const LIFT = 0.12, SINK = -0.5, FADE = 0.08;
const ORDER: LayerId[] = ["comment", "research", "study", "option", "sales"]; // inside out
const RISE = 0.85, FALL = 0.7, STAGGER = 0.07;                                 // seconds
const easeOutBack = (t: number) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2);
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

// Focus choreography: the chosen layer springs up (slight overshoot) with a soft scale pulse; the others sink and
// fade in a ripple outward from it. Releasing focus ripples back the same way. Under reduced motion the layers still
// glide (the move is what shows which layer the item belongs to), just without overshoot, pulse or ripple.
function Layer({ id, focus, children }: { id: LayerId; focus: LayerId | null; children: ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const st = useRef({ y: 0, a: 1, fy: 0, fa: 1, t0: -1, delay: 0, rising: false, focus: null as LayerId | null });
  const reduced = useMemo(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false, []);
  useFrame(({ clock }) => {
    const g = ref.current;
    if (!g) return;
    const s = st.current, now = clock.elapsedTime;
    if (s.focus !== focus) {                 // new target: start a tween from wherever the layer is now
      const anchor = focus ?? s.focus;       // ripple out from the layer gaining (or losing) focus
      s.focus = focus;
      s.fy = s.y; s.fa = s.a; s.t0 = now; s.rising = focus === id;
      s.delay = reduced || anchor == null || s.rising ? 0 : Math.abs(ORDER.indexOf(id) - ORDER.indexOf(anchor)) * STAGGER;
    }
    const [ty, ta] = focus == null ? [0, 1] : focus === id ? [LIFT, 1] : [SINK, FADE];
    let p = 1;
    if (s.t0 >= 0) p = Math.min(1, Math.max(0, (now - s.t0 - s.delay) / (s.rising ? RISE : FALL)));
    if (p >= 1 && s.y === ty && s.a === ta && g.userData.settled === children) return;
    s.y = s.fy + (ty - s.fy) * (s.rising && !reduced ? easeOutBack(p) : easeInOut(p));
    s.a = s.fa + (ta - s.fa) * easeOut(p);
    if (p >= 1) { s.y = ty; s.a = ta; }
    g.position.y = s.y;
    g.scale.setScalar(s.rising && !reduced ? 1 + 0.04 * Math.sin(Math.PI * p) : 1);
    g.userData.settled = children;
    g.traverse((o) => {
      const mat = (o as THREE.Mesh).material;
      if (!mat) return;
      for (const m of Array.isArray(mat) ? mat : [mat]) {
        if (m instanceof THREE.ShaderMaterial) { if (m.uniforms.uFade) m.uniforms.uFade.value = s.a; continue; }
        if (m.userData.written !== m.opacity) m.userData.baseOpacity = m.opacity;   // React set a new opacity (e.g. a filter)
        m.opacity = m.userData.written = m.userData.baseOpacity * s.a;
      }
    });
  });
  return <group ref={ref}>{children}</group>;
}

// A car name moves with the focus too: the selected item's car line rises with its layer, the other names sink and
// (via data-dim) fade. Items without a car (most research) sink every name.
type LabelState = "rest" | "up" | "down";
function LabelLift({ state, children }: { state: LabelState; children: ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const st = useRef({ fy: 0, t0: -1, state: "rest" as LabelState });
  const reduced = useMemo(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false, []);
  useFrame(({ clock }) => {
    const g = ref.current;
    if (!g) return;
    const s = st.current, now = clock.elapsedTime;
    if (s.state !== state) { s.state = state; s.fy = g.position.y; s.t0 = now; }
    if (s.t0 < 0) return;
    const up = state === "up", ty = state === "rest" ? 0 : up ? LIFT : SINK;
    const p = Math.min(1, (now - s.t0) / (up ? RISE : FALL));
    g.position.y = s.fy + (ty - s.fy) * (up && !reduced ? easeOutBack(p) : easeInOut(p));
    if (p >= 1) { g.position.y = ty; s.t0 = -1; }
  });
  return <group ref={ref}>{children}</group>;
}

/* ------------------------------------------------------------------------------------------- sweep clock */
function useSweep(mats: THREE.ShaderMaterial[], position: number, fromPosition: number, sweepId: number, onAngle: (a: number | null) => void) {
  const start = useRef<number | null>(null);
  const reduced = useMemo(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false, []);
  useEffect(() => {
    for (const m of mats) { m.uniforms.uCp.value = position; m.uniforms.uFrom.value = fromPosition; m.uniforms.uSweep.value = reduced ? 1 : 0; }
    start.current = reduced || position === fromPosition ? null : performance.now();
  }, [sweepId]); // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(() => {
    if (start.current == null) { onAngle(null); return; }
    const t = Math.min(1, (performance.now() - start.current) / 2400);
    const e = 1 - Math.pow(1 - t, 3);
    for (const m of mats) m.uniforms.uSweep.value = e;
    onAngle(t < 1 ? SWEEP_START + e * TAU : null);
    if (t >= 1) { start.current = null; for (const m of mats) m.uniforms.uFrom.value = m.uniforms.uCp.value; }
  });
}

/* ------------------------------------------------------------------------------------------- camera fit */
/** Camera distance that frames the whole volume at spread 1. */
function useFit() {
  const { camera, size } = useThree();
  return () => {
    const aspect = size.width / size.height;
    const fit = (R.labels + 0.3) / (Math.tan(THREE.MathUtils.degToRad((camera as THREE.PerspectiveCamera).fov / 2)) * aspect);
    return Math.max(aspect < 1 ? 6 : 5.6, fit);
  };
}
function CameraFit({ fit }: { fit: () => number }) {
  const { camera, size } = useThree();
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    cam.fov = size.width / size.height < 1 ? 58 : 40;
    cam.position.setLength(fit());
    cam.updateProjectionMatrix();
  }, [camera, size.width, size.height]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/* ------------------------------------------------------------------------------------------- scene */
export interface Hover { title: string; sub?: string; comment?: number; acquiredHere?: boolean; x: number; y: number }

interface SceneProps {
  points: PointsPayload;
  sources: SourcesPayload | undefined;
  mask: Uint8Array;
  position: number; fromPosition: number; sweepId: number;
  hoverComment: number | null;
  locked: [number, number, number] | null;
  focus: LayerId | null;
  onHover: (h: Hover | null) => void;
  onSelect: (s: Selection, at: [number, number, number]) => void;
  /** page 2: comments fly into their clusters and the AI's structure appears on top */
  mode?: "scan" | "structure" | "definition" | "prioritize";
  /** page 3: the definition layer (car, pins, link arcs), drawn outside the universe while the volume sinks away */
  extra?: ReactNode;
  structure?: StructurePayload;
  selected?: Selection | null;
  hoverKey?: string | null;
  onStructureHover?: (h: Hover | null, key?: string | null) => void;
  /** source ids the agent just classified (they flash in place) */
  pulse?: number[];
  /** the Key's filter on page 1: what doesn't match dims like a masked comment and can't be picked */
  filter?: Filter | null;
  /** layout scale of the whole universe (navigate.tsx) */
  spread?: number;
  /** page 2: the pipeline stage in view; classify keeps the comments where they are */
  stage?: Stage;
  /** the pad's hold-to-fly buttons and reset */
  nav: MutableRefObject<NavInput>;
}

export const studyValue = (s: { scale: string; value: number | null }) =>
  s.value == null ? "" : s.scale === "dist_7" ? `${Math.round(s.value * 100)}% top-2` : `${s.value.toFixed(1)} / 10`;

export function Scene(p: SceneProps) {
  const { gl } = useThree();
  const dpr = gl.getPixelRatio();
  const commentMat = useMemo(() => contactMaterial(15 * dpr, TYPE_COLOR.comment), [dpr]);
  const researchMat = useMemo(() => contactMaterial(19 * dpr, TYPE_COLOR.research), [dpr]);
  const sweepRef = useRef<THREE.Group>(null);
  const setCursor = (on: boolean) => { gl.domElement.style.cursor = on ? "pointer" : ""; };
  const spread = useMemo(() => spreadOf(p.spread ?? 1), [p.spread]);
  const fit = useFit();

  /* comments */
  const comments = useMemo(() => {
    const c = p.points.cols, n = p.points.n;
    const pos = new Float32Array(n * 3), cp = new Float32Array(n), az = new Float32Array(n), size = new Float32Array(n), idx = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      pos[i * 3] = c.x[i]; pos[i * 3 + 1] = c.y[i] * 0.72; pos[i * 3 + 2] = c.z[i];
      cp[i] = c.cp[i]; az[i] = Math.atan2(c.z[i], c.x[i]); idx[i] = i;
      size[i] = 0.85 + Math.min(0.8, Math.sqrt(c.len[i] / 300));
    }
    return attrGeometry(pos, { aCp: cp, aAz: az, aSize: size, aIdx: idx, aSel: new Float32Array(n).fill(1) });
  }, [p.points]);
  useEffect(() => {
    const a = comments.getAttribute("aSel") as THREE.BufferAttribute;
    for (let i = 0; i < p.mask.length; i++) a.setX(i, p.mask[i]);
    a.needsUpdate = true;
  }, [comments, p.mask]);
  useEffect(() => { commentMat.uniforms.uHover.value = p.hoverComment ?? -1; }, [commentMat, p.hoverComment]);

  /* page 2 morph: each comment's target is its cluster centre (pulled in tight); unclustered comments stay and dim */
  useEffect(() => {
    const n = p.points.n, src = comments.getAttribute("position") as THREE.BufferAttribute;
    const target = new Float32Array(n * 3), clustered = new Float32Array(n);
    const st = p.structure;
    const at = new Map<number, number>();
    if (st?.ready) st.member.ids.forEach((id, i) => at.set(id, st.member.cluster[i]));
    for (let i = 0; i < n; i++) {
      const x = src.getX(i), y = src.getY(i), z = src.getZ(i);
      const ci = at.get(p.points.cols.id[i]);
      const c = ci != null && ci >= 0 ? st!.clusters[ci] : null;
      if (c && !c.tail) {
        target.set([c.x + (x - c.x) * 0.07, c.y + (y - c.y) * 0.07, c.z + (z - c.z) * 0.07], i * 3);
        clustered[i] = 1;
      } else target.set([x, y, z], i * 3);
    }
    comments.setAttribute("aTarget", new THREE.BufferAttribute(target, 3));
    comments.setAttribute("aClustered", new THREE.BufferAttribute(clustered, 1));
  }, [comments, p.points, p.structure]);
  const morph = useRef(0);
  useFrame((_, dt) => {
    const goal = p.mode === "structure" && p.structure?.ready && p.stage !== "classify" ? 1 : 0;
    if (morph.current === goal) return;
    const step = dt / 1.6;
    morph.current = goal > morph.current ? Math.min(goal, morph.current + step) : Math.max(goal, morph.current - step);
    const t = morph.current;
    commentMat.uniforms.uMorph.value = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  });

  /* research on the time ring */
  const research = useMemo(() => {
    const items = (p.sources?.research ?? []).filter((r) => !r.ring);
    const n = items.length;
    const pos = new Float32Array(n * 3), cp = new Float32Array(n), az = new Float32Array(n), size = new Float32Array(n), idx = new Float32Array(n);
    items.forEach((it, i) => {
      const a = timeAngle(it.published_at);
      const lane = (it.id % 7) / 7;
      const [x, , z] = polar(R.time + (lane - 0.5) * 0.1, a);
      pos.set([x, (lane - 0.5) * 0.05, z], i * 3);
      cp[i] = it.new ? 2 : 1; az[i] = a; size[i] = it.tier === "T1" ? 1.5 : 1.1; idx[i] = i;
    });
    return { items, geom: attrGeometry(pos, { aCp: cp, aAz: az, aSize: size, aIdx: idx, aSel: new Float32Array(n).fill(1) }) };
  }, [p.sources]);

  /* public research about one car line, on that car's study / options / sales ring (D-042) */
  const studyMat = useMemo(() => contactMaterial(17 * dpr, TYPE_COLOR.study), [dpr]);
  const optionMat = useMemo(() => contactMaterial(17 * dpr, TYPE_COLOR.option), [dpr]);
  const salesMat = useMemo(() => contactMaterial(17 * dpr, TYPE_COLOR.sales), [dpr]);
  const carRings = useMemo(() => {
    const all = (p.sources?.research ?? []).filter((r) => r.ring);
    const build = (ring: "study" | "options" | "sales", radius: number) => {
      // one entry per (item × car); the 5 Series' China items go to the long-wheelbase G68 part of the sector
      const slots = new Map<string, { it: ResearchItem; car: string }[]>();
      for (const it of all.filter((r) => r.ring === ring)) for (const car of it.cars) {
        const key = car === "G60" && it.region === "CN" ? "G68" : car;
        slots.set(key, [...(slots.get(key) ?? []), { it, car: key }]);
      }
      const items: ResearchItem[] = [], v: number[] = [], cp: number[] = [], az: number[] = [], size: number[] = [], idx: number[] = [];
      const sticks: { i: number; seg: number[] }[] = [];
      for (const [car, rows] of slots) {
        const [a0, a1] = sector(car);
        rows.sort((a, b) => (a.it.published_at ?? "").localeCompare(b.it.published_at ?? ""));
        rows.forEach(({ it }, i) => {
          const a = a0 + ((a1 - a0) * (i + 0.5)) / rows.length;
          const h = ring === "sales" && it.unit === "units" && it.value ? Math.min(0.42, (it.value / 120000) * 0.3) : 0;
          const [x, , z] = polar(radius + 0.07, a);
          v.push(x, h, z); cp.push(it.new ? 2 : 1); az.push(a); size.push(1.2); idx.push(items.length); items.push(it);
          if (h > 0) sticks.push({ i: items.length - 1, seg: [x, 0, z, x, h, z] });
        });
      }
      const f = (a: number[]) => new Float32Array(a);
      return {
        items,
        geom: attrGeometry(f(v), { aCp: f(cp), aAz: f(az), aSize: f(size), aIdx: f(idx), aSel: new Float32Array(items.length).fill(1) }),
        sticks,
      };
    };
    return { study: build("study", R.study), options: build("options", R.options), sales: build("sales", R.sales) };
  }, [p.sources]);

  /* filter: research and public research dim like masked comments */
  const filter = p.filter ?? null;
  const researchSel = useMemo(() => research.items.map((it) => passResearch(filter, it)), [research, filter]);
  const carRingSel = useMemo(() => ({
    study: carRings.study.items.map((it) => passResearch(filter, it)),
    options: carRings.options.items.map((it) => passResearch(filter, it)),
    sales: carRings.sales.items.map((it) => passResearch(filter, it)),
  }), [carRings, filter]);
  // public sales figures stand on sticks; held and new apart (new ones appear with the second checkpoint), filtered ones drop
  const salesSticks = useMemo(() => [false, true].map((isNew) => new THREE.BufferGeometry().setAttribute("position",
    new THREE.Float32BufferAttribute(carRings.sales.sticks.filter((st) => !!carRings.sales.items[st.i].new === isNew && carRingSel.sales[st.i]).flatMap((st) => st.seg), 3))),
  [carRings, carRingSel]);
  useEffect(() => {
    const apply = (g: THREE.BufferGeometry, sel: boolean[]) => {
      const a = g.getAttribute("aSel") as THREE.BufferAttribute;
      sel.forEach((on, i) => a.setX(i, on ? 1 : 0));
      a.needsUpdate = true;
    };
    apply(research.geom, researchSel);
    apply(carRings.study.geom, carRingSel.study); apply(carRings.options.geom, carRingSel.options); apply(carRings.sales.geom, carRingSel.sales);
  }, [research, carRings, researchSel, carRingSel]);

  useEffect(() => {
    for (const m of [commentMat, researchMat, studyMat, optionMat, salesMat]) { m.uniforms.uGrow.value = spread.grow; m.uniforms.uDepth.value = spread.spread; }
  }, [spread, commentMat, researchMat, studyMat, optionMat, salesMat]);

  useSweep([commentMat, researchMat, studyMat, optionMat, salesMat], p.position, p.fromPosition, p.sweepId, (a) => {
    const g = sweepRef.current;
    if (!g) return;
    g.visible = a != null;
    if (a != null) g.rotation.y = -a;
  });

  /* picking */
  const first = (e: ThreeEvent<PointerEvent | MouseEvent>, ok: (i: number) => boolean) =>
    e.intersections.find((h) => h.object === e.object && h.index != null && ok(h.index))?.index ?? null;
  const commentOk = (i: number) => (p.mode !== "structure" || p.stage === "classify") && p.mask[i] === 1 && p.points.cols.cp[i] <= p.position;
  const researchOk = (i: number) => researchSel[i] && (research.items[i]?.new ? 2 : 1) <= p.position;
  const at = (g: THREE.BufferGeometry, i: number): [number, number, number] => {
    const a = g.getAttribute("position");
    return [a.getX(i), a.getY(i), a.getZ(i)];
  };

  const onComment = {
    onPointerMove: (e: ThreeEvent<PointerEvent>) => {
      const i = first(e, commentOk);
      if (i == null) return;
      e.stopPropagation(); setCursor(true);
      p.onHover({ title: "", comment: i, acquiredHere: p.points.cols.cp[i] === p.position, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
    },
    onPointerOut: () => { setCursor(false); p.onHover(null); },
    onClick: (e: ThreeEvent<MouseEvent>) => {
      const i = first(e, commentOk);
      if (i == null) return;
      e.stopPropagation(); p.onSelect({ kind: "comment", id: p.points.cols.id[i] }, at(comments, i));
    },
  };
  const onResearch = {
    onPointerMove: (e: ThreeEvent<PointerEvent>) => {
      const i = first(e, researchOk);
      if (i == null) return;
      e.stopPropagation(); setCursor(true);
      const it = research.items[i];
      p.onHover({ title: it.headline, sub: `Research · ${it.published_at ?? "undated"}`, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
    },
    onPointerOut: () => { setCursor(false); p.onHover(null); },
    onClick: (e: ThreeEvent<MouseEvent>) => {
      const i = first(e, researchOk);
      if (i == null) return;
      e.stopPropagation(); p.onSelect({ kind: "research", item: research.items[i] }, at(research.geom, i));
    },
  };

  const carRingHandlers = (layer: { items: ResearchItem[]; geom: THREE.BufferGeometry }, sel: boolean[], label: string) => {
    const ok = (i: number) => sel[i] && (layer.items[i]?.new ? 2 : 1) <= p.position;
    return {
      onPointerMove: (e: ThreeEvent<PointerEvent>) => {
        const i = first(e, ok);
        if (i == null) return;
        e.stopPropagation(); setCursor(true);
        const it = layer.items[i];
        p.onHover({ title: it.headline, sub: `${label} · ${it.published_at ?? "undated"}`, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
      },
      onPointerOut: () => { setCursor(false); p.onHover(null); },
      onClick: (e: ThreeEvent<MouseEvent>) => {
        const i = first(e, ok);
        if (i == null) return;
        e.stopPropagation(); p.onSelect({ kind: "research", item: layer.items[i] }, at(layer.geom, i));
      },
    };
  };

  /* comment id → its current place (raw position, or its cluster once the morph has run) */
  const posOf = useMemo(() => {
    const index = new Map(p.points.cols.id.map((id, i) => [id, i]));
    return (id: number): [number, number, number] | null => {
      const i = index.get(id);
      if (i == null) return null;
      const src = comments.getAttribute("position"), tgt = comments.getAttribute("aTarget");
      const m = commentMat.uniforms.uMorph.value as number;
      const a = [src.getX(i), src.getY(i), src.getZ(i)];
      if (!tgt || !m) return a as [number, number, number];
      return [a[0] + (tgt.getX(i) - a[0]) * m, a[1] + (tgt.getY(i) - a[1]) * m, a[2] + (tgt.getZ(i) - a[2]) * m];
    };
  }, [p.points, comments, commentMat]);

  /* where each evidence item sits on the rings (for the arcs on page 2) */
  const ends = useMemo(() => {
    const m = new Map<string, [number, number, number]>();
    const put = (g: THREE.BufferGeometry, items: { id: number }[]) => {
      const a = g.getAttribute("position");
      items.forEach((it, i) => m.set(`research:${it.id}`, [a.getX(i), a.getY(i), a.getZ(i)]));
    };
    put(research.geom, research.items);
    put(carRings.study.geom, carRings.study.items);
    put(carRings.options.geom, carRings.options.items);
    put(carRings.sales.geom, carRings.sales.items);
    for (const { item, tip } of studyLayout(p.sources?.study ?? [])) m.set(`study:${item.id}`, tip);
    for (const { item, at: pos } of optionLayout(p.sources?.options ?? [])) m.set(`option:${item.id}`, pos);
    return (type: string, id: string) => m.get(`${type}:${id}`) ?? null;
  }, [research, carRings, p.sources]);

  // the lock reticle rides with the focused layer, so it stays on the item as the layer rises
  const reticle = (id: LayerId) => (p.locked && p.focus === id ? <Reticle at={p.locked} /> : null);

  // car lines of the focused item, for the car names (G68 sits in the 5 Series sector)
  const focusLines = useMemo(() => {
    const s = p.selected;
    if (!s || p.focus == null) return null;
    let cars: string[] = [];
    if (s.kind === "comment") {
      const i = p.points.cols.id.indexOf(s.id);
      if (i >= 0) cars = [p.points.dict.car[p.points.cols.car[i]]];
    } else if (s.kind === "research") cars = s.item.cars;
    else if (s.kind === "study" || s.kind === "option" || s.kind === "sales") cars = [s.item.car];
    return new Set(cars.map((c) => (c === "G68" ? "G60" : c)));
  }, [p.selected, p.focus, p.points]);

  return (
    <>
      <CameraFit fit={fit} />
      {/* zoom goes toward the cursor and may come close, so any spot can be reached; right-drag (or Shift-drag) pans */}
      <OrbitControls makeDefault enablePan screenSpacePanning zoomToCursor minDistance={0.15} maxDistance={16 * spread.spread}
                     enableDamping dampingFactor={0.08} maxPolarAngle={Math.PI * 0.62} />
      {/* pages with their own home view (Definition, Prioritize) re-plan their own flight on Reset */}
      <Navigator spread={spread.spread} nav={p.nav} fit={fit} homeOverride={p.mode !== "scan" && p.mode !== "structure"} />
      <SpreadCtx.Provider value={spread}>
      <VolumeSink sunk={p.mode === "definition" || p.mode === "prioritize"}>
      <group scale={spread.spread}>
      <Layer id="comment" focus={p.focus}>
        <points geometry={comments} material={commentMat} {...onComment} />
        {reticle("comment")}
      </Layer>
      <Rings sources={p.sources} focus={p.focus} focusLines={focusLines} filter={filter} onHover={p.onHover} onSelect={p.onSelect} setCursor={setCursor} slots={{
        research: <><points geometry={research.geom} material={researchMat} {...onResearch} />{reticle("research")}</>,
        study: <><points geometry={carRings.study.geom} material={studyMat} {...carRingHandlers(carRings.study, carRingSel.study, "Public rating")} />{reticle("study")}</>,
        option: <><points geometry={carRings.options.geom} material={optionMat} {...carRingHandlers(carRings.options, carRingSel.options, "Product news")} />{reticle("option")}</>,
        sales: (
          <>
            <points geometry={carRings.sales.geom} material={salesMat} {...carRingHandlers(carRings.sales, carRingSel.sales, "Public sales")} />
            <lineSegments geometry={salesSticks[0]}><lineBasicMaterial color={TYPE_COLOR.sales} transparent opacity={0.45} /></lineSegments>
            {p.position >= 2 && <lineSegments geometry={salesSticks[1]}><lineBasicMaterial color={TYPE_COLOR.sales} transparent opacity={0.45} /></lineSegments>}
            {reticle("sales")}
          </>
        ),
      }} />
      <group ref={sweepRef} visible={false}><SweepBlade /></group>
      {p.structure?.ready && (
        <StructureLayer data={p.structure} morph={morph} stage={p.stage ?? "areas"} dpr={dpr * spread.grow} selected={p.selected ?? null} hoverKey={p.hoverKey ?? null}
                        ends={ends} onHover={p.onStructureHover ?? (() => {})} onSelect={p.onSelect} setCursor={setCursor} />
      )}
      {p.mode === "structure" && p.locked && p.focus == null && <Reticle at={p.locked} />}
      <ClassifyPulse ids={p.pulse} posOf={posOf} dpr={dpr * spread.grow} />
      </group>
      </VolumeSink>
      </SpreadCtx.Provider>
      {p.extra}
    </>
  );
}

/* ------------------------------------------------------------------------------------------- sweep + lock */
function SweepBlade() {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
    fragmentShader: "varying vec2 vUv; void main(){ float a = (1.0 - vUv.x * 0.7) * (1.0 - abs(vUv.y - 0.5) * 2.0); gl_FragColor = vec4(0.18, 0.45, 0.95, 0.32 * a); }",
  }), []);
  return (
    <>
      <mesh material={mat} position={[(R.sales + 0.1) / 2, 0, 0]}><planeGeometry args={[R.sales + 0.1, 1.4]} /></mesh>
      <mesh position={[(R.sales + 0.1) / 2, 0, 0]}><boxGeometry args={[R.sales + 0.1, 0.004, 0.004]} /><meshBasicMaterial color="#4d94ff" /></mesh>
    </>
  );
}

function Reticle({ at }: { at: [number, number, number] }) {
  const ref = useRef<THREE.Group>(null);
  const { k } = useSpread();
  useFrame(({ clock }) => { if (ref.current) ref.current.rotation.z = clock.elapsedTime * 0.8; });
  return (
    <Billboard position={at} scale={k}>
      <group ref={ref}>
        {[0, 1, 2, 3].map((k) => (
          <mesh key={k} rotation={[0, 0, (k * Math.PI) / 2]}>
            <ringGeometry args={[0.045, 0.052, 16, 1, -0.45, 0.9]} />
            <meshBasicMaterial color="#ffffff" transparent opacity={0.95} depthTest={false} />
          </mesh>
        ))}
      </group>
    </Billboard>
  );
}

/* ------------------------------------------------------------------------------------------- source rings */
function ringPoints(r: number, a0 = 0, a1 = TAU, seg = 256) {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= seg; i++) { const a = a0 + ((a1 - a0) * i) / seg; pts.push(new THREE.Vector3(...polar(r, a))); }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

const OFF = 0.07;                  // opacity of ring items the filter leaves out (masked comments sit at 0.06)
const RING_BEARING = Math.PI / 2; // the gap between the 7 Series and 1 Series sectors faces the viewer
const RINGS: Record<Exclude<LayerId, "comment">, { r: number; name: string; color: string }> = {
  research: { r: R.time, name: "Research", color: TYPE_COLOR.research }, study: { r: R.study, name: "Study", color: TYPE_COLOR.study },
  option: { r: R.options, name: "Options", color: TYPE_COLOR.option }, sales: { r: R.sales, name: "Sales", color: TYPE_COLOR.sales },
};

function Rings({ sources, focus, focusLines, filter, slots, onHover, onSelect, setCursor }: {
  sources: SourcesPayload | undefined;
  focus: LayerId | null;
  focusLines: Set<string> | null;
  filter: Filter | null;
  slots: Record<Exclude<LayerId, "comment">, ReactNode>;
  onHover: (h: Hover | null) => void;
  onSelect: (s: Selection, at: [number, number, number]) => void;
  setCursor: (on: boolean) => void;
}) {
  const { grow, k } = useSpread();
  // sector guides per ring, each ring with its own material so it can fade on its own
  const lines = useMemo(() => {
    const guides = (r: number) => {
      const guide = new THREE.LineBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.1 });
      return CARS.map((car) => new THREE.Line(ringPoints(r, ...sector(car), 64), guide));
    };
    const time = new THREE.Line(ringPoints(R.time, TIME_START - 0.12, TIME_START + (300 / 360) * TAU, 360),
      new THREE.LineDashedMaterial({ color: "#ffffff", transparent: true, opacity: 0.22, dashSize: 0.02, gapSize: 0.025 }));
    time.computeLineDistances();
    return { research: [time], study: guides(R.study), option: guides(R.options), sales: guides(R.sales) };
  }, []);

  // a bracket just outside the sales ring marking the China long-wheelbase part of the 5 Series sector
  const lwbArc = useMemo(() => new THREE.Line(ringPoints(R.sales + 0.08, ...sector("G68"), 32),
    new THREE.LineBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.35 })), []);

  // study: a radial tick per item (outward = above this car × market's average item, inward = below); the tip is pickable.
  // Items the filter leaves out go to a second, faint set with no handlers. Positions never change, so page 2's arcs hold.
  const study = useMemo(() => {
    const geo = (a: number[]) => new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(a, 3));
    const on = { seg: [] as number[], tips: [] as number[], items: [] as NonNullable<typeof sources>["study"] };
    const off = { seg: [] as number[], tips: [] as number[] };
    for (const { item, base, tip } of studyLayout(sources?.study ?? [])) {
      const t = passStudy(filter, item) ? on : off;
      t.seg.push(...base, ...tip); t.tips.push(...tip);
      if (t === on) on.items.push(item);
    }
    return { items: on.items, lines: geo(on.seg), tips: geo(on.tips), offLines: geo(off.seg), offTips: geo(off.tips) };
  }, [sources, filter]);

  // options: one dot per equipment option of today's car
  const options = useMemo(() => {
    const geo = (a: number[]) => new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(a, 3));
    const v: number[] = [], off: number[] = [], items: NonNullable<typeof sources>["options"] = [];
    for (const { item, at } of optionLayout(sources?.options ?? [])) {
      if (passOption(filter, item)) { v.push(...at); items.push(item); } else off.push(...at);
    }
    return { items, geom: geo(v), off: geo(off) };
  }, [sources, filter]);

  // sales: one bar per car × market × year; the 2030 forecast is an outline
  const bars = useMemo(() => {
    const rows = (sources?.sales ?? []).filter((s) => s.units && s.units > 0);
    const byCar = new Map<string, typeof rows>();
    for (const s of rows) byCar.set(s.car, [...(byCar.get(s.car) ?? []), s]);
    const out: { row: (typeof rows)[number]; pos: [number, number, number]; rot: number; h: number }[] = [];
    for (const [car, items] of byCar) {
      const [a0, a1] = sector(car);
      items.forEach((s, i) => {
        const a = a0 + ((a1 - a0) * (i + 0.5)) / items.length;
        const h = Math.max(0.01, (s.units! / 120000) * 0.3);
        out.push({ row: s, pos: polar(R.sales, a, h / 2), rot: -a, h });
      });
    }
    return out;
  }, [sources]);

  const pick = (e: ThreeEvent<PointerEvent | MouseEvent>) =>
    e.intersections.find((h) => h.object === e.object && h.index != null)?.index ?? null;
  const pos = (g: THREE.BufferGeometry, i: number): [number, number, number] => {
    const a = g.getAttribute("position");
    return [a.getX(i), a.getY(i), a.getZ(i)];
  };
  const hover = (e: ThreeEvent<PointerEvent>, title: string, sub: string) => {
    e.stopPropagation(); setCursor(true); onHover({ title, sub, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
  };
  const out = () => { setCursor(false); onHover(null); };

  const dim = (id: LayerId) => (focus != null && focus !== id ? "" : undefined);
  const ringName = (id: Exclude<LayerId, "comment">) => (
    <Html position={polar(RINGS[id].r, RING_BEARING, 0.02)} center zIndexRange={[10, 0]}>
      <div className="ring-name" data-dim={dim(id)}><i style={{ background: RINGS[id].color }} />{RINGS[id].name}</div>
    </Html>
  );
  const guides = (id: Exclude<LayerId, "comment">) => lines[id].map((l, i) => <primitive key={i} object={l} />);

  return (
    <>
      {/* Under StrictMode (dev), the first drei <Html> mounted here comes up empty: its double-mounted root is
          unmounted mid-render and wipes the label (it hid the Research ring name). This blank one takes that hit. */}
      <Html />
      <Layer id="research" focus={focus}>
        {guides("research")}
        {slots.research}
        {ringName("research")}
        {[["JUL 25", "2025-07-01"], ["JAN 26", "2026-01-31"], ["JUL 26", "2026-07-31"]].map(([t, d]) => (
          <Html key={t} position={polar(R.time, timeAngle(d), 0.16)} center zIndexRange={[10, 0]}>
            <div className="time-label" data-dim={dim("research")}>{t}</div>
          </Html>
        ))}
      </Layer>
      <Layer id="study" focus={focus}>
        {guides("study")}
        <lineSegments geometry={study.lines}><lineBasicMaterial color={TYPE_COLOR.study} transparent opacity={0.75} /></lineSegments>
        <lineSegments geometry={study.offLines}><lineBasicMaterial color={TYPE_COLOR.study} transparent opacity={OFF} /></lineSegments>
        <points geometry={study.offTips}><pointsMaterial color={TYPE_COLOR.study} size={0.016 * grow} transparent opacity={OFF} /></points>
        <points geometry={study.tips}
                onPointerMove={(e) => { const i = pick(e); if (i != null) { const s = study.items[i]; hover(e, s.item, `Study · ${CAR_NAME[s.car]} · ${MARKET_NAME[s.market]} · ${studyValue(s)}`); } }}
                onPointerOut={out}
                onClick={(e) => { const i = pick(e); if (i != null) { e.stopPropagation(); onSelect({ kind: "study", item: study.items[i] }, pos(study.tips, i)); } }}>
          <pointsMaterial color={TYPE_COLOR.study} size={0.016 * grow} transparent opacity={0.9} />
        </points>
        {slots.study}
        {ringName("study")}
      </Layer>
      <Layer id="option" focus={focus}>
        {guides("option")}
        <points geometry={options.geom}
                onPointerMove={(e) => { const i = pick(e); if (i != null) { const o = options.items[i]; hover(e, o.name ?? o.code ?? "Option", `Option · ${CAR_NAME[o.car]} · ${o.availability ?? ""}`); } }}
                onPointerOut={out}
                onClick={(e) => { const i = pick(e); if (i != null) { e.stopPropagation(); onSelect({ kind: "option", item: options.items[i] }, pos(options.geom, i)); } }}>
          <pointsMaterial color={TYPE_COLOR.option} size={0.014 * grow} transparent opacity={0.85} />
        </points>
        <points geometry={options.off}><pointsMaterial color={TYPE_COLOR.option} size={0.014 * grow} transparent opacity={OFF} /></points>
        {slots.option}
        {ringName("option")}
      </Layer>
      <Layer id="sales" focus={focus}>
        {guides("sales")}
        {bars.map((b, i) => passSales(filter, b.row) ? (
          <mesh key={`on${i}`} position={b.pos} rotation={[0, b.rot, 0]} scale={[k, 1, k]}
                onPointerMove={(e) => hover(e, `${(b.row.units ?? 0).toLocaleString("en-US")} cars`, `Sales · ${CAR_NAME[b.row.car]} · ${MARKET_NAME[b.row.market]} · ${b.row.year}${b.row.is_forecast ? " forecast" : ""}`)}
                onPointerOut={out}
                onClick={(e) => { e.stopPropagation(); onSelect({ kind: "sales", item: b.row }, [b.pos[0], b.h, b.pos[2]]); }}>
            <boxGeometry args={[0.014, b.h, 0.014]} />
            {b.row.is_forecast ? <meshBasicMaterial color={TYPE_COLOR.sales} wireframe transparent opacity={0.6} /> : <meshBasicMaterial color={TYPE_COLOR.sales} transparent opacity={0.85} />}
          </mesh>
        ) : (
          <mesh key={`off${i}`} position={b.pos} rotation={[0, b.rot, 0]} scale={[k, 1, k]}>
            <boxGeometry args={[0.014, b.h, 0.014]} />
            <meshBasicMaterial color={TYPE_COLOR.sales} wireframe={!!b.row.is_forecast} transparent opacity={OFF} />
          </mesh>
        ))}
        <primitive object={lwbArc} />
        <Html position={polar(R.sales + 0.17, (sector("G68")[0] + sector("G68")[1]) / 2, 0.02)} center zIndexRange={[10, 0]}>
          <div className="ring-sub" data-dim={dim("sales")}>LWB · China</div>
        </Html>
        {slots.sales}
        {ringName("sales")}
      </Layer>
      {LINES.map((line) => {
        const [a0, a1] = lineSector(line);
        const state: LabelState = focusLines == null ? "rest" : focusLines.has(line) ? "up" : "down";
        return (
          <LabelLift key={line} state={state}>
            <Html position={polar(R.labels, (a0 + a1) / 2, 0.18)} center zIndexRange={[10, 0]}>
              <div className="ring-label" data-dim={state === "down" ? "" : undefined}><b>{CAR_NAME[line]}</b><span>{LINE_CODES[line]}</span></div>
            </Html>
          </LabelLift>
        );
      })}
    </>
  );
}
