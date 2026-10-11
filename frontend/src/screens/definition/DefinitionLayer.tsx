// Page 3 inside the shared scan canvas. Before the last stage the requirements live on a plane above the volume
// (StageLayer: drafted → specified → linked); on the "car" stage today's car rises at the centre, the
// requirement definitions sit on it as pins at their car zone (colour = domain, mark shape = track state), and the
// couplings between requirements run as arcs over and through the car between their zones (solid = synergy /
// enables, dashed = conflicts / competes for, width = strength, the shared resource named at the apex).
// Selecting a requirement flies the camera to its zone (x-ray for interior zones and the battery floor).
import { memo, useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import type { NavInput } from "../scan/navigate";
import type { DefLink, Requirement } from "@/lib/definition";
import { DefinitionCar, QuietLight, type CarLook } from "@/three/DefinitionCar";
import { INTERIOR_ZONES, frameDir, poseFor, zoneToWorld, type CarFrame, type Vec3, type ZoneDef } from "@/three/frame";
import { PLACEHOLDER_FRAME } from "@/three/PlaceholderCar";
import { domainColor, isDashed, linkVerdict, rowFor, useDefinition } from "./data";
import { select, setView, useView } from "./store";
import { StageLayer, glide, type StageAnim } from "./StageLayer";
import { Skyline } from "../prioritize/Skyline";
import { useP } from "../prioritize/store";

/** The car is normalised to 4.8 units; page 3 shows it at this scale so it sits inside the scan's camera range. */
export const CAR_SCALE = 0.72;
const XRAY_ZONES = new Set([...INTERIOR_ZONES, "underfloor"]);
const RISE_DELAY = 0.35, RISE = 1.1;   // seconds: the car starts rising while the volume is still sinking
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const INK = "#f2f4f7";

type Orbit = { target: THREE.Vector3; update: () => void };

// prioritize: page 4 keeps this car on stage and hands its pins to the priority skyline (../prioritize/Skyline), which
// lifts them off the car; the pins come back once the columns have landed again.
export function DefinitionLayer({ active, sweepId, spread = 1, nav, prioritize = false }: { active: boolean; sweepId: number; spread?: number; nav?: MutableRefObject<NavInput>; prioritize?: boolean }) {
  const def = useDefinition();
  const line = useView((s) => s.line);
  const selected = useView((s) => s.selected);
  const hover = useView((s) => s.hover);
  const domains = useView((s) => s.domains);
  const linkMode = useView((s) => s.links);
  const bundle = useView((s) => s.bundle);
  const pendingLinks = useView((s) => s.pendingLinks);   // optimistic link reviews
  const stage = useView((s) => s.stage);
  const { data } = def;
  // the car only comes up at the last stage; before it the requirements live on the plane (StageLayer)
  const carOn = active && (stage === "car" || prioritize);
  const skyOut = useP((s) => s.out);   // the skyline's columns are (partly) off the car
  const anim = useRef<StageAnim>({ rise: 0, split: 0, link: 0, fly: 0, flyWait: 0 });
  const [landed, setLanded] = useState(false);   // the requirements have flown onto the car: the pins take over
  // arriving straight on page 4: the stage moves are already done, so nothing flies about under the skyline
  useEffect(() => { if (prioritize) Object.assign(anim.current, { rise: 1, split: 1, link: 0, fly: 1, flyWait: 0 }); }, [prioritize]);

  const [frame, setFrame] = useState<CarFrame>(PLACEHOLDER_FRAME);
  const onFrame = useCallback((f: CarFrame) => setFrame((p) => (p.L === f.L && p.W === f.W && p.H === f.H ? p : f)), []);
  const model = data.models[line];

  /* what is on the car for this line */
  const reqs = useMemo(() => data.requirements.filter((r) => r.lines.includes(line)), [data, line]);
  const byKey = useMemo(() => new Map(data.requirements.map((r) => [r.key, r])), [data]);
  const passes = useCallback((r: Requirement) => !domains.length || domains.includes(r.domain), [domains]);
  const sel = selected ? byKey.get(selected) ?? null : null;
  const zoneOf = useCallback((r: Requirement) => r.zones.find((z) => data.zones[z]) ?? null, [data.zones]);
  const focusZone = sel ? zoneOf(sel) : null;

  /* the rise: the car (and its pins) come up as the volume sinks; leaving runs it back down */
  const group = useRef<THREE.Group>(null);
  const look = useRef<CarLook>({ show: 0, xray: 0 });
  const rise = useRef({ t: 0, wait: 0 });
  const [present, setPresent] = useState(active);
  // the story moves play like page 2's morph, which ignores reduced motion too: the motion is the explanation
  // (only the decorative CSS pulses honour it)
  const reduced = false;
  useEffect(() => { if (active) setPresent(true); }, [active]);
  useEffect(() => { if (carOn) rise.current.wait = reduced ? 0 : RISE_DELAY; }, [carOn, reduced]);
  useFrame((_, dt) => {
    const r = rise.current;
    const goal = carOn ? 1 : 0;
    if (carOn && r.wait > 0) r.wait -= dt;
    else if (r.t !== goal) {
      const step = reduced ? 1 : dt / RISE;
      r.t = goal > r.t ? Math.min(1, r.t + step) : Math.max(0, r.t - step * 1.6);
    }
    const e = easeOut(r.t);
    look.current.show = e;
    // on page 4 the car stays solid (no x-ray): the skyline stands on the ring around it
    const xGoal = prioritize && active ? 0 : carOn && focusZone && XRAY_ZONES.has(focusZone) ? 1 : 0;
    look.current.xray += (xGoal - look.current.xray) * (reduced ? 1 : 1 - Math.exp(-dt * 5));
    if (Math.abs(look.current.xray - xGoal) < 0.003) look.current.xray = xGoal;
    if (group.current) group.current.position.y = -0.55 * (1 - e);
    if (!active && r.t === 0 && anim.current.rise === 0 && present) setPresent(false);
  });

  useCameraFlight(carOn && !prioritize, focusZone ? data.zones[focusZone] : null, frame, reduced, nav);

  /* pins grouped by zone, in domain order then title, so a zone's fan reads the same way every time */
  const zones = useMemo(() => {
    const order = data.domains.map((d) => d.key);
    const m = new Map<string, Requirement[]>();
    for (const r of reqs) {
      const z = zoneOf(r);
      if (z) m.set(z, [...(m.get(z) ?? []), r]);
    }
    for (const list of m.values()) list.sort((a, b) => order.indexOf(a.domain) - order.indexOf(b.domain) || a.title.localeCompare(b.title));
    return [...m.entries()];
  }, [reqs, zoneOf, data.domains]);

  /* links between requirements both on this line */
  const onLine = useMemo(() => new Set(reqs.map((r) => r.key)), [reqs]);
  const bundleKeys = useMemo(() => new Set(data.bundles.find((b) => b.id === bundle)?.keys ?? []), [data.bundles, bundle]);
  const arcs = useMemo(() => {
    const out: { l: DefLink; a: Vec3; b: Vec3; level: "hot" | "warm" | "faint"; label: boolean }[] = [];
    for (const l of data.links) {
      if (!onLine.has(l.a) || !onLine.has(l.b)) continue;
      const ra = byKey.get(l.a)!, rb = byKey.get(l.b)!;
      const za = zoneOf(ra), zb = zoneOf(rb);
      if (!za || !zb) continue;
      const verdict = linkVerdict(l);
      const mine = !!selected && (l.a === selected || l.b === selected);
      if (verdict === "removed" && !mine) continue;
      const inBundle = bundleKeys.size > 0 && bundleKeys.has(l.a) && bundleKeys.has(l.b) && l.strength >= 2;
      const hovered = !!hover && (l.a === hover || l.b === hover);
      let level: "hot" | "warm" | "faint" | null;
      if (mine || inBundle) level = "hot";
      else if (hovered) level = "warm";
      else if (selected || bundleKeys.size) level = null;            // focus: only the selected requirement's links
      else if (linkMode === "off") level = null;
      else if (linkMode === "strong" && l.strength < 2) level = null;
      else level = passes(ra) && passes(rb) ? "faint" : null;
      if (!level) continue;
      const pa = zoneToWorld(data.zones[za].pos, frame), pb = zoneToWorld(data.zones[zb].pos, frame);
      out.push({ l, a: pa, b: pb, level, label: level === "hot" });
    }
    return out;
  }, [data, onLine, byKey, zoneOf, selected, hover, bundleKeys, linkMode, passes, frame, pendingLinks]);

  const linkedToSel = useMemo(() => {
    if (!selected) return null;
    const s = new Set<string>([selected]);
    for (const l of data.links) if (linkVerdict(l) !== "removed") { if (l.a === selected) s.add(l.b); if (l.b === selected) s.add(l.a); }
    return s;
  }, [selected, data.links, pendingLinks]);

  const pinsOn = carOn && landed && !prioritize && !skyOut;
  if (!present) return null;
  return (
    <>
    <StageLayer active={active} data={data} reqs={reqs} line={line} frame={frame} carScale={CAR_SCALE} spread={spread}
                anim={anim} onLanded={setLanded} reduced={reduced} nav={nav} />
    <group ref={group}>
      <QuietLight />
      <group scale={CAR_SCALE}>
        <DefinitionCar url={model?.url ?? null} orientation={model?.orientation} look={look} onFrame={onFrame} />
        {carOn && <GroundRing frame={frame} />}
        {pinsOn && arcs.map((x) => <Arc key={`${x.l.id}`} {...x} frame={frame} sweepId={sweepId} reduced={reduced} />)}
        {pinsOn && zones.map(([z, list]) => (
          <ZonePins key={z} zone={z} def={data.zones[z]} frame={frame} list={list} line={line} selected={selected}
                    focus={focusZone === z} xray={!!focusZone && XRAY_ZONES.has(focusZone)} passes={passes} linked={linkedToSel}
                    bundle={bundleKeys} sweepId={sweepId} />
        ))}
      </group>
      {(prioritize || skyOut) && <Skyline active={prioritize && active} frame={frame} zones={data.zones} carScale={CAR_SCALE} reduced={reduced} nav={nav} sweepId={sweepId} />}
    </group>
    </>
  );
}

/* --------------------------------------------------------------------------------------------- camera */
// Flights move the camera and the orbit centre together, like the scan's reset glide; under reduced motion they jump.
// The nav pad's Reset re-plans the same flight, so it returns to this page's car view (not the scan's volume).
function useCameraFlight(active: boolean, zone: ZoneDef | null, frame: CarFrame, reduced: boolean, nav?: MutableRefObject<NavInput>) {
  const controls = useThree((s) => s.controls) as unknown as Orbit | null;
  const camera = useThree((s) => s.camera);
  const aspect = useThree((s) => s.size.width / Math.max(1, s.size.height));
  const flight = useRef<{ t0: number; fromP: THREE.Vector3; fromT: THREE.Vector3; toP: THREE.Vector3; toT: THREE.Vector3; dur: number } | null>(null);
  const lastReset = useRef(nav?.current.reset ?? 0);
  const plan = () => {
    if (!controls) return;
    const raw = poseFor(zone, frame);
    const pull = aspect < 1.25 ? Math.min(2.1, Math.pow(1.25 / aspect, 0.85)) : 1;
    const t = new THREE.Vector3(...raw.target).multiplyScalar(CAR_SCALE);
    const p = new THREE.Vector3(...raw.eye).multiplyScalar(CAR_SCALE).sub(t).multiplyScalar(pull).add(t);
    // a selected zone sits left of centre, clear of the inspector on the right (wide viewports only)
    if (zone && aspect > 1.25) {
      const right = new THREE.Vector3().subVectors(t, p).cross(new THREE.Vector3(0, 1, 0)).normalize();
      const shift = right.multiplyScalar(p.distanceTo(t) * 0.22);
      p.add(shift); t.add(shift);
    }
    flight.current = { t0: -1, fromP: camera.position.clone(), fromT: controls.target.clone(), toP: p, toT: t, dur: reduced ? 0 : zone ? 1.1 : 1.4 };
  };
  useEffect(() => {
    if (!active) { flight.current = null; return; }
    plan();
  }, [active, zone, frame, aspect, controls, camera, reduced]); // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(({ clock }) => {
    if (nav && nav.current.reset !== lastReset.current) { lastReset.current = nav.current.reset; if (active) plan(); }
    const f = flight.current;
    if (!f || !controls) return;
    if (f.t0 < 0) f.t0 = clock.elapsedTime;
    const p = f.dur ? Math.min(1, (clock.elapsedTime - f.t0) / f.dur) : 1;
    const e = easeOut(p);
    glide(f.fromP, f.fromT, f.toP, f.toT, e, camera.position, controls.target);
    controls.update();
    if (p >= 1) flight.current = null;
  });
}

