"""Stage `benchmarks` (D-048): cited numeric benchmarks (`spec_fact`) that `specify` anchors target ladders on.

A target ladder (baseline / competitive threshold / target / stretch) is only credible if its numbers come from cited
sources: "BYD charges at 1,000 kW", "Mercedes CLA adds 325 km in 10 min", "49 % of Germans name range their top BEV
worry". This module turns the cited items we already hold (research, web, reference) into one row per number:
- ATTRIBUTES is a controlled list of customer-experienced numeric attributes, each with one canonical unit and the
  aspect it anchors. Customer-facing only (scope rule): DC kW and charge times are in because they are how customers
  experience charging; battery kWh, cell chemistry or component specs are not. Generic survey/adoption shares
  (fitment_pct, wtp_pct, concern_pct, want_pct, satisfaction_pts, pp100) take their aspect from the extraction.
- Extraction: a regex prefilter keeps items that contain a number with a relevant unit (or a survey share with a
  relevant keyword); research items whose curated value + unit is unambiguous (charging kW, range km/mi with "range")
  are read by rule; everything else goes to luna in batches of 15 with a strict schema. Code then checks every fact:
  attribute in the list, source id in the batch, the quote an exact (whitespace/quote-normalised) substring of the
  item's text or source quote, the value literally present in the quote, and a unit convertible to the attribute's
  canonical unit. Units are CONVERTED to the canonical unit (miles → km, mph → km/h, hp → kW, cu ft → l, s → min for
  charge times); the number as written stays in raw_value / raw_unit, so a US view can show miles again losslessly.
  This also repairs mislabelled curated units (a research row storing "452 km" whose quote says "452 miles").
- Idempotent: `spec_fact_scan` marks every item processed (by rule, luna or prefilter-skip); re-runs only see new
  items. Visibility is never stored on a fact — it is the source item's checkpoint (D-041), joined at read time, so a
  fact from an item published after the last cut-off is never visible.
- Gap research (`--research`, capped): a few targeted web-search queries reuse the cited research agents' machinery
  (citation-filtered URLs, quote verification against the fetched page, trust tiers, research.run.store); new items
  get their checkpoint from the publish date (D-040) and are then extracted like any other item.

`uv run python -m bmw_req.definition.benchmarks [--research] [--pilot]`
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.llm import LLM
from bmw_req.structure.events import log
from bmw_req.structure.taxonomy import ALL_ASPECTS

STAGE = "benchmarks"
BATCH = 15
KINDS = ("research", "web", "reference")
EXTRACT_VERSION = "benchmarks-v1"

# slug, aspect (None = generic: the extraction names the aspect), canonical unit, direction (better), label
_A = [
    ("range_km", "range", "km", "higher", "Electric range (cycle in `cycle`; miles converted)"),
    ("range_retention_pct", "range", "%", "higher", "Range kept in cold/hot or highway conditions vs rated"),
    ("consumption_kwh_100km", "efficiency", "kWh/100km", "lower", "Energy consumption shown to the driver"),
    ("dc_peak_kw", "charging_speed", "kW", "higher", "Peak DC charging power (car or charger)"),
    ("charge_10_80_min", "charging_speed", "min", "lower", "DC charge time, 10–80 % (other windows named in condition)"),
    ("km_added_10min", "charging_speed", "km", "higher", "Range added by fast charging in 10 min (other durations in condition)"),
    ("ac_charge_kw", "charging_hardware", "kW", "higher", "On-board AC charging power"),
    ("charging_sites", "charging_planning", "count", "higher", "Charging stations/sites available to the brand's customers"),
    ("screen_in", "display_ui", "in", "higher", "Largest front display diagonal"),
    ("screen_count", "display_ui", "count", "higher", "Number of front displays"),
    ("hud_in", "display_ui", "in", "higher", "Head-up / panoramic display diagonal"),
    ("rear_screen_in", "rear_entertainment", "in", "higher", "Rear-seat screen diagonal"),
    ("boot_l", "cargo_space", "l", "higher", "Luggage compartment volume (seats up unless stated)"),
    ("frunk_l", "cargo_space", "l", "higher", "Front trunk volume"),
    ("rear_legroom_mm", "rear_space", "mm", "higher", "Rear legroom"),
    ("wheelbase_mm", "rear_space", "mm", "higher", "Wheelbase (proxy for rear space; LWB variants)"),
    ("length_mm", "body_variants", "mm", "higher", "Overall vehicle length"),
    ("accel_0_100_s", "performance", "s", "lower", "0–100 km/h acceleration"),
    ("accel_0_60mph_s", "performance", "s", "lower", "0–60 mph acceleration (US)"),
    ("power_kw", "performance", "kW", "higher", "System power as advertised (hp/PS converted)"),
    ("turning_circle_m", "handling_steering", "m", "lower", "Turning circle"),
    ("hands_off_kmh", "highway_assist", "km/h", "higher", "Max speed of hands-off assisted driving"),
    ("eyes_off_kmh", "automated_driving", "km/h", "higher", "Max speed of eyes-off (L3) driving"),
    ("seat_massage_programs", "seat_comfort", "count", "higher", "Seat massage programmes"),
    ("speakers", "audio", "count", "higher", "Number of audio speakers"),
    ("audio_w", "audio", "W", "higher", "Audio system output"),
    ("fridge_l", "storage", "l", "higher", "Cool box / fridge capacity"),
    ("cabin_noise_db", "cabin_noise", "dB", "lower", "Interior noise level"),
    ("fitment_pct", None, "%", "higher", "Equipment adoption / take rate (e.g. seat ventilation fitted to 36 %)"),
    ("wtp_pct", None, "%", "higher", "Share of customers willing to pay for a feature"),
    ("want_pct", None, "%", "higher", "Share of customers wanting / rating a feature important or must-have"),
    ("concern_pct", None, "%", "lower", "Share of customers citing a concern, complaint or rejection reason"),
    ("satisfaction_pts", None, "pts", "higher", "Satisfaction / experience index score (study named in condition)"),
    ("pp100", None, "PP100", "lower", "Problems per 100 vehicles (J.D. Power style quality studies)"),
]
ATTRIBUTES: dict[str, dict] = {s: {"slug": s, "aspect": a, "unit": u, "direction": d, "label": lab} for s, a, u, d, lab in _A}
SLUGS = tuple(ATTRIBUTES)
# Plausible canonical values: catches unit slips such as "0h28" read as 28 hours. Shares are 0–100 by construction.
PLAUSIBLE: dict[str, tuple[float, float]] = {
    "range_km": (50, 1500), "consumption_kwh_100km": (8, 40), "dc_peak_kw": (3, 2500), "charge_10_80_min": (2, 120),
    "km_added_10min": (20, 800), "ac_charge_kw": (2, 50), "screen_in": (3, 60), "hud_in": (3, 120),
    "rear_screen_in": (5, 45), "boot_l": (50, 2500), "frunk_l": (5, 200), "rear_legroom_mm": (600, 1500),
    "wheelbase_mm": (2000, 3800), "length_mm": (3000, 6500), "accel_0_100_s": (1.5, 20), "accel_0_60mph_s": (1.5, 20),
    "power_kw": (30, 1500), "turning_circle_m": (8, 16), "hands_off_kmh": (10, 200), "eyes_off_kmh": (10, 200),
    "seat_massage_programs": (1, 30), "speakers": (2, 60), "audio_w": (50, 5000), "fridge_l": (1, 60),
    "cabin_noise_db": (25, 90), "satisfaction_pts": (0, 1000), "pp100": (0, 500), "charging_sites": (1, 1e7),
}

# canonical unit → {alias (lower, no spaces/dots): factor to canonical}
UNITS: dict[str, dict[str, float]] = {
    "km": {"km": 1, "kms": 1, "kilometre": 1, "kilometres": 1, "kilometer": 1, "kilometers": 1, "公里": 1,
           "mi": 1.609344, "mile": 1.609344, "miles": 1.609344},
    "km/h": {"km/h": 1, "kmh": 1, "kph": 1, "kilometresperhour": 1, "kilometersperhour": 1, "mph": 1.609344},
    "kW": {"kw": 1, "kilowatt": 1, "kilowatts": 1, "mw": 1000, "megawatt": 1000, "hp": 0.7457, "bhp": 0.7457,
           "ps": 0.7355, "千瓦": 1},
    "min": {"min": 1, "mins": 1, "minute": 1, "minutes": 1, "分钟": 1, "s": 1 / 60, "sec": 1 / 60, "seconds": 1 / 60,
            "h": 60, "hour": 60, "hours": 60},
    "s": {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1, "秒": 1},
    "in": {"in": 1, "inch": 1, "inches": 1, '"': 1, "”": 1, "cm": 1 / 2.54, "英寸": 1, "zoll": 1},
    "mm": {"mm": 1, "cm": 10, "m": 1000, "in": 25.4, "inch": 25.4, "inches": 25.4},
    "m": {"m": 1, "metre": 1, "metres": 1, "meter": 1, "meters": 1, "ft": 0.3048, "feet": 0.3048},
    "l": {"l": 1, "litre": 1, "litres": 1, "liter": 1, "liters": 1, "litern": 1, "升": 1, "cuft": 28.3168, "cubicfeet": 28.3168,
          "cubicfoot": 28.3168},
    "kWh/100km": {"kwh/100km": 1, "kwh/100kilometres": 1},
    "%": {"%": 1, "pct": 1, "percent": 1, "percentage": 1, "percentagepoints": 1},
    "count": {"count": 1, "": 1, "programs": 1, "programmes": 1, "program": 1, "speakers": 1, "speaker": 1,
              "screens": 1, "displays": 1, "stations": 1, "sites": 1, "chargers": 1, "units": 1, "modes": 1},
    "W": {"w": 1, "watt": 1, "watts": 1, "kw": 1000},
    "dB": {"db": 1, "dba": 1, "db(a)": 1, "decibels": 1},
    "pts": {"pts": 1, "points": 1, "point": 1, "": 1},
    "PP100": {"pp100": 1, "problemsper100vehicles": 1, "": 1},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS spec_fact (
    id INTEGER PRIMARY KEY, source_item_id INTEGER NOT NULL REFERENCES source_item(id),
    aspect TEXT NOT NULL, attribute TEXT NOT NULL, entity TEXT NOT NULL, brand TEXT, model_code TEXT, market TEXT,
    value REAL NOT NULL, value_max REAL, unit TEXT NOT NULL,   -- canonical unit of the attribute
    raw_value REAL, raw_unit TEXT,                             -- the number as written in the quote
    cycle TEXT, condition TEXT, quote TEXT NOT NULL,
    quote_field TEXT,                                          -- quote | text: which field of the item holds it
    method TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_item_id, attribute, entity, market, cycle)
);
CREATE INDEX IF NOT EXISTS spec_fact_aspect ON spec_fact(aspect, attribute);
CREATE TABLE IF NOT EXISTS spec_fact_scan (
    source_item_id INTEGER PRIMARY KEY REFERENCES source_item(id),
    attributes_found INTEGER NOT NULL, method TEXT NOT NULL,   -- rule | luna | skip
    model TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


def ensure(conn) -> None:
    conn.executescript(SCHEMA)


# ------------------------------------------------------------------------------------------------ deterministic checks
_QCHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\u00a0": " ", "\u202f": " "})


def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_QCHARS)).strip().lower()


def quote_field(quote: str, text: str | None, src_quote: str | None) -> str | None:
    """'quote' / 'text' when the fact's quote is an exact (normalised) substring of that item field, else None."""
    q = norm(quote).strip(" .\"'")
    if len(q) < 2:
        return None
    for name, field in (("quote", src_quote), ("text", text)):
        if field and q in norm(field):
            return name
    return None


