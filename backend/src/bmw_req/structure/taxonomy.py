"""The shared aspect space (D-043): one fixed list of customer-facing aspects under the ten categories. Every source —
comments, customer study items, research, options — is mapped onto it, so clusters, evidence links and requirements
join on `aspect` instead of free text."""

import re
from typing import Literal

ASPECTS: dict[str, list[str]] = {
    "Exterior": ["exterior_design", "lighting", "doors_tailgate", "wheels_tyres", "paint_body", "mirrors_wipers"],
    "Interior": ["interior_design", "materials", "storage", "controls_layout", "interior_lighting"],
    "Comfort & Space": ["seat_comfort", "front_space", "rear_space", "cargo_space", "ride_comfort", "cabin_noise",
                        "climate", "ingress_egress"],
    "Infotainment & Digital": ["display_ui", "voice", "phone_projection", "navigation", "audio", "app_remote",
                               "connectivity_ota", "rear_entertainment"],
    "Driving Experience": ["handling_steering", "performance", "braking", "driving_modes", "visibility"],
    "Powertrain (as experienced)": ["powertrain_refinement", "transmission", "efficiency", "engine_sound"],
    "Range & Charging": ["range", "charging_speed", "charging_hardware", "charging_planning"],
    "Driver Assistance (as experienced)": ["parking_aids", "cameras", "highway_assist", "safety_warnings",
                                           "automated_driving"],
    "Variants & Packages": ["equipment_availability", "trims_packages", "powertrain_choice", "body_variants"],
    "Design & Quality Perception": ["build_quality", "squeaks_rattles", "durability_wear", "brand_image"],
}
CATEGORIES = list(ASPECTS)
# the ten categories as a schema type (same values and order as ASPECTS; was pipeline.extract.Category)
Category = Literal[
    "Exterior", "Interior", "Comfort & Space", "Infotainment & Digital", "Driving Experience",
    "Powertrain (as experienced)", "Range & Charging", "Driver Assistance (as experienced)",
    "Variants & Packages", "Design & Quality Perception",
]
ALL_ASPECTS = [a for v in ASPECTS.values() for a in v] + ["other"]
CATEGORY_OF = {a: c for c, v in ASPECTS.items() for a in v}

NATURES = ["like", "defect", "usability", "performance_gap", "missing_feature", "support_question"]
# Backward-compatible columns used by scoring/findings (D-024 vocabulary)
FEEDBACK_TYPE = {"like": "like", "defect": "defect", "usability": "difficult_to_use", "performance_gap": "complaint",
                 "missing_feature": "want", "support_question": "difficult_to_use"}
IMPACTS = ["none", "annoyance", "impaired", "unusable", "safety"]
SEVERITY = {"none": "low", "annoyance": "low", "impaired": "medium", "unusable": "high", "safety": "high"}
CONTEXTS = ["cold", "heat", "long_distance", "city_parking", "family", "chauffeured", "home_charging", "public_charging"]


def taxonomy_text() -> str:
    """The aspect list as prompt text (part of the cacheable prefix)."""
    return "\n".join(f"- {c}: {', '.join(a)}" for c, a in ASPECTS.items()) + "\n- (anything else): other"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_ok(quote: str, text: str) -> bool:
    """Quote is a contiguous span of the text (whitespace and case normalized)."""
    return bool(quote.strip()) and _norm(quote) in _norm(text)