/* --------------------------------------------------------------------------------------------- ground */
/** One hairline ellipse on the ground under the car, the scan's range-ring vocabulary (white at 10%). */
function GroundRing({ frame }: { frame: CarFrame }) {
  const geom = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 160; i++) { const a = (i / 160) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * frame.L * 1.22, 0.002, Math.sin(a) * frame.W * 2.1)); }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [frame]);
  return <lineLoop geometry={geom}><lineBasicMaterial color="#ffffff" transparent opacity={0.1} depthWrite={false} /></lineLoop>;
}

/* --------------------------------------------------------------------------------------------- arcs */
const WIDTH = { 1: 1, 2: 1.7, 3: 2.6 } as Record<number, number>;
const OPACITY = { hot: 0.92, warm: 0.6, faint: 0.2 };

// The pins are DOM marks fanned out around their zone on screen, so an arc aimed at the zone centre would miss them.
// Each frame both ends are re-anchored on their pin: the pin's screen centre, unprojected at its zone's depth.
const SEG = 48;
function arcCurve(A: THREE.Vector3, B: THREE.Vector3, frame: CarFrame, out: THREE.QuadraticBezierCurve3) {
  out.v0.copy(A); out.v2.copy(B);
  // over the roof for long links, a low hop between neighbours (pins next to each other get a small bridge)
  const d = A.distanceTo(B);
  out.v1.lerpVectors(A, B, 0.5);
  out.v1.y = Math.max(A.y, B.y) + Math.min(frame.H * 0.35, d * 0.6) + d * 0.22;
  return out;
}
const _ndc = new THREE.Vector3(), _w = new THREE.Vector3();
/** A pin's centre in the arc's local space, at the depth of its zone anchor `zone` (local); false if not on screen. */
function pinPoint(el: HTMLElement | null, zone: THREE.Vector3, parent: THREE.Object3D, camera: THREE.Camera, canvas: DOMRect, out: THREE.Vector3) {
  if (!el || !el.isConnected) return false;
  const r = el.getBoundingClientRect();
  if (!r.width) return false;
  _w.copy(zone); parent.localToWorld(_w); _w.project(camera);
  _ndc.set(((r.left + r.width / 2 - canvas.left) / canvas.width) * 2 - 1, -((r.top + r.height / 2 - canvas.top) / canvas.height) * 2 + 1, _w.z);
  out.copy(_ndc).unproject(camera);
  parent.worldToLocal(out);
  return true;
}
const pinEl = (key: string) => document.querySelector<HTMLElement>(`.dzone .dpin[data-req="${CSS.escape(key)}"]`);