_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def numbers_in(s: str) -> set[float]:
    """Every reading of every number in `s`: '1,000' → {1000, 1.0}; '45,4' → {45.4, 454}; '1.500' → {1.5, 1500}."""
    out: set[float] = set()
    for tok in re.findall(r"\d[\d.,\u202f]*\d|\d", s):   # no plain spaces: "10,000 1-MW" is two numbers
        tok = tok.replace("\u202f", "")
        for cand in (tok.replace(",", ""), tok.replace(".", "").replace(",", "."), tok.replace(",", ".")):
            try:
                out.add(float(cand))
            except ValueError:
                pass
    out |= {float(i) for i, w in enumerate(_WORDS) if re.search(rf"\b{w}\b", s, re.I)}
    return out


def value_in_quote(value: float, quote: str) -> bool:
    return any(abs(n - value) <= max(1e-6, abs(value) * 0.002) for n in numbers_in(quote))


def convert(attribute: str, value: float | None, unit: str | None) -> tuple[float | None, str] | None:
    """Value in the attribute's canonical unit, or None when the unit does not fit the attribute."""
    canon = ATTRIBUTES[attribute]["unit"]
    alias = re.sub(r"[\s.]", "", (unit or "").lower())
    alias = re.sub(r"\(.*?\)", "", alias) or alias   # 'kilowatts (kW)' → 'kilowatts'
    alias = {"kilometres/hour": "km/h", "km/hr": "km/h", "litres(vda)": "l", "l(vda)": "l"}.get(alias, alias)
    factor = UNITS.get(canon, {}).get(alias)
    if factor is None and alias == canon.lower():
        factor = 1
    if factor is None:
        return None
    return (None if value is None else round(value * factor, 3)), canon


