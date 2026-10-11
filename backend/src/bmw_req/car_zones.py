"""Car zones for the 3D view (D-039): where on the car a requirement or a piece of today's equipment lives.

Deterministic keyword rules, no LLM. Zones are positioned in a normalised car frame — `f` along the length
(-1 rear … +1 front), `r` across (-1 left … +1 right, seen from the driver's seat), `h` up (0 ground … 1 roof) —
so one zone table serves every model. Each 3D model only needs its file and axes in `MODELS_GLTF`.

The 3D models are third-party CC BY models (originally from Sketchfab), not BMW data, served locally from
`$DATA_DIR/models/` — no requirement text goes to a third party (AGENTS rule 1).
"""

from __future__ import annotations

from pathlib import Path

# ------------------------------------------------------------------------------------------------ zones
# pos: anchor of the hotspot; view: direction the camera looks from (same frame), dist: camera distance in half-lengths.
ZONES: dict[str, dict] = {
    "front":      {"label": "Front, lights & sensors", "pos": (0.97, 0.0, 0.38), "view": (1.0, 0.35, 0.35), "dist": 2.2},
    "powertrain": {"label": "Powertrain",              "pos": (0.70, 0.0, 0.66), "view": (0.8, -0.5, 0.7), "dist": 2.3},
    "assist":     {"label": "Assistance systems",      "pos": (0.38, 0.0, 0.93), "view": (0.9, 0.5, 0.6), "dist": 2.4},
    "cockpit":    {"label": "Cockpit & displays",      "pos": (0.22, -0.32, 0.72), "view": (0.25, -0.9, 0.75), "dist": 1.7},
    "front_seats": {"label": "Front seats & storage",  "pos": (-0.02, -0.35, 0.60), "view": (-0.1, -1.0, 0.65), "dist": 1.8},
    "cabin":      {"label": "Cabin & climate",         "pos": (-0.08, 0.0, 0.97), "view": (0.15, -0.6, 1.0), "dist": 2.1},
    "rear_seats": {"label": "Rear cabin",              "pos": (-0.38, 0.32, 0.60), "view": (-0.3, 1.0, 0.6), "dist": 1.8},
    "doors":      {"label": "Doors & access",          "pos": (0.08, 1.0, 0.48), "view": (0.1, 1.0, 0.3), "dist": 2.0},
    "chassis":    {"label": "Chassis, ride & steering", "pos": (0.64, 1.0, 0.20), "view": (0.55, 1.0, 0.25), "dist": 1.9},
    "charging":   {"label": "Range & charging",        "pos": (-0.66, 1.0, 0.62), "view": (-0.6, 1.0, 0.4), "dist": 2.0},
    "trunk":      {"label": "Trunk & luggage",         "pos": (-0.97, 0.0, 0.62), "view": (-1.0, 0.35, 0.55), "dist": 2.1},
    "underfloor": {"label": "Battery & energy",        "pos": (-0.05, 0.0, 0.14), "view": (0.2, 1.0, 0.18), "dist": 2.2},
}

# First match wins; checked against the lower-cased requirement title (then description).
KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("front", ("parking", "clearance", "surrounding view")),
    ("rear_seats", ("rear-seat", "rear seat", "rear cabin", "chauffeur", "privacy", "video meeting", "rear passenger")),
    ("trunk", ("luggage", "trunk", "tailgate", "boot", "cargo", "load and retrieve")),
    ("charging", ("charg", "range", "battery")),
    ("doors", ("door", "entry", "keyless", "comfort access")),
    ("chassis", ("ride", "steering", "handling", "deceleration", "brak", "suspension", "road disturbance")),
    ("front", ("exterior", "headlight")),
    ("assist", ("assistance", "assist", "highway", "lane", "cruise")),
    ("front_seats", ("front-seat", "front seat", "belongings", "storage", "cupholder")),
    ("cabin", ("quiet", "cabin", "thermal", "climate", "material", "craftsmanship", "reflection", "noise")),
    ("powertrain", ("sound", "fuel", "power", "start-stop", "engine", "journey starts")),
    ("cockpit", ("voice", "display", "screen", "navigation", "digital", "control", "information", "app")),
]
CATEGORY_ZONE = {
    "Infotainment & Digital": "cockpit", "Interior": "cockpit", "Driver Assistance (as experienced)": "assist",
    "Driving Experience": "chassis", "Powertrain (as experienced)": "powertrain", "Range & Charging": "charging",
    "Exterior": "front", "Comfort & Space": "cabin", "Design & Quality Perception": "cabin",
    "Variants & Packages": "front",
}

