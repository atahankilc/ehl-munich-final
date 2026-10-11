// Page 2 inside the scan volume: what the AI made of the raw evidence at the current checkpoint.
// Comment points have already flown into their clusters (the morph in Scene). This layer adds the structure on top:
// cluster nodes (blue = something to improve, white = something to keep; mark shape = track state: dot held,
// ring new, double ring strengthened, amber weakened, amber cross lost), theme halos around groups of clusters,
// potential requirement AREAS as diamonds floating above the themes they group, and — for the theme in focus —
// evidence arcs down to the exact research, study and option items on the rings.
import { createContext, useCallback, useContext, useMemo, useRef, type MutableRefObject, type ReactNode } from "react";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Billboard, Html } from "@react-three/drei";
import * as THREE from "three";
import type { AreaNode, ClusterNode, Selection, StructurePayload, ThemeNode, TrackState } from "@/lib/types";
import type { Hover } from "../scan/Scene";
import { TYPE_COLOR } from "../scan/colors";

export const AREA_Y = 1.15;
const STATE_CODE: Record<TrackState, number> = { held: 0, new: 1, strengthened: 2, weakened: 3, lost: 4 };
const SRC_COLOR: Record<string, string> = { research: TYPE_COLOR.research, study: TYPE_COLOR.study, option: TYPE_COLOR.option };

const NODE_VERT = /* glsl */ `
attribute float aState; attribute float aPol; attribute float aSize; attribute float aIdx;
uniform float uScale, uShow, uHover;
varying float vState; varying float vPol; varying float vHov;
void main() {
  vState = aState; vPol = aPol; vHov = abs(aIdx - uHover) < 0.5 ? 1.0 : 0.0;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = aSize * uScale * (1.0 + vHov * 0.6) * uShow / -mv.z;
}`;
const NODE_FRAG = /* glsl */ `
uniform float uShow;
varying float vState; varying float vPol; varying float vHov;
void main() {
  vec2 c = gl_PointCoord - 0.5; float r = length(c);
  if (r > 0.5) discard;
  float dot = smoothstep(0.5, 0.44, r);
  float ring = smoothstep(0.5, 0.45, r) * smoothstep(0.34, 0.39, r);
  float dbl = ring + smoothstep(0.27, 0.23, r) * smoothstep(0.15, 0.19, r);
  float cross = (abs(c.x - c.y) < 0.06 || abs(c.x + c.y) < 0.06) && r < 0.45 ? 1.0 : 0.0;
  float a = vState < 0.5 ? dot : vState < 1.5 ? ring : vState < 2.5 ? dbl : vState < 3.5 ? dot : cross;
  vec3 base = vPol > 0.5 ? vec3(0.224, 0.529, 0.898) : vec3(0.93, 0.95, 0.97);
  vec3 amber = vec3(0.96, 0.65, 0.14);
  vec3 col = vState > 2.5 ? amber : base;
  col = mix(col, vec3(1.0), vHov);
  gl_FragColor = vec4(col, a * uShow * (vState > 3.5 ? 0.8 : 0.95));
}`;

/** Fades every material below it with the morph (structure appears as the comments arrive). The labels are DOM
 *  overlays (drei <Html>) that ignore `visible`, so the same fade goes to them as a CSS variable on the canvas
 *  container they live in, and they are taken out entirely at 0: on the Evidence page none of them show. */
