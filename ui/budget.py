"""OpenAI budget (D-010, D-014): spent / committed vs. thresholds, spend by job and model, usage log."""

import altair as alt
import pandas as pd
import streamlit as st

from bmw_req.llm import budget
from ui.common import empty, page_header, q, q1

page_header("Budget", "Every OpenAI call is reserved, logged and settled through the budget-guarded wrapper — "
                      "$100 total for the whole project.")

spent = q1("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE status != 'reserved'") or 0.0
committed = q1("SELECT COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END), 0) FROM llm_usage") or 0.0
n_calls = q1("SELECT COUNT(*) FROM llm_usage") or 0
cache_hits = q1("SELECT COUNT(*) FROM llm_cache") or 0

c = st.columns(4)
c[0].metric("Spent", f"${spent:.2f}")
c[1].metric("Committed (incl. open reservations)", f"${committed:.2f}")
c[2].metric("Warn / block non-demo / hard stop",
            f"${budget.WARN_USD:.0f} / ${budget.BLOCK_NON_DEMO_USD:.0f} / ${budget.HARD_STOP_USD:.0f}")
c[3].metric("Calls logged", f"{n_calls:,}", help=f"{cache_hits:,} cached responses available for free reuse")

bar = pd.DataFrame([{"what": "committed", "usd": committed}, {"what": "spent", "usd": spent}])
rules = pd.DataFrame([{"usd": budget.WARN_USD, "label": "warn"}, {"usd": budget.BLOCK_NON_DEMO_USD, "label": "block non-demo"},
                      {"usd": budget.HARD_STOP_USD, "label": "hard stop"}])
st.altair_chart(
    (alt.Chart(bar).mark_bar(size=22, cornerRadiusEnd=3).encode(
        y=alt.Y("what:N", title=None, sort=["spent", "committed"]),
        x=alt.X("usd:Q", scale=alt.Scale(domain=[0, 100]), title="USD of $100"),
        color=alt.Color("what:N", scale=alt.Scale(domain=["spent", "committed"], range=["#1c69d4", "#8fb8ee"]), legend=None),
        tooltip=["what", alt.Tooltip("usd:Q", format="$.2f")])
     + alt.Chart(rules).mark_rule(color="#c0392b", strokeDash=[4, 3]).encode(x="usd:Q", tooltip=["label", "usd"])
     + alt.Chart(rules).mark_text(dy=-34, fontSize=10, color="#842029").encode(x="usd:Q", text="label:N"))
    .properties(height=110), width="stretch")

usage = q("SELECT * FROM llm_usage ORDER BY id DESC")
if usage.empty:
    empty("No LLM calls yet.")
    st.stop()
usage["job_group"] = usage["job"].str.split(":").str[0]
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Spend by job**")
    by_job = usage.groupby("job", as_index=False).agg(calls=("id", "count"), usd=("cost_usd", "sum"),
                                                      reserved=("reserved_usd", "sum")).sort_values("usd", ascending=False)
    st.altair_chart(alt.Chart(by_job.head(20)).mark_bar(color="#1c69d4", cornerRadiusEnd=3).encode(
        y=alt.Y("job:N", sort=None, title=None), x=alt.X("usd:Q", title="USD"),
        tooltip=["job", "calls", alt.Tooltip("usd:Q", format="$.4f")]).properties(height=22 * min(len(by_job), 20) + 30),
        width="stretch")
with right:
    st.markdown("**Spend by model**")
    by_model = usage.groupby(["model", "kind"], as_index=False).agg(
        calls=("id", "count"), usd=("cost_usd", "sum"), input_tokens=("input_tokens", "sum"),
        cached_tokens=("cached_tokens", "sum"), output_tokens=("output_tokens", "sum"), searches=("search_calls", "sum"))
    st.dataframe(by_model, hide_index=True, width="stretch",
                 column_config={"usd": st.column_config.NumberColumn("USD", format="$%.4f")})
    st.markdown("**By status**")
    st.dataframe(usage.groupby("status", as_index=False).agg(calls=("id", "count"), usd=("cost_usd", "sum")),
                 hide_index=True, width="stretch", column_config={"usd": st.column_config.NumberColumn("USD", format="$%.4f")})

st.markdown("**Usage log**")
jobs = st.multiselect("Job group", sorted(usage["job_group"].dropna().unique()))
log = usage[usage["job_group"].isin(jobs)] if jobs else usage
st.dataframe(log.drop(columns=["job_group"]).head(500), hide_index=True, width="stretch", height=420,
             column_config={"cost_usd": st.column_config.NumberColumn("cost", format="$%.5f"),
                            "reserved_usd": st.column_config.NumberColumn("reserved", format="$%.5f")})
