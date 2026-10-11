// CarStage — the real-time 3D studio for today's car, with requirement hotspots pinned to car zones.
//
// Everything is in a normalised world frame: front = +X, up = +Y, right = front × up = +Z, wheels on y = 0,
// length = 4.8 units (see frame.ts). Zones (pos/view/dist) live in the car frame and map through `zoneToWorld`.
// Per-frame work (camera turntable, x-ray fade, glow, pin dimming) runs in useFrame on refs — no React renders.
import {
  Component,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  CameraControls,
  ContactShadows,
  Environment,
  Lightformer,
  MeshReflectorMaterial,
  useGLTF,
  useProgress,
} from "@react-three/drei";
import type CameraControlsImpl from "camera-controls";
import * as THREE from "three";
import { THEME, CAR_LENGTH } from "./theme";
import {
  DEFAULT_ORIENTATION,
  INTERIOR_ZONES,
  frameDir,
  frameFromSize,
  orientationMatrix,
  poseFor,
  zoneToWorld,
  type CarFrame,
  type Orientation,
  type Vec3,
  type ZoneDef,
} from "./frame";
import { PLACEHOLDER_FRAME, PlaceholderCar } from "./PlaceholderCar";
import "./carstage.css";

export type { ZoneDef, Orientation, CarFrame } from "./frame";
export { zoneToWorld } from "./frame";

export type Priority = "Must" | "Should" | "Could";
export type Hotspot = { zone: string; count: number; top: Priority; aiOnly?: boolean };

export interface CarStageProps {
  /** "/models/g60.glb", "/models/g60/scene.gltf", or null → placeholder car. */
  modelUrl: string | null;
  /** How the model's own axes map; default { up: "+y", front: "+z" }. */
  orientation?: Orientation;
  zones: Record<string, ZoneDef>;
  hotspots: Hotspot[];
  selectedZone: string | null;
  onSelectZone: (zone: string | null) => void;
  /** Highlight a pin from outside (e.g. list hover). */
  hoverZone?: string | null;
  /** compact = thumbnail use: no controls, slow turntable. */
  mode?: "showroom" | "compact";
  className?: string;
}

/** Warm the glTF cache before the stage mounts. */
export function preloadCar(url: string) {
  useGLTF.preload(url);
}

const IDLE_MS = 20_000;
const TURN_SPEED = 0.15; // rad/s
const XRAY_OPACITY = 0.18;

// ------------------------------------------------------------------------------------------------ helpers
function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

let glowTex: THREE.Texture | null = null;
function glowTexture() {
  if (glowTex) return glowTex;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.25, "rgba(255,255,255,0.45)");
  grd.addColorStop(0.6, "rgba(255,255,255,0.09)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  glowTex = new THREE.CanvasTexture(c);
  glowTex.colorSpace = THREE.SRGBColorSpace;
  return glowTex;
}

type MatState = { m: THREE.Material; opacity: number; transparent: boolean; depthWrite: boolean };

function collectMaterials(root: THREE.Object3D): MatState[] {
  const out: MatState[] = [];
  const seen = new Set<THREE.Material>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const ms = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const m of ms) {
      if (!m || seen.has(m)) continue;
      seen.add(m);
      out.push({ m, opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite });
    }
  });
  return out;
}

// ------------------------------------------------------------------------------------------------ model
type CarReady = (root: THREE.Object3D, frame: CarFrame) => void;