# ------------------------------------------------------------------------------------------------ candidates
SPEC_RX = re.compile(
    r"\d[\d.,]*\s*(?:-|–|to)?\s*[\d.,]*\s*(?:km\b|km/h|kilomet|kph|mph|mi\b|miles?\b|kw\b|kilowatt|mw\b|minutes?\b|"
    r"mins?\b|inch|-in\b|\"|”|cm\b|mm\b|litres?\b|liters?\b|l\b|cu\.?\s?ft|cubic|db\b|dba|watts?\b|w\b|speakers?|"
    r"programs?|programmes?|screens?|displays?|seconds?|sec\b|s\b|pp100|bottles?|hp\b|ps\b|kwh/100|公里|分钟|英寸)", re.I)
PCT_RX = re.compile(r"\d[\d.,]*\s*(?:%|percent|per cent|prozent)", re.I)
TOPIC_RX = re.compile(r"fitment|take.?rate|standard|optional|equipped|willing|pay|concern|worr|want|prefer|consider|"
                      r"must.?have|important|expect|complain|problem|satisf|distract|useful|interest|feature|seat|"
                      r"screen|button|voice|charg|range|assist|adas|driving|rear|comfort", re.I)
SALES_METRICS = {"retail_sales", "deliveries", "registrations", "market_share", "price", "yoy", "bev_share", "nev_share"}


