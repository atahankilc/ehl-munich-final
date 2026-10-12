"""Benchmark facts (D-048): deterministic checks, unit normalisation and checkpoint visibility (no paid calls)."""

import json

import pytest

from bmw_req import checkpoints as C
from bmw_req.db import connect
from bmw_req.definition import benchmarks as B
from bmw_req.ingest import reference


@pytest.fixture
def conn(pg_url):
    c = connect()
    reference.seed(c)
    C.ensure(c)
    B.ensure(c)
    return c


def add_item(conn, ref, cp, text="", quote="", tier="T1", published=None, kind="research", meta=None):
    return conn.execute("INSERT INTO source_item (kind, ref, trust_tier, url, published_at, text, quote, checkpoint, meta_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                        (kind, ref, tier, f"https://example.com/{ref}", published, text, quote, cp,
                         json.dumps(meta or {}))).fetchone()[0]


def add_fact(conn, sid, attribute, entity, value, brand=None):
    conn.execute("INSERT INTO spec_fact (source_item_id, aspect, attribute, entity, brand, value, unit, quote, method) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, 'q', 'rule')",
                 (sid, B.ATTRIBUTES[attribute]["aspect"], attribute, entity, brand, value, B.ATTRIBUTES[attribute]["unit"]))


def test_attribute_config_is_consistent():
    for a in B.ATTRIBUTES.values():
        assert a["direction"] in ("higher", "lower") and a["unit"] in B.UNITS
    assert 25 <= len(B.ATTRIBUTES) <= 40


def test_quote_must_be_a_substring_of_the_item():
    text, src = "BYD launches 1,500 kW charger — second-gen", "The charger boasts a single-gun power output of up to 1500 kW, a 50% increase"
    assert B.quote_field("up to  1500 kW", text, src) == "quote"            # whitespace-normalised
    assert B.quote_field("1,500 kW charger", text, src) == "text"
    assert B.quote_field("“1500 kW”", "x", "output of up to \"1500 kW\"") == "quote"   # typographic quotes
    assert B.quote_field("up to 2000 kW", text, src) is None
    assert B.quote_field("k", text, src) is None                              # too short to cite
    assert B.value_in_quote(10000, "10,000 1-MW charging stations")


def test_value_must_appear_in_the_quote():
    assert B.value_in_quote(1000, "up to 1,000 kW")
    assert B.value_in_quote(45.4, "45,4 Prozent der Pannen")
    assert B.value_in_quote(1500, "1.500 kW")
    assert not B.value_in_quote(900, "up to 452 miles")


def test_units_convert_to_the_canonical_unit():
    assert B.convert("range_km", 452, "miles") == (pytest.approx(727.4, abs=0.1), "km")
    assert B.convert("range_km", 900, "km") == (900, "km")
    assert B.convert("hands_off_kmh", 85, "mph")[0] == pytest.approx(136.8, abs=0.1)
    assert B.convert("boot_l", 13.1, "cu ft")[0] == pytest.approx(370.9, abs=0.1)
    assert B.convert("charge_10_80_min", 30, "s")[0] == 0.5
    assert B.convert("screen_in", 14.9, "inch") == (14.9, "in")
    assert B.convert("dc_peak_kw", 1, "MW")[0] == 1000
    assert B.convert("range_km", 300, "kW") is None                           # unit does not fit the attribute


def test_rule_reads_the_unit_from_the_text_not_the_curated_meta(conn):
    sid = add_item(conn, "i7", "cp2", text="7 Series facelift: i7 up to 452 miles",
                   quote="range across the BMW i7 lineup – up to 452 miles (WLTP) in the BMW i7 50 xDrive.",
                   meta={"entity": "BMW 7 Series", "value": 452, "unit": "km"})
    [f] = B.rule_facts(conn.execute("SELECT * FROM source_item WHERE id = ?", (sid,)).fetchone())
    assert f["attribute"] == "range_km" and f["raw_unit"] == "miles" and f["value"] == pytest.approx(727.4, abs=0.1)
    assert f["cycle"] == "WLTP"