function GltfCar({ url, orientation, onReady }: { url: string; orientation: Orientation; onReady: CarReady }) {
  const { scene } = useGLTF(url);
  const groupRef = useRef<THREE.Group>(null);

  // Own copy (shared geometry/textures, cloned materials) so x-ray / env boosts never leak into the glTF cache.
  const prepared = useMemo(() => {
    const car = scene.clone(true);
    car.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = false;
      mesh.receiveShadow = false;
      const clone = (m: THREE.Material) => {
        const c = m.clone();
        const std = c as THREE.MeshStandardMaterial;
        if ("envMapIntensity" in std && typeof std.envMapIntensity === "number") {
          std.envMapIntensity = Math.max(1.2, std.envMapIntensity * 1.5);
        }
        return c;
      };
      mesh.material = Array.isArray(mesh.material) ? mesh.material.map(clone) : clone(mesh.material);
    });

    // rotate so the model's front → +X, up → +Y
    const rot = new THREE.Group();
    const m = orientationMatrix(orientation) ?? orientationMatrix(DEFAULT_ORIENTATION)!;
    rot.quaternion.setFromRotationMatrix(
      new THREE.Matrix4().set(m[0], m[1], m[2], 0, m[3], m[4], m[5], 0, m[6], m[7], m[8], 0, 0, 0, 0, 1),
    );
    rot.add(car);
    rot.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(rot);
    const size = box.getSize(new THREE.Vector3());
    const s = size.x > 0 ? CAR_LENGTH / size.x : 1;
    const centre = box.getCenter(new THREE.Vector3());

    const wrap = new THREE.Group();
    wrap.name = "car-normalised";
    wrap.scale.setScalar(s);
    wrap.position.set(-centre.x * s, -box.min.y * s, -centre.z * s);
    wrap.add(rot);
    const frame = frameFromSize([size.x * s, size.y * s, size.z * s]);
    return { wrap, frame };
  }, [scene, orientation]);

  useLayoutEffect(() => {
    if (groupRef.current) onReady(groupRef.current, prepared.frame);
  }, [prepared, onReady]);

  return (
    <group ref={groupRef}>
      <primitive object={prepared.wrap} />
    </group>
  );
}

function Placeholder({ onReady }: { onReady: CarReady }) {
  const ref = useRef<THREE.Group>(null);
  useLayoutEffect(() => {
    if (ref.current) onReady(ref.current, PLACEHOLDER_FRAME);
  }, [onReady]);
  return (
    <group ref={ref}>
      <PlaceholderCar />
    </group>
  );
}

class ModelBoundary extends Component<{ fallback: ReactNode; onError: (e: Error) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError(error);
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

// ------------------------------------------------------------------------------------------------ studio
function StagePool() {
  const tex = useMemo(() => glowTexture(), []);
  return (
    <mesh rotation-x={-Math.PI / 2} position={[0, 0.001, 0]} renderOrder={1}>
      <planeGeometry args={[18, 12]} />
      <meshBasicMaterial map={tex} color="#56607a" transparent opacity={0.6} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} fog={false} />
    </mesh>
  );
}

function Studio({ shadowKey }: { shadowKey: string }) {
  return (
    <>
      <color attach="background" args={[THEME.bg]} />
      <fog attach="fog" args={[THEME.bg, 12, 30]} />
      <ambientLight intensity={0.08} />

      <Environment resolution={256} frames={1}>
        <color attach="background" args={["#020203"]} />
        {/* long softbox strips overhead */}
        {[-2.4, 0, 2.4].map((z) => (
          <Lightformer key={z} form="rect" intensity={2.4} color="#f2f5fb" position={[0, 6, z]} rotation-x={Math.PI / 2} scale={[14, 0.7, 1]} />
        ))}
        {/* side strips → long highlight along the shoulder line */}
        <Lightformer form="rect" intensity={2.8} color="#e6ecf7" position={[0, 1.6, 7]} scale={[16, 0.35, 1]} target={[0, 0.8, 0]} />
        <Lightformer form="rect" intensity={2.8} color="#e6ecf7" position={[0, 1.6, -7]} scale={[16, 0.35, 1]} target={[0, 0.8, 0]} />
        {/* key + cool rim */}
        <Lightformer form="rect" intensity={3} color="#ffffff" position={[7, 3.5, -4]} scale={[3, 5, 1]} target={[0, 0.5, 0]} />
        <Lightformer form="rect" intensity={2.2} color="#8fb6ff" position={[-8, 2, 3]} scale={[2.5, 6, 1]} target={[0, 0.5, 0]} />
        <Lightformer form="ring" intensity={1.2} color={THEME.blueBright} position={[-4, 5, -6]} scale={3} target={[0, 0, 0]} />
        {/* faint floor bounce */}
        <Lightformer form="rect" intensity={0.25} color="#9aa3b5" position={[0, -2, 0]} rotation-x={-Math.PI / 2} scale={[14, 14, 1]} />
      </Environment>

      {/* glossy floor fading into the fog */}
      <mesh rotation-x={-Math.PI / 2} position={[0, -0.002, 0]}>
        <planeGeometry args={[70, 70]} />
        <MeshReflectorMaterial
          resolution={512}
          blur={[400, 120]}
          mixBlur={1}
          mixStrength={3}
          mixContrast={1.1}
          mirror={0.4}
          roughness={0.85}
          metalness={0.6}
          depthScale={1.1}
          minDepthThreshold={0.35}
          maxDepthThreshold={1.3}
          color="#15171c"
        />
      </mesh>

      {/* soft stage pool: lifts the floor around the car, fades to the background */}
      <StagePool />

      <ContactShadows key={shadowKey} frames={1} position={[0, 0.004, 0]} scale={[8, 4]} resolution={512} blur={2} far={1.2} opacity={1} color="#000000" />
    </>
  );
}

