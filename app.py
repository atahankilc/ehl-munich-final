"""Streamlit entry point (D-019): `uv run streamlit run app.py`. For now it only shows LLM spend."""

import streamlit as st

from bmw_req.db import connect
from bmw_req.llm import budget

st.set_page_config(page_title="BMW Requirements", layout="wide")
st.title("BMW Requirements")

conn = connect()
st.subheader("OpenAI budget (D-014)")
c1, c2, c3 = st.columns(3)
c1.metric("Spent", f"${budget.spent_usd(conn):.2f}")
c2.metric("Committed (incl. open reservations)", f"${budget.committed_usd(conn):.2f}")
c3.metric("Warn / block non-demo / hard stop", f"${budget.WARN_USD:.0f} / ${budget.BLOCK_NON_DEMO_USD:.0f} / ${budget.HARD_STOP_USD:.0f}")
rows = conn.execute("SELECT * FROM llm_usage ORDER BY id DESC LIMIT 200").fetchall()
st.dataframe([dict(r) for r in rows], width="stretch")
