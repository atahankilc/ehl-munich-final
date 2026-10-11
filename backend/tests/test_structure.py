"""Deterministic parts of the structure & context stages (D-043): no paid calls, synthetic text."""

from bmw_req.structure.classify import hints, quote_good, severity
from bmw_req.structure.cluster import line_of, polarity, z_state
from bmw_req.structure.taxonomy import ALL_ASPECTS, CATEGORY_OF, FEEDBACK_TYPE


def test_hints_parse_source_c_severity_and_source_d_prompt():
    h = hints("I had a serious problem with the seat. That is the one thing could be most improved about the interior of my vehicle",
              {"channel": "Source C", "engine": "BEV"})
    assert h["reported_severity"] == "serious"
    assert h["survey_prompt"].startswith("That is the one thing")


def test_quote_rules():
    text = "The rear seat is too upright. That is the one thing could be most improved about the interior of my vehicle"
    assert quote_good("The rear seat is too upright", text, None)
    assert not quote_good("too upright", text, None)                                   # under 4 words
    assert not quote_good("the rear seats are upright", text, None)                    # not a span
    assert not quote_good("could be most improved about the interior", text,
                          "That is the one thing could be most improved about the interior of my vehicle")


def test_severity_from_impact_and_intensity():
    assert severity("impaired", 3) == "high" and severity("impaired", 2) == "medium"
    assert severity("safety", 1) == "high" and severity("none", 3) == "low"


def test_taxonomy_is_closed():
    assert all(a in CATEGORY_OF for a in ALL_ASPECTS if a != "other")
    assert set(FEEDBACK_TYPE.values()) <= {"like", "defect", "difficult_to_use", "complaint", "want"}


def test_cluster_helpers():
    assert line_of("G68") == "5 Series" and line_of("F70") == "1 Series"
    assert polarity("like") == "like" and polarity("defect") == "improve"


def test_change_needs_significance_not_just_ten_percent():
    assert z_state(100, 5000, 108, 5000) == "held"          # +8 %: noise
    assert z_state(100, 5000, 112, 5000) == "held"          # +12 % but not significant
    assert z_state(100, 5000, 160, 5000) == "strengthened"
    assert z_state(160, 5000, 100, 5000) == "weakened"
