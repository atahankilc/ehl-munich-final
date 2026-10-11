// Procedural stand-in car (no assets): satin dark-grey body, dark glasshouse, four wheels.
// Already in the normalised world frame: front = +X, up = +Y, length ≈ 4.8, wheels on y = 0.
import { useMemo } from "react";
import * as THREE from "three";
import type { CarFrame } from "./frame";

export const PLACEHOLDER_FRAME: CarFrame = { L: 2.4, W: 0.95, H: 1.44 };

const WHEEL_X = 1.46;
const WHEEL_R = 0.355;
const ARCH_R = 0.44;

function bodyShape(): THREE.Shape {
  const s = new THREE.Shape();
  s.moveTo(-2.3, 0.3);
  // bottom, rear arch, front arch
  s.lineTo(-WHEEL_X - ARCH_R, 0.3);
  s.absarc(-WHEEL_X, 0.3, ARCH_R, Math.PI, 0, true);
  s.lineTo(WHEEL_X - ARCH_R, 0.3);
  s.absarc(WHEEL_X, 0.3, ARCH_R, Math.PI, 0, true);
  s.lineTo(2.28, 0.3);
  // front fascia → bonnet
  s.quadraticCurveTo(2.42, 0.32, 2.42, 0.56);
  s.quadraticCurveTo(2.41, 0.78, 2.14, 0.86);
  s.quadraticCurveTo(1.4, 0.95, 0.78, 0.99);
  // beltline → boot lid
  s.lineTo(-1.7, 1.01);
  s.quadraticCurveTo(-2.26, 1.0, -2.36, 0.88);
  s.quadraticCurveTo(-2.44, 0.6, -2.4, 0.4);
  s.quadraticCurveTo(-2.38, 0.3, -2.3, 0.3);
  return s;
}

function glassShape(): THREE.Shape {
  const s = new THREE.Shape();
  s.moveTo(0.86, 0.93);
  s.quadraticCurveTo(0.32, 1.36, -0.12, 1.4);
  s.quadraticCurveTo(-0.6, 1.43, -1.02, 1.39);
  s.quadraticCurveTo(-1.62, 1.3, -1.95, 0.97);
  s.lineTo(0.86, 0.93);
  return s;
}

function extrude(shape: THREE.Shape, depth: number, bevel: number) {
  const g = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelThickness: bevel,
    bevelSize: bevel * 0.9,
    bevelSegments: 6,
    curveSegments: 32,
  });
  g.translate(0, 0, -depth / 2);
  g.computeVertexNormals();
  return g;
}

export function PlaceholderCar() {
  const geo = useMemo(
    () => ({
      body: extrude(bodyShape(), 1.62, 0.13),
      glass: extrude(glassShape(), 1.3, 0.12),
      tyre: new THREE.CylinderGeometry(WHEEL_R, WHEEL_R, 0.25, 40, 1),
      rim: new THREE.CylinderGeometry(WHEEL_R * 0.72, WHEEL_R * 0.72, 0.02, 40, 1),
    }),
    [],
  );
  const mat = useMemo(
    () => ({
      paint: new THREE.MeshPhysicalMaterial({
        color: "#3a3f48",
        metalness: 0.55,
        roughness: 0.38,
        clearcoat: 1,
        clearcoatRoughness: 0.12,
        envMapIntensity: 1.25,
      }),
      glass: new THREE.MeshPhysicalMaterial({ color: "#05070a", metalness: 0.9, roughness: 0.06, envMapIntensity: 1.6 }),
      tyre: new THREE.MeshStandardMaterial({ color: "#0b0c0e", roughness: 0.92, metalness: 0 }),
      rim: new THREE.MeshStandardMaterial({ color: "#7d838e", roughness: 0.28, metalness: 1, envMapIntensity: 1.4 }),
      front: new THREE.MeshBasicMaterial({ color: "#dfe9ff", toneMapped: false }),
      rear: new THREE.MeshBasicMaterial({ color: "#d4252f", toneMapped: false }),
    }),
    [],
  );

  const wheels: [number, number][] = [
    [WHEEL_X, 1],
    [WHEEL_X, -1],
    [-WHEEL_X, 1],
    [-WHEEL_X, -1],
  ];

  return (
    <group name="placeholder-car">
      <mesh name="body" geometry={geo.body} material={mat.paint} />
      <mesh name="glass" geometry={geo.glass} material={mat.glass} />
      {wheels.map(([x, side]) => (
        <group key={`${x}${side}`} position={[x, WHEEL_R, side * 0.8]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh geometry={geo.tyre} material={mat.tyre} />
          <mesh geometry={geo.rim} material={mat.rim} position={[0, side * 0.13, 0]} />
        </group>
      ))}
      {/* light signatures */}
      {[1, -1].map((side) => (
        <mesh key={`h${side}`} material={mat.front} position={[2.535, 0.7, side * 0.6]} rotation={[0, 0, 0.35]}>
          <boxGeometry args={[0.02, 0.035, 0.42]} />
        </mesh>
      ))}
      <mesh material={mat.rear} position={[-2.545, 0.8, 0]}>
        <boxGeometry args={[0.02, 0.03, 1.5]} />
      </mesh>
    </group>
  );
}