// ------------------------------------------------------------------------------------------------ zone glow + x-ray
function ZoneFocus({
  carRef,
  carVersion,
  target,
  xray,
  reduced,
}: {
  carRef: React.RefObject<THREE.Object3D | null>;
  carVersion: number;
  target: Vec3 | null;
  xray: boolean;
  reduced: boolean;
}) {
  const sprite = useRef<THREE.Sprite>(null);
  const pool = useRef<THREE.Mesh>(null);
  const light = useRef<THREE.PointLight>(null);
  const mats = useRef<MatState[]>([]);
  const k = useRef(0); // x-ray amount 0..1
  const g = useRef(0); // glow amount 0..1
  const tex = useMemo(() => glowTexture(), []);
  const lastTarget = useRef<Vec3>([0, 0, 0]);

  useEffect(() => {
    mats.current = carRef.current ? collectMaterials(carRef.current) : [];
    k.current = 0;
    return () => {
      for (const s of mats.current) {
        s.m.opacity = s.opacity;
        s.m.transparent = s.transparent;
        s.m.depthWrite = s.depthWrite;
        s.m.needsUpdate = true;
      }
    };
  }, [carRef, carVersion]);

  if (target) lastTarget.current = target;

  useFrame((_, dt) => {
    const rate = reduced ? 1 : 1 - Math.exp(-dt * 4.5);
    const kGoal = xray ? 1 : 0;
    const gGoal = target ? 1 : 0;
    const kPrev = k.current;
    k.current += (kGoal - k.current) * rate;
    if (Math.abs(k.current - kGoal) < 0.002) k.current = kGoal;
    g.current += (gGoal - g.current) * rate;
    if (Math.abs(g.current - gGoal) < 0.002) g.current = gGoal;

    if (kPrev !== k.current || (k.current > 0 && kPrev === 0)) {
      const kk = k.current;
      for (const s of mats.current) {
        const wantTransparent = kk > 0.001 ? true : s.transparent;
        const wantDepth = kk > 0.35 ? false : s.depthWrite;
        if (s.m.transparent !== wantTransparent) {
          s.m.transparent = wantTransparent;
          s.m.needsUpdate = true;
        }
        s.m.depthWrite = wantDepth;
        s.m.opacity = s.opacity + (Math.min(s.opacity, XRAY_OPACITY) - s.opacity) * kk;
      }
    }

    const [x, y, z] = lastTarget.current;
    const gg = g.current;
    if (sprite.current) {
      sprite.current.position.set(x, y, z);
      const pulse = reduced ? 1 : 1 + Math.sin(performance.now() / 700) * 0.06;
      sprite.current.scale.setScalar(1.5 * pulse * (0.6 + 0.4 * gg));
      (sprite.current.material as THREE.SpriteMaterial).opacity = 0.55 * gg;
      sprite.current.visible = gg > 0.01;
    }
    if (pool.current) {
      pool.current.position.set(x, 0.006, z);
      (pool.current.material as THREE.MeshBasicMaterial).opacity = 0.5 * gg;
      pool.current.visible = gg > 0.01;
    }
    if (light.current) {
      light.current.position.set(x, y + 0.25, z);
      light.current.intensity = 6 * gg;
    }
  });

  return (
    <>
      <sprite ref={sprite} renderOrder={10} visible={false}>
        <spriteMaterial map={tex} color={THEME.blueBright} transparent depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <mesh ref={pool} rotation-x={-Math.PI / 2} renderOrder={2} visible={false}>
        <planeGeometry args={[3.2, 3.2]} />
        <meshBasicMaterial map={tex} color={THEME.blue} transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      <pointLight ref={light} color={THEME.blueBright} intensity={0} distance={3.2} decay={2} />
    </>
  );
}

