"""Overview: end-to-end workflow (AI-autonomous steps vs. mandatory human gates), live funnel, evidence sources,
simulated wave timeline."""

import altair as alt
import pandas as pd
import streamlit as st

from bmw_req.pipeline.waves import WAVES
from ui.common import (actor, chip, clear_caches, current_wave, empty, md, page_header, q, q1)

page_header("Overview",
            "From customer voice to PM-approved, evidence-linked requirements for the successor BMW — "
            "AI does the heavy lifting, the product manager decides, every step is audited.")

# ------------------------------------------------------------------------------------------------ counts
latest_ver = q1("SELECT MAX(extractor_version) FROM verbatim_extraction")
n_verb = q1("SELECT COUNT(*) FROM source_item WHERE kind = 'feedback'") or 0
n_extracted = q1("SELECT COUNT(*) FROM verbatim_extraction WHERE extractor_version = ?", (latest_ver,)) or 0 if latest_ver else 0
n_inscope = q1("SELECT COALESCE(SUM(in_scope), 0) FROM verbatim_extraction WHERE extractor_version = ?", (latest_ver,)) or 0 if latest_ver else 0
n_signals = q1("SELECT COUNT(*) FROM signal WHERE extractor_version = ?", (latest_ver,)) or 0 if latest_ver else 0
fk = q("SELECT COALESCE(source_kind, 'other') kind, COUNT(*) n FROM finding GROUP BY 1")
fk_map = dict(zip(fk["kind"], fk["n"])) if not fk.empty else {}
n_findings = int(sum(fk_map.values()))
rs = q("SELECT status, COUNT(*) n FROM requirement GROUP BY status")
rs_map = dict(zip(rs["status"], rs["n"])) if not rs.empty else {}
n_req = int(sum(rs_map.values()))
n_fit = q1("SELECT COUNT(DISTINCT requirement_id) FROM fit_check") or 0
n_runs = q1("SELECT COUNT(*) FROM prioritization_run") or 0
n_open_props = q1("SELECT COUNT(*) FROM change_proposal WHERE status = 'open'") or 0
n_audit = q1("SELECT COUNT(*) FROM audit_event") or 0
n_src = q("SELECT kind, COUNT(*) n FROM source_item GROUP BY kind")
src_map = dict(zip(n_src["kind"], n_src["n"])) if not n_src.empty else {}

# ------------------------------------------------------------------------------------------------ workflow graph
st.subheader("End-to-end workflow")


def node(name, title, sub, who, fill, border="#b8c2cf", pen=1):
    import html as _h
    title, sub, who = _h.escape(title), _h.escape(sub), _h.escape(who)
    return (f'{name} [label=<<b>{title}</b><br/><font point-size="9">{sub}</font><br/>'
            f'<font point-size="8" color="#4a5563">{who}</font>>, fillcolor="{fill}", color="{border}", penwidth={pen}];')


AI, HUMAN, SYS = "#e3edfb", "#d8f0e2", "#f3f5f8"
dot = "\n".join([
    "digraph G {", 'rankdir=TB; bgcolor="transparent"; nodesep=0.45; ranksep=0.5; newrank=true;',
    'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13, margin="0.16,0.1"];',
    'edge [color="#8a94a3", fontname="Helvetica", fontsize=9, fontcolor="#4a5563"];',
    node("ingest", "1 Ingest", f"{sum(src_map.values()):,} source items", "SYSTEM · deterministic", SYS),
    node("signals", "2 Signals", f"{n_signals:,} signals from {n_inscope:,} in-scope verbatims", "AI · autonomous (luna)", AI),
    node("findings", "3 Findings", f"{n_findings:,} findings (clusters, study, web)", "AI · autonomous", AI),
    node("reqs", "4 Requirements", f"{n_req} drafted, status 'proposed'", "AI proposes (sol)", AI),
    node("fit", "5 Fit checks", f"brand · segment · market · feasibility ({n_fit} req.)", "AI · brand FAIL = gate", AI),
    node("score", "6 Scoring", f"{n_runs} prioritization run(s)", "SYSTEM · explainable, no LLM", SYS),
    node("review", "7 PM review", f"{rs_map.get('approved', 0)} approved · {rs_map.get('rejected', 0)} rejected",
         "HUMAN GATE · mandatory", HUMAN, "#2e8b57", 2.2),
    node("inbox", "Change inbox", f"{n_open_props} open AI proposal(s)", "HUMAN GATE · accept / reject", HUMAN, "#2e8b57", 2.2),
    node("audit", "8 Audit & export", f"{n_audit:,} append-only events", "SYSTEM · every action logged", SYS),
    "{rank=same; ingest; signals; findings;}", "{rank=same; fit; reqs; score;}", "{rank=same; inbox; review; audit;}",
    "ingest -> signals -> findings;", "findings -> fit [style=invis];",
    'findings -> reqs [constraint=false]; reqs -> fit; fit -> score [constraint=false];',
    "score -> audit [style=invis];", "fit -> inbox [style=invis];",
    'score -> inbox [label=" new wave / weights", constraint=false]; inbox -> review; review -> audit;',
    'score -> review [constraint=false]; review -> reqs [label=" challenge / edit", style=dashed, constraint=false];',
    "}",
])
st.graphviz_chart(dot, width="content")
md(" ".join([chip("AI · autonomous", "proposed"), chip("SYSTEM · deterministic", "system"),
             chip("HUMAN GATE · mandatory", "approved"),
             "<span class='muted'>AI only ever creates or edits in status <b>proposed</b> and recomputes scores; "
             "status and priority changes need a named PM and a rationale. Brand-fit FAIL blocks approval unless "
             "the PM overrides with a rationale.</span>"]))