# Option-list names (DE price list, English names) → zone; then the option's category.
OPTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("rear_seats", ("rear", "executive lounge", "sun blind", "passenger screen", "theatre")),
    ("trunk", ("tailgate", "through-loading", "luggage", "trunk", "towbar", "trailer")),
    ("charging", ("charg", "cable", "heat pump")),
    ("doors", ("door", "comfort access", "soft-close", "key")),
    ("chassis", ("wheel", "tyre", "tire", "suspension", "steering", "brake", "chassis", "adaptive m")),
    ("front", ("light", "laser", "kidney", "paint", "shadow line", "bumper", "spoiler", "mirror", "parking")),
    ("front_seats", ("seat", "armrest", "storage", "wireless charging tray")),
    ("cabin", ("climate", "glazing", "panoramic glass", "sky lounge", "ambient", "leather", "trim", "upholstery",
               "sound system", "headliner", "veganza", "merino", "heat comfort")),
    ("cockpit", ("display", "idrive", "head-up", "screen", "navigation", "digital", "dab", "radio", "smartphone",
                 "touch", "panoramic vision", "steering wheel")),
]

# ------------------------------------------------------------------------------------------------ 3D models
# Self-hosted glTF/GLB files (third-party CC BY models, downloaded once into `$DATA_DIR/models/`, git-ignored), rendered
# locally in the browser: nothing about requirements leaves the machine. `orientation` names the model's world axes
# as loaded in three.js (after the files' Sketchfab Z-up→Y-up root matrix); derived from the Sketchfab-viewer calibration
# (5 Series nose at +Y, 1/7 Series at −Y in Z-up) and checked by rendering. Kept as data so the viewer never hardcodes a model.
MODELS_GLTF: dict[str, dict] = {
    "F70": {"file": "f70", "name": "Bmw-1-series 2025", "author": "teenlin3", "license": "CC BY 4.0",
            "source_url": "https://sketchfab.com/3d-models/bmw-1-series-2025-aca5bc34dd014aff89eef647124b485d",
            "orientation": {"up": "+y", "front": "+z"}},
    "G60": {"file": "g60", "name": "i5", "author": "akyolefe319", "license": "CC BY 4.0",
            "source_url": "https://sketchfab.com/3d-models/i5-1e52b6b8821040c2aea037b7c029a20d",
            "orientation": {"up": "+y", "front": "-z"}},
    "G70": {"file": "g70", "name": "2023 BMW I7 G70", "author": "NazhDesign", "license": "CC BY 4.0",
            "source_url": "https://sketchfab.com/3d-models/2023-bmw-i7-g70-07937cca69864dfe9f4b4ed235fc32f7",
            "orientation": {"up": "+y", "front": "+z"}},
}
MODELS_GLTF["G68"] = {**MODELS_GLTF["G60"], "shared_with": "G60",
                      "stand_in": "Shown on the 5 Series model; the China long-wheelbase body is longer."}


def model_url(vehicle: str, models_dir: Path | None = None) -> str | None:
    """URL path of the vehicle's 3D model if its file is present: `<file>.glb`, else `<file>/scene.gltf`, else None."""
    m = MODELS_GLTF.get(vehicle)
    if m is None:
        return None
    if models_dir is None:
        from bmw_req.config import get_settings

        models_dir = get_settings().data_dir / "models"
    if (models_dir / f"{m['file']}.glb").is_file():
        return f"/models/{m['file']}.glb"
    if (models_dir / m["file"] / "scene.gltf").is_file():
        return f"/models/{m['file']}/scene.gltf"
    return None


# Public BMW configurator (Germany) per derivative — the current car as customers configure it today.
CONFIGURATOR_URL = {"F70": "https://configure.bmw.de/de_DE/configure/F70",
                    "G60": "https://configure.bmw.de/de_DE/configure/G60",
                    "G70": "https://configure.bmw.de/de_DE/configure/G70"}


def _match(text: str, rules: list[tuple[str, tuple[str, ...]]]) -> str | None:
    t = (text or "").lower()
    for zone, words in rules:
        if any(w in t for w in words):
            return zone
    return None


def requirement_zone(title: str, category: str | None = None, description: str | None = None) -> str:
    """Zone for a requirement: keyword rules on the title, then on the description, then the category default."""
    return (_match(title, KEYWORD_RULES) or CATEGORY_ZONE.get(category or "")
            or _match(description or "", KEYWORD_RULES) or "cabin")


def option_zone(name_en: str, category: str | None = None) -> str:
    return _match(name_en, OPTION_RULES) or CATEGORY_ZONE.get(category or "", "cabin")