// ------------------------------------------------------------------------------------------------ hotspots
// Pins are plain DOM in an overlay above the canvas (normal React tree, crisp text, real <button>s).
// A projector inside the canvas writes their screen transform/opacity every frame through refs.
type PinItem = { h: Hotspot; z: ZoneDef; pos: THREE.Vector3; facing: THREE.Vector3 };
type PinEls = Map<string, HTMLDivElement>;

function PinProjector({
  items,
  els,
  xray,
  selectedZone,
}: {
  items: PinItem[];
  els: React.RefObject<PinEls>;
  xray: boolean;
  selectedZone: string | null;
}) {
  const tmp = useMemo(() => new THREE.Vector3(), []);
  const last = useRef(new Map<string, { x: number; y: number; o: string; z: number }>());
  useFrame(({ camera, size }) => {
    const map = els.current;
    for (const it of items) {
      const el = map.get(it.h.zone);
      if (!el) continue;
      tmp.copy(it.pos).project(camera);
      const visible = tmp.z < 1 && Math.abs(tmp.x) < 1.2 && Math.abs(tmp.y) < 1.2;
      const x = Math.round((tmp.x * 0.5 + 0.5) * size.width * 10) / 10;
      const y = Math.round((-tmp.y * 0.5 + 0.5) * size.height * 10) / 10;
      tmp.copy(camera.position).sub(it.pos).normalize();
      const sel = it.h.zone === selectedZone;
      const behind = !xray && !sel && tmp.dot(it.facing) < -0.05;
      const o = !visible ? "0" : behind ? "0.3" : "1";
      const zi = sel ? 30 : behind ? 5 : 10 + Math.round((1 - Math.min(1, camera.position.distanceTo(it.pos) / 30)) * 10);
      const prev = last.current.get(it.h.zone);
      if (!prev || prev.x !== x || prev.y !== y) el.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (!prev || prev.o !== o) {
        el.style.opacity = o;
        el.style.visibility = o === "0" ? "hidden" : "visible";
      }
      if (!prev || prev.z !== zi) el.style.zIndex = String(zi);
      if (prev) {
        prev.x = x;
        prev.y = y;
        prev.o = o;
        prev.z = zi;
      } else last.current.set(it.h.zone, { x, y, o, z: zi });
    }
  });
  return null;
}

