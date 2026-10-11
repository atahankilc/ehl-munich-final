"""Plain-language labels and enums — the single source for the API (and, later, `ui/common.py`).

The data model keeps codes (G60, E1, basic …); the API returns codes and `/api/meta` ships these maps so the
frontend renders the words a PM reads.
"""

DEFAULT_PM = "Atahan (PM)"

PRIORITIES = ["Must", "Should", "Could"]
PRIORITY_RANK = {"Must": 0, "Should": 1, "Could": 2}
STATUSES = ["proposed", "challenged", "approved", "deferred", "rejected"]
REVIEW_STATUSES = ("proposed", "challenged")
DECIDED_STATUSES = ("approved", "rejected", "deferred")
SOURCE_KINDS = ["feedback", "study", "sales", "option_list", "web", "reference"]
MARKETS = ["US", "EU", "CN", "RoW"]

VEHICLE_NAMES = {"F70": "1 Series", "G60": "5 Series", "G68": "5 Series LWB", "G70": "7 Series"}
MARKET_SHORT = {"US": "USA", "EU": "Europe", "CN": "China", "RoW": "Rest of world"}
MARKET_NAMES = {"US": "United States", "EU": "Europe", "CN": "China", "RoW": "Rest of world"}

EVIDENCE_LABELS = {"E1": "Strong evidence", "E2": "Good evidence", "E3": "Limited evidence", "E4": "Assumption only"}
EVIDENCE_HELP = {"E1": "20+ customer comments from 2+ channels, plus study or cited web evidence",
                 "E2": "15+ comments, or comments plus study/web evidence",
                 "E3": "a few comments, or study/web evidence only",
                 "E4": "no direct evidence — forward-looking assumption"}
KANO_LABELS = {"basic": "Expected", "performance": "Differentiator", "delighter": "Delighter"}
HORIZON_LABELS = {"today": "Needed today", "at_successor_launch": "Needed by successor launch"}
STATUS_LABELS = {"proposed": "To review", "challenged": "Challenged", "approved": "Approved", "deferred": "Deferred",
                 "rejected": "Rejected"}
PROPOSAL_KINDS = {"priority": "Priority changes", "content": "Content edits", "link_finding": "Evidence links",
                  "new_requirement": "New requirements", "extend": "Merge into existing", "status": "Status"}
PROPOSAL_STATES = {"open": "Open", "accepted": "Accepted", "rejected": "Rejected", "superseded": "Superseded"}
VERDICTS = {"upheld": "You're right", "partially_upheld": "Partly right", "not_upheld": "The evidence holds"}
FIT_TYPES = {"brand": {"label": "Brand", "effect": "gate"},
             "segment": {"label": "Segment", "effect": "shown"},
             "market": {"label": "Market", "effect": "score modifier"},
             "feasibility": {"label": "Feasibility", "effect": "context"}}
FIT_RESULTS = ["pass", "warn", "fail", "overridden"]
REALIZATION = {"carry_over": "Carry over", "platform_wide": "Platform-wide", "derivative_specific": "Derivative-specific",
               "market_variant": "Market variant", "package": "Package"}
ACTOR_TYPES = {"ai": "AI", "system": "System · no AI", "human": "Product manager"}
TRUST_TIERS = {"T1": "Official / primary source", "T2": "Established press / analysts", "T3": "Forums / blogs"}
FACTOR_HELP = {
    "customer_voice": "Severity-weighted share of this market's in-scope feedback that supports the requirement.",
    "satisfaction_gap": "Customer study: item weak vs. other items (or strong, for must-not-lose).",
    "market_volume": "BMW sales of the derivative in the market + 2030 momentum (relative only, Q-015).",
    "competitive_pressure": "Cited competitor advantages / review criticism in this market (trust-tier weighted).",
    "future_relevance": "Horizon, Kano drift towards basic, cited trends and expectations.",
    "portfolio_leverage": "How many derivative × market targets benefit; platform-wide realization.",
}

# Enums the PM may set via PATCH /api/requirements/{id} (kano_drift is free text in the data).
ENUMS = {"horizon": list(HORIZON_LABELS), "kano_class": list(KANO_LABELS), "effort": ["S", "M", "L"]}

# 3D car view defaults (were in ui/car3d.py)
DEFAULT_MARKET = {"F70": "EU", "G60": "US", "G68": "CN", "G70": "US"}
OPTION_SOURCE = {"G68": "G60"}   # no China price list: the LWB shows the 5 Series list (assumption, labelled)
OPTIONS_PER_ZONE = 8
AVAILABILITY = {"standard": "standard", "optional": "option", "package": "in a package"}
EQUIPMENT_NOTE = "German price list, Jul 2026 — US/China equipment assumed comparable (assumption, not evidence)."


def car(d) -> str:
    return VEHICLE_NAMES.get(str(d), str(d))


def mkt(m) -> str:
    return MARKET_SHORT.get(str(m), str(m))


def plain_target(d, m) -> str:
    """'G60', 'US' → '5 Series · USA'."""
    return f"{car(d)} · {mkt(m)}"
