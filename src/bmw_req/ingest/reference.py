"""Minimal reference rows the ingest needs (D-021). Markets and models are config, not code paths
(AGENTS rule 7). Platforms, plants, production and market profiles come later from the cited seed docs."""

import json
import sqlite3

EUROPE = [
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE",
    "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK",
]

MARKETS = [
    ("EU", "Europe", EUROPE),
    ("US", "United States", ["US"]),
    ("CN", "China", ["CN"]),
    ("RoW", "Rest of world", ["*"]),
]

BRANDS = [("BMW", "BMW", "BMW Group")]

# (id, brand, line, body)
VEHICLE_MODELS = [
    ("F70", "BMW", "1 Series", "hatchback"),
    ("G60", "BMW", "5 Series", "sedan"),
    ("G68", "BMW", "5 Series", "sedan, long wheelbase (China)"),
    ("G70", "BMW", "7 Series", "sedan"),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO brand (id, name, brand_group) VALUES (?, ?, ?)", BRANDS
    )
    conn.executemany(
        "INSERT OR IGNORE INTO market (code, name, countries_json) VALUES (?, ?, ?)",
        [(code, name, json.dumps(countries)) for code, name, countries in MARKETS],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO vehicle_model (id, brand_id, line, body) VALUES (?, ?, ?, ?)", VEHICLE_MODELS
    )


def country_to_market(conn: sqlite3.Connection) -> callable:
    """Build a country → market-code lookup from the `market` rows; '*' is the catch-all."""
    exact, fallback = {}, None
    for row in conn.execute("SELECT code, countries_json FROM market"):
        for c in json.loads(row["countries_json"]):
            if c == "*":
                fallback = row["code"]
            else:
                exact[c] = row["code"]
    return lambda country: exact.get(country, fallback)
