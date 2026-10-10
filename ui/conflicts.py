"""Market conflicts (D-011): requirements whose score or AI priority differs strongly between markets, with
realization type and market notes, so the PM sees cross-market trade-offs."""

import altair as alt
import pandas as pd
import streamlit as st

from ui.common import empty, open_requirement, page_header, short, targets_df

page_header("Market conflicts",
            "The same need can be a Must in one market and a Could in another — climate, usage and culture differ. "
            "Decide per market, or choose a market variant / package.")

df = targets_df()
if df.empty:
    empty("No scored requirements yet.")
    st.stop()

c1, c2 = st.columns([2, 3])
thr = c1.slider("Score spread threshold (points)", 5, 50, 15)
by_prio = c2.toggle("Also flag different AI priorities", value=True)

rows = []
for rid, g in df[df["status"] != "rejected"].groupby("requirement_id"):
    g = g[g["score"].notna()]
    if len(g) < 2:
        continue
    spread = g["score"].max() - g["score"].min()
    prios = set(g["proposed_priority"].dropna())
    if spread >= thr or (by_prio and len(prios) > 1):
        hi, lo = g.loc[g["score"].idxmax()], g.loc[g["score"].idxmin()]
        rows.append({"requirement_id": rid, "title": g.iloc[0]["title"], "targets": len(g), "spread": spread,
                     "highest": f"{hi['target']} {hi['score']:.0f} ({hi['proposed_priority']})",
                     "lowest": f"{lo['target']} {lo['score']:.0f} ({lo['proposed_priority']})",
                     "priorities": " / ".join(f"{r.market_code}:{r.proposed_priority}" for r in g.itertuples()),
                     "realizations": ", ".join(sorted(set(g["realization"].dropna())))})
if not rows:
    st.success(f"No requirement differs by ≥ {thr} points{' or in AI priority' if by_prio else ''} across its markets.")
    st.stop()
summary = pd.DataFrame(rows).sort_values("spread", ascending=False)
st.metric("Requirements with a cross-market conflict", len(summary))
st.dataframe(summary, hide_index=True, width="stretch", column_config={
    "spread": st.column_config.ProgressColumn("Spread", min_value=0, max_value=100, format="%.0f pts"),
    "title": st.column_config.TextColumn("Requirement", width="large")})

st.subheader("Side by side")
for r in summary.head(20).itertuples():
    g = df[df["requirement_id"] == r.requirement_id].sort_values("score", ascending=False)
    with st.expander(f"{r.requirement_id} · {short(r.title, 90)} — spread {r.spread:.0f} pts", expanded=False):
        left, right = st.columns([2, 3], gap="large")
        with left:
            st.altair_chart(alt.Chart(g).mark_bar(cornerRadiusEnd=3).encode(
                y=alt.Y("target:N", sort=None, title=None), x=alt.X("score:Q", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("proposed_priority:N", title="AI priority",
                                scale=alt.Scale(domain=["Must", "Should", "Could"], range=["#1c69d4", "#8fb8ee", "#c9d0d8"]),
                                legend=alt.Legend(orient="bottom")),
                tooltip=["target", alt.Tooltip("score:Q", format=".1f"), "proposed_priority", "pm_priority",
                         "target_evidence"]).properties(height=40 * len(g) + 40), width="stretch")
        with right:
            st.dataframe(g[["target", "score", "proposed_priority", "pm_priority", "target_evidence", "realization",
                            "market_note"]], hide_index=True, width="stretch", column_config={
                "score": st.column_config.NumberColumn(format="%.0f"), "proposed_priority": "AI prio",
                "pm_priority": "PM prio", "target_evidence": "Evid.",
                "market_note": st.column_config.TextColumn("Why this market (AI note)", width="large")})
        st.caption("Options: approve per market with different priorities, realize as a market variant / package, "
                   "or defer where evidence is thin (check the evidence level — CN often rests on study + web only).")
        if st.button("Open requirement", key=f"open_{r.requirement_id}", icon=":material/open_in_new:"):
            open_requirement(r.requirement_id)
