// Copied from backend/src/bmw_req/car_zones.py ZONES (pos/view = [f, r, h]). Lab-only fixture; the app gets zones from the API.
import type { ZoneDef } from "@/three/frame";

export const LAB_ZONES: Record<string, ZoneDef> = {
  front: { label: "Front, lights & sensors", pos: [0.97, 0.0, 0.38], view: [1.0, 0.35, 0.35], dist: 2.2 },
  powertrain: { label: "Powertrain", pos: [0.7, 0.0, 0.66], view: [0.8, -0.5, 0.7], dist: 2.3 },
  assist: { label: "Assistance systems", pos: [0.38, 0.0, 0.93], view: [0.9, 0.5, 0.6], dist: 2.4 },
  cockpit: { label: "Cockpit & displays", pos: [0.22, -0.32, 0.72], view: [0.25, -0.9, 0.75], dist: 1.7 },
  front_seats: { label: "Front seats & storage", pos: [-0.02, -0.35, 0.6], view: [-0.1, -1.0, 0.65], dist: 1.8 },
  cabin: { label: "Cabin & climate", pos: [-0.08, 0.0, 0.97], view: [0.15, -0.6, 1.0], dist: 2.1 },
  rear_seats: { label: "Rear cabin", pos: [-0.38, 0.32, 0.6], view: [-0.3, 1.0, 0.6], dist: 1.8 },
  doors: { label: "Doors & access", pos: [0.08, 1.0, 0.48], view: [0.1, 1.0, 0.3], dist: 2.0 },
  chassis: { label: "Chassis, ride & steering", pos: [0.64, 1.0, 0.2], view: [0.55, 1.0, 0.25], dist: 1.9 },
  charging: { label: "Range & charging", pos: [-0.66, 1.0, 0.62], view: [-0.6, 1.0, 0.4], dist: 2.0 },
  trunk: { label: "Trunk & luggage", pos: [-0.97, 0.0, 0.62], view: [-1.0, 0.35, 0.55], dist: 2.1 },
  underfloor: { label: "Battery & energy", pos: [-0.05, 0.0, 0.14], view: [0.2, 1.0, 0.18], dist: 2.2 },
};