const Arc = memo(function Arc({ l, a, b, level, label, frame, sweepId, reduced }: {
  l: DefLink; a: Vec3; b: Vec3; level: "hot" | "warm" | "faint"; label: boolean; frame: CarFrame; sweepId: number; reduced: boolean;
}) {
  const forward = l.direction !== "b_to_a";
  const tAt = forward ? 0.8 : 0.2;
  const { pts, apex } = useMemo(() => {
    const c = arcCurve(new THREE.Vector3(...a), new THREE.Vector3(...b), frame, new THREE.QuadraticBezierCurve3());
    return { pts: c.getPoints(SEG), apex: c.getPoint(0.5) };
  }, [a, b, frame]);
  const dashed = isDashed(l.relation);
  const ref = useRef<{ material: THREE.Material & { opacity: number } } | null>(null);
  const cone = useRef<THREE.Mesh>(null);
  const labelG = useRef<THREE.Group>(null);
  const camera = useThree((s) => s.camera);
  const gl = useThree((s) => s.gl);
  const live = useMemo(() => ({
    za: new THREE.Vector3(...a), zb: new THREE.Vector3(...b), A: new THREE.Vector3(), B: new THREE.Vector3(),
    curve: new THREE.QuadraticBezierCurve3(), flat: new Float32Array((SEG + 1) * 3), p: new THREE.Vector3(),
    up: new THREE.Vector3(0, 1, 0), last: "", ea: null as HTMLElement | null, eb: null as HTMLElement | null,
  }), [a, b]);
  useEffect(() => { live.last = ""; }, [pts, live]);   // a new points prop resets the geometry: re-anchor next frame
  useFrame(() => {
    const line = ref.current as unknown as (THREE.Object3D & { geometry: { setPositions: (p: Float32Array) => void }; computeLineDistances: () => void }) | null;
    const parent = line?.parent;
    if (!line || !parent) return;
    if (!live.ea?.isConnected) live.ea = pinEl(l.a);
    if (!live.eb?.isConnected) live.eb = pinEl(l.b);
    const canvas = gl.domElement.getBoundingClientRect();
    if (!pinPoint(live.ea, live.za, parent, camera, canvas, live.A)) live.A.copy(live.za);
    if (!pinPoint(live.eb, live.zb, parent, camera, canvas, live.B)) live.B.copy(live.zb);
    const key = `${live.A.x.toFixed(4)},${live.A.y.toFixed(4)},${live.A.z.toFixed(4)},${live.B.x.toFixed(4)},${live.B.y.toFixed(4)},${live.B.z.toFixed(4)}`;
    if (key === live.last) return;
    live.last = key;
    const c = arcCurve(live.A, live.B, frame, live.curve);
    for (let i = 0; i <= SEG; i++) { c.getPoint(i / SEG, live.p); live.flat.set([live.p.x, live.p.y, live.p.z], i * 3); }
    line.geometry.setPositions(live.flat);
    if (dashed) line.computeLineDistances();
    if (cone.current) {
      c.getPoint(tAt, cone.current.position);
      const tan = c.getTangent(tAt, live.p);
      if (!forward) tan.negate();
      cone.current.quaternion.setFromUnitVectors(live.up, tan.normalize());
    }
    if (labelG.current) c.getPoint(0.5, labelG.current.position);
  });
  // a link that is new at this checkpoint brightens once when the sweep lands, then settles
  const pulse = useRef(-1);
  useEffect(() => { pulse.current = !reduced && l.state === "new" ? 0 : -1; }, [sweepId, l.state, reduced]);
  const base = OPACITY[level] * (l.strength >= 3 ? 1 : l.strength === 2 ? 0.9 : 0.75);
  useFrame((_, dt) => {
    const m = ref.current?.material;
    if (!m) return;
    let o = base;
    if (pulse.current >= 0) {
      pulse.current += dt;
      const p = pulse.current / 1.6;
      o = base + (1 - base) * Math.sin(Math.min(1, p) * Math.PI);
      if (p >= 1) pulse.current = -1;
    }
    m.opacity = o;
    const cm = cone.current?.material as THREE.MeshBasicMaterial | undefined;
    if (cm) cm.opacity = o;
  });
  return (
    <group>
      <Line ref={ref as never} points={pts} color={INK} lineWidth={(WIDTH[l.strength] ?? 1.4) * (level === "hot" ? 1.15 : 1)} transparent
            opacity={base} dashed={dashed} dashSize={0.07} gapSize={0.06} depthTest={false} depthWrite={false} renderOrder={level === "hot" ? 6 : 4} />
      {l.relation === "enables" && (
        <mesh ref={cone} renderOrder={6}>
          <coneGeometry args={[0.032, 0.095, 12]} />
          <meshBasicMaterial color={INK} transparent opacity={base} depthTest={false} depthWrite={false} />
        </mesh>
      )}
      {label && (
        <group ref={labelG} position={apex}>
          <Html center zIndexRange={[13, 11]}>
            <div className="dlink-label" data-dashed={dashed ? "" : undefined}>{l.via}</div>
          </Html>
        </group>
      )}
    </group>
  );
});

