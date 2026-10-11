// Page 3 leaves the scan volume behind: it sinks and shrinks out of view, then unmounts (its DOM labels and pick
// targets go with it). Leaving page 3 remounts it below and it rises back into place. Wraps Scene's universe group.
// Structure's area diamonds do not sink: page 3 lifts its own copies of them out of the volume (StageLayer), so the
// originals are hidden (not unmounted) for as long as page 3 shows; their DOM labels are hidden by definition.css.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import type * as THREE from "three";

const DROP = 2.6, SHRINK = 0.4, DUR = 0.9;   // units, scale loss, seconds
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function VolumeSink({ sunk, children }: { sunk: boolean; children: ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const t = useRef(sunk ? 1 : 0);
  const [gone, setGone] = useState(sunk);
  const hidDiamonds = useRef(false);
  // the story moves play like page 2's morph, which ignores reduced motion too: the motion is the explanation
  // (only the decorative CSS pulses honour it)
  const reduced = false;
  useEffect(() => { if (!sunk) setGone(false); }, [sunk]);
  useFrame((_, dt) => {
    const g = ref.current;
    if (!g) return;
    const goal = sunk ? 1 : 0;
    if (t.current !== goal) {
      const step = reduced ? 1 : dt / DUR;
      t.current = goal > t.current ? Math.min(goal, t.current + step) : Math.max(goal, t.current - step);
    }
    if (hidDiamonds.current !== sunk) {
      hidDiamonds.current = sunk;
      g.traverse((o) => { if ((o as THREE.Mesh).geometry?.type === "OctahedronGeometry") o.visible = !sunk; });
    }
    const e = ease(t.current);
    g.position.y = -DROP * e;
    g.scale.setScalar(1 - SHRINK * e);
    if (t.current === 1 && sunk && !gone) setGone(true);
  });
  return <group ref={ref}>{!gone && children}</group>;
}