def is_candidate(text: str, metric: str | None = None) -> bool:
    spec = bool(SPEC_RX.search(text))
    pct = bool(PCT_RX.search(text)) and bool(TOPIC_RX.search(text)) and metric not in SALES_METRICS
    return spec or pct


def _items(conn, ids: list[int] | None = None) -> list[sqlite3.Row]:
    q = (f"SELECT id, kind, text, quote, meta_json, market_code, vehicle_model_id, published_at FROM source_item "
         f"WHERE kind IN ({','.join('?' * len(KINDS))})")
    args: list = list(KINDS)
    if ids is not None:
        q += f" AND id IN ({','.join('?' * len(ids))})"
        args += ids
    return conn.execute(q + " AND id NOT IN (SELECT source_item_id FROM spec_fact_scan) ORDER BY id", args).fetchall()


# ------------------------------------------------------------------------------------------------ rule extraction
_RANGE_RX = re.compile(r"(\d[\d,.]*)\s*(km|kilometres|kilometers|miles|mi)\b(?:\s*\(?\s*(WLTP|CLTC|EPA|NEDC))?", re.I)


_N = rf"(\d+|{'|'.join(_WORDS[1:])})"
_MASSAGE_RX = re.compile(rf"\b{_N}\s+(?:different\s+)?massage\s+programs?|massage\s+(?:function\s+)?with\s+{_N}\s+programs?", re.I)
LINE_CODE = {"1 series": "F70", "5 series": "G60", "7 series": "G70"}   # BMW lines in scope (rule facts only)


def rule_facts(row) -> list[dict]:
    """Unambiguous numbers read by rule. Massage programmes (often written as words, which luna tends to skip) from
    any item; and research items whose curated value + unit is DC charging kW or rated range — the unit is read from
    the text around the number (never trusted from meta alone: some rows store miles as 'km')."""
    m = json.loads(row["meta_json"] or "{}")
    for field in ("quote", "text"):
        hit = _MASSAGE_RX.search(row[field] or "")
        entity = m.get("competitor") or next(iter(m.get("models") or []), None) or m.get("entity")
        if hit and entity and entity != "market":
            w = (hit.group(1) or hit.group(2)).lower()
            n = float(_WORDS.index(w)) if w in _WORDS else float(w)
            return [_rule(row, m | {"entity": entity}, "seat_massage_programs", n, "programs", None, hit.group(0), field)]
    if row["kind"] != "research":
        return []
    value, unit = m.get("value"), (m.get("unit") or "").lower()
    if value is None or unit not in ("kw", "km") or (m.get("entity") or "market") == "market":
        return []
    for field in ("quote", "text"):
        s = row[field] or ""
        if unit == "kw" and re.search(r"charg", s, re.I):
            hit = re.search(rf"({re.escape(f'{value:,.0f}')}|{value:g})\s*(?:kW|kilowatts?)", s, re.I)
            if hit and not re.search(r"\d\s*(km|miles?|min)", s, re.I):
                return [_rule(row, m, "dc_peak_kw", value, "kW", None, hit.group(0), field)]
        if unit == "km" and re.search(r"\brange\b|WLTP|CLTC|EPA", s, re.I) and not re.search(r"\bminutes?\b|\bmin\b", s, re.I):
            for hit in _RANGE_RX.finditer(s):
                if value_in_quote(value, hit.group(1)) and 100 <= value <= 1500:
                    cycle = (hit.group(3) or "").upper() or next(
                        (c for c in ("WLTP", "CLTC", "EPA") if c in s.upper()), None)
                    return [_rule(row, m, "range_km", value, hit.group(2), cycle, s[hit.start():hit.end(2)], field)]
    return []


def _rule(row, meta, attribute, value, raw_unit, cycle, quote, field) -> dict:
    v, canon = convert(attribute, value, raw_unit)
    entity = meta.get("entity") or "market"
    brand = entity.split()[0] if entity != "market" else None
    code = next((c for k, c in LINE_CODE.items() if k in entity.lower()), None) if brand == "BMW" else None
    return {"source_item_id": row["id"], "attribute": attribute, "aspect": ATTRIBUTES[attribute]["aspect"],
            "entity": entity, "brand": brand, "model_code": code, "market": row["market_code"] or "global",
            "value": v, "value_max": None, "unit": canon, "raw_value": value, "raw_unit": raw_unit, "cycle": cycle,
            "condition": None, "quote": quote, "quote_field": field, "method": "rule", "model": None}


