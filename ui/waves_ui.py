"""Simulated wave stepper (Q-012, D-027): where we are in the ~2-year process, and the paid "open next wave" action.
Used by the Home page."""

import streamlit as st

from bmw_req.pipeline.waves import WAVES
from ui.common import actor, chip, clear_caches, current_wave, md, q


@st.dialog("Open the next simulated wave?")
def confirm_wave(w: int):
    st.markdown(f"**{WAVES[w]['label']}** (simulated {WAVES[w]['simulated_date']})")
    st.write(WAVES[w]["description"])
    st.warning("This runs the AI pipeline — requirement drafting (reasoning model), a duplicate check against the "
               "backlog, fit checks and a re-prioritization. It **costs OpenAI budget** and takes a few minutes; "
               "the page waits until it is done.", icon=":material/payments:")
    st.caption(f"Recorded in the audit trail as initiated by **{actor()}**.")
    a, b = st.columns(2)
    if a.button("Run it", type="primary", width="stretch"):
        try:
            from bmw_req.pipeline import graph

            with st.spinner(f"Running {WAVES[w]['label']} …"):
                out = graph.advance(w, initiated_by=actor())
            st.session_state["wave_log"] = {"wave": w, "log": out.get("log", []), "error": None}
        except Exception as e:
            st.session_state["wave_log"] = {"wave": w, "log": [], "error": f"{type(e).__name__}: {e}"}
        clear_caches()
        st.rerun()
    if b.button("Cancel", width="stretch"):
        st.rerun()


def wave_stepper() -> None:
    """Three wave cards: done / now / next, with the button to open the next wave."""
    wave = current_wave()
    opened = q("SELECT entity_id, ts, actor_id FROM audit_event WHERE action = 'open_wave' ORDER BY id")
    opened_map = {str(r.entity_id): r for r in opened.itertuples()}
    nxt = wave + 1 if wave + 1 in WAVES else None
    cols = st.columns(len(WAVES))
    for col, (w, info) in zip(cols, WAVES.items()):
        with col, st.container(border=True):
            state = "now" if w == wave else ("done" if w < wave else ("next" if w == nxt else "later"))
            md(f"{chip(state, {'now': 'Must', 'done': 'approved', 'next': 'proposed', 'later': 'Could'}[state])}"
               f" <span class='muted'>simulated {info['simulated_date']}</span>")
            st.markdown(f"**{info['label']}**")
            st.caption(info["description"])
            ev = opened_map.get(str(w))
            if ev is not None:
                st.caption(f"Opened {str(ev.ts)[:16].replace('T', ' ')} by {ev.actor_id}")
            if w == nxt and st.button(f"Open wave {w}", type="primary", key=f"open_wave_{w}", icon=":material/play_arrow:"):
                confirm_wave(w)
    wl = st.session_state.get("wave_log")
    if wl:
        if wl["error"]:
            st.error(f"Wave {wl['wave']} failed: {wl['error']}")
        else:
            st.success(f"Wave {wl['wave']} done — review the new requirements and the AI suggestions below.")
        if wl["log"]:
            with st.expander("Pipeline log"):
                st.code("\n".join(wl["log"]), language=None)
