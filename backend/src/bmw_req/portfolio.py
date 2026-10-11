"""Portfolio configuration: which derivative × market combinations are requirement targets, and how
derivatives group into vehicle lines (AGENTS rule 7: data/config, never code paths).

A target exists where BMW sells the derivative (sales_volumes.xlsx) — G68 is the China long-wheelbase
5 Series, so China targets of the 5 Series line are G68, the rest G60.
"""

LINES = {
    "1 Series": {"derivatives": ["F70"], "segment": "premium compact"},
    "5 Series": {"derivatives": ["G60", "G68"], "segment": "upper mid-size / executive"},
    "7 Series": {"derivatives": ["G70"], "segment": "luxury"},
}

TARGETS = {
    "F70": ["EU", "RoW"],
    "G60": ["US", "EU", "RoW"],
    "G68": ["CN"],
    "G70": ["US", "CN", "EU", "RoW"],
}

# Successor launch assumption for the 3–5 year horizon (D-012); used in prompts and the UI only.
SUCCESSOR_LAUNCH = {"F70": "~2031", "G60": "~2030", "G68": "~2030", "G70": "~2029–2030"}

# Targets the PM app shows first (demo slice D-021: best-evidenced US, China variant, Europe). UI default only.
FOCUS_TARGETS = [("G60", "US"), ("G68", "CN"), ("G60", "EU")]

MIN_MARKET_VERBATIMS = 30   # below this a market has no usable verbatim base (CN: 0, G70 EU: ~19) → evidence gap


def line_of(derivative: str) -> str:
    for line, cfg in LINES.items():
        if derivative in cfg["derivatives"]:
            return line
    raise KeyError(derivative)


def all_targets() -> list[tuple[str, str]]:
    return [(d, m) for d, ms in TARGETS.items() for m in ms]