function FadeIn({ morph, children }: { morph: MutableRefObject<number>; children: ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  // the element drei <Html> mounts its labels into (the event source, else the canvas's parent)
  const host = useThree((s) => ((s.events.connected as HTMLElement | undefined) ?? s.gl.domElement.parentElement) as HTMLElement | null);
  const last = useRef(-1);
  useFrame(() => {
    const g = ref.current;
    if (!g) return;
    const a = Math.max(0, (morph.current - 0.45) / 0.55);
    g.visible = a > 0.01;
    if (host && Math.abs(a - last.current) > 0.004) {
      last.current = a;
      host.style.setProperty("--structure-fade", a.toFixed(3));
      host.toggleAttribute("data-structure-off", a <= 0.01);
    }
    g.traverse((o) => {
      const mat = (o as THREE.Mesh).material;
      if (!mat) return;
      for (const m of Array.isArray(mat) ? mat : [mat]) {
        if (m instanceof THREE.ShaderMaterial) { if (m.uniforms.uShow) m.uniforms.uShow.value = a; continue; }
        m.userData.baseOpacity ??= m.opacity;
        m.transparent = true;
        m.opacity = m.userData.baseOpacity * a;
      }
    });
  });
  return <group ref={ref}>{children}</group>;
}

/* ------------------------------------------------------------------------------------------- label collisions */
// Labels are placed in priority order: the label in focus or under the pointer first, then requirement areas by
// comments, then themes by comments. A label whose screen box would overlap one already placed is hidden (visibility
// only, so it stays measurable) until the view turns or its node is hovered. Checked a few times a second.
type Register = (key: string, prio: number) => (el: HTMLDivElement | null) => void;
const LabelCtx = createContext<Register>(() => () => {});
const PAD = 3;

function useLabelCollisions() {
  const labels = useRef(new Map<string, { el: HTMLDivElement; prio: number }>());
  const tick = useRef(0);
  const register = useCallback<Register>((key, prio) => (el) => {
    if (el) labels.current.set(key, { el, prio }); else labels.current.delete(key);
  }, []);
  useFrame(() => {
    if (tick.current++ % 6) return;
    const placed: DOMRect[] = [];
    const list = [...labels.current.values()].sort((a, b) => b.prio - a.prio);
    for (const { el, prio } of list) {
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const hit = prio < FOCUS && placed.some((q) =>
        r.left < q.right + PAD && r.right > q.left - PAD && r.top < q.bottom + PAD && r.bottom > q.top - PAD);
      el.toggleAttribute("data-collide", hit);
      if (!hit) placed.push(r);
    }
  });
  return register;
}
const FOCUS = 1e9;          // focused or hovered: always shown
const AREA = 1e6;           // areas outrank themes

interface Props {
  data: StructurePayload;
  morph: MutableRefObject<number>;
  dpr: number;
  selected: Selection | null;
  hoverKey: string | null;
  ends: (type: string, id: string) => [number, number, number] | null;
  onHover: (h: Hover | null, key?: string | null) => void;
  onSelect: (s: Selection, at: [number, number, number]) => void;
  setCursor: (on: boolean) => void;
}

export function StructureLayer(p: Props) {
  const clusters = useMemo(() => p.data.clusters.filter((c) => c.comments > 0 && !c.tail), [p.data]);
  const themeOf = useMemo(() => Object.fromEntries(p.data.themes.map((t) => [t.key, t])), [p.data]);


  /* cluster nodes */
  const nodeMat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: NODE_VERT, fragmentShader: NODE_FRAG, transparent: true, depthWrite: false,
    uniforms: { uScale: { value: 24 * p.dpr }, uShow: { value: 0 }, uHover: { value: -1 } },
  }), [p.dpr]);
  const nodes = useMemo(() => {
    const n = clusters.length;
    const pos = new Float32Array(n * 3), st = new Float32Array(n), pol = new Float32Array(n), size = new Float32Array(n), idx = new Float32Array(n);
    clusters.forEach((c, i) => {
      pos.set([c.x, c.y, c.z], i * 3);
      st[i] = STATE_CODE[c.state ?? "held"]; pol[i] = c.polarity === "improve" ? 1 : 0;
      size[i] = 1.2 + Math.sqrt(c.comments) * 0.32; idx[i] = i;
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    for (const [k, v] of Object.entries({ aState: st, aPol: pol, aSize: size, aIdx: idx })) g.setAttribute(k, new THREE.BufferAttribute(v, 1));
    g.computeBoundingSphere();
    return g;
  }, [clusters]);
  nodeMat.uniforms.uHover.value = Math.max(-1, clusters.findIndex((c) => c.key === p.hoverKey));

  /* cluster → theme lines */
  const memberLines = useMemo(() => {
    const v: number[] = [];
    for (const c of clusters) {
      const t = c.theme ? themeOf[c.theme] : null;
      if (t) v.push(c.x, c.y, c.z, t.x, t.y, t.z);
    }
    return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  }, [clusters, themeOf]);

  /* requirement areas float on a ring above the galaxy: each at an evenly spaced slot, in the order of its themes'
     bearing, so labels never pile up over the centre; stems tie every area to its themes below */
  const areas = useMemo(() => {
    const placed: { a: AreaNode; ts: ThemeNode[]; bearing: number }[] = [];
    for (const a of p.data.areas) {
      const ts = a.themes.map((k) => themeOf[k]).filter(Boolean);
      if (!ts.length) continue;
      const w = ts.reduce((n, t) => n + (t.comments || 1), 0);
      const x = ts.reduce((n, t) => n + t.x * (t.comments || 1), 0) / w, z = ts.reduce((n, t) => n + t.z * (t.comments || 1), 0) / w;
      placed.push({ a, ts, bearing: Math.atan2(z, x) });
    }
    placed.sort((m, n) => m.bearing - n.bearing);
    const n = placed.length || 1;
    return placed.map(({ a, ts }, i) => {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
      const r = a.kind === "quality" ? 0.35 : 1.05;
      const y = a.kind === "quality" ? AREA_Y - 0.25 : AREA_Y + (i % 2) * 0.12;   // alternate heights for neighbours
      return { a, ts, at: [r * Math.cos(ang), y, r * Math.sin(ang)] as [number, number, number] };
    });
  }, [p.data, themeOf]);
  const focusArea = p.selected?.kind === "area" ? p.selected.key : null;
  const stems = useMemo(() => {
    const v: number[] = [], hot: number[] = [];
    for (const { a, at, ts } of areas) for (const t of ts) (a.key === focusArea ? hot : v).push(t.x, t.y, t.z, ...at);
    const g = (xs: number[]) => new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(xs, 3));
    return { all: g(v), hot: g(hot) };
  }, [areas, focusArea]);

  /* evidence arcs for the theme in focus */
  const focusTheme = p.selected?.kind === "theme" ? p.selected.key
    : p.selected?.kind === "cluster" ? clusters.find((c) => c.key === (p.selected as { key: string }).key)?.theme ?? null
    : p.hoverKey && themeOf[p.hoverKey] ? p.hoverKey : null;
  const arcs = useMemo(() => {
    if (!focusTheme || !themeOf[focusTheme]) return [];
    const t = themeOf[focusTheme];
    const out: THREE.Line[] = [];
    for (const e of p.data.edges) {
      if (e.dst_id !== focusTheme || !(e.src_type in SRC_COLOR)) continue;
      const end = p.ends(e.src_type, e.src_id);
      if (!end) continue;
      const a = new THREE.Vector3(t.x, t.y, t.z), b = new THREE.Vector3(...end);
      const mid = a.clone().lerp(b, 0.5).add(new THREE.Vector3(0, 0.45 + a.distanceTo(b) * 0.15, 0));
      const pts = new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(40);
      const geom = new THREE.BufferGeometry().setFromPoints(pts);
      const contra = e.relation === "contradicts";
      const line = new THREE.Line(geom, contra
        ? new THREE.LineDashedMaterial({ color: SRC_COLOR[e.src_type], transparent: true, opacity: 0.7, dashSize: 0.03, gapSize: 0.03 })
        : new THREE.LineBasicMaterial({ color: SRC_COLOR[e.src_type], transparent: true, opacity: 0.85 }));
      if (contra) line.computeLineDistances();
      out.push(line);
    }
    return out;
  }, [focusTheme, themeOf, p.data, p.ends]);

  const topThemes = useMemo(() => [...p.data.themes].sort((a, b) => b.comments - a.comments).slice(0, 8).map((t) => t.key), [p.data]);
  const pick = (e: ThreeEvent<PointerEvent | MouseEvent>) => e.intersections.find((h) => h.object === e.object && h.index != null)?.index ?? null;
  const register = useLabelCollisions();

  return (
    <LabelCtx.Provider value={register}>
    <FadeIn morph={p.morph}>
      <lineSegments geometry={memberLines}><lineBasicMaterial color="#ffffff" transparent opacity={0.07} /></lineSegments>
      <points geometry={nodes} material={nodeMat}
              onPointerMove={(e) => {
                const i = pick(e); if (i == null) return;
                const c = clusters[i]; e.stopPropagation(); p.setCursor(true);
                p.onHover({ title: c.insight?.title ?? c.category ?? "Cluster", sub: `${c.comments} comments · ${c.state ?? ""}`, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY }, c.key);
              }}
              onPointerOut={() => { p.setCursor(false); p.onHover(null, null); }}
              onClick={(e) => { const i = pick(e); if (i == null) return; e.stopPropagation(); const c = clusters[i]; p.onSelect({ kind: "cluster", key: c.key }, [c.x, c.y, c.z]); }} />
      {p.data.themes.map((t) => <ThemeHalo key={t.key} t={t} active={t.key === focusTheme} label={topThemes.includes(t.key) || t.key === focusTheme}
                                            hot={p.hoverKey === t.key}
                                            onHover={p.onHover} onSelect={p.onSelect} setCursor={p.setCursor} />)}
      <lineSegments geometry={stems.all}><lineBasicMaterial color="#ffffff" transparent opacity={0.12} /></lineSegments>
      <lineSegments geometry={stems.hot}><lineBasicMaterial color="#ffffff" transparent opacity={0.7} /></lineSegments>
      {areas.map(({ a, at }) => <Diamond key={a.key} a={a} at={at} active={focusArea === a.key} hot={p.hoverKey === a.key}
                                         onHover={p.onHover} onSelect={p.onSelect} setCursor={p.setCursor} />)}
      {arcs.map((l, i) => <primitive key={`${focusTheme}-${i}`} object={l} />)}
    </FadeIn>
    </LabelCtx.Provider>
  );
}