with st.expander("Who does what — AI autonomy vs. human review"):
    st.dataframe(pd.DataFrame([
        ["Ingest & provenance", "System", "file/sheet/row, URL + date, trust tier", "–"],
        ["Signal extraction, scope check", "AI (cheap model)", "verbatim → signal with verified quote", "–"],
        ["Clustering into findings", "AI", "finding ← signals ← verbatims", "–"],
        ["Requirement drafting", "AI (reasoning model)", "requirement ← findings; evidence vs. assumptions", "Created only as 'proposed'"],
        ["Brand / segment / market / feasibility fit", "AI (luna, sol re-check)", "pass/warn/fail + rationale", "Brand FAIL blocks approval"],
        ["Scoring & ranking", "System (deterministic)", "factor breakdown + rationale per derivative × market", "–"],
        ["Priority changes after new evidence", "AI proposes", "change proposal with factor delta", "PM accepts / rejects"],
        ["Approve / reject / defer / edit / challenge", "PM", "audit event with actor + rationale", "Mandatory human decision"],
    ], columns=["Step", "Actor", "Traceability", "Human gate"]), hide_index=True, width="stretch")

# ------------------------------------------------------------------------------------------------ funnel
st.subheader("Live funnel")
c = st.columns(6)
c[0].metric("Verbatims", f"{n_verb:,}", help="Customer feedback items (deduplicated by ID).")
c[1].metric("In scope", f"{n_inscope:,}", help=f"Of {n_extracted:,} verbatims processed by extractor {latest_ver or '–'}; "
            "out-of-scope = regulatory, engineering, pricing, dealer/service.")
c[2].metric("Signals", f"{n_signals:,}", help="Customer signals extracted from in-scope verbatims (one verbatim can carry several).")
c[3].metric("Findings", f"{n_findings:,}", help=", ".join(f"{k}: {v}" for k, v in fk_map.items()) or "none yet")
c[4].metric("Requirements", f"{n_req}", help=", ".join(f"{k}: {v}" for k, v in rs_map.items()) or "none yet")
c[5].metric("Approved by PM", f"{rs_map.get('approved', 0)}")