# ------------------------------------------------------------------------------------------------ luna extraction
class Fact(BaseModel):
    source_item_id: int
    attribute: Literal[SLUGS]  # type: ignore[valid-type]
    aspect: Literal[tuple(ALL_ASPECTS)] | None = Field(  # type: ignore[valid-type]
        description="Only for generic attributes (fitment_pct, wtp_pct, want_pct, concern_pct, satisfaction_pts, "
                    "pp100): the aspect the share is about; null otherwise")
    entity: str = Field(description="Car as 'Brand Model [variant]' (e.g. 'BYD Han L', 'BMW i7 xDrive60'), a charger "
                                    "('BYD flash charger'), or a population ('consumers Germany', 'US EV shoppers')")
    brand: str | None
    model_code: str | None = Field(description="BMW only: F70, G60, G68, G70, or the Neue Klasse model name (e.g. 'iX3 NK'); else null")
    market: Literal["EU", "US", "CN", "RoW", "global"]
    value: float = Field(description="The number exactly as written in the quote (no unit conversion)")
    value_max: float | None = Field(description="Upper end if the quote gives a range of values, else null")
    unit: str = Field(description="Unit exactly as written: km, miles, kW, min, s, inch, mm, litres, cu ft, %, mph, km/h, hp, dB, W, points, PP100, count")
    cycle: Literal["WLTP", "CLTC", "EPA", "NEDC", "real_world"] | None = Field(description="Range/consumption test cycle if stated")
    condition: str | None = Field(description="Short qualifier: SOC window, minutes for range added, temperature, "
                                              "seat position, survey name/year, trim; null if none")
    quote: str = Field(description="The shortest exact span copied character-for-character from the item's text or "
                                   "quote that contains the number")


class FactBatch(BaseModel):
    facts: list[Fact]


INSTRUCTIONS = """You extract cited numeric benchmarks for a BMW product-requirements team. Each input item is a cited
source (research note, web evidence, reference line). Return every number in the items that measures one of these
customer-experienced attributes (slug — canonical unit — meaning):
{attrs}

Rules:
- Only numbers that state a capability, size, time, count, share or score of a car, charger, brand offer or customer
  population. Never sales volumes, prices, market shares, margins, production, battery kWh or other engineering specs.
- quote: copy the shortest span containing the number EXACTLY from that item's text or quote (same characters, no
  ellipsis joins, no translation). value and unit exactly as written in that span — do not convert units. Numbers
  written as words count ("nine massage programs" → value 9, unit programs).
- Survey shares: wtp_pct (would pay), want_pct (want / important / must-have / prefer / would use), concern_pct
  (worry, complaint, rejection reason, distraction source), with the aspect the share is about and entity naming the
  population and country ('consumers Germany'). If one item lists the same share for several countries, return one
  fact per country only where the item states which number belongs to which country. Shares about brands, OEMs,
  switching intent or powertrain preference are not feature wants — skip them.
- charge_10_80_min: also other SOC windows, naming the window in condition ('10-70 %'). km_added_10min: also other
  durations, naming the minutes in condition ('in 5 min'). range_km: put WLTP/CLTC/EPA in cycle when stated.
- market: the market the number applies to (US for EPA/mph figures, CN for CLTC, EU for WLTP unless stated).
- If an item has no such number, return nothing for it. Never invent or infer numbers."""


def _instructions() -> str:
    attrs = "\n".join(f"- {a['slug']} — {a['unit']} — {a['label']}" for a in ATTRIBUTES.values())
    return INSTRUCTIONS.format(attrs=attrs)


def _payload(rows) -> str:
    out = []
    for r in rows:
        m = json.loads(r["meta_json"] or "{}")
        it = {"id": r["id"], "kind": r["kind"], "text": r["text"], "quote": r["quote"],
              "published": r["published_at"], "market": r["market_code"]}
        if m.get("entity"):
            it["entity"] = m["entity"]
        if m.get("models"):
            it["models"] = m["models"]
        out.append(it)
    return json.dumps(out, ensure_ascii=False)


def validate(facts: list[Fact], rows, item_aspects: dict[int, str] | None = None) -> tuple[list[dict], Counter]:
    """Code checks on luna's facts; returns accepted fact dicts + drop reasons. A generic attribute without an aspect
    from luna falls back to the item's own aspect (`source_aspect`), quality scores to build_quality."""
    by_id = {r["id"]: r for r in rows}
    ok, drops = [], Counter()
    for f in facts:
        r = by_id.get(f.source_item_id)
        if r is None:
            drops["unknown_id"] += 1
            continue
        if f.attribute not in ATTRIBUTES:
            drops["attribute"] += 1
            continue
        field = quote_field(f.quote, r["text"], r["quote"])
        if field is None:
            drops["quote_not_substring"] += 1
            continue
        if not value_in_quote(f.value, f.quote):
            drops["value_not_in_quote"] += 1
            continue
        conv = convert(f.attribute, f.value, f.unit)
        if conv is None:
            drops["unit"] += 1
            continue
        v, canon = conv
        vmax = convert(f.attribute, f.value_max, f.unit)[0] if f.value_max is not None else None
        attr = ATTRIBUTES[f.attribute]
        aspect = (attr["aspect"] or (f.aspect if f.aspect and f.aspect != "other" else None)
                  or (item_aspects or {}).get(r["id"])
                  or ("build_quality" if f.attribute in ("pp100", "satisfaction_pts") else None))
        if aspect is None:
            drops["no_aspect"] += 1
            continue
        lo, hi = PLAUSIBLE.get(f.attribute, (0, 100))
        if not lo <= v <= hi:
            drops["range"] += 1
            continue
        brand = (f.brand or "").strip() or None
        ok.append({"source_item_id": r["id"], "attribute": f.attribute, "aspect": aspect, "entity": f.entity.strip(),
                   "brand": brand, "model_code": f.model_code if brand and brand.upper() == "BMW" else None,
                   "market": f.market, "value": v, "value_max": vmax, "unit": canon, "raw_value": f.value,
                   "raw_unit": f.unit, "cycle": f.cycle, "condition": f.condition, "quote": f.quote,
                   "quote_field": field, "method": "luna"})
    return ok, drops


