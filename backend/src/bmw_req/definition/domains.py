"""Requirement definition config (D-048): vehicle domains, car zones and shared resources per aspect.

Deterministic, no LLM. Everything joins on the extract-v4 aspect space (`structure/taxonomy.py`):
- DOMAINS group the aspects the way BMW groups a requirement list (Exterior / Interior / Powertrain / Driver
  assistance / …). Data, not code (rule 7) — a requirement's domain is the domain of its primary aspect.
- ASPECT_ZONE puts an aspect on the car (zones in `car_zones.ZONES`) for the 3D view.
- RESOURCES are the customer-level budgets requirements compete for or share (energy, mass, cabin space, …). Two
  requirements that draw on the same resource are a *candidate* coupling; the `couple` stage judges whether it is
  real. A resource is the "via" of a link — it explains a trade-off without stating an engineering spec.
"""

from __future__ import annotations

from bmw_req.structure.taxonomy import ALL_ASPECTS

DOMAINS: list[dict] = [
    {"key": "exterior", "label": "Exterior",
     "aspects": ["exterior_design", "lighting", "doors_tailgate", "wheels_tyres", "paint_body", "mirrors_wipers"]},
    {"key": "interior", "label": "Interior & comfort",
     "aspects": ["interior_design", "materials", "storage", "interior_lighting", "seat_comfort", "front_space",
                 "rear_space", "cargo_space", "cabin_noise", "climate", "ingress_egress"]},
    {"key": "powertrain", "label": "Powertrain & charging",
     "aspects": ["powertrain_refinement", "transmission", "efficiency", "engine_sound", "range", "charging_speed",
                 "charging_hardware", "charging_planning", "powertrain_choice"]},
    {"key": "chassis", "label": "Chassis & dynamics",
     "aspects": ["handling_steering", "performance", "braking", "driving_modes", "ride_comfort"]},
    {"key": "assist", "label": "Driver assistance",
     "aspects": ["parking_aids", "cameras", "highway_assist", "safety_warnings", "automated_driving", "visibility"]},
    {"key": "digital", "label": "Infotainment & digital",
     "aspects": ["display_ui", "controls_layout", "voice", "phone_projection", "navigation", "audio", "app_remote",
                 "connectivity_ota", "rear_entertainment"]},
    {"key": "variants", "label": "Variants & packages",
     "aspects": ["equipment_availability", "trims_packages", "body_variants"]},
    {"key": "quality", "label": "Design & quality perception",
     "aspects": ["build_quality", "squeaks_rattles", "durability_wear", "brand_image"]},
]
DOMAIN_OF: dict[str, str] = {a: d["key"] for d in DOMAINS for a in d["aspects"]}
DOMAIN_LABEL: dict[str, str] = {d["key"]: d["label"] for d in DOMAINS}

ASPECT_ZONE: dict[str, str] = {
    "exterior_design": "front", "lighting": "front", "doors_tailgate": "doors", "wheels_tyres": "chassis",
    "paint_body": "front", "mirrors_wipers": "front",
    "interior_design": "cabin", "materials": "cabin", "storage": "front_seats", "interior_lighting": "cabin",
    "seat_comfort": "front_seats", "front_space": "front_seats", "rear_space": "rear_seats", "cargo_space": "trunk",
    "cabin_noise": "cabin", "climate": "cabin", "ingress_egress": "doors",
    "powertrain_refinement": "powertrain", "transmission": "powertrain", "efficiency": "underfloor",
    "engine_sound": "powertrain", "range": "underfloor", "charging_speed": "charging", "charging_hardware": "charging",
    "charging_planning": "cockpit", "powertrain_choice": "powertrain",
    "handling_steering": "chassis", "performance": "powertrain", "braking": "chassis", "driving_modes": "powertrain",
    "ride_comfort": "chassis",
    "parking_aids": "front", "cameras": "assist", "highway_assist": "assist", "safety_warnings": "assist",
    "automated_driving": "assist", "visibility": "cabin",
    "display_ui": "cockpit", "controls_layout": "cockpit", "voice": "cockpit", "phone_projection": "cockpit",
    "navigation": "cockpit", "audio": "cabin", "app_remote": "cockpit", "connectivity_ota": "cockpit",
    "rear_entertainment": "rear_seats",
    "equipment_availability": "cabin", "trims_packages": "cabin", "body_variants": "rear_seats",
    "build_quality": "cabin", "squeaks_rattles": "cabin", "durability_wear": "cabin", "brand_image": "front",
    "other": "cabin",
}

