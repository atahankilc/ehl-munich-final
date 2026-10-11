// While the agent classifies, each comment it just read flashes with an expanding ring at its place in the galaxy.
// Fed by /api/structure/activity `recent` (comments classified in the last few seconds).
import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const LIFE = 1.8; // seconds a pulse lives
const MAX = 600;

const VERT = /* glsl */ `
attribute float aBorn; uniform float uNow, uScale;
varying float vAge;
void main() {
  vAge = clamp((uNow - aBorn) / ${LIFE.toFixed(1)}, 0.0, 1.0);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = (aBorn < 0.0 ? 0.0 : uScale * (0.6 + vAge * 2.4)) / -mv.z;
}`;
const FRAG = /* glsl */ `
varying float vAge;
void main() {
  float r = length(gl_PointCoord - 0.5);
  float ring = smoothstep(0.5, 0.44, r) * smoothstep(0.30, 0.38, r);
  float core = smoothstep(0.22, 0.0, r) * (1.0 - vAge);
  float a = (ring * 0.9 + core) * (1.0 - vAge);
  if (a < 0.01) discard;
  gl_FragColor = vec4(1.0, 1.0, 1.0, a);
}`;

export function ClassifyPulse({ ids, posOf, dpr }: { ids: number[] | undefined; posOf: (id: number) => [number, number, number] | null; dpr: number }) {
  const born = useRef(new Map<number, number>());
  const clock = useRef(0);
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(MAX * 3), 3));
    g.setAttribute("aBorn", new THREE.BufferAttribute(new Float32Array(MAX).fill(-1), 1));
    return g;
  }, []);
  const mat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uNow: { value: 0 }, uScale: { value: 30 * dpr } },
  }), [dpr]);

  // stagger new arrivals over ~1.5 s so a batch of 20 reads as the agent moving through them
  useEffect(() => {
    if (!ids?.length) return;
    let k = 0;
    for (const id of ids) {
      if (!born.current.has(id)) born.current.set(id, clock.current + (k++ % 20) * 0.075);
    }
  }, [ids]);

  useFrame((_, dt) => {
    clock.current += dt;
    mat.uniforms.uNow.value = clock.current;
    const pos = geom.getAttribute("position") as THREE.BufferAttribute, b = geom.getAttribute("aBorn") as THREE.BufferAttribute;
    let i = 0;
    for (const [id, t] of born.current) {
      if (clock.current - t > LIFE) { born.current.delete(id); continue; }
      const p = posOf(id);
      if (!p || i >= MAX) continue;
      pos.setXYZ(i, p[0], p[1], p[2]); b.setX(i, t); i++;
    }
    for (let j = i; j < MAX; j++) b.setX(j, -1);
    pos.needsUpdate = true; b.needsUpdate = true;
    geom.setDrawRange(0, i);
  });

  return <points geometry={geom} material={mat} frustumCulled={false} />;
}
