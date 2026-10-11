// Dev harness for the 3D CarStage: http://127.0.0.1:5173/lab.html?zone=cockpit&model=/models/g60.glb&up=+y&front=+z
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/mona-sans";
import { CarStage, type Hotspot } from "@/three/CarStage";
import type { Axis, Orientation, ZoneDef } from "@/three/frame";
import { LAB_ZONES } from "./zones";
import "./lab.css";

const AXES: Axis[] = ["+x", "-x", "+y", "-y", "+z", "-z"];

const HOTSPOTS: Hotspot[] = [
  { zone: "cockpit", count: 4, top: "Must" },
  { zone: "rear_seats", count: 3, top: "Must", aiOnly: true },
  { zone: "trunk", count: 2, top: "Should" },
  { zone: "charging", count: 5, top: "Must" },
  { zone: "assist", count: 2, top: "Should", aiOnly: true },
  { zone: "front", count: 1, top: "Could" },
  { zone: "cabin", count: 3, top: "Should" },
  { zone: "chassis", count: 1, top: "Could", aiOnly: true },
  { zone: "doors", count: 2, top: "Could" },
];

function readParams() {
  const q = new URLSearchParams(location.search);
  const ax = (v: string | null, d: Axis): Axis => (v && AXES.includes(v.replace(" ", "+") as Axis) ? (v.replace(" ", "+") as Axis) : d);
  return {
    zone: q.get("zone"),
    model: q.get("model"),
    up: ax(q.get("up"), "+y"),
    front: ax(q.get("front"), "+z"),
    mode: q.get("mode") === "compact" ? ("compact" as const) : ("showroom" as const),
  };
}

function writeParams(p: Record<string, string | null>) {
  const q = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(p)) {
    if (v) q.set(k, v);
    else q.delete(k);
  }
  history.replaceState(null, "", `?${q.toString()}`);
}

function Lab() {
  const init = readParams();
  const [zone, setZone] = useState<string | null>(init.zone && LAB_ZONES[init.zone] ? init.zone : null);
  const [model, setModel] = useState<string>(init.model ?? "");
  const [draft, setDraft] = useState<string>(init.model ?? "");
  const [orientation, setOrientation] = useState<Orientation>({ up: init.up, front: init.front });
  const [hover, setHover] = useState<string | null>(null);
  const [mode, setMode] = useState(init.mode);

  useEffect(() => {
    writeParams({ zone, model: model || null, up: orientation.up, front: orientation.front, mode: mode === "compact" ? "compact" : null });
  }, [zone, model, orientation, mode]);

  const zones: Record<string, ZoneDef> = LAB_ZONES;

  return (
    <div className="lab">
      <div className={mode === "compact" ? "lab-stage lab-stage--compact" : "lab-stage"}>
        <CarStage
          modelUrl={model || null}
          orientation={orientation}
          zones={zones}
          hotspots={HOTSPOTS}
          selectedZone={zone}
          onSelectZone={setZone}
          hoverZone={hover}
          mode={mode}
        />
      </div>
      <div className="lab-strip">
        <div className="lab-zones">
          <button className={zone === null ? "on" : ""} onClick={() => setZone(null)}>
            Overview
          </button>
          {Object.entries(zones).map(([id, z]) => (
            <button
              key={id}
              className={zone === id ? "on" : ""}
              onClick={() => setZone(id)}
              onMouseEnter={() => setHover(id)}
              onMouseLeave={() => setHover(null)}
            >
              {z.label}
            </button>
          ))}
        </div>
        <form
          className="lab-model"
          onSubmit={(e) => {
            e.preventDefault();
            setModel(draft.trim());
          }}
        >
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="/models/g60.glb (empty = placeholder)" aria-label="Model URL" />
          <label>
            up
            <select value={orientation.up} onChange={(e) => setOrientation((o) => ({ ...o, up: e.target.value as Axis }))}>
              {AXES.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
          <label>
            front
            <select value={orientation.front} onChange={(e) => setOrientation((o) => ({ ...o, front: e.target.value as Axis }))}>
              {AXES.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
          <label>
            <input type="checkbox" checked={mode === "compact"} onChange={(e) => setMode(e.target.checked ? "compact" : "showroom")} /> compact
          </label>
          <button type="submit">Load</button>
        </form>
      </div>
    </div>
  );
}

createRoot(document.getElementById("lab")!).render(
  <StrictMode>
    <Lab />
  </StrictMode>,
);
