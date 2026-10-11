// SAMPLE DATA for page 3 while the definition pipeline / API (D-048) is not ready. Shown on screen as "Sample data";
// the page switches to the live payload as soon as GET /api/definition returns ready: true. Nothing here is a BMW
// figure or a real citation: values are plausible placeholders and source ids are made up. Area keys name real
// requirement areas from Structure, so the stage steps (areas → drafted) split the right diamonds.
import type { CheckpointId } from "@/lib/types";
import type {
  Basis, DefinitionPayload, DefLink, EvidenceRef, LadderRow, Level, Requirement, RequirementDetail,
} from "@/lib/definition";
import type { ZoneDef } from "@/three/frame";

/** Copied from src/bmw_req/car_zones.py ZONES; the live payload carries its own. */
export const FIXTURE_ZONES: Record<string, ZoneDef> = {
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

const MODELS: DefinitionPayload["models"] = {
  "1 Series": { url: "/models/f70.glb", orientation: { up: "+y", front: "+z" }, attribution: "teenlin3, CC BY 4.0" },
  "5 Series": { url: "/models/g60.glb", orientation: { up: "+y", front: "-z" }, attribution: "akyolefe319, CC BY 4.0" },
  "7 Series": { url: "/models/g70.glb", orientation: { up: "+y", front: "+z" }, attribution: "NazhDesign, CC BY 4.0" },
};

const DOMAINS: DefinitionPayload["domains"] = [
  { key: "exterior", label: "Exterior", aspects: [] },
  { key: "interior", label: "Interior & comfort", aspects: [] },
  { key: "powertrain", label: "Powertrain & charging", aspects: [] },
  { key: "chassis", label: "Chassis & dynamics", aspects: [] },
  { key: "assist", label: "Driver assistance", aspects: [] },
  { key: "digital", label: "Infotainment & digital", aspects: [] },
  { key: "variants", label: "Variants & packages", aspects: [] },
  { key: "quality", label: "Design & quality perception", aspects: [] },
];

const RESOURCES: Record<string, string> = {
  energy: "Usable energy on board — what range, climate, performance and electronics all draw from",
  mass: "Vehicle weight — felt in range, acceleration, braking, handling and ride",
  thermal: "Heat the car can move — fast charging, sustained performance, cabin and seat climate",
  package: "Physical space in body and cabin — legroom, luggage, storage, battery height, roofline",
  attention: "Driver attention and screen/control real estate — displays, controls, warnings, assistance hand-over",
  aero: "Air resistance and wind noise — styling, wheels, mirrors versus range and quietness",
  acoustic: "Sound in the cabin — tyres, road, wind, powertrain versus quietness and audio",
  compute: "On-board computing and connectivity — assistance, voice, navigation, apps, updates",
};

const L = (value: number | null, text: string, basis: Basis, source_ids: string[] = [], note = ""): Level =>
  ({ value, text, basis, source_ids, note });
const gap = (note: string): Level => ({ value: null, text: "?", basis: "gap", source_ids: [], note });
const row = (line: string, market: string, r: Omit<LadderRow, "line" | "market">): LadderRow => ({ line, market, ...r });

type Base = Omit<Requirement, "version" | "state" | "change_note" | "evidence_count" | "assumptions" | "gaps"> &
  Partial<Pick<Requirement, "assumptions" | "gaps">>;

function req(b: Base, extra: Partial<Requirement> = {}): Requirement {
  const ids = new Set(b.ladder.flatMap((r) => [r.baseline, r.threshold, r.target, r.stretch].flatMap((l) => l?.source_ids ?? [])));
  return { version: 1, state: "held", change_note: null, evidence_count: ids.size + 3, assumptions: [], gaps: [], ...b, ...extra };
}

/* --------------------------------------------------------------------------------------------- requirements */
function requirements(cp: CheckpointId): Requirement[] {
  const jul = cp === "cp2";
  const out: Requirement[] = [
    req({
      key: "rq:highway-range:1", area_key: "ar:confident-real-world-range", area_title: "Confident real-world electric range",
      title: "Real-world highway range", statement: "Drivers reach their usual long-distance destination at motorway pace without planning an extra stop.",
      domain: "powertrain", aspects: ["range", "efficiency"], zones: ["underfloor", "charging"], lines: ["5 Series", "7 Series"],
      markets: ["US", "EU"], decision_type: "improve", today_status: "below rivals", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "Highway range at 120 km/h", unit: "km", direction: "higher", method: "Constant 120 km/h, 20 °C, climate on, new tyres", conditions: "Summer, dry road" },
      acceptance: [
        { criterion: "Range at 120 km/h", condition: "20 °C, climate on, 100 → 0 %", pass: "≥ target" },
        { criterion: "Range shown vs driven", condition: "Mixed motorway, 300 km", pass: "within 5 %" },
      ],
      ladder: [
        row("5 Series", "EU", { baseline: L(410, "410 km", "cited", ["S-2201"], "Independent 120 km/h test, today's car"),
          threshold: L(470, "470 km", "cited", ["S-2207", "S-2210"], "Two segment rivals measured in the same test"),
          target: L(540, "540 km", "projected", ["S-2215"], "Rival generation changes announced for 2027–28"),
          stretch: L(620, "620 km", "assumption", [], "Delighter: Munich → Paris without a stop"),
          recommended: "target", rationale: "Parity alone is overtaken before launch; the projected rival step sets the bar.",
          choice: { level: "target", rationale: "Long-distance EU drivers are the core; parity would date at launch.", actor: "Atahan (PM)", at: "2026-07-08T10:12:00Z" } }),
        row("5 Series", "US", { baseline: L(390, "390 km", "cited", ["S-2201"]), threshold: L(450, "450 km", "cited", ["S-2212"]),
          target: L(520, "520 km", "projected", ["S-2215"]), stretch: L(600, "600 km", "assumption"), recommended: "target",
          rationale: "Interstate distances between fast chargers in the South-West." }),
        row("7 Series", "US", { baseline: L(430, "430 km", "cited", ["S-2203"]), threshold: L(480, "480 km", "cited", ["S-2212"]),
          target: L(560, "560 km", "projected", ["S-2215"]), stretch: null, recommended: "target", rationale: "Flagship must not trail the 5 Series." }),
      ],
      assumptions: ["Rival announcements are delivered on time."],
    }),
    req({
      key: "rq:fast-charge:1", area_key: "ar:convenient-reliable-charging", area_title: "Convenient, reliable vehicle charging",
      title: "Quick top-up on a road trip", statement: "A coffee-length stop puts back enough range for the next leg.",
      domain: "powertrain", aspects: ["charging_speed"], zones: ["charging"], lines: ["1 Series", "5 Series", "7 Series"],
      markets: ["EU", "US", "CN"], decision_type: "improve", today_status: "parity", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "Charge 10 → 80 %", unit: "min", direction: "lower", method: "High-power charger, pre-conditioned battery", conditions: "25 °C ambient" },
      acceptance: [
        { criterion: "10 → 80 % time", condition: "≥ 300 kW charger, 25 °C", pass: "≤ target" },
        { criterion: "10 → 80 % time", condition: "−7 °C, navigation pre-conditioning", pass: "≤ target + 25 %" },
      ],
      ladder: [
        row("5 Series", "EU", { baseline: L(30, "30 min", "cited", ["S-3101"]), threshold: L(22, "22 min", "cited", ["S-3104"], "Segment median of current rivals"),
          target: jul ? L(16, "16 min", "projected", ["S-3110", "S-3118"], "JUL: a rival now shows 15 min in independent tests") : L(18, "18 min", "projected", ["S-3110"]),
          stretch: L(12, "12 min", "assumption", [], "Faster than a coffee"), recommended: "target", rationale: "Charging time is the most-cited road-trip pain." }),
        row("5 Series", "CN", { baseline: L(30, "30 min", "cited", ["S-3101"]), threshold: L(18, "18 min", "cited", ["S-3120"], "Local rivals"),
          target: L(14, "14 min", "projected", ["S-3121"]), stretch: L(10, "10 min", "assumption"), recommended: jul ? "stretch" : "target",
          rationale: "China rivals move fastest; the threshold is already higher there." }),
        row("1 Series", "EU", { baseline: gap("No public 10–80 % figure for today's 1 Series PHEV variants"), threshold: L(28, "28 min", "cited", ["S-3130"]),
          target: L(24, "24 min", "projected", ["S-3130"]), stretch: null, recommended: "threshold", rationale: "Compact buyers charge mostly at home." }),
      ],
      gaps: ["Today's 1 Series has no comparable fast-charge figure; research task opened."],
    }, jul ? { state: "changed", change_note: "Target 18 → 16 min (EU): a rival's independent 15-minute result became visible in July." } : {}),
    req({
      key: "rq:winter-range:1", area_key: "ar:confident-real-world-range", area_title: "Confident real-world electric range",
      title: "Winter range that holds up", statement: "Cold mornings don't cut the range so much that customers change their plans.",
      domain: "powertrain", aspects: ["range", "climate"], zones: ["underfloor"], lines: ["5 Series", "1 Series"], markets: ["EU"],
      decision_type: "improve", today_status: "unknown", horizon: "successor launch", horizon_year: 2029, kano: "must-be",
      metric: { name: "Range kept at −7 °C", unit: "% of summer range", direction: "higher", method: "Mixed cycle, cabin 21 °C", conditions: "Overnight cold soak" },
      acceptance: [{ criterion: "Range retention", condition: "−7 °C soak, cabin 21 °C", pass: "≥ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: gap("No winter test of today's car in the sources"), threshold: L(72, "72 %", "cited", ["S-4102"]),
          target: L(80, "80 %", "projected", ["S-4105"]), stretch: L(86, "86 %", "assumption"), recommended: "target", rationale: "Nordic and Alpine customers." }),
        row("1 Series", "EU", { baseline: gap("No winter test"), threshold: L(70, "70 %", "cited", ["S-4102"]), target: gap("No rival trend for compact PHEVs yet"),
          stretch: null, recommended: "threshold", rationale: "Until a trend is visible, parity is the honest bar." }),
      ],
      gaps: ["Baseline winter retention for today's 5 Series and 1 Series.", "Compact PHEV winter trend."],
    }),
    req({
      key: "rq:seat-cooling:1", area_key: "ar:effortless-climate-comfort", area_title: "Effortless climate comfort",
      title: "Seat feels cool fast after heat soak", statement: "Getting into a car parked in the sun, the seat feels cool before the first junction.",
      domain: "interior", aspects: ["seat_comfort", "climate"], zones: ["front_seats", "cabin"], lines: ["5 Series", "7 Series"], markets: ["US", "CN"],
      decision_type: "improve", today_status: "below rivals", horizon: "successor launch", horizon_year: 2029, kano: "attractive",
      metric: { name: "Time until seat feels cool", unit: "min", direction: "lower", method: "Panel of 12, ventilation max", conditions: "35 °C, 1 h sun soak" },
      acceptance: [
        { criterion: "Seat feels cool", condition: "35 °C, 1 h soak", pass: "≤ target for 10 of 12 testers" },
        { criterion: "Fan noise at max", condition: "Idle, windows up", pass: "not noticed over climate fan" },
      ],
      ladder: [
        row("5 Series", "US", { baseline: L(6, "6 min", "assumption", [], "Customer comments, no measurement"), threshold: L(4, "4 min", "cited", ["S-5101"]),
          target: L(2.5, "2.5 min", "projected", ["S-5104"]), stretch: L(1.5, "1.5 min", "assumption"), recommended: "target", rationale: "US South comments are explicit about this." }),
        row("7 Series", "CN", { baseline: L(5, "5 min", "assumption"), threshold: L(3, "3 min", "cited", ["S-5110"]), target: L(2, "2 min", "projected", ["S-5110"]),
          stretch: null, recommended: "target", rationale: "Chauffeur use: the rear seats count as much as the front." }),
      ],
    }),
    req({
      key: "rq:rear-comfort-cn:1", area_key: "ar:comfortable-space-access", area_title: "Keep comfortable space and access",
      title: "Stretch out in the rear seat", statement: "A rear passenger can cross their legs behind a tall driver on a long ride.",
      domain: "interior", aspects: ["rear_space", "seat_comfort"], zones: ["rear_seats"], lines: ["5 Series", "7 Series"], markets: ["CN"],
      decision_type: "keep", today_status: "parity", horizon: "successor launch", horizon_year: 2029, kano: "must-be",
      metric: { name: "Rear knee room", unit: "mm", direction: "higher", method: "Behind a 95th-percentile driver position", conditions: "Long-wheelbase body" },
      acceptance: [{ criterion: "Rear knee room", condition: "Driver seat set for 1.90 m", pass: "≥ target" }],
      ladder: [
        row("5 Series", "CN", { baseline: L(120, "120 mm", "cited", ["S-6101"]), threshold: L(135, "135 mm", "cited", ["S-6105"]),
          target: L(150, "150 mm", "projected", ["S-6106"]), stretch: L(170, "170 mm", "assumption"), recommended: "target", rationale: "LWB buyers compare on paper first." }),
        row("7 Series", "CN", { baseline: L(185, "185 mm", "cited", ["S-6102"]), threshold: L(180, "180 mm", "cited", ["S-6107"]),
          target: L(195, "195 mm", "projected", ["S-6107"]), stretch: null, recommended: "threshold", rationale: "Already ahead; keep, don't spend." }),
      ],
    }),
    req({
      key: "rq:bottles:1", area_key: "ar:everyday-cabin-storage", area_title: "Practical storage for everyday belongings",
      title: "Bottles fit upright within reach", statement: "Driver and passenger can each put a large water bottle somewhere it stays upright and reachable.",
      domain: "interior", aspects: ["storage"], zones: ["front_seats"], lines: ["1 Series", "5 Series"], markets: ["US", "EU"],
      decision_type: "improve", today_status: "below rivals", horizon: "near term", horizon_year: 2028, kano: "must-be",
      metric: { name: "Upright 0.75 l bottles within reach", unit: "bottles", direction: "higher", method: "Count, front row", conditions: "Doors closed, armrest down" },
      acceptance: [{ criterion: "Bottles that stay upright", condition: "Front row, through a roundabout", pass: "≥ target" }],
      ladder: [
        row("5 Series", "US", { baseline: L(2, "2", "cited", ["S-7101"]), threshold: L(4, "4", "cited", ["S-7104"]), target: L(4, "4", "projected", ["S-7104"]),
          stretch: L(6, "6", "assumption"), recommended: "threshold", rationale: "Parity is enough; no trend beyond it." }),
        row("1 Series", "EU", { baseline: L(2, "2", "cited", ["S-7102"]), threshold: L(3, "3", "cited", ["S-7105"]), target: L(4, "4", "assumption"),
          stretch: null, recommended: "threshold", rationale: "Compact package." }),
      ],
    }),
    req({
      key: "rq:quiet-cabin:1", area_key: "ar:refined-cabin-character", area_title: "Keep the refined cabin character",
      title: "Quiet cabin at motorway speed", statement: "Passengers talk at normal voice at 130 km/h on rough asphalt.",
      domain: "interior", aspects: ["cabin_noise"], zones: ["cabin"], lines: ["5 Series", "7 Series"], markets: ["EU", "US"],
      decision_type: "keep", today_status: "ahead", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "Interior noise at 130 km/h", unit: "dB(A)", direction: "lower", method: "Front passenger ear, rough asphalt", conditions: "Winter tyres" },
      acceptance: [{ criterion: "Interior noise", condition: "130 km/h, rough asphalt, winter tyres", pass: "≤ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: L(66, "66 dB(A)", "cited", ["S-8101"]), threshold: L(66, "66 dB(A)", "cited", ["S-8103"]),
          target: L(64, "64 dB(A)", "projected", ["S-8105"]), stretch: L(62, "62 dB(A)", "assumption"), recommended: "target", rationale: "Quiet EVs reset expectations." }),
        row("7 Series", "US", { baseline: L(62, "62 dB(A)", "cited", ["S-8102"]), threshold: L(63, "63 dB(A)", "cited", ["S-8104"]),
          target: L(62, "62 dB(A)", "projected"), stretch: null, recommended: "threshold", rationale: "Hold the lead." }),
      ],
    }),
    req({
      key: "rq:voice-first-time:1", area_key: "ar:understandable-digital-features", area_title: "Digital features customers can understand",
      title: "Voice understands the first time", statement: "Common requests (climate, destination, music) work on the first try in natural phrasing.",
      domain: "digital", aspects: ["voice"], zones: ["cockpit"], lines: ["1 Series", "5 Series", "7 Series"], markets: ["US", "EU", "CN"],
      decision_type: "improve", today_status: "below rivals", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "Requests done on first try", unit: "%", direction: "higher", method: "Scripted set of 40 everyday requests", conditions: "Native speakers, road noise 100 km/h" },
      acceptance: [
        { criterion: "First-try success", condition: "40 requests, 100 km/h", pass: "≥ target" },
        { criterion: "Response time", condition: "Online", pass: "≤ 1.5 s" },
      ],
      ladder: [
        row("5 Series", "US", { baseline: L(68, "68 %", "cited", ["S-9101"]), threshold: L(80, "80 %", "cited", ["S-9104"]),
          target: L(90, "90 %", "projected", ["S-9108"]), stretch: L(96, "96 %", "assumption"), recommended: "target", rationale: "LLM assistants raise the floor fast." }),
        row("5 Series", "CN", { baseline: L(72, "72 %", "cited", ["S-9102"]), threshold: L(88, "88 %", "cited", ["S-9110"]),
          target: L(94, "94 %", "projected", ["S-9110"]), stretch: null, recommended: "target", rationale: "Local rivals lead." }),
      ],
    }),
    req({
      key: "rq:displays-sun:1", area_key: "ar:legible-driving-information", area_title: "Legible displays and driving information",
      title: "Displays readable in direct sun", statement: "Navigation and speed stay readable at a glance with low sun behind the driver.",
      domain: "digital", aspects: ["display_ui", "visibility"], zones: ["cockpit"], lines: ["5 Series", "7 Series"], markets: ["US", "EU"],
      decision_type: "improve", today_status: "parity", horizon: "near term", horizon_year: 2028, kano: "must-be",
      metric: { name: "Readable at a glance", unit: "% of testers", direction: "higher", method: "Low sun from behind, polarised sunglasses", conditions: "Midday summer" },
      acceptance: [{ criterion: "Readable at a glance", condition: "Low sun, polarised glasses", pass: "≥ target" }],
      ladder: [
        row("5 Series", "US", { baseline: gap("No glare study of today's car"), threshold: L(85, "85 %", "assumption", [], "Expert estimate"),
          target: L(95, "95 %", "projected", ["S-9201"]), stretch: null, recommended: "target", rationale: "Bigger glass surfaces make glare more visible." }),
      ],
      gaps: ["Glare study of today's displays."],
    }),
    req({
      key: "rq:hands-off:1", area_key: "ar:dependable-driving-parking-assistance", area_title: "Dependable driving and parking assistance",
      title: "Hands-off on the motorway", statement: "On a clear motorway the driver can take hands off the wheel at normal traffic speed.",
      domain: "assist", aspects: ["highway_assist", "automated_driving"], zones: ["assist"], lines: ["5 Series", "7 Series"], markets: ["US", "EU", "CN"],
      decision_type: "improve", today_status: "parity", horizon: "successor launch", horizon_year: 2029, kano: "attractive",
      metric: { name: "Hands-off up to", unit: "km/h", direction: "higher", method: "Where permitted, mapped motorway", conditions: "Dry, daylight" },
      acceptance: [
        { criterion: "Hands-off speed", condition: "Mapped motorway", pass: "≥ target" },
        { criterion: "Take-over requests", condition: "100 km of motorway", pass: "≤ 1 unplanned" },
      ],
      ladder: [
        row("5 Series", "US", { baseline: L(130, "130 km/h", "cited", ["S-9301"]), threshold: L(130, "130 km/h", "cited", ["S-9304"]),
          target: L(145, "145 km/h", "projected", ["S-9306"]), stretch: L(160, "160 km/h", "assumption"), recommended: "target", rationale: "Rivals announce higher speeds." }),
        row("5 Series", "CN", { baseline: gap("Not offered in China today; no comparable figure"), threshold: L(120, "120 km/h", "cited", ["S-9310"]),
          target: gap("Local rules for 2029 not yet visible"), stretch: null, recommended: "threshold", rationale: "Rules drive this market." }),
      ],
      gaps: ["China hands-off rules for 2029."],
    }),
    req({
      key: "rq:overtake:1", area_key: "ar:refined-powertrain-character", area_title: "Keep refined powertrain character",
      title: "Effortless overtaking", statement: "A lorry on a country road can be passed briskly without planning.",
      domain: "chassis", aspects: ["performance"], zones: ["powertrain"], lines: ["1 Series", "5 Series"], markets: ["EU", "US"],
      decision_type: "keep", today_status: "ahead", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "80 → 120 km/h", unit: "s", direction: "lower", method: "Full load, 50 % charge", conditions: "Dry road" },
      acceptance: [{ criterion: "80 → 120 km/h", condition: "Four occupants, 50 % charge", pass: "≤ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: L(3.4, "3.4 s", "cited", ["S-9401"]), threshold: L(3.6, "3.6 s", "cited", ["S-9403"]),
          target: L(3.3, "3.3 s", "projected"), stretch: null, recommended: "threshold", rationale: "Already strong; mass spent here costs range." }),
        row("1 Series", "EU", { baseline: L(4.6, "4.6 s", "cited", ["S-9402"]), threshold: L(4.5, "4.5 s", "cited", ["S-9404"]),
          target: L(4.2, "4.2 s", "projected"), stretch: null, recommended: "threshold", rationale: "Hold parity." }),
      ],
    }),
    req({
      key: "rq:broken-roads:1", area_key: "ar:quiet-smooth-ride", area_title: "Keep the quiet, smooth ride",
      title: "Composed ride on broken roads", statement: "Patched city streets and expansion joints don't shake the cabin.",
      domain: "chassis", aspects: ["ride_comfort"], zones: ["chassis"], lines: ["5 Series", "7 Series"], markets: ["US", "CN"],
      decision_type: "improve", today_status: "below rivals", horizon: "successor launch", horizon_year: 2029, kano: "performance",
      metric: { name: "Ride rating on broken roads", unit: "/ 10", direction: "higher", method: "Expert panel, fixed route", conditions: "Largest optional wheels" },
      acceptance: [{ criterion: "Panel rating", condition: "Fixed route, largest wheels", pass: "≥ target" }],
      ladder: [
        row("5 Series", "US", { baseline: L(6.8, "6.8", "cited", ["S-9501"]), threshold: L(7.5, "7.5", "cited", ["S-9503"]),
          target: L(8.2, "8.2", "projected"), stretch: L(8.8, "8.8", "assumption"), recommended: "target", rationale: "Comments on US roads are consistent." }),
      ],
    }),
    req({
      key: "rq:big-wheels:1", area_key: "ar:suitable-tires-wheels", area_title: "Tires and wheels suited to use",
      title: "Large wheels without a range penalty", statement: "Choosing the bigger design wheels doesn't noticeably shorten the trip.",
      domain: "exterior", aspects: ["wheels_tyres", "exterior_design"], zones: ["chassis", "front"], lines: ["5 Series", "7 Series"], markets: ["US", "EU"],
      decision_type: "improve", today_status: "below rivals", horizon: "successor launch", horizon_year: 2029, kano: "attractive",
      metric: { name: "Range lost with the largest wheels", unit: "%", direction: "lower", method: "Versus base wheels, same test", conditions: "120 km/h" },
      acceptance: [{ criterion: "Range loss", condition: "Largest vs base wheel, 120 km/h", pass: "≤ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: L(9, "9 %", "cited", ["S-9601"]), threshold: L(7, "7 %", "cited", ["S-9603"]),
          target: L(5, "5 %", "projected", ["S-9605"]), stretch: L(3, "3 %", "assumption"), recommended: "target", rationale: "Wheels sell the car; range keeps it." }),
      ],
    }),
    req({
      key: "rq:luggage-four:1", area_key: "ar:everyday-cabin-storage", area_title: "Practical storage for everyday belongings",
      title: "Luggage for four on a road trip", statement: "Four carry-on cases and soft bags fit without folding a seat.",
      domain: "interior", aspects: ["cargo_space"], zones: ["trunk"], lines: ["1 Series", "5 Series"], markets: ["EU"],
      decision_type: "keep", today_status: "parity", horizon: "successor launch", horizon_year: 2029, kano: "must-be",
      metric: { name: "Carry-on cases in the boot", unit: "cases", direction: "higher", method: "IATA carry-on size, upright or flat", conditions: "Under the parcel shelf" },
      acceptance: [{ criterion: "Cases that fit", condition: "Parcel shelf in place", pass: "≥ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: L(4, "4", "cited", ["S-9701"]), threshold: L(4, "4", "cited", ["S-9702"]), target: L(5, "5", "assumption"),
          stretch: null, recommended: "threshold", rationale: "Parity; space competes with the rear seat." }),
      ],
    }),
    req({
      key: "rq:comfort-unbundled:1", area_key: "ar:clear-equipment-availability", area_title: "Clear equipment and configuration choices",
      title: "Comfort features without the top package", statement: "Customers can add the comfort feature they want without buying a bundle they don't.",
      domain: "variants", aspects: ["trims_packages", "equipment_availability"], zones: ["cabin"], lines: ["1 Series", "5 Series", "7 Series"], markets: ["US", "EU"],
      decision_type: "improve", today_status: "below rivals", horizon: "near term", horizon_year: 2028, kano: "performance",
      metric: { name: "Comfort features orderable on their own", unit: "%", direction: "higher", method: "Share of the comfort list", conditions: "Configurator, mid trim" },
      acceptance: [{ criterion: "Standalone share", condition: "Mid trim, each market's configurator", pass: "≥ target" }],
      ladder: [
        row("5 Series", "US", { baseline: L(35, "35 %", "cited", ["S-9801"]), threshold: L(50, "50 %", "cited", ["S-9803"]),
          target: L(65, "65 %", "projected"), stretch: null, recommended: "target", rationale: "Bundles are a frequent complaint in comments." }),
      ],
    }),
  ];
  if (jul) {
    out.push(req({
      key: "rq:route-charging:1", area_key: "ar:convenient-reliable-charging", area_title: "Convenient, reliable vehicle charging",
      title: "Route planner you can trust", statement: "The planned arrival charge and charger availability match what happens on the trip.",
      domain: "digital", aspects: ["charging_planning", "navigation"], zones: ["cockpit", "charging"], lines: ["5 Series", "7 Series"], markets: ["EU", "US"],
      decision_type: "emerging", today_status: "parity", horizon: "successor launch", horizon_year: 2029, kano: "attractive",
      metric: { name: "Arrival charge error", unit: "%-points", direction: "lower", method: "Planned vs actual at destination", conditions: "300 km mixed motorway" },
      acceptance: [{ criterion: "Arrival charge error", condition: "300 km, live traffic", pass: "≤ target" }],
      ladder: [
        row("5 Series", "EU", { baseline: gap("No public test of today's planner accuracy"), threshold: L(6, "6 pts", "cited", ["S-9901"]),
          target: L(3, "3 pts", "projected", ["S-9903"]), stretch: null, recommended: "target", rationale: "New in July: research flagged planner trust." }),
      ],
      gaps: ["Accuracy of today's route planner."],
    }, { state: "new", change_note: "New in July: an emerging area on charging-stop planning." }));
  }
  return out;
}