function PinLayer({
  items,
  els,
  selectedZone,
  hoverZone,
  onSelectZone,
}: {
  items: PinItem[];
  els: React.RefObject<PinEls>;
  selectedZone: string | null;
  hoverZone: string | null;
  onSelectZone: (z: string | null) => void;
}) {
  return (
    <div className="cs-pins">
      {items.map(({ h, z }) => {
        const sel = selectedZone === h.zone;
        const label = `${z.label} — ${h.count} recommendation${h.count === 1 ? "" : "s"}`;
        return (
          <div
            key={h.zone}
            ref={(el) => {
              if (el) els.current.set(h.zone, el);
              else els.current.delete(h.zone);
            }}
            className="cs-pin-anchor"
          >
            <div className="cs-pin-wrap" data-selected={sel ? "1" : "0"} data-hover={hoverZone === h.zone ? "1" : "0"}>
              <button
                type="button"
                className="cs-pin"
                data-top={h.top}
                aria-label={label + (h.aiOnly ? " (AI suggestion, not yet confirmed)" : "")}
                aria-pressed={sel}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectZone(sel ? null : h.zone);
                }}
              >
                {h.aiOnly && <span className="cs-pin-ai" aria-hidden />}
                {h.count}
              </button>
              <span className="cs-label" aria-hidden>
                {z.label}
                <b>{h.count}</b>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ camera
function CameraRig({
  frame,
  zone,
  compact,
  reduced,
}: {
  frame: CarFrame;
  zone: ZoneDef | null;
  compact: boolean;
  reduced: boolean;
}) {
  const ref = useRef<CameraControlsImpl>(null);
  const lastInput = useRef(performance.now());
  const first = useRef(true);

  // constraints + input mapping (no pan)
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const A = (c.constructor as typeof CameraControlsImpl).ACTION;
    c.minPolarAngle = 0.12;
    c.maxPolarAngle = Math.PI / 2 - 0.05;
    c.minDistance = frame.L * 0.9;
    c.maxDistance = frame.L * 5.5;
    c.dollyToCursor = false;
    c.mouseButtons.left = A.ROTATE;
    c.mouseButtons.right = A.NONE;
    c.mouseButtons.middle = A.DOLLY;
    c.mouseButtons.wheel = A.DOLLY;
    c.touches.one = A.TOUCH_ROTATE;
    c.touches.two = A.TOUCH_DOLLY;
    c.touches.three = A.NONE;
    c.enabled = !compact;
    const onStart = () => {
      lastInput.current = performance.now();
    };
    c.addEventListener("controlstart", onStart);
    c.addEventListener("control", onStart);
    return () => {
      c.removeEventListener("controlstart", onStart);
      c.removeEventListener("control", onStart);
    };
  }, [frame, compact]);

  // fly to zone / overview; portrait viewports pull the camera back so the whole car stays in frame
  const aspect = useThree((st) => st.size.width / Math.max(1, st.size.height));
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const raw = poseFor(zone, frame);
    const pull = aspect < 1.25 ? Math.min(2.1, Math.pow(1.25 / aspect, 0.85)) : 1;
    const p = {
      target: raw.target,
      eye: raw.eye.map((e, i) => raw.target[i] + (e - raw.target[i]) * pull) as typeof raw.eye,
    };
    const animate = !reduced && !first.current;
    first.current = false;
    c.smoothTime = 0.32; // ≈1.2 s settle, ease-out
    lastInput.current = performance.now();
    void c.setLookAt(p.eye[0], p.eye[1], p.eye[2], p.target[0], p.target[1], p.target[2], animate);
  }, [zone, frame, reduced, aspect]);

  useFrame((_, dt) => {
    const c = ref.current;
    if (!c || reduced || zone) return;
    const idle = compact || performance.now() - lastInput.current > IDLE_MS;
    if (idle) {
      void c.rotate(TURN_SPEED * Math.min(dt, 0.1), 0, false);
    }
  });

  return <CameraControls ref={ref} makeDefault />;
}

// ------------------------------------------------------------------------------------------------ scene
function Scene({
  modelUrl,
  orientation,
  frame,
  onFrame,
  zones,
  pinItems,
  pinEls,
  selectedZone,
  compact,
  reduced,
  onModelError,
  modelFailed,
}: {
  modelUrl: string | null;
  orientation: Orientation;
  frame: CarFrame;
  onFrame: (f: CarFrame) => void;
  zones: Record<string, ZoneDef>;
  pinItems: PinItem[];
  pinEls: React.RefObject<PinEls>;
  selectedZone: string | null;
  compact: boolean;
  reduced: boolean;
  onModelError: (e: Error) => void;
  modelFailed: boolean;
}) {
  const carRef = useRef<THREE.Object3D | null>(null);
  const [carVersion, setCarVersion] = useState(0);

  const onReady = useCallback<CarReady>(
    (root, f) => {
      carRef.current = root;
      onFrame(f);
      setCarVersion((v) => v + 1);
    },
    [onFrame],
  );

  const zone = selectedZone ? zones[selectedZone] ?? null : null;
  const target = zone ? zoneToWorld(zone.pos, frame) : null;
  const xray = !!selectedZone && INTERIOR_ZONES.has(selectedZone);

  const placeholder = <Placeholder onReady={onReady} />;

  return (
    <>
      <Studio shadowKey={`${modelUrl ?? "placeholder"}:${modelFailed}:${carVersion}`} />
      {modelUrl && !modelFailed ? (
        <ModelBoundary key={modelUrl} fallback={placeholder} onError={onModelError}>
          <Suspense fallback={null}>
            <GltfCar url={modelUrl} orientation={orientation} onReady={onReady} />
          </Suspense>
        </ModelBoundary>
      ) : (
        placeholder
      )}
      <ZoneFocus carRef={carRef} carVersion={carVersion} target={target} xray={xray} reduced={reduced} />
      <PinProjector items={pinItems} els={pinEls} xray={xray} selectedZone={selectedZone} />
      <CameraRig frame={frame} zone={zone} compact={compact} reduced={reduced} />
    </>
  );
}

