"""Portfolio matrix: derivative × market targets with evidence base, requirements, priorities, sales and gaps;
platform and plant context per derivative."""

import altair as alt
import pandas as pd
import streamlit as st

from ui.common import (LINES, MIN_MARKET_VERBATIMS, SUCCESSOR_LAUNCH, TARGETS, all_targets, current_wave, empty,
                       loads, md, metrics_wave, page_header, q, q1, tlabel)

page_header("Portfolio",
            "Every derivative × market is its own customer group (D-011). Evidence, requirements and priorities "
            "per target — with the gaps stated, not hidden.")

wave = current_wave()
as_of = st.segmented_control("Evidence as of", options=["current wave", "all ingested data"],
                             default="current wave" if wave else "all ingested data",
                             help="Waves are a simulation: each wave makes more evidence visible to the pipeline.")
W = wave if (as_of == "current wave" and wave) else 99
mw = metrics_wave(W if W != 99 else 2)
if as_of == "current wave" and not wave:
    st.caption("No wave opened yet — showing all ingested data.")

latest_ver = q1("SELECT MAX(extractor_version) FROM verbatim_extraction")
inscope = q("""SELECT s.vehicle_model_id d, s.market_code m, COUNT(*) total, COALESCE(SUM(e.in_scope), 0) inscope
               FROM source_item s LEFT JOIN verbatim_extraction e ON e.source_item_id = s.id AND e.extractor_version = ?
               WHERE s.kind = 'feedback' AND s.wave <= ? GROUP BY 1, 2""", (latest_ver or "", W))
verb_total = {(r.d, r.m): int(r.total) for r in inscope.itertuples()}
verb_in = {(r.d, r.m): int(r.inscope or 0) for r in inscope.itertuples()}
extracted_d = set(q("""SELECT DISTINCT s.vehicle_model_id d FROM verbatim_extraction e
                       JOIN source_item s ON s.id = e.source_item_id""")["d"]) if latest_ver else set()

vf = q("SELECT vehicle_model_id d, metrics_json FROM finding WHERE source_kind = 'verbatim' AND COALESCE(first_wave, 1) <= ?", (W,))
vf_count: dict = {}
for r in vf.itertuples():
    for mk, v in (loads(r.metrics_json, {}).get("by_wave", {}).get(mw, {}).get("markets", {}) or {}).items():
        if (v or {}).get("verbatims"):
            vf_count[(r.d, mk)] = vf_count.get((r.d, mk), 0) + 1
of = q("""SELECT vehicle_model_id d, market_code m, source_kind k, COUNT(*) n FROM finding
          WHERE source_kind IN ('study', 'web') AND COALESCE(first_wave, 1) <= ? GROUP BY 1, 2, 3""", (W,))
of_count = {(r.d, r.m, r.k): int(r.n) for r in of.itertuples()}
study_items = q("SELECT vehicle_model_id d, market_code m, COUNT(*) n FROM study_metric GROUP BY 1, 2")
study_map = {(r.d, r.m): int(r.n) for r in study_items.itertuples()}
web = q("SELECT vehicle_model_id d, market_code m, COUNT(*) n FROM source_item WHERE kind = 'web' AND wave <= ? GROUP BY 1, 2", (W,))
web_map = {(r.d, r.m): int(r.n) for r in web.itertuples()}
sales = q("SELECT vehicle_model_id d, market_code m, year, units FROM sales")
sales_map = {(r.d, r.m, int(r.year)): r.units for r in sales.itertuples()}
rt = q("""SELECT t.vehicle_model_id d, t.market_code m, t.proposed_priority ai, t.priority pm, r.status
          FROM requirement_target t JOIN requirement r ON r.id = t.requirement_id""")

