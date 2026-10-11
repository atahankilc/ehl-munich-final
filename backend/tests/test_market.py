"""Market context (D-046) on synthetic figures: BMW volumes are only a weight, trends come from public figures, and
large BMW-vs-public differences surface as conflicts. No BMW data, no paid calls."""

from bmw_req.structure import market as M


def fig(line, market, region, period, value, yoy=None, tier="T1", sid=1, published="2026-01-05"):
    return {"line": line, "market": market, "region": region, "period": period, "metric": "retail_sales",
            "value": value, "yoy": yoy, "tier": tier, "source_id": sid, "published_at": published, "verified": True}


VOL = {"5 Series:US": {2024: 60000, 2025: 60000}, "5 Series:EU": {2025: 100000}, "7 Series:US": {2025: 10000}}


def test_weights_are_shares_of_the_latest_actual_year():
    w = M.weights(VOL)
    assert w == {"5 Series:US": round(60000 / 170000, 4), "5 Series:EU": round(100000 / 170000, 4),
                 "7 Series:US": round(10000 / 170000, 4)}


def test_trend_prefers_longer_periods_then_latest_then_most_trusted():
    figs = [fig("5 Series", "CN", "CN", "Dec-2025", 1, yoy=22, published="2026-01-10", sid=1),
            fig("5 Series", "CN", "CN", "FY2025", 1, yoy=31, published="2026-01-09", sid=2),
            fig("5 Series", "US", "US", "FY2025", 1, yoy=7, tier="T1", sid=3),
            fig("5 Series", "US", "US", "FY2025", 1, yoy=9, tier="T3", sid=4),
            fig("5 Series", "global", "GLOBAL", "FY2025", 1, yoy=1, sid=5)]
    t = M.trends(figs)
    assert t["5 Series:CN"]["source_id"] == 2          # full year beats a single month
    assert t["5 Series:US"]["source_id"] == 3          # same date: T1 beats T3
    assert "5 Series:global" not in t                  # global is not a market trend


def test_conflicts_only_for_comparable_full_years_beyond_25_percent():
    figs = [fig("5 Series", "US", "US", "FY2025", 20000, sid=10),      # BMW 60k: +200 % → conflict
            fig("5 Series", "EU", "DE", "FY2025", 30000, sid=11),      # Germany is not Europe → not compared
            fig("7 Series", "US", "US", "FY2025", 9000, sid=12),       # +11 % → fine
            fig("5 Series", "US", "US", "H1-2026", 1000, sid=13)]      # not a full year → not compared
    c = M.conflicts(VOL, figs)
    assert [(x["key"], x["year"], x["diff_pct"], x["source_id"]) for x in c] == [("5 Series:US", 2025, 200, 10)]


def test_area_market_is_additive_per_covered_market():
    ctx = {"bmw_weight": M.weights(VOL), "public_trend": {"5 Series:US": {"yoy": -7}}, "conflicts": [{"key": "5 Series:US"}]}
    m = M.area_market({"5 Series:US": 12, "1 Series:CN": 3}, ctx)
    assert m["markets"][0] == {"key": "5 Series:US", "comments": 12, "bmw_share": ctx["bmw_weight"]["5 Series:US"],
                               "trend": {"yoy": -7}, "conflict": True}
    assert m["markets"][1]["bmw_share"] is None and m["markets"][1]["conflict"] is False
    assert m["bmw_volume_share"] == ctx["bmw_weight"]["5 Series:US"]
    assert "stylized" in m["label"]


def test_usage_groups_jobs_into_pipelines_and_steps():
    from api.routers.usage import pipeline_of, step_of
    assert (pipeline_of("specify:cp1"), step_of("specify:cp1")) == ("definition", "specify")
    assert (pipeline_of("contextualize:link"), step_of("contextualize:link")) == ("structure", "contextualize:link")
    assert (pipeline_of("research:trend_scout"), step_of("research:trend_scout")) == ("sources", "research:trend_scout")
    assert (pipeline_of("derive:5 Series:w1"), step_of("derive:5 Series:w1")) == ("legacy", "derive")
    assert step_of("consolidate:w1:p0") == "consolidate"