function ThemeHalo({ t, active, hot, label, onHover, onSelect, setCursor }: {
  t: ThemeNode; active: boolean; hot: boolean; label: boolean;
  onHover: Props["onHover"]; onSelect: Props["onSelect"]; setCursor: Props["setCursor"];
}) {
  const r = 0.05 + Math.sqrt(t.comments) * 0.006;
  const lost = t.state === "lost", changed = t.state === "strengthened" || t.state === "new";
  const register = useContext(LabelCtx);
  return (
    <Billboard position={[t.x, t.y, t.z]}>
      <mesh onPointerMove={(e) => { e.stopPropagation(); setCursor(true); onHover({ title: t.title, sub: `Theme · ${t.comments} comments${t.state ? ` · ${t.state}` : ""}`, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY }, t.key); }}
            onPointerOut={() => { setCursor(false); onHover(null, null); }}
            onClick={(e) => { e.stopPropagation(); onSelect({ kind: "theme", key: t.key }, [t.x, t.y, t.z]); }}>
        <ringGeometry args={[r, r + (active ? 0.008 : 0.004), 48]} />
        <meshBasicMaterial color={lost ? "#f5a524" : "#ffffff"} transparent opacity={active ? 0.95 : changed ? 0.55 : 0.32} depthWrite={false} />
      </mesh>
      {label && (
        <Html position={[0, r + 0.06, 0]} center zIndexRange={[12, 0]}>
          <div className="theme-label" data-active={active ? "" : undefined}
               ref={register(`theme:${t.key}`, active || hot ? FOCUS : t.comments)}>{t.title}</div>
        </Html>
      )}
    </Billboard>
  );
}

