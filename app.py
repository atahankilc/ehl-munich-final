"""Streamlit entry point (D-019): `uv run streamlit run app.py`.

PM web app: overview → portfolio → backlog → requirement detail (evidence, score, fit, decision, audit) →
change inbox, market conflicts, findings, weights & runs, audit trail, export, budget. Every write goes through
`bmw_req.service` / `bmw_req.pipeline.scoring` with a named human actor and rationale (AGENTS rules 5, 6).
"""

import streamlit as st

from ui.common import DEFAULT_PM, current_wave, inject_css, md, q1

st.set_page_config(page_title="BMW Requirements Studio", page_icon=":material/directions_car:", layout="wide")
inject_css()

PAGES = {
    "Workflow": [
        st.Page("ui/overview.py", title="Overview", icon=":material/account_tree:", default=True),
        st.Page("ui/portfolio.py", title="Portfolio", icon=":material/grid_view:"),
    ],
    "Decide": [
        st.Page("ui/backlog.py", title="Backlog", icon=":material/format_list_numbered:"),
        st.Page("ui/requirement.py", title="Requirement", icon=":material/description:"),
        st.Page("ui/inbox.py", title="Change inbox", icon=":material/inbox:"),
        st.Page("ui/conflicts.py", title="Market conflicts", icon=":material/compare_arrows:"),
    ],
    "Evidence": [
        st.Page("ui/findings.py", title="Findings explorer", icon=":material/search:"),
    ],
    "Governance": [
        st.Page("ui/weights.py", title="Weights & runs", icon=":material/tune:"),
        st.Page("ui/audit.py", title="Audit trail", icon=":material/history:"),
        st.Page("ui/export.py", title="Export", icon=":material/download:"),
        st.Page("ui/budget.py", title="Budget", icon=":material/payments:"),
    ],
}
nav = st.navigation(PAGES)

with st.sidebar:
    md("**BMW Requirements Studio**<br><span class='muted'>AI proposes · PM decides · everything audited</span>")
    st.session_state.setdefault("pm", DEFAULT_PM)
    st.text_input("Acting as", key="pm", help="Named human actor recorded on every decision and access event.")
    wave = current_wave()
    if wave:
        from bmw_req.pipeline.waves import WAVES

        w = WAVES.get(wave, {})
        md(f"<span class='sim-badge'>SIMULATION</span> &nbsp;**{w.get('label', f'Wave {wave}')}**"
           f"<br><span class='muted'>simulated date {w.get('simulated_date', '–')}</span>")
    else:
        md("<span class='sim-badge'>SIMULATION</span> &nbsp;no wave opened yet")
    try:
        from bmw_req.llm import budget

        spent = q1("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE status != 'reserved'") or 0.0
        st.metric("OpenAI spend", f"${spent:.2f}", help=f"of $100 total; hard stop at ${budget.HARD_STOP_USD:.0f}",
                  border=True)
    except Exception:
        pass

nav.run()