rows = []
for d, m in all_targets():
    sub = rt[(rt["d"] == d) & (rt["m"] == m)] if not rt.empty else rt
    n_in = verb_in.get((d, m), 0)
    gaps = []
    if n_in < MIN_MARKET_VERBATIMS:
        gaps.append("no verbatims" if verb_total.get((d, m), 0) == 0 else
                    (f"only {n_in} in-scope verbatims" if d in extracted_d else "verbatims not yet extracted"))
    if not study_map.get((d, m)):
        gaps.append("no customer study")
    if not web_map.get((d, m)):
        gaps.append("no web research")
    if not any((d, m, y) in sales_map for y in (2024, 2025)):
        gaps.append("no sales data")

    def pc(col, p):
        return int((sub[col] == p).sum()) if not sub.empty else 0

    s24, s25, s30 = (sales_map.get((d, m, y)) for y in (2024, 2025, 2030))
    rows.append({
        "target": tlabel(d, m), "derivative": d, "market": m,
        "verbatims": verb_total.get((d, m), 0), "in_scope": n_in,
        "f_verbatim": vf_count.get((d, m), 0), "f_study": of_count.get((d, m, "study"), 0),
        "f_web": of_count.get((d, m, "web"), 0),
        "requirements": len(sub), "approved": int((sub["status"] == "approved").sum()) if not sub.empty else 0,
        "ai_msc": f"{pc('ai', 'Must')} / {pc('ai', 'Should')} / {pc('ai', 'Could')}",
        "pm_msc": f"{pc('pm', 'Must')} / {pc('pm', 'Should')} / {pc('pm', 'Could')}",
        "sales_2024": s24, "sales_2025": s25, "sales_2030": s30,
        "trend_2030": (s30 / s25 - 1) if (s30 and s25) else None,
        "gaps": ", ".join(gaps) or "–",
    })
df = pd.DataFrame(rows)

st.subheader("Derivative × market matrix")
st.dataframe(
    df.drop(columns=["derivative", "market"]), hide_index=True, width="stretch",
    column_config={
        "target": st.column_config.TextColumn("Target", width="small"),
        "verbatims": st.column_config.NumberColumn("Verbatims", help="Customer verbatims for this derivative × market"),
        "in_scope": st.column_config.NumberColumn("In scope", help=f"In-scope verbatims; < {MIN_MARKET_VERBATIMS} = no usable verbatim base (evidence gap)"),
        "f_verbatim": st.column_config.NumberColumn("Verbatim findings", help="Clusters with ≥ 1 verbatim from this market"),
        "f_study": st.column_config.NumberColumn("Study findings"),
        "f_web": st.column_config.NumberColumn("Web findings"),
        "requirements": st.column_config.NumberColumn("Requirements", help="Requirements targeting this derivative × market"),
        "approved": st.column_config.NumberColumn("Approved"),
        "ai_msc": st.column_config.TextColumn("AI Must/Should/Could", help="AI-proposed priority (score bands)"),
        "pm_msc": st.column_config.TextColumn("PM Must/Should/Could", help="Priorities confirmed by the PM"),
        "sales_2024": st.column_config.NumberColumn("Sales 2024", format="localized"),
        "sales_2025": st.column_config.NumberColumn("Sales 2025", format="localized"),
        "sales_2030": st.column_config.NumberColumn("Forecast 2030", format="localized"),
        "trend_2030": st.column_config.NumberColumn("2025→2030", format="percent"),
        "gaps": st.column_config.TextColumn("Evidence gaps", width="medium"),
    })