/* --------------------------------------------------------------------------------------------- pins */
// DOM pins (crisp marks, real buttons) anchored at the zone. A zone with several requirements fans them out in rows
// of four. Pins on the far side of the car dim, unless the body is in x-ray.
const ZonePins = memo(function ZonePins({ zone, def, frame, list, line, selected, focus, xray, passes, linked, bundle, sweepId }: {
  zone: string; def: ZoneDef; frame: CarFrame; list: Requirement[]; line: string; selected: string | null; focus: boolean; xray: boolean;
  passes: (r: Requirement) => boolean; linked: Set<string> | null; bundle: Set<string>; sweepId: number;
}) {
  const pos = useMemo(() => zoneToWorld(def.pos, frame), [def, frame]);
  const facing = useMemo(() => new THREE.Vector3(...frameDir(def.view)), [def]);
  const el = useRef<HTMLDivElement>(null);
  const world = useMemo(() => new THREE.Vector3(...pos).multiplyScalar(CAR_SCALE), [pos]);
  const v = useMemo(() => new THREE.Vector3(), []);
  const lastBehind = useRef<boolean | null>(null);
  useFrame(({ camera }) => {
    if (!el.current) return;
    const behind = !xray && !focus && v.copy(camera.position).sub(world).normalize().dot(facing) < -0.15;
    if (behind !== lastBehind.current) { lastBehind.current = behind; el.current.toggleAttribute("data-behind", behind); }
  });
  return (
    <Html position={pos} center zIndexRange={[14, 12]}>
      <div ref={el} className="dzone" data-zone={zone} data-focus={focus ? "" : undefined}>
        <div className="dzone-pins">
          {list.map((r) => {
            const on = r.key === selected;
            const dim = !passes(r) ? "off" : linked && !linked.has(r.key) ? "dim" : bundle.size && !bundle.has(r.key) ? "dim" : undefined;
            const changed = r.state === "changed" || r.state === "strengthened";
            const pulse = r.state === "new" || changed;
            const rec = rowFor(r, line);
            return (
              <button key={`${r.key}:${pulse ? sweepId : 0}`} type="button" className="dpin" data-req={r.key} data-state={r.state ?? "held"}
                      data-on={on ? "" : undefined} data-linked={linked?.has(r.key) && !on ? "" : undefined} data-dim={dim}
                      data-pulse={pulse ? "" : undefined} style={{ ["--c" as string]: domainColor(r.domain) }}
                      aria-label={`${r.title}${rec ? ` · ${rec.market}` : ""}`} aria-pressed={on}
                      onPointerEnter={(e) => setView({ hover: r.key, hoverPos: { x: e.clientX, y: e.clientY } })}
                      onPointerMove={(e) => setView({ hoverPos: { x: e.clientX, y: e.clientY } })}
                      onPointerLeave={() => setView({ hover: null, hoverPos: null })}
                      onClick={(e) => { e.stopPropagation(); select(on ? null : r.key); }}>
                <i aria-hidden />
              </button>
            );
          })}
        </div>
        <span className="dzone-label">{def.label}{list.length > 1 ? <b>{list.length}</b> : null}</span>
      </div>
    </Html>
  );
});
