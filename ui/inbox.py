"""Change inbox: open AI change proposals (priority / content / evidence link / new requirement); the PM accepts
or rejects each with a rationale (service.decide_proposal). Accepting applies the change."""

import streamlit as st

from bmw_req import service
from ui.common import (act, actor, chip, empty, esc, loads, md, nz, open_requirement, page_header, q, run_label, short)

page_header("Change inbox",
            "The AI never changes a PM decision. When new evidence, a weight change or a challenge suggests a "
            "change, it lands here as a proposal with its cause — you accept or reject it.")

props = q("""SELECT p.*, r.title, r.status AS req_status, pr.ts AS run_ts, pr.trigger AS run_trigger
             FROM change_proposal p JOIN requirement r ON r.id = p.requirement_id
             LEFT JOIN prioritization_run pr ON pr.id = p.run_id ORDER BY p.id""")
if props.empty:
    empty("No change proposals yet. They appear after a new wave, a weight change or a PM challenge.")
    st.stop()
props["kind"] = props["kind"].fillna("priority")
open_p = props[props["status"] == "open"]
KINDS = [("priority", "Priority changes"), ("content", "Content edits"), ("link_finding", "Evidence links"),
         ("new_requirement", "New requirements"), ("extend", "Merge into existing"), ("status", "Status")]
me = actor()

c = st.columns(len(KINDS) - 1)
for col, (k, lbl) in zip(c, KINDS[:-1]):
    col.metric(lbl, int((open_p["kind"] == k).sum()))

present = [(k, lbl) for k, lbl in KINDS if (open_p["kind"] == k).any()]
if open_p.empty:
    st.success("Inbox zero — no open proposals.", icon=":material/done_all:")
else:
    tabs = st.tabs([f"{lbl} ({int((open_p['kind'] == k).sum())})" for k, lbl in present])
    for tab, (k, lbl) in zip(tabs, present):
        with tab:
            for p in open_p[open_p["kind"] == k].itertuples():
                with st.container(border=True):
                    tgt = f" · {p.vehicle_model_id} × {p.market_code}" if isinstance(p.vehicle_model_id, str) else ""
                    md(f"**#{int(p.id)} · {esc(p.requirement_id)}{esc(tgt)}** — {esc(short(p.title, 100))} "
                       f"{chip(p.req_status)}")
                    if k == "priority":
                        md(f"PM priority {chip(nz(p.old_value, 'not set'), nz(p.old_value))} → AI proposes "
                           f"{chip(p.proposed_value, p.proposed_value)}")
                    elif k == "link_finding":
                        fid = str(p.field).split(":")[-1]
                        f = q("SELECT id, source_kind, title, summary FROM finding WHERE id = ?", (int(fid),)) if fid.isdigit() else None
                        md(f"Link finding **F{esc(fid)}** as {chip(p.proposed_value, 'pass')}"
                           + (f" — {esc(f.iloc[0]['source_kind'])}: <i>{esc(short(f.iloc[0]['title'], 120))}</i>"
                              if f is not None and not f.empty else ""))
                    elif k == "extend":
                        delta = loads(p.evidence_delta_json, {}) or {}
                        md(f"A new AI draft — <i>{esc(delta.get('draft_title', ''))}</i> — states the same need as "
                           f"<b>{esc(p.requirement_id)}</b>. Instead of a duplicate, the AI proposes to extend it: "
                           f"<b>{esc(p.proposed_value)}</b>.")
                        if delta.get("targets"):
                            for t in delta["targets"]:
                                st.caption(f"{t['vehicle_model_id']} × {t['market_code']} ({t.get('realization') or '–'}): "
                                           f"{short(t.get('market_note'), 220)}")
                        fids = [*delta.get("supports", []), *delta.get("contradicts", [])]
                        if fids:
                            fl = q(f"SELECT id, source_kind, title FROM finding WHERE id IN ({','.join('?' * len(fids))})",
                                   tuple(int(x) for x in fids))
                            st.caption(" · ".join(f"F{r.id} {r.source_kind}: {short(r.title, 60)}" for r in fl.itertuples()))
                    elif k == "new_requirement":
                        md("New AI-drafted requirement — accept to keep it in the backlog as <b>proposed</b>, "
                           "reject to drop it from review.")
                    else:
                        md(f"<b>{esc(p.field)}</b>")
                        c1, c2 = st.columns(2)
                        c1.markdown("Current")
                        c1.code(nz(p.old_value, "∅"), language=None, wrap_lines=True)
                        c2.markdown("Proposed")
                        c2.code(nz(p.proposed_value, "∅"), language=None, wrap_lines=True)
                    st.caption(f"Cause: {nz(p.reason, '–')}" + (
                        f"  ·  {run_label(p.run_id, p.run_ts, p.run_trigger)}" if nz(p.run_id) else ""))
                    delta = loads(p.evidence_delta_json, None)
                    if isinstance(delta, dict) and delta.get("score") is not None:
                        st.caption(f"New score {delta['score']:.1f}"
                                   + (f" (previous run {delta['previous_run']})" if delta.get("previous_run") else ""))
                    with st.form(f"prop_{int(p.id)}", clear_on_submit=True, border=False):
                        c1, c2, c3 = st.columns([5, 1, 1], vertical_alignment="bottom")
                        why = c1.text_input("Rationale (required)", key=f"why_{int(p.id)}",
                                            placeholder="Why accept / reject?")
                        acc = c2.form_submit_button("Accept", type="primary", width="stretch")
                        rej = c3.form_submit_button("Reject", width="stretch")
                        if acc or rej:
                            act(service.decide_proposal, int(p.id), bool(acc), me, why,
                                success=f"Proposal #{int(p.id)} {'accepted' if acc else 'rejected'}")
                    if st.button("Open requirement", key=f"open_{int(p.id)}", icon=":material/open_in_new:"):
                        open_requirement(p.requirement_id)

st.subheader("Decided proposals")
hist = props[props["status"] != "open"]
if hist.empty:
    st.caption("None yet.")
else:
    st.dataframe(hist.sort_values("id", ascending=False)[
        ["id", "status", "kind", "requirement_id", "vehicle_model_id", "market_code", "field", "old_value",
         "proposed_value", "decided_by", "decided_at", "decision_rationale", "reason"]],
        hide_index=True, width="stretch",
        column_config={"reason": st.column_config.TextColumn("AI cause", width="large"),
                       "decision_rationale": st.column_config.TextColumn("PM rationale", width="medium")})
    st.caption("'superseded' = replaced by a newer proposal for the same target from a later run.")
