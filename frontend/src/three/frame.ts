// Pure car-frame math (no React, no WebGL) so it can be unit-tested.
//
// Normalised car frame: f along the length (-1 rear … +1 front), r across (-1 left … +1 right, seen from the
// driver's seat), h up (0 ground … 1 roof). After normalisation every car sits in world space with
// front = +X, up = +Y, centred on the origin, wheels on y = 0. The right-hand side is front × up = +Z.

export type Vec3 = [number, number, number];
export type Axis = "+x" | "-x" | "+y" | "-y" | "+z" | "-z";
export type Orientation = { up: Axis; front: Axis };

export type ZoneDef = { label: string; pos: Vec3; view: Vec3; dist: number };

/** World-space frame of a normalised car. L = half-length, W = half-width, H = height (roof). */
export type CarFrame = { L: number; W: number; H: number };

export const DEFAULT_ORIENTATION: Orientation = { up: "+y", front: "+z" };

export const WORLD_FRONT: Vec3 = [1, 0, 0];
export const WORLD_UP: Vec3 = [0, 1, 0];
export const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
/** right = front × up → +Z in world. */
export const WORLD_RIGHT: Vec3 = cross(WORLD_FRONT, WORLD_UP);

export function axisVec(a: Axis): Vec3 {
  const s = a[0] === "-" ? -1 : 1;
  const i = a[1] === "x" ? 0 : a[1] === "y" ? 1 : 2;
  const v: Vec3 = [0, 0, 0];
  v[i] = s;
  return v;
}

/**
 * Row-major 3×3 rotation that maps the model's local front → world +X, local up → world +Y and
 * local right (front × up) → world right (+Z). Rows are front, up, right (an orthonormal basis, det = +1).
 * Returns null when front and up are parallel (invalid orientation).
 */
export function orientationMatrix(o: Orientation): number[] | null {
  const f = axisVec(o.front);
  const u = axisVec(o.up);
  const r = cross(f, u);
  if (r[0] === 0 && r[1] === 0 && r[2] === 0) return null;
  // world = M · local, with M rows expressed so that M·f = X, M·u = Y, M·r = Z (r maps to WORLD_RIGHT = +Z).
  return [...f, ...u, ...r];
}

/** Frame from the normalised bounding-box size (world units, after rotation + scale). */
export function frameFromSize(size: Vec3): CarFrame {
  return { L: size[0] / 2, W: size[2] / 2, H: size[1] };
}

/** A normalised zone position [f, r, h] → world [x, y, z]. */
export function zoneToWorld(pos: Vec3, frame: CarFrame): Vec3 {
  const [f, r, h] = pos;
  return [
    f * frame.L * WORLD_FRONT[0] + r * frame.W * WORLD_RIGHT[0],
    h * frame.H,
    f * frame.L * WORLD_FRONT[2] + r * frame.W * WORLD_RIGHT[2],
  ];
}

/** A view direction [f, r, h] in the frame → unit world vector (not scaled by the car's proportions). */
export function frameDir(view: Vec3): Vec3 {
  const [f, r, h] = view;
  const v: Vec3 = [f * WORLD_FRONT[0] + r * WORLD_RIGHT[0], h, f * WORLD_FRONT[2] + r * WORLD_RIGHT[2]];
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

export type CameraPose = { eye: Vec3; target: Vec3 };

/** Overview: front-left three-quarter, slightly elevated. */
export const OVERVIEW = { target: [0, 0, 0.42] as Vec3, view: [0.85, -0.95, 0.42] as Vec3, dist: 2.75 };

export function poseFor(zone: Pick<ZoneDef, "pos" | "view" | "dist"> | null, frame: CarFrame): CameraPose {
  const z = zone ?? { pos: OVERVIEW.target, view: OVERVIEW.view, dist: OVERVIEW.dist };
  const target = zoneToWorld(z.pos, frame);
  const d = frameDir(z.view);
  const k = z.dist * frame.L;
  return { target, eye: [target[0] + d[0] * k, target[1] + d[1] * k, target[2] + d[2] * k] };
}

/** Zones whose focus turns the body into x-ray. */
export const INTERIOR_ZONES = new Set(["cockpit", "front_seats", "cabin", "rear_seats"]);
