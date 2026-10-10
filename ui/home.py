"""Home: the question, where we are in the (simulated) process, what needs the PM's decision, and the current top
priorities for the focus markets. The starting point of the app and of the demo tour."""

import streamlit as st

from ui.common import (FOCUS_TARGETS, chip, evidence_chip, md, page_header, plain_target, priority_chip, q, q1,
                       review_requirement, short, targets_df)
from ui.waves_ui import wave_stepper

page_header("What should the next BMW offer its customers?",
            "The AI reads customer feedback, the customer study, sales data and web research, and drafts ranked "
            "customer requirements for the successor models. <b>You decide</b> — every step is traceable.")

# ------------------------------------------------------------------------------------------------ how it works
steps = [
    ("1", "Read", "10k customer comments, study, sales, web research", "AI"),
    ("2", "Group", "comments → themes, e.g. 'climate controls hard to use'", "AI"),
    ("3", "Propose", "themes → customer requirements per car & market", "AI"),
    ("4", "Rank", "score per car & market → suggested Must / Should / Could", "AI"),
    ("5", "Decide", "approve, reject, defer, edit, ask the AI why", "You"),
    ("6", "Repeat", "new data each wave → AI suggests changes, you accept or reject", "You"),
]
cols = st.columns(len(steps))
for c, (n, title, text, who) in zip(cols, steps):
    with c:
        md(f"<div class='card' style='min-height:118px'><h4>{n} · {title} "
           f"{chip(who, 'approved' if who == 'You' else 'proposed')}</h4><div class='muted'>{text}</div></div>")
if st.button("See every step on a real requirement — from one customer comment to your decision",
             icon=":material/route:", type="tertiary"):
    st.switch_page("ui/journey.py")

# ------------------------------------------------------------------------------------------------ where we are
st.subheader("Where we are")
md("<span class='sim-badge'>SIMULATION</span> <span class='muted'>The feedback has no dates, so the ~2-year "
   "requirements process is replayed in three waves of new evidence.</span>")
wave_stepper()

# ------------------------------------------------------------------------------------------------ to do
st.subheader("What needs your decision")
n_review = q1("SELECT COUNT(*) FROM requirement WHERE status IN ('proposed', 'challenged')") or 0
n_sugg = q1("SELECT COUNT(*) FROM change_proposal WHERE status = 'open'") or 0
n_done = q1("SELECT COUNT(*) FROM requirement WHERE status IN ('approved', 'rejected', 'deferred')") or 0
n_appr = q1("SELECT COUNT(*) FROM requirement WHERE status = 'approved'") or 0
c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    st.metric("Requirements to review", n_review)
    st.caption("Drafted by the AI, waiting for your decision.")
    if st.button("Start review", type="primary", icon=":material/arrow_forward:", disabled=not n_review):
        st.switch_page("ui/review.py")
with c2, st.container(border=True):
    st.metric("AI suggestions", n_sugg)
    st.caption("Changes the AI proposes after new evidence — you accept or reject.")
    if st.button("Open AI suggestions", icon=":material/inbox:", disabled=not n_sugg):
        st.switch_page("ui/inbox.py")
with c3, st.container(border=True):
    st.metric("Decided", n_done, help=f"{n_appr} approved")
    st.caption(f"{n_appr} approved; the rest rejected or deferred.")
    if st.button("Priorities by market", icon=":material/view_kanban:"):
        st.switch_page("ui/board.py")

if (q1("SELECT COUNT(*) FROM prioritization_run") or 0) > 1:
    kinds = q("SELECT COALESCE(kind, 'priority') kind, COUNT(*) n FROM change_proposal WHERE status = 'open' GROUP BY 1")
    k = dict(zip(kinds["kind"], kinds["n"])) if not kinds.empty else {}
    parts = [f"{k[x]} {label}" for x, label in [
        ("new_requirement", "new requirement(s)"), ("extend", "duplicate draft(s) to merge into existing requirements"),
        ("priority", "priority change(s)"), ("content", "content edit(s)"), ("link_finding", "evidence link(s)")] if k.get(x)]
    if parts:
        st.info("Waiting for you after the latest wave: " + ", ".join(parts) + ".", icon=":material/notifications:")

# ------------------------------------------------------------------------------------------------ top priorities
st.subheader("Top priorities right now")
st.caption("Your confirmed priority where set, otherwise the AI's suggestion (marked). The same car line can rank "
           "a need differently per market.")
df = targets_df()
if df.empty:
    st.info("No requirements yet — open wave 1 above.")
    st.stop()
df = df[df["status"] != "rejected"].copy()
df["eff"] = df["pm_priority"].where(df["pm_priority"].notna(), df["proposed_priority"])
order = {"Must": 0, "Should": 1, "Could": 2}
cols = st.columns(len(FOCUS_TARGETS))
for col, (d, m) in zip(cols, FOCUS_TARGETS):
    g = df[(df["vehicle_model_id"] == d) & (df["market_code"] == m)].copy()
    g["o"] = g["eff"].map(order).fillna(3)
    g = g.sort_values(["o", "score"], ascending=[True, False]).head(5)
    with col, st.container(border=True):
        st.markdown(f"**{plain_target(d, m)}**")
        if g.empty:
            st.caption("No requirements target this market yet.")
        for r in g.itertuples():
            ai = not isinstance(r.pm_priority, str)
            md(f"{priority_chip(r.eff, ai)} {evidence_chip(r.target_evidence)}<br>{short(r.title, 70)}")
            if st.button("Review", key=f"home_{d}_{m}_{r.requirement_id}", type="tertiary", icon=":material/arrow_forward:"):
                review_requirement(r.requirement_id)
