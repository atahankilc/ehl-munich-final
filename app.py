"""Streamlit entry point (D-019): `uv run streamlit run app.py`.

PM web app, organised by the PM's job: Start here (home, guided review, priorities by market, AI suggestions) →
Explore & trace (requirement details, market conflicts, findings, audit trail) → Under the hood (pipeline, tables,
weights, export, budget), plus an optional demo tour. Every write goes through
`bmw_req.service` / `bmw_req.pipeline.scoring` with a named human actor and rationale (AGENTS rules 5, 6).
"""

import streamlit as st

from ui.common import DEFAULT_PM, current_wave, inject_css, md, q1

st.set_page_config(page_title="BMW Requirements Studio", page_icon=":material/directions_car:", layout="wide")
inject_css()

BY_PATH = {}


def page(path: str, **kw):
    BY_PATH[path] = st.Page(path, **kw)
    return BY_PATH[path]


PAGES = {
    "Start here": [
        page("ui/home.py", title="Home", icon=":material/home:", default=True),
        page("ui/journey.py", title="How it works", icon=":material/route:"),
        page("ui/review.py", title="Review requirements", icon=":material/fact_check:"),
        page("ui/board.py", title="Priorities by market", icon=":material/view_kanban:"),
        page("ui/inbox.py", title="AI suggestions", icon=":material/inbox:"),
    ],
    "Explore & trace": [
        page("ui/requirement.py", title="Requirement details", icon=":material/description:"),
        page("ui/conflicts.py", title="Market conflicts", icon=":material/compare_arrows:"),
        page("ui/findings.py", title="Findings explorer", icon=":material/search:"),
        page("ui/quality.py", title="Quality hand-over", icon=":material/build:"),
        page("ui/audit.py", title="Audit trail", icon=":material/history:"),
    ],
    "Under the hood": [
        page("ui/overview.py", title="Pipeline & data", icon=":material/account_tree:"),
        page("ui/backlog.py", title="All requirements (table)", icon=":material/table_rows:"),
        page("ui/portfolio.py", title="Portfolio coverage", icon=":material/grid_view:"),
        page("ui/weights.py", title="Weights & runs", icon=":material/tune:"),
        page("ui/export.py", title="Export", icon=":material/download:"),
        page("ui/budget.py", title="Budget", icon=":material/payments:"),
    ],
}
# Demo tour: the pitch path, one step per page (sidebar toggle).
TOUR = [
    ("ui/home.py", "The question and where we are",
     "BMW asks what the next 5 / 1 / 7 Series should offer. The AI turned 10k customer comments, a study, sales and "
     "web research into ranked requirements. Three simulated waves stand for ~2 years of new evidence."),
    ("ui/journey.py", "Follow one requirement, step by step",
     "One customer's words → the AI's signal → a theme → the requirement → brand/market fit → the score arithmetic → "
     "the PM's decision → re-scoring in later waves. Left: the rule for all data. Right: what it did here."),
    ("ui/review.py", "Review one requirement",
     "Plain language: the customer need, the evidence behind it (comments, study, competitors) and the AI's "
     "suggested priority per car and market. The PM approves, rejects or defers — always with a reason."),
    ("ui/board.py", "Markets are different customers",
     "Compare 5 Series · USA with 5 Series LWB · China: same car line, different priorities. China has no customer "
     "comments, so it rests on study and web evidence — shown, not hidden."),
    ("ui/inbox.py", "The AI suggests, the PM decides",
     "After new evidence the AI never changes a decision. It suggests priority changes with their cause, new "
     "requirements, and merges duplicates into existing requirements instead of re-creating them."),
    ("ui/requirement.py", "Full traceability",
     "Every score has a visible breakdown; every requirement links to findings and down to the customer comment; "
     "brand and market fit are checked; brand-fit FAIL blocks approval."),
    ("ui/audit.py", "Complete audit trail",
     "Every action — AI or human — with who, when, why and the model used. Append-only: the database rejects edits."),
    ("ui/export.py", "The deliverable",
     "The structured requirement list: ID, description, findings and sources, score and rationale, evidence level, "
     "assumptions and uncertainties, decision status."),
]
nav = st.navigation(PAGES, expanded=True)

with st.sidebar:
    md("**BMW Requirements Studio**<br><span class='muted'>AI proposes · PM decides · everything audited</span>")
    st.session_state.setdefault("pm", DEFAULT_PM)
    st.text_input("Acting as", key="pm", help="Named human actor recorded on every decision and access event.")
    # plain session keys (not widget keys): widget state doesn't reliably survive st.switch_page
    st.toggle("Demo tour", value=st.session_state.get("tour_on", False), key="_tour_toggle",
              help="Walk through the pitch path step by step.",
              on_change=lambda: st.session_state.update(tour_on=st.session_state["_tour_toggle"]))
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

if st.session_state.get("tour_on"):
    i = min(st.session_state.get("tour_step", 0), len(TOUR) - 1)
    path, title, text = TOUR[i]
    with st.container(border=True):
        a, b, c = st.columns([7, 1, 1], vertical_alignment="center")
        a.markdown(f"**Demo tour · step {i + 1} of {len(TOUR)} — {title}**  \n{text}")
        if b.button("Back", disabled=i == 0, width="stretch", key="tour_back"):
            st.session_state["tour_step"] = i - 1
            st.switch_page(TOUR[i - 1][0])
        if c.button("Next", type="primary", disabled=i == len(TOUR) - 1, width="stretch", key="tour_next"):
            st.session_state["tour_step"] = i + 1
            st.switch_page(TOUR[i + 1][0])
        if nav.url_path != BY_PATH[path].url_path and a.button("Go to this step's page", key="tour_go", type="tertiary"):
            st.switch_page(path)

nav.run()
