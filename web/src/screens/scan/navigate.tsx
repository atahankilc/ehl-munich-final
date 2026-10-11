// Moving through the scan volume. Spread scales the whole universe (layout positions) around a camera that stays put,
// while every mark keeps its size, so the space between contacts opens up on screen. The outer rings move past the
// view as it grows; scroll out or fly to reach them. Flying moves the camera and the orbit centre together:
// W/S forward and back, A/D sideways, Q/E down and up (Shift: faster), or hold the pad's buttons.
import { createContext, useContext, useEffect, useRef, type MutableRefObject, type PointerEvent as ReactPointerEvent } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { ArrowDown, ArrowUp, LocateFixed } from "lucide-react";
import * as THREE from "three";

export const SPREAD_MIN = 1, SPREAD_MAX = 4;
export const HOME: [number, number, number] = [0, 2.3, 5.3];

/** spread: layout scale; grow: how much marks grow with it (none); k: counter-scale for a mark inside the scaled world */
export interface Spread { spread: number; grow: number; k: number }
const make = (spread: number): Spread => ({ spread, grow: 1, k: 1 / spread });
export const spreadOf = make;
export const SpreadCtx = createContext<Spread>(make(1));
export const useSpread = () => useContext(SpreadCtx);

/** what the pad's buttons hold down; reset counts up once per press */
export interface NavInput { fwd: number; reset: number }
export const newNav = (): NavInput => ({ fwd: 0, reset: 0 });

const KEYS: Record<string, [number, number, number]> = {   // [forward, right, up]
  w: [1, 0, 0], s: [-1, 0, 0], a: [0, -1, 0], d: [0, 1, 0], e: [0, 0, 1], q: [0, 0, -1],
};
const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || /^(TEXTAREA|SELECT)$/.test(t.tagName) ||
                               (t instanceof HTMLInputElement && !/^(range|checkbox|radio|button)$/.test(t.type)));

type Orbit = { target: THREE.Vector3; update: () => void };

export function Navigator({ spread, nav, fit }: { spread: number; nav: MutableRefObject<NavInput>; fit: () => number }) {
  const { camera } = useThree();
  const controls = useThree((s) => s.controls) as unknown as Orbit | null;
  const held = useRef(new Set<string>());
  const fast = useRef(false);
  const home = useRef<{ t0: number; from: THREE.Vector3; fromT: THREE.Vector3 } | null>(null);
  const lastReset = useRef(nav.current.reset);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      const key = e.key.toLowerCase();
      fast.current = e.shiftKey;
      if (KEYS[key]) { held.current.add(key); e.preventDefault(); }
    };
    const up = (e: KeyboardEvent) => { fast.current = e.shiftKey; held.current.delete(e.key.toLowerCase()); };
    const clear = () => held.current.clear();
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); window.removeEventListener("blur", clear); };
  }, []);

  const fwd = new THREE.Vector3(), right = new THREE.Vector3(), step = new THREE.Vector3();
  useFrame(({ clock }, dt) => {
    if (!controls) return;
    // reset: glide back to the opening view
    if (nav.current.reset !== lastReset.current) {
      lastReset.current = nav.current.reset;
      home.current = { t0: clock.elapsedTime, from: camera.position.clone(), fromT: controls.target.clone() };
    }
    if (home.current) {
      const h = home.current, p = Math.min(1, (clock.elapsedTime - h.t0) / 0.7), e = 1 - Math.pow(1 - p, 3);
      const goal = new THREE.Vector3(...HOME).setLength(fit());
      camera.position.lerpVectors(h.from, goal, e);
      controls.target.lerpVectors(h.fromT, new THREE.Vector3(), e);
      controls.update();
      if (p >= 1) home.current = null;
      return;
    }
    let f = nav.current.fwd, r = 0, u = 0;
    for (const k of held.current) { const [a, b, c] = KEYS[k]; f += a; r += b; u += c; }
    if (!f && !r && !u) return;
    camera.getWorldDirection(fwd);
    right.crossVectors(fwd, camera.up).normalize();
    const speed = 1.4 * spread * (fast.current ? 2.5 : 1) * Math.min(dt, 0.05);
    step.copy(fwd).multiplyScalar(f).addScaledVector(right, r).addScaledVector(camera.up, u).multiplyScalar(speed);
    camera.position.add(step);
    controls.target.add(step);
    controls.update();
  });
  return null;
}

/** Bottom-centre pad: the spread slider, hold-to-fly buttons and a reset. */
export function NavPad({ spread, onSpread, nav }: { spread: number; onSpread: (s: number) => void; nav: MutableRefObject<NavInput> }) {
  const hold = (dir: number) => ({
    onPointerDown: (e: ReactPointerEvent<HTMLButtonElement>) => { e.currentTarget.setPointerCapture(e.pointerId); nav.current.fwd = dir; },
    onPointerUp: () => { nav.current.fwd = 0; },
    onPointerCancel: () => { nav.current.fwd = 0; },
    onLostPointerCapture: () => { nav.current.fwd = 0; },
  });
  return (
    <div className="navpad" role="group" aria-label="Move through the universe">
      <label className="navpad-spread">
        <span>Spread</span>
        <input type="range" min={SPREAD_MIN} max={SPREAD_MAX} step={0.05} value={spread}
               onChange={(e) => onSpread(Number(e.target.value))} aria-valuetext={`${spread.toFixed(1)} times`} />
        <output className="num">{spread.toFixed(1)}×</output>
      </label>
      <div className="navpad-fly">
        <button type="button" title="Fly back (S)" aria-label="Fly back" {...hold(-1)}><ArrowDown size={14} /></button>
        <button type="button" title="Fly forward (W)" aria-label="Fly forward" {...hold(1)}><ArrowUp size={14} /></button>
        <button type="button" title="Reset view" aria-label="Reset view" onClick={() => { nav.current.reset++; }}><LocateFixed size={14} /></button>
      </div>
      <span className="navpad-hint">W/S fly · A/D side · Q/E down/up · right-drag pan · scroll zooms to cursor</span>
    </div>
  );
}