st.caption("Sales are BMW-provided, stylized volumes (Q-015) — used as relative weights only, never blended with "
           "public figures. China has no verbatims: its requirements rest on the customer study and cited web research.")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("**In-scope / all verbatims per target**")
    base = alt.Chart(df.assign(cell=df["in_scope"].map("{:,}".format) + " / " + df["verbatims"].map("{:,}".format))).encode(
        x=alt.X("market:N", title=None, sort=["US", "EU", "CN", "RoW"], axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("derivative:N", title=None))
    st.altair_chart(
        (base.mark_rect(cornerRadius=3).encode(
            color=alt.Color("in_scope:Q", scale=alt.Scale(scheme="blues"), legend=None),
            tooltip=["target", "verbatims", "in_scope", "gaps"])
         + base.mark_text(fontSize=12).encode(text="cell:N",
                                              color=alt.condition(alt.datum.in_scope > 1500, alt.value("white"), alt.value("#1d2733"))))
        .properties(height=200), width="stretch")
with c2:
    st.markdown("**Requirements per target (AI-proposed priority)**")
    if rt.empty:
        empty("No requirements yet — they appear after the first wave is derived.")
    else:
        agg = rt.assign(target=rt["d"] + " × " + rt["m"], ai=rt["ai"].fillna("unscored")).groupby(
            ["target", "ai"]).size().reset_index(name="n")
        st.altair_chart(alt.Chart(agg).mark_bar().encode(
            y=alt.Y("target:N", title=None), x=alt.X("n:Q", title="requirements"),
            color=alt.Color("ai:N", title=None, scale=alt.Scale(domain=["Must", "Should", "Could", "unscored"],
                                                                range=["#1c69d4", "#8fb8ee", "#c9d0d8", "#eceff3"]),
                            legend=alt.Legend(orient="bottom")),
            tooltip=["target", "ai", "n"]).properties(height=200), width="stretch")

# ------------------------------------------------------------------------------------------------ platforms & plants
st.subheader("Platforms & plants (realization context)")
st.caption("Feasibility context only — a requirement must be buildable on the derivative's platform (or its successor) "
           "in a plant that serves the market. Never scored, never an engineering spec (Q-010, D-030).")
vm = q("SELECT * FROM vehicle_model")
pl = q("SELECT * FROM platform")
prod = q("""SELECT p.*, pl.name plant_name, pl.city, pl.country, pl.nk_ready_from, pl.capacity_note
            FROM production p LEFT JOIN plant pl ON pl.id = p.plant_id""")
if vm.empty:
    empty("No reference data (vehicle_model / platform / plant) loaded yet.")
else:
    cols = st.columns(len(TARGETS))
    for col, d in zip(cols, TARGETS):
        with col, st.container(border=True):
            row = vm[vm["id"] == d]
            line = next((ln for ln, c in LINES.items() if d in c["derivatives"]), "–")
            st.markdown(f"**{d}** · {line}")
            if row.empty:
                st.caption("no reference row")
                continue
            r = row.iloc[0]
            pid = r.get("platform_id")
            prow = pl[pl["id"] == pid] if pid is not None else pl.iloc[0:0]
            succ = prow.iloc[0]["successor_platform_id"] if not prow.empty else None
            pt = ", ".join(loads(r.get("powertrains_json"), []) or [])
            md(f"<div class='kv'><b>Platform</b> {pid or '–'}"
               + (f" → successor {succ}" if succ else "")
               + (f"<br><b>Phase-out</b> {prow.iloc[0]['phase_out']}" if not prow.empty and prow.iloc[0]['phase_out'] else "")
               + f"<br><b>Generation</b> {r.get('generation') or '–'}<br><b>Powertrains</b> {pt or '–'}"
               + f"<br><b>Segment</b> {r.get('segment') or '–'}"
               + f"<br><b>Successor launch (assumed)</b> {SUCCESSOR_LAUNCH.get(d, '–')}</div>")
            pr = prod[prod["vehicle_model_id"] == d]
            for p in pr.itertuples():
                served = ", ".join(loads(p.markets_served_json, []) or [])
                md(f"<div class='muted' style='margin-top:6px'><b>{p.plant_name or p.plant_id}</b> ({p.country or '–'})"
                   f" · {p.market_variant or ''}<br>serves {served or '–'}"
                   + (f" · NK-ready {p.nk_ready_from}" if p.nk_ready_from else "") + "</div>")
            if pr.empty:
                st.caption("no production rows")