# Customer-level shared budgets. Each aspect lists the resources it draws on (strongest first).
RESOURCES: dict[str, str] = {
    "energy": "Usable energy on board — what range, climate, performance and electronics all draw from",
    "mass": "Vehicle weight — felt in range, acceleration, braking, handling and ride",
    "thermal": "Heat the car can move — fast charging, sustained performance, cabin and seat climate",
    "package": "Physical space in body and cabin — legroom, luggage, storage, battery height, roofline",
    "attention": "Driver attention and screen/control real estate — displays, controls, warnings, assistance hand-over",
    "aero": "Air resistance and wind noise — styling, wheels, mirrors versus range and quietness",
    "acoustic": "Sound in the cabin — tyres, road, wind, powertrain versus quietness and audio",
    "compute": "On-board computing and connectivity — assistance, voice, navigation, apps, updates",
}
ASPECT_RESOURCES: dict[str, list[str]] = {
    "exterior_design": ["aero", "package"], "lighting": ["energy"], "doors_tailgate": ["package"],
    "wheels_tyres": ["aero", "mass", "acoustic"], "paint_body": [], "mirrors_wipers": ["aero", "acoustic"],
    "interior_design": ["package", "attention"], "materials": ["mass"], "storage": ["package"],
    "interior_lighting": ["energy"], "seat_comfort": ["package", "thermal"],
    "front_space": ["package"], "rear_space": ["package", "mass"], "cargo_space": ["package"],
    "cabin_noise": ["acoustic", "mass", "aero"], "climate": ["thermal", "energy"], "ingress_egress": ["package"],
    "powertrain_refinement": ["acoustic"], "transmission": [], "efficiency": ["energy", "mass", "aero"],
    "engine_sound": ["acoustic"], "range": ["energy", "mass", "package", "aero"],
    "charging_speed": ["thermal", "energy"], "charging_hardware": ["package"], "charging_planning": ["compute"],
    "powertrain_choice": ["package", "mass"],
    "handling_steering": ["mass"], "performance": ["energy", "thermal", "mass"], "braking": ["mass", "thermal"],
    "driving_modes": ["energy"], "ride_comfort": ["mass", "acoustic"],
    "parking_aids": ["compute"], "cameras": ["compute", "attention"], "highway_assist": ["compute", "attention", "energy"],
    "safety_warnings": ["attention"], "automated_driving": ["compute", "attention", "energy"],
    "visibility": ["package", "attention"],
    "display_ui": ["attention", "compute", "package"], "controls_layout": ["attention", "package"],
    "voice": ["compute", "attention"], "phone_projection": ["attention", "compute"], "navigation": ["compute", "attention"],
    "audio": ["acoustic", "energy", "package"], "app_remote": ["compute"], "connectivity_ota": ["compute"],
    "rear_entertainment": ["package", "energy", "compute"],
    "equipment_availability": [], "trims_packages": [], "body_variants": ["package", "mass"],
    "build_quality": [], "squeaks_rattles": ["acoustic"], "durability_wear": [], "brand_image": [],
    "other": [],
}

# Classic customer-level trade-offs between primary aspects (unordered). `couple` always judges such pairs, even when
# a requirement's neighbour cap is full — they are the conflicts a PM most needs to see.
TENSIONS: dict[frozenset, str] = {frozenset(k): v for k, v in [
    (("range", "handling_steering"), "mass"), (("range", "performance"), "energy"), (("range", "exterior_design"), "aero"),
    (("range", "rear_space"), "package"), (("range", "cargo_space"), "package"), (("range", "ride_comfort"), "mass"),
    (("charging_speed", "range"), "energy"), (("performance", "efficiency"), "energy"), (("wheels_tyres", "cabin_noise"), "acoustic"),
    (("wheels_tyres", "ride_comfort"), "acoustic"), (("wheels_tyres", "range"), "aero"), (("wheels_tyres", "efficiency"), "aero"),
    (("exterior_design", "rear_space"), "package"), (("exterior_design", "visibility"), "package"),
    (("exterior_design", "ingress_egress"), "package"), (("display_ui", "controls_layout"), "attention"),
    (("display_ui", "safety_warnings"), "attention"), (("highway_assist", "safety_warnings"), "attention"),
    (("ride_comfort", "handling_steering"), "mass"), (("climate", "range"), "energy"), (("audio", "cabin_noise"), "acoustic"),
    (("rear_space", "cargo_space"), "package"), (("body_variants", "handling_steering"), "mass"),
]}

assert set(ASPECT_ZONE) == set(ALL_ASPECTS) == set(ASPECT_RESOURCES), "aspect config out of sync with taxonomy"
assert all(len(k) == 2 and k <= set(ALL_ASPECTS) and v in RESOURCES for k, v in TENSIONS.items()), "bad TENSIONS entry"
assert set(DOMAIN_OF) == set(ALL_ASPECTS) - {"other"}, "every aspect needs exactly one domain"


def domain_for(aspects: list[str]) -> str:
    """Domain of the primary (first known) aspect; 'variants' when none is known."""
    return next((DOMAIN_OF[a] for a in aspects if a in DOMAIN_OF), "variants")


def zones_for(aspects: list[str]) -> list[str]:
    """Distinct car zones of the aspects, primary first."""
    out: list[str] = []
    for a in aspects:
        z = ASPECT_ZONE.get(a)
        if z and z not in out:
            out.append(z)
    return out or ["cabin"]


def shared_resources(a: list[str], b: list[str]) -> list[str]:
    """Resources both aspect lists draw on, in RESOURCES order — the candidate 'via' of a coupling."""
    ra = {r for x in a for r in ASPECT_RESOURCES.get(x, [])}
    rb = {r for x in b for r in ASPECT_RESOURCES.get(x, [])}
    return [r for r in RESOURCES if r in ra and r in rb]