funnel = pd.DataFrame([
    ("Verbatims", n_verb), ("Processed", n_extracted), ("In scope", n_inscope), ("Signals", n_signals),
    *[(f"Findings · {k}", v) for k, v in sorted(fk_map.items())],
    *[(f"Requirements · {s}", rs_map.get(s, 0)) for s in ["proposed", "challenged", "approved", "deferred", "rejected"] if rs_map.get(s)],
], columns=["stage", "count"])
left, right = st.columns([3, 2], gap="large")
with left:
    if funnel["count"].sum() == 0:
        empty("No data ingested yet.")
    else:
        ch = alt.Chart(funnel).mark_bar(color="#1c69d4", cornerRadiusEnd=3).encode(
            x=alt.X("count:Q", title=None, scale=alt.Scale(type="symlog")),
            y=alt.Y("stage:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
            tooltip=["stage", alt.Tooltip("count:Q", format=",")],
        ) + alt.Chart(funnel).mark_text(align="left", dx=4, fontSize=11, color="#1d2733").encode(
            x="count:Q", y=alt.Y("stage:N", sort=None), text=alt.Text("count:Q", format=","))
        st.altair_chart(ch.properties(height=28 * len(funnel) + 20), width="stretch")
        st.caption("Log-like scale so later stages stay visible next to 10k verbatims.")

with right:
    st.markdown("**Evidence sources**")
    labels = {"feedback": "Customer verbatims", "study": "Customer study items", "sales": "Sales volume cells",
              "option_list": "Option-list entries", "web": "Web research (cited)", "reference": "Reference facts"}
    src = pd.DataFrame([(labels.get(k, k), src_map.get(k, 0)) for k in labels], columns=["source", "items"])
    st.dataframe(src, hide_index=True, width="stretch",
                 column_config={"items": st.column_config.NumberColumn(format="%d")})
    tiers = q("SELECT kind, COALESCE(trust_tier, 'untiered') tier, COUNT(*) n FROM source_item "
              "WHERE kind IN ('web', 'reference') GROUP BY 1, 2 ORDER BY 1, 2")
    if not tiers.empty:
        st.markdown("**Trust tiers of web & reference sources**")
        st.altair_chart(alt.Chart(tiers).mark_bar().encode(
            x=alt.X("n:Q", title="items"), y=alt.Y("kind:N", title=None), yOffset=alt.YOffset("tier:N"),
            color=alt.Color("tier:N", scale=alt.Scale(domain=["T1", "T2", "T3", "untiered"],
                                                     range=["#2e8b57", "#d99a00", "#c0392b", "#c9d0d8"]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["kind", "tier", "n"]).properties(height=150), width="stretch")
        st.caption("T1 = official/primary (BMW, OEM, regulators), T2 = established press/analysts, T3 = forums/blogs.")

# ------------------------------------------------------------------------------------------------ waves
st.subheader("Timeline")
md("<span class='sim-badge'>SIMULATION</span> <span class='muted'>The feedback has no dates, so a ~2-year "
   "requirements process is simulated in three ingest waves. Each wave makes new evidence visible, re-derives "
   "and re-scores; the PM sees what changed and why.</span>")
@st.dialog("Open the next simulated wave?")
def confirm_wave(w: int):
    st.markdown(f"**{WAVES[w]['label']}** (simulated {WAVES[w]['simulated_date']})")
    st.write(WAVES[w]["description"])
    st.warning("This runs the AI pipeline — requirement derivation (reasoning model), fit checks and a "
               "prioritization run. It **costs OpenAI budget** and takes a few minutes.", icon=":material/payments:")
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


wave = current_wave()
opened = q("SELECT entity_id, ts, actor_id FROM audit_event WHERE action = 'open_wave' ORDER BY id")
opened_map = {str(r.entity_id): r for r in opened.itertuples()}
cols = st.columns(len(WAVES))
nxt = wave + 1 if wave + 1 in WAVES else None
for col, (w, info) in zip(cols, WAVES.items()):
    with col, st.container(border=True):
        state = "current" if w == wave else ("opened" if w < wave else ("next" if w == nxt else "upcoming"))
        md(f"{chip(state, {'current': 'Must', 'opened': 'approved', 'next': 'proposed', 'upcoming': 'Could'}[state])}"
           f" <span class='muted'>simulated {info['simulated_date']}</span>")
        st.markdown(f"**{info['label']}**")
        st.caption(info["description"])
        ev = opened_map.get(str(w))
        if ev is not None:
            st.caption(f"Opened {str(ev.ts)[:16].replace('T', ' ')} by {ev.actor_id}")
        if w == nxt:
            if st.button(f"Open wave {w}", type="primary", key=f"open_wave_{w}", icon=":material/play_arrow:"):
                confirm_wave(w)


if st.session_state.get("wave_log"):
    wl = st.session_state["wave_log"]
    if wl["error"]:
        st.error(f"Wave {wl['wave']} failed: {wl['error']}")
    else:
        st.success(f"Wave {wl['wave']} done. Review new requirements in the Backlog and AI proposals in the Change inbox.")
    if wl["log"]:
        st.code("\n".join(wl["log"]), language=None)
if nxt is None and wave:
    st.caption("All simulated waves are open.")