def _extract_batch(rows) -> tuple[list[Fact], float, str]:
    llm = LLM(conn=connect())
    try:
        res = llm.generate(job=f"structure.{STAGE}", tier="fast", instructions=_instructions(), input=_payload(rows),
                           schema=FactBatch, reasoning_effort="low", max_output_tokens=8000, flex=True)
        return (res.parsed.facts if res.parsed else []), res.cost_usd, llm.model_for("fast")
    finally:
        llm.conn.close()


def _store(conn, facts: list[dict], scanned: dict[int, tuple[int, str, str | None]]) -> int:
    cols = ("source_item_id", "aspect", "attribute", "entity", "brand", "model_code", "market", "value", "value_max",
            "unit", "raw_value", "raw_unit", "cycle", "condition", "quote", "quote_field", "method", "model")
    before = conn.total_changes
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany(f"INSERT OR IGNORE INTO spec_fact ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         [tuple(f.get(c) for c in cols) for f in facts])
        n = conn.total_changes - before
        conn.executemany("INSERT OR REPLACE INTO spec_fact_scan (source_item_id, attributes_found, method, model) "
                         "VALUES (?, ?, ?, ?)", [(i, *v) for i, v in scanned.items()])
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return n


def extract(conn, ids: list[int] | None = None, pilot: bool = False, workers: int = 6) -> dict:
    """Scan unprocessed research/web/reference items (or only `ids`). `pilot`: one luna batch, nothing else."""
    ensure(conn)
    rows = _items(conn, ids)
    cands, skip, rule, to_luna = [], {}, [], []
    for r in rows:
        m, blob = json.loads(r["meta_json"] or "{}"), f"{r['text'] or ''} {r['quote'] or ''}"
        rf = rule_facts(r)
        rule += rf
        if not is_candidate(blob, m.get("metric")):
            if not rf:
                skip[r["id"]] = (0, "skip", None)
            continue
        cands.append(r)
        # rule-read items still go to luna when they hold other spec numbers; luna won't duplicate the rule attribute
        if not rf or len(SPEC_RX.findall(blob)) > 1:
            to_luna.append(r)
    stats = {"items": len(rows), "candidates": len(cands), "rule_facts": len(rule), "luna_items": len(to_luna)}
    if pilot:
        to_luna, skip, rule = to_luna[:BATCH], {}, []
    rule_keys = {(f["source_item_id"], f["attribute"]) for f in rule}
    scanned = dict(skip) | {f["source_item_id"]: (1, "rule", None) for f in rule}
    batches = [to_luna[i:i + BATCH] for i in range(0, len(to_luna), BATCH)]
    facts, drops, cost, model = list(rule), Counter(), 0.0, None
    item_aspects = {r["source_item_id"]: r["aspect"] for r in conn.execute(
        "SELECT source_item_id, aspect FROM source_aspect WHERE aspect != 'other'")}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for rows_b, (out, c, model) in zip(batches, pool.map(_extract_batch, batches)):
            ok, d = validate(out, rows_b, item_aspects)
            ok = [f | {"model": model} for f in ok if (f["source_item_id"], f["attribute"]) not in rule_keys]
            facts += ok
            drops += d
            cost += c
            found = Counter(f["source_item_id"] for f in ok)
            for r in rows_b:
                prev = scanned.get(r["id"], (0, "luna", model))
                scanned[r["id"]] = (prev[0] + found[r["id"]], "luna" if prev[1] != "rule" else "rule+luna", model)
    stored = _store(conn, facts, scanned)
    stats |= {"luna_batches": len(batches), "accepted": len(facts), "stored": stored, "dropped": dict(drops),
              "cost_usd": round(cost, 5), "pilot": pilot}
    log(conn, STAGE, "extracted", stats, model=model)
    return stats


# ------------------------------------------------------------------------------------------------ retrieval for specify
def _fact_rows(conn, where: str, args: list, limit: int | None) -> list[dict]:
    q = f"""SELECT f.*, s.kind, s.url, s.published_at, s.trust_tier, s.checkpoint, s.meta_json
            FROM spec_fact f JOIN source_item s ON s.id = f.source_item_id
            WHERE {where}
            ORDER BY COALESCE(s.trust_tier, 'T9'), COALESCE(s.published_at, '') DESC, f.id"""
    if limit:
        q += f" LIMIT {int(limit)}"
    out = []
    for r in conn.execute(q, args):
        m = json.loads(r["meta_json"] or "{}")
        out.append({"id": f"fact:{r['id']}", "source_id": f"{r['kind']}:{r['source_item_id']}",
                    "attribute": r["attribute"], "label": ATTRIBUTES.get(r["attribute"], {}).get("label"),
                    "direction": ATTRIBUTES.get(r["attribute"], {}).get("direction"), "aspect": r["aspect"],
                    "entity": r["entity"], "brand": r["brand"], "model_code": r["model_code"], "market": r["market"],
                    "value": r["value"], "value_max": r["value_max"], "unit": r["unit"],
                    "raw_value": r["raw_value"], "raw_unit": r["raw_unit"], "cycle": r["cycle"],
                    "condition": r["condition"], "quote": r["quote"], "method": r["method"],
                    "url": r["url"], "publisher": m.get("publisher"), "published_at": r["published_at"],
                    "tier": r["trust_tier"], "checkpoint": r["checkpoint"],
                    "unverified": bool(m.get("unverified")) or m.get("quote_verified") == 0 or m.get("verified") is False})
    return out


def facts_for(conn, aspects: list[str], cp: str, limit: int = 40) -> list[dict]:
    """Facts on `aspects` whose source is visible at `cp` (cp2 sees cp1 + cp2), best tier first, then newest."""
    ensure(conn)
    vis = C.visible_ids(cp)
    return _fact_rows(conn, f"f.aspect IN ({','.join('?' * len(aspects))}) AND s.checkpoint IN ({','.join('?' * len(vis))})",
                      [*aspects, *vis], limit)


def _model_key(entity: str) -> str:
    """'2026 Lexus ES 350e' → 'lexus es'; 'BYD flash charger' → 'byd flash'; 'BYD' → 'byd'."""
    return " ".join(re.sub(r"^\d{4}\s+", "", entity.lower()).split()[:2])


def fact_delta(conn, aspects: list[str], cp_from: str = "cp1", cp_to: str = "cp2") -> list[dict]:
    """Facts newly visible at `cp_to` (not at `cp_from`) for `aspects` — "the bar moved". Each carries `previous`: the
    best `cp_from` fact on the same attribute for the same entity, else the same brand + model word ('BMW iX3 LWB' ~
    'BMW iX3 Long Wheelbase', 'BYD' ~ 'BYD'), else None. Never matched across models of one brand."""
    ensure(conn)
    new_cps = [c for c in C.visible_ids(cp_to) if c not in C.visible_ids(cp_from)]
    if not new_cps or not aspects:
        return []
    new = _fact_rows(conn, f"f.aspect IN ({','.join('?' * len(aspects))}) AND s.checkpoint IN ({','.join('?' * len(new_cps))})",
                     [*aspects, *new_cps], None)
    old = defaultdict(list)
    for f in facts_for(conn, aspects, cp_from, limit=100000):
        old[f["attribute"]].append(f)
    for f in new:
        cands = old.get(f["attribute"], [])
        f["previous"] = (next((o for o in cands if o["entity"].lower() == f["entity"].lower()), None)
                         or next((o for o in cands if _model_key(o["entity"]) == _model_key(f["entity"])), None))
    return new


# ------------------------------------------------------------------------------------------------ gap research
GAP_QUERIES = [
    ("bm:boot:5", "5 Series", "G60", "EU", "Luggage compartment volume in litres (VDA) of the Mercedes E-Class, Mercedes EQE, Audi A6 e-tron / A6 Avant, Volvo ES90 and BMW 5 Series / i5 sedan."),
    ("bm:boot:1", "1 Series", "F70", "EU", "Luggage compartment volume in litres of the Mercedes A-Class, Mercedes CLA, Audi A3 Sportback, VW Golf and BMW 1 Series (F70)."),
    ("bm:charge:5", "5 Series", "G60", "EU", "DC fast-charging time 10-80 % in minutes and peak charging power in kW of the Mercedes EQE / new electric E-Class, Audi A6 e-tron, Porsche Macan Electric and BMW i5."),
    ("bm:charge:7", "7 Series", "G70", "EU", "DC fast-charging time 10-80 % in minutes and peak kW of the Mercedes EQS, Porsche Taycan, Lucid Air and BMW i7."),
    ("bm:charge:1", "1 Series", "F70", "EU", "DC charging 10-80 % time in minutes and peak kW of the Mercedes CLA electric, Audi A3 e-hybrid / Q4 e-tron, Tesla Model 3 and other compact premium EVs."),
    ("bm:fridge", "7 Series", "G70", "CN", "Capacity of in-car fridges / cool boxes (litres or number of bottles) in premium sedans and SUVs such as Mercedes S-Class / Maybach, Li Auto L9, AITO M9, Audi A8, BMW 7 Series."),
    ("bm:seats", "5 Series", "G60", "US", "Number of seat massage programs and availability of ventilated seats in the Mercedes E-Class, Mercedes S-Class, Audi A6, Genesis G80 / G90, BMW 5 Series and 7 Series."),
    ("bm:accel", "5 Series", "G60", "EU", "0-100 km/h acceleration times in seconds of the Mercedes E-Class, Audi A6, Mercedes C-Class, Audi A3, Mercedes A-Class, Mercedes S-Class and their BMW counterparts."),
    ("bm:epa", "5 Series", "G60", "US", "EPA-estimated range in miles of the BMW i5, BMW i7, Mercedes EQE sedan, Mercedes EQS sedan, Lucid Air, Tesla Model S and Audi A6 e-tron (US)."),
]
GAP_TOOL_CALLS = 3
GAP_CAP_USD = 0.45


def research(conn, cap_usd: float = GAP_CAP_USD, only: list[str] | None = None) -> dict:
    """Targeted, capped gap-fill web research reusing the cited research agents (D-014 caps; quotes verified)."""
    import httpx

    from bmw_req.research import agents as A
    from bmw_req.research.run import done_task_ids, store

    llm = LLM(conn=conn)
    done = done_task_ids(conn)
    spent, out = 0.0, []
    for tid, line, code, mkt, focus in GAP_QUERIES:
        if tid in done or (only and tid not in only):
            continue
        if spent + 0.07 > cap_usd:
            out.append({"task": tid, "skipped": "cap"})
            continue
        task = A.Task(id=tid, agent="competitor_scout", line=line, vehicle_model_id=code, market_code=mkt,
                      focus=focus + " Return only items whose quote states the number; prefer OEM press releases and "
                                    "spec sheets or reputable reviews published before August 2026.", max_items=8)
        res = llm.generate(job="research:benchmarks", tier="fast", instructions=A.RULES, input=A.build_prompt(task),
                           schema=A.AgentOutput, reasoning_effort="low", tools=[{"type": "web_search"}],
                           max_tool_calls=GAP_TOOL_CALLS, max_output_tokens=6000,
                           include=["web_search_call.action.sources"], use_cache=False)
        spent += res.cost_usd
        parsed = res.parsed or A.AgentOutput(items=[])
        cited = A.cited_urls(res.response)
        kept, dropped = A.filter_cited(parsed.items, cited)
        ar = A.AgentResult(task, kept, dropped, cited, A.search_queries(res.response), res.usage_id, res.cost_usd,
                           llm.model_for("fast"))
        with httpx.Client(follow_redirects=True, timeout=8.0, headers={"User-Agent": A.UA}) as client:
            verified = [A.verify_quote(A.clean_url(it.url), it.quote, client=client) for it in kept]
        ids = store(conn, ar, verified)
        for sid in ids:   # D-040: first checkpoint whose cut-off is on/after the publish date; later or undated → never
            pub = conn.execute("SELECT published_at FROM source_item WHERE id = ?", (sid,)).fetchone()[0]
            conn.execute("UPDATE source_item SET checkpoint = ? WHERE id = ?", (C.checkpoint_for(C.parse_date(pub)), sid))
        out.append({"task": tid, "kept": len(kept), "dropped": len(dropped), "verified": verified, "ids": ids,
                    "cost_usd": round(res.cost_usd, 4)})
    log(conn, STAGE, "gap_research", {"tasks": out, "cost_usd": round(spent, 4)}, model=llm.model_for("fast"))
    return {"tasks": out, "cost_usd": round(spent, 4)}


# ------------------------------------------------------------------------------------------------ CLI
def summary(conn) -> dict:
    ensure(conn)
    rows = conn.execute("""SELECT f.attribute, COALESCE(s.checkpoint, 'never') cp, COUNT(*) n FROM spec_fact f
                           JOIN source_item s ON s.id = f.source_item_id GROUP BY 1, 2""").fetchall()
    table: dict[str, dict] = {a: {} for a in SLUGS}
    for r in rows:
        table[r["attribute"]][r["cp"]] = r["n"]
    return {a: v for a, v in table.items() if v}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--research", action="store_true", help="run the capped gap-fill web research first")
    ap.add_argument("--only", nargs="*", help="gap-research task ids")
    ap.add_argument("--pilot", action="store_true", help="extract one luna batch only")
    ap.add_argument("--cap-usd", type=float, default=GAP_CAP_USD)
    args = ap.parse_args(argv)
    conn = connect()
    ensure(conn)
    if args.research:
        print(json.dumps(research(conn, args.cap_usd, args.only), indent=1))
    print(json.dumps(extract(conn, pilot=args.pilot), indent=1))
    print(f"{'attribute':24} {'cp1':>5} {'cp2':>5} {'never':>6}")
    for a, v in summary(conn).items():
        print(f"{a:24} {v.get('cp1', 0):>5} {v.get('cp2', 0):>5} {v.get('never', 0):>6}")


if __name__ == "__main__":
    main()