function Diamond({ a, at, active, hot, onHover, onSelect, setCursor }: {
  a: AreaNode; at: [number, number, number]; active: boolean; hot: boolean;
  onHover: Props["onHover"]; onSelect: Props["onSelect"]; setCursor: Props["setCursor"];
}) {
  const ref = useRef<THREE.Mesh>(null);
  const register = useContext(LabelCtx);
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.y += dt * (active ? 1.6 : 0.4); });
  const quality = a.kind === "quality";
  const color = quality ? "#f5a524" : a.kind === "keep" ? "#eef1f5" : a.kind === "emerging" ? "#d95926" : "#3987e5";
  const size = 0.028 + Math.min(0.03, Math.sqrt(a.metrics.comments ?? 1) * 0.0012);
  return (
    <group position={at}>
      <mesh ref={ref}
            onPointerMove={(e) => { e.stopPropagation(); setCursor(true); onHover({ title: a.title, sub: quality ? "Quality hand-over" : `Requirement area · ${a.kind} · ${a.metrics.comments ?? 0} comments${a.state ? ` · ${a.state}` : ""}`, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY }, a.key); }}
            onPointerOut={() => { setCursor(false); onHover(null, null); }}
            onClick={(e) => { e.stopPropagation(); onSelect({ kind: "area", key: a.key }, at); }}>
        <octahedronGeometry args={[active ? size * 1.5 : size, 0]} />
        <meshBasicMaterial color={color} wireframe={a.state === "new" || quality} transparent opacity={active ? 1 : 0.9} />
      </mesh>
      {(active || (a.metrics.comments ?? 0) > 0) && (
        <Html position={[0, size + 0.05, 0]} center zIndexRange={[12, 0]}>
          <div className="area-label" data-active={active ? "" : undefined}
               ref={register(`area:${a.key}`, active || hot ? FOCUS : AREA + (a.metrics.comments ?? 0))}>{a.title}</div>
        </Html>
      )}
    </group>
  );
}

export type { ClusterNode };