/* --------------------------------------------------------------------------------------------- links */
function links(cp: CheckpointId): DefLink[] {
  const jul = cp === "cp2";
  let n = 0;
  const lk = (a: string, b: string, relation: DefLink["relation"], via: string, strength: number, rationale: string,
              extra: Partial<DefLink> = {}): DefLink =>
    ({ id: `lk${++n}`, a, b, relation, via, strength, direction: relation === "enables" ? "a_to_b" : "mutual", rationale, state: "held", review: null, ...extra });
  const out: DefLink[] = [
    lk("rq:highway-range:1", "rq:overtake:1", "conflicts", "mass", 2, "More battery for range adds weight that blunts the overtaking response."),
    lk("rq:highway-range:1", "rq:big-wheels:1", "conflicts", "aero", 3, "Large wheels raise drag at motorway speed, the very range this target measures.",
       { review: { verdict: "confirmed", actor: "Atahan (PM)", rationale: "Seen in every rival test; decide both rungs together.", at: "2026-07-08T10:20:00Z" } }),
    lk("rq:fast-charge:1", "rq:highway-range:1", "enables", "energy", 2, "Short stops make a given range feel like enough for a road trip."),
    lk("rq:winter-range:1", "rq:highway-range:1", "synergy", "energy", 3, "The same efficiency work lifts both summer and winter range."),
    lk("rq:seat-cooling:1", "rq:winter-range:1", "competes_for", "energy", 1, "Climate comfort draws on the same on-board energy."),
    lk("rq:fast-charge:1", "rq:seat-cooling:1", "competes_for", "thermal", 1, "Both ask the thermal system for capacity in summer heat."),
    lk("rq:quiet-cabin:1", "rq:big-wheels:1", "conflicts", "acoustic", 2, "Wider, larger tyres add road roar."),
    lk("rq:quiet-cabin:1", "rq:broken-roads:1", "synergy", "acoustic", 2, "Isolating impacts also quietens the cabin on rough roads."),
    lk("rq:broken-roads:1", "rq:big-wheels:1", "conflicts", "mass", 2, "Low-profile tyres pass more of every impact into the cabin."),
    lk("rq:hands-off:1", "rq:voice-first-time:1", "enables", "attention", 2, "With hands and eyes freed, voice becomes the natural way to control the car."),
    lk("rq:voice-first-time:1", "rq:displays-sun:1", "synergy", "attention", 1, "Both keep glances short."),
    lk("rq:rear-comfort-cn:1", "rq:luggage-four:1", "competes_for", "package", 3, "Rear knee room and boot length share the same body length."),
    lk("rq:bottles:1", "rq:displays-sun:1", "competes_for", "package", 1, "Console storage and the display cluster share the centre stack."),
  ];
  if (jul) out.push(lk("rq:route-charging:1", "rq:fast-charge:1", "enables", "compute", 2,
    "Pre-conditioning on the way to a planned charger is what delivers the quick top-up.", { state: "new" }));
  return out;
}