function LoadingLine() {
  const { active, progress } = useProgress();
  if (!active) return null;
  const pct = Math.round(progress);
  return (
    <div className="cs-progress" role="status" aria-live="polite">
      <div className="cs-progress-track">
        <div className="cs-progress-bar" style={{ width: `${pct}%` }} />
      </div>
      <div className="cs-progress-pct">{pct}%</div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ public component
export function CarStage({
  modelUrl,
  orientation = DEFAULT_ORIENTATION,
  zones,
  hotspots,
  selectedZone,
  onSelectZone,
  hoverZone = null,
  mode = "showroom",
  className,
}: CarStageProps) {
  const reduced = usePrefersReducedMotion();
  const compact = mode === "compact";
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const modelFailed = !!modelUrl && failedUrl === modelUrl;
  const down = useRef<{ x: number; y: number } | null>(null);
  // stable orientation identity so the model isn't re-normalised on every parent render
  const orient = useMemo<Orientation>(() => ({ up: orientation.up, front: orientation.front }), [orientation.up, orientation.front]);

  const onModelError = useCallback(
    (e: Error) => {
      console.warn("[CarStage] model failed to load, showing placeholder:", modelUrl, e);
      setFailedUrl(modelUrl);
    },
    [modelUrl],
  );

  const showNote = !modelUrl || modelFailed;

  const [frame, setFrame] = useState<CarFrame>(PLACEHOLDER_FRAME);
  const onFrame = useCallback((f: CarFrame) => {
    setFrame((prev) => (prev.L === f.L && prev.W === f.W && prev.H === f.H ? prev : f));
  }, []);
  const pinEls = useRef<PinEls>(new Map());
  const pinItems = useMemo<PinItem[]>(
    () =>
      hotspots
        .filter((h) => zones[h.zone])
        .map((h) => {
          const z = zones[h.zone];
          return { h, z, pos: new THREE.Vector3(...zoneToWorld(z.pos, frame)), facing: new THREE.Vector3(...frameDir(z.view)) };
        }),
    [hotspots, zones, frame],
  );

  return (
    <div
      className={`cs-root${compact ? " cs-compact" : ""}${className ? ` ${className}` : ""}`}
      tabIndex={-1}
      onKeyDown={(e) => {
        if (e.key === "Escape" && selectedZone) onSelectZone(null);
      }}
      onPointerDown={(e) => {
        down.current = { x: e.clientX, y: e.clientY };
      }}
    >
      <Canvas
        dpr={[1, 2]}
        frameloop="always"
        shadows={false}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ fov: 40, near: 0.1, far: 80, position: poseFor(null, PLACEHOLDER_FRAME).eye }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.15;
        }}
        onPointerMissed={(e) => {
          const d = down.current;
          if (compact || !d || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) return;
          if (selectedZone) onSelectZone(null);
        }}
      >
        <Scene
          modelUrl={modelUrl}
          orientation={orient}
          frame={frame}
          onFrame={onFrame}
          zones={zones}
          pinItems={pinItems}
          pinEls={pinEls}
          selectedZone={selectedZone}
          compact={compact}
          reduced={reduced}
          onModelError={onModelError}
          modelFailed={modelFailed}
        />
      </Canvas>
      <PinLayer items={pinItems} els={pinEls} selectedZone={selectedZone} hoverZone={hoverZone} onSelectZone={onSelectZone} />
      <LoadingLine />
      {showNote && !compact && <div className="cs-note">3D model not installed — showing a placeholder</div>}
    </div>
  );
}

export default CarStage;