def test_validate_drops_unciteable_facts(conn):
    sid = add_item(conn, "cla", "cp1", kind="web", text="CLA adds up to 325 km in 10 minutes",
                   quote="its 800V technology can add up to 325 kilometres of range in just 10 minutes")
    rows = conn.execute("SELECT * FROM source_item WHERE id = ?", (sid,)).fetchall()
    base = dict(attribute="km_added_10min", aspect=None, entity="Mercedes-Benz CLA", brand="Mercedes-Benz",
                model_code=None, market="EU", value=325, value_max=None, unit="kilometres", cycle=None, condition=None)
    facts = [B.Fact(source_item_id=sid, quote="add up to 325 kilometres", **base),
             B.Fact(source_item_id=sid, quote="add up to 400 kilometres", **base),            # not in the item
             B.Fact(source_item_id=sid + 99, quote="add up to 325 kilometres", **base),       # not in the batch
             B.Fact(source_item_id=sid, quote="add up to 325 kilometres", **(base | {"value": 352})),
             B.Fact(source_item_id=sid, quote="add up to 325 kilometres", **(base | {"unit": "kW"}))]
    ok, drops = B.validate(facts, rows)
    assert len(ok) == 1 and ok[0]["value"] == 325 and ok[0]["quote_field"] == "quote"
    assert drops == {"quote_not_substring": 1, "unknown_id": 1, "value_not_in_quote": 1, "unit": 1}


def test_facts_for_respects_checkpoint_visibility_and_delta(conn):
    a = add_item(conn, "byd-1000", "cp1", tier="T2", published="2025-03-18")
    b = add_item(conn, "byd-1500", "cp2", tier="T1", published="2026-03-05")
    late = add_item(conn, "late", None, published="2026-09-01")                    # after the last cut-off
    add_fact(conn, a, "dc_peak_kw", "BYD", 1000, "BYD")
    add_fact(conn, b, "dc_peak_kw", "BYD", 1500, "BYD")
    add_fact(conn, late, "dc_peak_kw", "BYD", 2100, "BYD")
    assert [f["value"] for f in B.facts_for(conn, ["charging_speed"], "cp1")] == [1000]
    cp2 = B.facts_for(conn, ["charging_speed"], "cp2")
    assert [f["value"] for f in cp2] == [1500, 1000]                                # T1 first
    assert cp2[0]["source_id"] == f"research:{b}" and cp2[0]["id"].startswith("fact:")
    assert B.facts_for(conn, ["range"], "cp2") == []
    [d] = B.fact_delta(conn, ["charging_speed"])
    assert d["value"] == 1500 and d["previous"]["value"] == 1000


def test_candidate_prefilter():
    assert B.is_candidate("BYD 1,000 kW charging, 400 km in 5 minutes")
    assert B.is_candidate("49% of Germans name driving range a concern")
    assert not B.is_candidate("BMW deliveries up 3% in China", "deliveries")
    assert not B.is_candidate("UK market tops two million in 2025")


def test_massage_programmes_written_as_words_are_read_by_rule(conn):
    sid = add_item(conn, "g70", "cp2", kind="web", text="The BMW 7 Series offers massage.",
                   quote="The seats come with a massage function with nine programs.", meta={"models": ["BMW 7 Series"]})
    [f] = B.rule_facts(conn.execute("SELECT * FROM source_item WHERE id = ?", (sid,)).fetchone())
    assert (f["attribute"], f["value"], f["model_code"]) == ("seat_massage_programs", 9, "G70")


def test_implausible_values_are_dropped(conn):
    sid = add_item(conn, "q4", "cp1", kind="web", text="Q4 charges 10-80 % in 0h28")
    rows = conn.execute("SELECT * FROM source_item WHERE id = ?", (sid,)).fetchall()
    f = B.Fact(source_item_id=sid, attribute="charge_10_80_min", aspect=None, entity="Audi Q4", brand="Audi",
               model_code=None, market="EU", value=28, value_max=None, unit="h", cycle=None, condition=None, quote="0h28")
    ok, drops = B.validate([f], rows)
    assert ok == [] and drops == {"range": 1}