/** Connected components over links with strength ≥ 2 that are not removed (the API computes the same). */
export function bundlesOf(ls: DefLink[]): DefinitionPayload["bundles"] {
  const parent = new Map<string, string>();
  const find = (k: string): string => { let p = parent.get(k) ?? k; if (p !== k) { p = find(p); parent.set(k, p); } return p; };
  for (const l of ls) {
    if (l.strength < 2 || l.review?.verdict === "removed") continue;
    const a = find(l.a), b = find(l.b);
    if (!parent.has(l.a)) parent.set(l.a, l.a);
    if (!parent.has(l.b)) parent.set(l.b, l.b);
    if (a !== b) parent.set(a, b);
  }
  const groups = new Map<string, string[]>();
  for (const k of parent.keys()) { const r = find(k); groups.set(r, [...(groups.get(r) ?? []), k]); }
  return [...groups.values()].filter((g) => g.length > 1).map((keys, i) => ({ id: `b${i + 1}`, keys: keys.sort(), reason: "Strongly linked" }));
}

export function fixtureFor(cp: CheckpointId): DefinitionPayload {
  const ls = links(cp);
  return {
    checkpoint: cp, ready: true,
    runs: { define: null, specify: null, couple: null },
    domains: DOMAINS, resources: RESOURCES, zones: FIXTURE_ZONES, models: MODELS,
    requirements: requirements(cp), links: ls, bundles: bundlesOf(ls),
  };
}

/** Requirement detail for the sample: evidence rows for every source id its ladder cites (made-up placeholders). */
export function fixtureDetail(r: Requirement): RequirementDetail {
  const ids = [...new Set(r.ladder.flatMap((row) => [row.baseline, row.threshold, row.target, row.stretch].flatMap((l) => l?.source_ids ?? [])))];
  const evidence: EvidenceRef[] = ids.map((id, i) => ({
    id, kind: i % 3 === 0 ? "research" : i % 3 === 1 ? "web" : "reference",
    text: `Sample source ${id}: placeholder for a cited test or announcement behind “${r.metric?.name ?? r.title}”.`,
    url: null, tier: i % 2 ? "T2" : "T1", published: "2026-03-01", relation: "supports", quote: null,
  }));
  return { ...r, evidence, facts: [], area: { key: r.area_key, title: r.area_title, need: r.statement }, history: [] };
}
