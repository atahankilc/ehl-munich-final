// Today's car for page 3 (Definition), inside the shared scan canvas. Restyled for the black instrument field
// (DESIGN.md): no environment map, floor or turntable; the body becomes a quiet graphite study model so the
// requirement pins and link arcs carry the colour. Normalised like CarStage: front = +X, up = +Y, wheels on y = 0,
// length CAR_LENGTH (frame.ts). The parent scales it into the scene.
import { Component, Suspense, useEffect, useLayoutEffect, useMemo, useRef, type MutableRefObject, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { CAR_LENGTH } from "./theme";
import { DEFAULT_ORIENTATION, frameFromSize, orientationMatrix, type CarFrame, type Orientation } from "./frame";
import { PLACEHOLDER_FRAME, PlaceholderCar } from "./PlaceholderCar";

/** show: 0 hidden … 1 shown (the rise); xray: 0 solid … 1 see-through (interior zones). */
export interface CarLook { show: number; xray: number }

type Mat = { m: THREE.MeshStandardMaterial; base: number; glass: boolean };

const XRAY = 0.12;
const tmp = new THREE.Color();

/** Replace every material with a neutral graphite study material; keeps brightness contrast, drops hue and textures. */
function restyle(root: THREE.Object3D): Mat[] {
  const out: Mat[] = [];
  const made = new Map<THREE.Material, THREE.MeshStandardMaterial>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = mesh.receiveShadow = false;
    const swap = (src: THREE.Material) => {
      const hit = made.get(src);
      if (hit) return hit;
      const name = `${src.name} ${mesh.name}`.toLowerCase();
      const glass = (src.transparent && src.opacity < 0.95) || /glass|window|windshield|windscreen|scheibe/.test(name);
      const col = (src as THREE.MeshStandardMaterial).color;
      let lum = 0.4;
      if (col) { tmp.copy(col); lum = 0.2126 * tmp.r + 0.7152 * tmp.g + 0.0722 * tmp.b; }
      const g = glass ? 0.02 : 0.035 + Math.pow(lum, 0.6) * 0.2;
      const m = new THREE.MeshStandardMaterial({
        color: new THREE.Color(g, g, g * 1.06), roughness: glass ? 0.08 : 0.5, metalness: glass ? 0 : 0.3,
        transparent: glass, opacity: glass ? 0.6 : 1, depthWrite: !glass, side: src.side,
      });
      made.set(src, m);
      out.push({ m, base: m.opacity, glass });
      return m;
    };
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(swap) : swap(mesh.material);
  });
  return out;
}

function useLook(root: MutableRefObject<THREE.Object3D | null>, look: MutableRefObject<CarLook>, key: unknown) {
  const mats = useRef<Mat[]>([]);
  const last = useRef({ show: -1, xray: -1 });
  useLayoutEffect(() => {
    if (!root.current) return;
    mats.current = restyle(root.current);
    last.current = { show: -1, xray: -1 };
    return () => { for (const s of mats.current) s.m.dispose(); mats.current = []; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(() => {
    const { show, xray } = look.current;
    if (Math.abs(show - last.current.show) < 0.002 && Math.abs(xray - last.current.xray) < 0.002) return;
    last.current = { show, xray };
    if (root.current) root.current.visible = show > 0.01;
    for (const s of mats.current) {
      const o = s.base * show * (1 - (1 - (s.glass ? 0.3 : XRAY)) * xray);
      const transparent = s.glass || o < 0.999;
      if (s.m.transparent !== transparent) { s.m.transparent = transparent; s.m.needsUpdate = true; }
      s.m.opacity = o;
      s.m.depthWrite = !s.glass && o > 0.6;
    }
  });
}

function Gltf({ url, orientation, look, onFrame }: { url: string; orientation: Orientation; look: MutableRefObject<CarLook>; onFrame: (f: CarFrame) => void }) {
  const { scene } = useGLTF(url);
  const ref = useRef<THREE.Group>(null);
  const prepared = useMemo(() => {
    const car = scene.clone(true);
    const rot = new THREE.Group();
    const m = orientationMatrix(orientation) ?? orientationMatrix(DEFAULT_ORIENTATION)!;
    rot.quaternion.setFromRotationMatrix(new THREE.Matrix4().set(m[0], m[1], m[2], 0, m[3], m[4], m[5], 0, m[6], m[7], m[8], 0, 0, 0, 0, 1));
    rot.add(car);
    rot.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(rot);
    const size = box.getSize(new THREE.Vector3());
    const s = size.x > 0 ? CAR_LENGTH / size.x : 1;
    const c = box.getCenter(new THREE.Vector3());
    const wrap = new THREE.Group();
    wrap.scale.setScalar(s);
    wrap.position.set(-c.x * s, -box.min.y * s, -c.z * s);
    wrap.add(rot);
    return { wrap, frame: frameFromSize([size.x * s, size.y * s, size.z * s]) };
  }, [scene, orientation]);
  useLook(ref, look, prepared);
  useLayoutEffect(() => { onFrame(prepared.frame); }, [prepared, onFrame]);
  return <group ref={ref}><primitive object={prepared.wrap} /></group>;
}

function Stand({ look, onFrame }: { look: MutableRefObject<CarLook>; onFrame: (f: CarFrame) => void }) {
  const ref = useRef<THREE.Group>(null);
  useLook(ref, look, "placeholder");
  useLayoutEffect(() => { onFrame(PLACEHOLDER_FRAME); }, [onFrame]);
  return <group ref={ref}><PlaceholderCar /></group>;
}

class Boundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { console.warn("[DefinitionCar] model failed, showing the stand-in car:", e.message); }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export function DefinitionCar({ url, orientation, look, onFrame }: {
  url: string | null; orientation?: Orientation; look: MutableRefObject<CarLook>; onFrame: (f: CarFrame) => void;
}) {
  const orient = useMemo<Orientation>(() => orientation ?? DEFAULT_ORIENTATION, [orientation?.up, orientation?.front]); // eslint-disable-line react-hooks/exhaustive-deps
  const stand = <Stand look={look} onFrame={onFrame} />;
  useEffect(() => { if (url) useGLTF.preload(url); }, [url]);
  if (!url) return stand;
  return (
    <Boundary key={url} fallback={stand}>
      <Suspense fallback={null}>
        <Gltf url={url} orientation={orient} look={look} onFrame={onFrame} />
      </Suspense>
    </Boundary>
  );
}

/** Quiet studio light for the graphite car: a soft sky, one key, one cool rim. No environment, no floor. */
export function QuietLight() {
  return (
    <>
      <hemisphereLight args={["#dfe5ee", "#000000", 0.6]} />
      <directionalLight position={[3, 6, 4]} intensity={1.6} />
      <directionalLight position={[-5, 3, -4]} intensity={1.1} color="#e8eef8" />
      <directionalLight position={[0, -2, 5]} intensity={0.25} />
    </>
  );
}
