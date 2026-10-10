"""Quality hand-over (D-038): comment themes that are mostly defect reports. Things that are broken belong to quality
engineering, not to the successor's requirement backlog — so they are listed here with their evidence, per car and
market, ready to hand over. A requirement may still cite one when it asks for a real product decision."""

import pandas as pd
import streamlit as st

from bmw_req.pipeline.requirements import QUALITY_DEFECT_SHARE
from ui.common import MARKET_SHORT, car, chip, empty, esc, loads, md, metrics_wave, page_header, q, short

page_header("Quality hand-over",
            "Comment themes where most signals are defect reports — things that are broken today. Every car must "
            "simply work, so these are not product decisions for the successor: they go to quality engineering, "
            "with the customer evidence attached.")

df = q("""SELECT f.id, f.vehicle_model_id, f.category, f.title, f.summary, f.metrics_json, COUNT(*) n_signals,
                 AVG(g.feedback_type = 'defect') defect_share, SUM(g.severity = 'high') n_high,
                 (SELECT GROUP_CONCAT(rf.requirement_id) FROM requirement_finding rf
                   WHERE rf.finding_id = f.id AND rf.relation = 'supports') reqs
          FROM finding f JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
          WHERE f.source_kind = 'verbatim' AND COALESCE(f.polarity, '') != 'like'
          GROUP BY f.id HAVING defect_share >= ? ORDER BY n_signals DESC""", (QUALITY_DEFECT_SHARE,))
if df.empty:
    empty("No defect-dominated themes.")
    st.stop()

mw = metrics_wave()
c = st.columns(4)
c[0].metric("Quality issues", len(df), help=f"Comment themes with ≥ {QUALITY_DEFECT_SHARE:.0%} defect signals")
c[1].metric("Customer signals", f"{int(df['n_signals'].sum()):,}")
c[2].metric("High severity", f"{int(df['n_high'].sum()):,}")
c[3].metric("Cited by a requirement", int(df["reqs"].notna().sum()),
            help="Only as evidence for a real product decision — never restated as 'make it work'.")

f1, f2 = st.columns(2)
cars = f1.multiselect("Car", sorted(df["vehicle_model_id"].dropna().unique()), format_func=car)
cats = f2.multiselect("Category", sorted(df["category"].dropna().unique()))
sel = df[(df["vehicle_model_id"].isin(cars) if cars else True) & (df["category"].isin(cats) if cats else True)]

rows = []
for r in sel.itertuples():
    mk = ((loads(r.metrics_json, {}) or {}).get("by_wave", {}).get(mw, {}) or {}).get("markets", {}) or {}
    rows.append({"theme": r.title, "car": car(r.vehicle_model_id), "category": r.category, "signals": r.n_signals,
                 "defect share": r.defect_share, "high severity": r.n_high,
                 "markets": ", ".join(f"{MARKET_SHORT.get(k, k)} {v.get('verbatims')}" for k, v in
                                      sorted(mk.items(), key=lambda kv: -(kv[1].get("verbatims") or 0))),
                 "cited by": r.reqs or "–"})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
    "defect share": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
    "theme": st.column_config.TextColumn(width="large")})
st.download_button("Download hand-over list (CSV)", pd.DataFrame(rows).to_csv(index=False).encode(),
                   "quality_handover.csv", "text/csv", icon=":material/download:")

st.subheader("Evidence per issue")
for r in sel.head(25).itertuples():
    with st.expander(f"{car(r.vehicle_model_id)} · {short(r.title, 80)} — {r.n_signals} signals, {r.defect_share:.0%} defects"):
        md(" ".join([chip(r.category, "system"), chip(f"{int(r.n_high)} high severity", "fail" if r.n_high else "system")]))
        st.write(r.summary or "")
        qs = q("""SELECT s.external_id, s.market_code, g.quote FROM finding_signal fs JOIN signal g ON g.id = fs.signal_id
                  JOIN source_item s ON s.id = g.source_item_id WHERE fs.finding_id = ? AND g.feedback_type = 'defect'
                  AND g.quote_verified = 1 ORDER BY CASE g.severity WHEN 'high' THEN 0 ELSE 1 END LIMIT 4""", (int(r.id),))
        for x in qs.itertuples():
            md(f"<span class='muted'>{esc(x.external_id)} · {esc(MARKET_SHORT.get(x.market_code, x.market_code))}</span>"
               f"<div class='quote'>“{esc(x.quote)}”</div>")
