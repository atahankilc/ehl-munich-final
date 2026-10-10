"""Requirement detail: content (evidence vs. assumption), per-market score breakdown + history, evidence chain,
fit checks, PM decisions (approve/reject/defer, gates, priorities, edits, evidence links, challenge), audit trail."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from bmw_req import service
from ui.common import (FACTOR_COLOR, NO_DATA_COLOR, PRIORITIES, _LOCK, act, actor, chip, clear_caches, conn, empty, esc,
                       latest_fit, loads, log_access_once, md, metrics_wave, page_header, q, requirement_options,
                       nz, run_label, short, targets_df, write)

page_header("Requirement details", "One requirement, fully traceable: sources → findings → requirement → score → PM decision. "
            "For a quicker read, use Review requirements.")

opts = requirement_options()
if not opts:
    empty("No requirements yet. They are drafted by the AI when a wave is opened (Home → Where we are).")
    st.stop()
cur = st.session_state.get("req_id")
idx = next((i for i, o in enumerate(opts) if cur and o.startswith(f"{cur} ·")), 0)
pick = st.selectbox("Requirement", opts, index=idx, label_visibility="collapsed")
rid = pick.split(" · ")[0]
st.session_state["req_id"] = rid
log_access_once("view", "requirement", rid)

rdf = q("SELECT * FROM requirement WHERE id = ?", (rid,))
if rdf.empty:
    empty(f"{rid} not found.")
    st.stop()
req = rdf.iloc[0].to_dict()
deriv = loads(req.get("derivation_json"), {}) or {}
tdf = targets_df()
tdf = tdf[tdf["requirement_id"] == rid].sort_values(["vehicle_model_id", "market_code"]) if not tdf.empty else tdf

# ------------------------------------------------------------------------------------------------ header
st.markdown(f"### {esc(rid)} · {esc(req['title'])}")
mnl = bool(req.get("must_not_lose") or 0)
md(" ".join([
    chip(req["status"]), chip(f"v{int(req['version'])}", "system"),
    chip(f"Evidence {req.get('evidence_level') or '–'}", req.get("evidence_level")),
    chip(f"Horizon: {(req.get('horizon') or '–').replace('_', ' ')}", "proposed"),
    chip(f"Kano: {req.get('kano_class') or '–'}", "system"),
    chip(f"Effort {req.get('effort') or '–'}", "system"),
    chip("Must-not-lose", "approved") if mnl else "",
    f"<span class='muted'>{esc(req.get('category') or '')} · created by {esc(req.get('created_by') or '–')}"
    f" · {esc(str(req.get('created_at') or '')[:16].replace('T', ' '))}</span>",
]))
if req.get("kano_drift") and str(req["kano_drift"]).lower() != "stable":
    st.caption(f"Kano drift: {req['kano_drift']}")

tabs = st.tabs(["Overview", "Score", "Evidence chain", "Fit checks", "PM decision", "Audit trail"])

# ------------------------------------------------------------------------------------------------ a. overview
with tabs[0]:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("**Description**")
        st.write(req.get("description") or "–")
        st.markdown("**Target metric**")
        st.write(req.get("target_metric") or "–")
        st.markdown("**Acceptance criteria**")
        st.write(req.get("acceptance_criteria") or "–")
        if not tdf.empty:
            st.markdown("**Targets (derivative × market)**")
            st.dataframe(tdf[["target", "realization", "score", "proposed_priority", "pm_priority", "target_evidence",
                              "market_note"]], hide_index=True, width="stretch",
                         column_config={"score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
                                        "proposed_priority": "AI prio", "pm_priority": "PM prio", "target_evidence": "Evid.",
                                        "market_note": st.column_config.TextColumn("Market note", width="large")})
    with right:
        def card(kind, title, body):
            md(f"<div class='card {kind}'><h4>{chip(title.split(' ')[0].upper(), title.split(' ')[0].upper())} "
               f"{esc(' '.join(title.split(' ')[1:]))}</h4><div class='kv'>{esc(body or '–').replace(chr(10), '<br>')}</div></div>")

        card("evidence", "Evidence what the cited sources show", deriv.get("evidence_summary"))
        horizon_txt = deriv.get("horizon_reason")
        card("assumption", "Assumption forward-looking (3–5 yr)",
             (req.get("assumptions") or "") + (f"\n\nHorizon: {horizon_txt}" if horizon_txt else "")
             + (f"\nEffort: {deriv.get('effort_reason')}" if deriv.get("effort_reason") else ""))
        card("uncertainty", "Uncertainty what could make this wrong", req.get("uncertainties"))
        ce = req.get("conflicting_evidence")
        if ce and str(ce).strip().lower() not in ("none", "none found", "-", "–"):
            card("conflict", "Conflict conflicting evidence", ce)
        else:
            card("evidence", "Conflict none found by the AI — check the Evidence chain tab", "")

# ------------------------------------------------------------------------------------------------ b. score
with tabs[1]:
    if tdf.empty or tdf["score"].isna().all():
        empty("Not scored yet — scores appear after a prioritization run.")
    else:
        st.caption("score = 100 × Σ(weight × factor value) / Σ(weights of factors with data) × confidence(evidence level)"
                   " + market-fit modifier + effort modifier, clipped to 0–100. Bands: Must ≥ 60, Should ≥ 45.")
        sub_tabs = st.tabs(list(tdf["target"]))
        for stab, (_, t) in zip(sub_tabs, tdf.iterrows()):
            with stab:
                b = loads(t["score_breakdown_json"], {}) or {}
                if not b:
                    st.caption("No breakdown stored for this target.")
                    continue
                m = st.columns(5)
                m[0].metric("Score", f"{b.get('score', t['score'] or 0):.0f}")
                m[1].metric("AI proposes", nz(t["proposed_priority"], "–"))
                m[2].metric("PM priority", nz(t["pm_priority"], "not set"))
                m[3].metric("Evidence level", b.get("evidence_level", "–"), help=f"confidence ×{b.get('confidence', '–')}")
                mods = b.get("modifiers", {})
                m[4].metric("Modifiers", f"{sum(v or 0 for v in mods.values()):+.0f}",
                            help=", ".join(f"{k.replace('_', ' ')} {v:+.0f}" for k, v in mods.items()))
                facs = b.get("factors", {})
                fdf = pd.DataFrame([{
                    "factor": f.get("label", k), "points": f.get("points") or 0.0, "weight": f.get("weight"),
                    "value": f.get("value"), "available": bool(f.get("available")),
                    "state": "has data" if f.get("available") else "no data",
                    "explanation": f.get("explanation"),
                } for k, f in facs.items()])
                if not fdf.empty:
                    fdf["shown"] = fdf.apply(lambda r: r["points"] if r["available"] else 1.5, axis=1)
                    fdf["label"] = fdf.apply(lambda r: f"{r['points']:.1f} pts" if r["available"] else "no data", axis=1)
                    bars = alt.Chart(fdf).mark_bar(cornerRadiusEnd=3).encode(
                        y=alt.Y("factor:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
                        x=alt.X("shown:Q", title="points contributed to the score"),
                        color=alt.Color("state:N", scale=alt.Scale(domain=["has data", "no data"],
                                                                   range=[FACTOR_COLOR, NO_DATA_COLOR]), legend=None),
                        tooltip=["factor", "weight", "value", alt.Tooltip("points:Q", format=".1f"), "explanation"])
                    text = alt.Chart(fdf).mark_text(align="left", dx=4, fontSize=11, color="#4a5563").encode(
                        y=alt.Y("factor:N", sort=None), x="shown:Q", text="label:N")
                    st.altair_chart((bars + text).properties(height=34 * len(fdf) + 20), width="stretch")
                    st.dataframe(fdf[["factor", "weight", "value", "points", "explanation"]], hide_index=True,
                                 width="stretch", column_config={
                                     "value": st.column_config.NumberColumn("value 0–1", format="%.2f"),
                                     "points": st.column_config.NumberColumn(format="%.1f"),
                                     "explanation": st.column_config.TextColumn(width="large")})
                st.markdown("**Rationale**")
                st.write(b.get("rationale") or "–")
                if b.get("gaps"):
                    md("**Evidence gaps** " + " ".join(chip(g, "warn") for g in b["gaps"])
                       + " <span class='muted'>— weights renormalized over the factors with data</span>")
                gates = b.get("gates", {})
                if gates:
                    md("**Gates** " + " ".join(chip(f"{k}: {v or '–'}", v) for k, v in gates.items())
                       + " <span class='muted'>brand = gate; feasibility = context only</span>")
                if nz(t["market_note"]):
                    st.caption(f"Market note: {t['market_note']}")

        st.markdown("**Score history across prioritization runs**")
        hist = q("""SELECT s.run_id, s.vehicle_model_id || ' × ' || s.market_code target, s.score, s.rank, s.priority,
                           r.ts, r.trigger FROM score_snapshot s JOIN prioritization_run r ON r.id = s.run_id
                    WHERE s.requirement_id = ? ORDER BY s.run_id""", (rid,))
        if hist.empty:
            st.caption("No snapshots yet.")
        else:
            hist["run"] = hist.apply(lambda r: run_label(r["run_id"], None, r["trigger"]), axis=1)
            order = list(dict.fromkeys(hist["run"]))
            st.altair_chart(alt.Chart(hist).mark_line(point=True).encode(
                x=alt.X("run:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 100]), title="score"),
                color=alt.Color("target:N", title=None, legend=alt.Legend(orient="bottom")),
                tooltip=["run", "target", alt.Tooltip("score:Q", format=".1f"), "rank", "priority", "ts"],
            ).properties(height=240), width="stretch")
            causes = q("""SELECT run_id, entity_id, rationale FROM audit_event WHERE action = 'rescore'
                          AND entity_id LIKE ? ORDER BY id""", (f"{rid}:%",))
            if not causes.empty:
                with st.expander("Why the score moved (per run)"):
                    st.dataframe(causes.rename(columns={"entity_id": "target", "rationale": "cause"}), hide_index=True,
                                 width="stretch", column_config={"cause": st.column_config.TextColumn(width="large")})

# ------------------------------------------------------------------------------------------------ c. evidence chain
with tabs[2]:
    fl = q("""SELECT f.id, f.source_kind, f.type, f.title, f.summary, f.category, f.vehicle_model_id, f.market_code,
                     f.metrics_json, f.first_wave, rf.relation
              FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ?
              ORDER BY rf.relation DESC, f.id""", (rid,))
    if fl.empty:
        empty("No linked findings.")
    else:
        cnt = q("""SELECT fs.finding_id, s.kind, COALESCE(s.market_code, '–') market, COUNT(*) n,
                          MAX(s.trust_tier) tier, MAX(s.external_id) ext
                   FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id
                   WHERE fs.finding_id IN (SELECT finding_id FROM requirement_finding WHERE requirement_id = ?)
                   GROUP BY 1, 2, 3""", (rid,))
        n_src = cnt.groupby("finding_id")["n"].sum().to_dict() if not cnt.empty else {}
        fl["n_sources"] = fl["id"].map(n_src).fillna(0).astype(int)
        CAP = 14
        shown = pd.concat([fl[fl["relation"] != "supports"],
                           fl[fl["relation"] == "supports"].sort_values("n_sources", ascending=False)]).head(CAP)
        kinds = fl["source_kind"].value_counts().to_dict()
        md(" ".join(chip(f"{v} {k} finding(s)", "proposed") for k, v in kinds.items())
           + f" {chip(str(int(fl['n_sources'].sum())) + ' linked sources', 'system')}"
           + (f" {chip(str((fl['relation'] == 'contradicts').sum()) + ' conflicting', 'fail')}"
              if (fl["relation"] == "contradicts").any() else "")
           + (f" <span class='muted'>graph shows {len(shown)} of {len(fl)} findings</span>" if len(fl) > CAP else ""))

        def lab(s):
            import re
            return re.sub(r"\\(?!n)", "/", str(s)).replace('"', "'")

        KCOL = {"verbatim": "#e3edfb", "study": "#efe5f8", "web": "#fff1d0", "reference": "#eceff3"}
        g = ['digraph E {', 'rankdir=LR; bgcolor="transparent"; nodesep=0.12; ranksep=0.55;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, margin="0.1,0.05"];',
             'edge [color="#8a94a3", arrowsize=0.6];',
             f'R [label="{lab(rid)}\\n{lab(short(req["title"], 38))}", fillcolor="#1c69d4", fontcolor="white", fontsize=11];']
        for f in shown.itertuples():
            sc = cnt[cnt["finding_id"] == f.id] if not cnt.empty else cnt
            if f.source_kind == "verbatim":
                by_m = " · ".join(f"{r.market} {int(r.n)}" for r in sc.sort_values("n", ascending=False).itertuples())
                slabel = f"{int(sc['n'].sum()) if not sc.empty else 0} verbatims\\n{by_m}"
            elif f.source_kind == "web":
                tiers = ", ".join(sorted({str(t) for t in sc["tier"].dropna()})) if not sc.empty else "–"
                slabel = f"{int(sc['n'].sum()) if not sc.empty else 0} web source(s)\\n{tiers}"
            else:
                slabel = f"{int(sc['n'].sum()) if not sc.empty else 0} {f.source_kind} item(s)"
            g.append(f'S{f.id} [label="{lab(slabel)}", fillcolor="#f3f5f8", color="#c9d0d8", fontsize=9];')
            g.append(f'F{f.id} [label="F{f.id} · {lab(f.source_kind)}\\n{lab(short(f.title, 34))}", '
                     f'fillcolor="{KCOL.get(f.source_kind, "#eceff3")}"'
                     + (', color="#c0392b", penwidth=2' if f.relation == "contradicts" else "") + '];')
            g.append(f"S{f.id} -> F{f.id};")
            g.append(f'F{f.id} -> R' + (' [color="#c0392b", style=dashed, label="contradicts", fontsize=8, fontcolor="#c0392b"]'
                                        if f.relation == "contradicts" else "") + ";")
        if len(fl) > CAP:
            g.append(f'MORE [label="+ {len(fl) - CAP} more finding(s)", shape=plaintext, fillcolor="transparent"]; MORE -> R [style=dotted];')
        for t in tdf.itertuples():
            fill = {"Must": "#d6e6fb", "Should": "#eef4fd", "Could": "#f3f5f8"}.get(t.proposed_priority, "#f3f5f8")
            sc_txt = f"{t.score:.0f}" if pd.notna(t.score) else "–"
            g.append(f'T_{t.vehicle_model_id}_{t.market_code} [label="{t.vehicle_model_id} × {t.market_code}\\n'
                     f'score {sc_txt} · {t.proposed_priority or "–"}", fillcolor="{fill}", shape=box];')
            g.append(f"R -> T_{t.vehicle_model_id}_{t.market_code};")
        g.append("}")
        st.graphviz_chart("\n".join(g), width="content")

        st.markdown("**Linked findings and their sources**")
        mw = metrics_wave()
        for f in fl.itertuples():
            conflict = f.relation == "contradicts"
            head = (f"{'CONFLICTING · ' if conflict else ''}F{f.id} · {f.source_kind} · {short(f.title, 90)}"
                    f"  ({f.n_sources} source{'s' if f.n_sources != 1 else ''})")
            with st.expander(head, expanded=False):
                md(" ".join([chip(f.relation, "fail" if conflict else "pass"), chip(f.source_kind, "proposed"),
                             chip(f.type or "–", "system"), chip(f.category or "–", "system"),
                             f"<span class='muted'>scope {esc(f.vehicle_model_id or 'line')} × {esc(f.market_code or 'all markets')}"
                             f" · first wave {f.first_wave or 1}</span>"]))
                st.write(f.summary or "")
                mt = loads(f.metrics_json, {}) or {}
                if f.source_kind == "verbatim":
                    mk = (mt.get("by_wave", {}).get(mw, {}) or {}).get("markets", {}) or {}
                    if mk:
                        st.dataframe(pd.DataFrame([{
                            "market": k, "verbatims": v.get("verbatims"), "share of market feedback": v.get("share"),
                            "market base": v.get("base"), "severity-weighted": v.get("severity_weighted"),
                            "types": ", ".join(f"{a} {b}" for a, b in (v.get("types") or {}).items()),
                            "channels": ", ".join(f"{a} {b}" for a, b in (v.get("channels") or {}).items()),
                        } for k, v in mk.items()]), hide_index=True, width="stretch", column_config={
                            "share of market feedback": st.column_config.NumberColumn(format="percent")})
                        st.caption(f"As of simulated wave {mw} (cumulative).")
                elif mt:
                    st.caption("Metrics: " + ", ".join(f"{k} = {v}" for k, v in mt.items() if not isinstance(v, (dict, list)))
                               + ("; tiers " + json.dumps(mt["tiers"]) if isinstance(mt.get("tiers"), dict) else ""))
                srcs = q("""SELECT s.kind, s.external_id, s.ref, s.country, s.market_code, s.url, s.published_at,
                                   s.retrieved_at, s.trust_tier, s.text, s.meta_json, COALESCE(fs.quote, s.quote) quote
                            FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id
                            WHERE fs.finding_id = ? LIMIT 30""", (int(f.id),))
                for s in srcs.itertuples():
                    meta = loads(s.meta_json, {}) or {}
                    if s.kind == "feedback":
                        md(f"<span class='muted'><b>{esc(s.external_id)}</b> · {esc(s.country or s.market_code)} · "
                           f"{esc(meta.get('channel') or '–')} · {esc(meta.get('engine') or '')}</span>"
                           f"<div class='quote'>“{esc(s.quote or short(s.text, 300))}”</div>")
                    elif s.kind == "web":
                        md(f"<span class='muted'>{chip(s.trust_tier or 'T?', s.trust_tier)} <b>{esc(meta.get('publisher') or '–')}</b>"
                           f" · published {esc(s.published_at or 'n/a')} · retrieved {esc(str(s.retrieved_at or '')[:10])}"
                           f" · <a href='{esc(s.url)}' target='_blank'>{esc(short(s.url, 70))}</a></span>"
                           f"<div class='quote'>“{esc(s.quote or short(s.text, 300))}”</div>")
                    elif s.kind == "study":
                        nums = ", ".join(f"{k} {meta[k]:.2f}" if isinstance(meta.get(k), float) else f"{k} {meta[k]}"
                                         for k in ("mean", "z_within_column", "rank_within_column", "n_items_in_column")
                                         if meta.get(k) is not None)
                        md(f"<span class='muted'><b>Study</b> · {esc(s.external_id)} · {esc(s.market_code)} · "
                           f"{esc(meta.get('scale') or '')} · {esc(nums)}</span><div class='quote'>{esc(short(s.text, 300))}</div>")
                    else:
                        md(f"<span class='muted'><b>{esc(s.kind)}</b> · {esc(s.ref)}</span><div class='quote'>{esc(short(s.text, 300))}</div>")
                if f.n_sources > 30:
                    st.caption(f"Showing 30 of {f.n_sources} sources — all are in the Findings explorer and the export.")

# ------------------------------------------------------------------------------------------------ d. fit checks
with tabs[3]:
    fit = latest_fit(rid)
    if fit.empty:
        empty("No fit checks yet.")
    else:
        TYPES = [("brand", "Brand fit (gate)"), ("segment", "Segment fit"), ("market", "Market fit (scored ±)"),
                 ("feasibility", "Realization context (non-blocking, Q-010)")]
        blocked = set()
        with _LOCK:
            blocked = set(service.brand_blocked(conn(), rid))
        rows_html = ["<table style='width:100%;border-collapse:collapse;font-size:0.88rem'><tr>"
                     "<th style='text-align:left;padding:4px'>Target</th>"
                     + "".join(f"<th style='text-align:left;padding:4px'>{esc(lbl)}</th>" for _, lbl in TYPES) + "</tr>"]
        for (d, m), grp in fit.groupby(["vehicle_model_id", "market_code"], dropna=False):
            res = {r.check_type: r.result for r in grp.itertuples()}
            tgt = f"{d}×{m}"
            cells = []
            for ct, _ in TYPES:
                v = res.get(ct)
                extra = chip("overridden", "overridden") if ct == "brand" and v == "fail" and tgt not in blocked else ""
                cells.append(f"<td style='padding:4px'>{chip(v or '–', v)}{extra}</td>")
            rows_html.append(f"<tr style='border-top:1px solid #eceff3'><td style='padding:4px'><b>{esc(d)} × {esc(m)}</b></td>"
                             + "".join(cells) + "</tr>")
        md("".join(rows_html) + "</table>")
        if blocked:
            st.warning(f"Brand-fit FAIL without override on {', '.join(blocked)} — approval is blocked until the PM "
                       "overrides the gate with a rationale (PM decision tab).", icon=":material/block:")
        st.markdown("**Rationales**")
        for ct, lbl in TYPES:
            sub = fit[fit["check_type"] == ct]
            if sub.empty:
                continue
            with st.expander(lbl, expanded=ct == "brand" or (sub["result"] != "pass").any()):
                uniq = sub.drop_duplicates(subset=["result", "rationale"])
                for r in uniq.itertuples():
                    tg = ", ".join(f"{a}×{b}" for a, b in sub[(sub["result"] == r.result) & (sub["rationale"] == r.rationale)]
                                   [["vehicle_model_id", "market_code"]].itertuples(index=False))
                    md(f"{chip(r.result)} <span class='muted'>{esc(tg)} · {esc(r.checked_by)} · "
                       f"{esc(str(r.checked_at)[:16].replace('T', ' '))}</span><br>{esc(r.rationale)}")
                if ct == "feasibility":
                    st.caption("Feasibility uses platform/plant reference data as context only; it never blocks approval "
                               "and is never scored (Q-010 option b, D-030).")

# ------------------------------------------------------------------------------------------------ e. PM decision
with tabs[4]:
    me = actor()
    st.caption(f"Acting as **{me}** (change in the sidebar). Every decision needs a rationale and is written to "
               "the append-only audit trail.")
    with _LOCK:
        blocked = service.brand_blocked(conn(), rid)

    st.markdown("##### Decision")
    with st.form(f"status_{rid}", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        decision = c1.radio("Set status", ["approved", "rejected", "deferred", "proposed"],
                            format_func=lambda s: {"approved": "Approve", "rejected": "Reject", "deferred": "Defer",
                                                   "proposed": "Back to proposed"}[s])
        why = c2.text_area("Rationale (required)", placeholder="Why? e.g. strong US evidence, fits brand, CN needs a variant …")
        if blocked:
            c2.warning(f"Approval blocked: brand-fit FAIL on {', '.join(blocked)} — override below first.",
                       icon=":material/block:")
        if st.form_submit_button("Record decision", type="primary"):
            act(service.set_status, rid, decision, me, why, success=f"{rid} → {decision}")

    if blocked:
        st.markdown("##### Brand-fit gate override")
        fit = latest_fit(rid)
        for tgt in blocked:
            d, m = tgt.split("×")
            rat = fit[(fit["vehicle_model_id"] == d) & (fit["market_code"] == m) & (fit["check_type"] == "brand")]
            with st.form(f"override_{rid}_{tgt}", clear_on_submit=True):
                md(f"**{esc(d)} × {esc(m)}** {chip('fail')} <span class='muted'>"
                   f"{esc(rat.iloc[0]['rationale'] if not rat.empty else '')}</span>")
                why_o = st.text_input("Override rationale (required)", key=f"ovr_{tgt}")
                if st.form_submit_button("Override gate"):
                    act(service.override_gate, rid, tgt, me, why_o, success=f"Brand gate overridden for {tgt}")

    st.markdown("##### Priority per target")
    if tdf.empty:
        st.caption("No targets.")
    else:
        st.caption("Default = the AI proposal from the score. Confirming records your priority; later runs only "
                   "*propose* changes to it (AI suggestions).")
        with st.form(f"prio_{rid}", clear_on_submit=False):
            choices = {}
            cols = st.columns(min(len(tdf), 4))
            for i, t in enumerate(tdf.itertuples()):
                cur_p = nz(t.pm_priority) or nz(t.proposed_priority) or "Should"
                with cols[i % len(cols)]:
                    choices[(t.vehicle_model_id, t.market_code)] = st.selectbox(
                        f"{t.target}", PRIORITIES, index=PRIORITIES.index(cur_p) if cur_p in PRIORITIES else 1,
                        help=f"AI proposes {t.proposed_priority or '–'} (score {t.score:.0f})" if pd.notna(t.score) else "not scored",
                        key=f"p_{rid}_{t.target}")
                    st.caption(f"AI: {t.proposed_priority or '–'} · PM: {t.pm_priority if isinstance(t.pm_priority, str) else 'not set'}")
            why_p = st.text_input("Rationale (required)", placeholder="e.g. confirmed — matches US evidence; CN lower due to study only")
            if st.form_submit_button("Confirm priorities", type="primary"):
                changed = [(d, m, p) for (d, m), p in choices.items()
                           if p != nz(tdf[(tdf.vehicle_model_id == d) & (tdf.market_code == m)]["pm_priority"].iloc[0])]
                if not changed:
                    st.info("No priority changed.")
                else:
                    ok = True
                    for d, m, p in changed:
                        ok = ok and write(service.set_priority, rid, d, m, p, me, why_p) is not None
                        if not ok:
                            break
                    if ok:
                        st.session_state["_flash"] = f"Priority recorded for {len(changed)} target(s)"
                        st.rerun()

    st.markdown("##### Edit content")
    with st.expander("Edit requirement fields (creates a new version)"):
        with st.form(f"edit_{rid}"):
            vals = {}
            vals["title"] = st.text_input("Title", req.get("title") or "")
            vals["description"] = st.text_area("Description", req.get("description") or "")
            c1, c2 = st.columns(2)
            vals["target_metric"] = c1.text_area("Target metric", req.get("target_metric") or "")
            vals["acceptance_criteria"] = c2.text_area("Acceptance criteria", req.get("acceptance_criteria") or "")
            c1, c2, c3, c4 = st.columns(4)
            hz = ["today", "at_successor_launch"]
            vals["horizon"] = c1.selectbox("Horizon", hz, index=hz.index(req["horizon"]) if req.get("horizon") in hz else 0)
            kc = ["basic", "performance", "delighter"]
            vals["kano_class"] = c2.selectbox("Kano", kc, index=kc.index(req["kano_class"]) if req.get("kano_class") in kc else 1)
            ef = ["S", "M", "L"]
            vals["effort"] = c3.selectbox("Effort", ef, index=ef.index(req["effort"]) if req.get("effort") in ef else 1)
            vals["category"] = c4.text_input("Category", req.get("category") or "")
            vals["kano_drift"] = st.text_input("Kano drift", req.get("kano_drift") or "")
            c1, c2, c3 = st.columns(3)
            vals["assumptions"] = c1.text_area("Assumptions", req.get("assumptions") or "")
            vals["uncertainties"] = c2.text_area("Uncertainties", req.get("uncertainties") or "")
            vals["conflicting_evidence"] = c3.text_area("Conflicting evidence", req.get("conflicting_evidence") or "")
            why_e = st.text_input("Rationale for the edit (required)")
            if st.form_submit_button("Save edit", type="primary"):
                changes = {k: v for k, v in vals.items() if (v or "") != (req.get(k) or "")}
                if not changes:
                    st.info("Nothing changed.")
                else:
                    act(service.edit_requirement, rid, changes, me, why_e,
                        success=f"{rid}: {len(changes)} field(s) edited → new version")

    st.markdown("##### Evidence links")
    links = q("""SELECT rf.finding_id, rf.relation, f.source_kind, f.title FROM requirement_finding rf
                 JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ? ORDER BY rf.finding_id""", (rid,))
    with st.form(f"links_{rid}", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        lopts = [f"F{r.finding_id} · {r.relation} · {r.source_kind} · {short(r.title, 70)}" for r in links.itertuples()]
        target_link = c1.selectbox("Linked finding", ["— add a new link —"] + lopts)
        new_fid = c2.number_input("…or finding ID to add", min_value=0, step=1, value=0)
        c1, c2 = st.columns([1, 3])
        rel = c1.radio("Relation", ["supports", "contradicts", "remove link"])
        why_l = c2.text_area("Rationale (required)", key=f"why_l_{rid}")
        if st.form_submit_button("Apply"):
            if target_link.startswith("—"):
                fid = int(new_fid)
                if not fid or q("SELECT id FROM finding WHERE id = ?", (fid,)).empty:
                    st.error("Enter an existing finding ID to add a link.")
                    fid = None
            else:
                fid = int(target_link.split(" · ")[0][1:])
            if fid:
                act(service.set_finding_link, rid, fid, None if rel == "remove link" else rel, me, why_l,
                    success=f"Evidence link F{fid} → {rel}")

    st.markdown("##### Challenge the AI")
    st.caption("Ask why, point out a gap or disagree. The reasoning model answers from the stored evidence plus a "
               "semantic search over all customer signals; any change it suggests becomes a proposal in the Change "
               "inbox — it never edits the requirement itself. Costs a few cents of OpenAI budget.")
    with st.form(f"challenge_{rid}", clear_on_submit=False):
        question = st.text_area("Your challenge", placeholder="e.g. Is this really a US-only need? EU owners seem to praise the opposite.")
        go = st.form_submit_button("Challenge", icon=":material/forum:")
    if go:
        if not question or len(question.strip()) < 5:
            st.error("Write the challenge first.")
        else:
            try:
                from bmw_req.llm import LLM
                from bmw_req.pipeline import challenge as ch

                with st.spinner("The AI analyst is reviewing the evidence …"), _LOCK:
                    out = ch.challenge(conn(), LLM(conn=conn()), rid, question.strip(), me)
                st.session_state[f"challenge:{rid}"] = out
                clear_caches()
            except Exception as e:
                st.error(f"Challenge failed: {type(e).__name__}: {e}")
    res = st.session_state.get(f"challenge:{rid}")
    if res:
        a = res["answer"]
        verdict = a.get("verdict", "–")
        md(f"**Verdict** {chip(verdict, {'upheld': 'fail', 'partially_upheld': 'warn', 'not_upheld': 'pass'}.get(verdict))}"
           f" <span class='muted'>cost ${res.get('cost') or 0:.3f}{' (cached)' if res.get('cached') else ''}</span>")
        st.write(a.get("answer"))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Evidence for**")
            for x in a.get("evidence_for") or ["–"]:
                st.markdown(f"- {x}")
        with c2:
            st.markdown("**Evidence against**")
            for x in a.get("evidence_against") or ["–"]:
                st.markdown(f"- {x}")
    props = q("""SELECT id, kind, field, old_value, proposed_value, reason FROM change_proposal
                 WHERE requirement_id = ? AND status = 'open' ORDER BY id""", (rid,))
    if not props.empty:
        st.markdown(f"**Open AI proposals for {rid}** — decide them under AI suggestions")
        st.dataframe(props, hide_index=True, width="stretch")
        if st.button("Go to AI suggestions", icon=":material/inbox:"):
            st.switch_page("ui/inbox.py")
    prev = q("""SELECT ts, new_value, model FROM audit_event WHERE entity_type = 'requirement' AND entity_id = ?
                AND action = 'challenge_response' ORDER BY id DESC""", (rid,))
    qs = q("""SELECT ts, actor_id, rationale FROM audit_event WHERE entity_type = 'requirement' AND entity_id = ?
              AND action = 'challenge' ORDER BY id DESC""", (rid,))
    if not prev.empty:
        with st.expander(f"Previous challenges ({len(prev)})"):
            for i, r in enumerate(prev.itertuples()):
                a = loads(r.new_value, {}) or {}
                qq = qs.iloc[i] if i < len(qs) else None
                if qq is not None:
                    md(f"<span class='muted'>{esc(str(qq['ts'])[:16].replace('T', ' '))} · {esc(qq['actor_id'])} asked:</span> "
                       f"<i>{esc(qq['rationale'])}</i>")
                md(f"{chip(a.get('verdict', '–'), 'system')} <span class='muted'>{esc(r.model or '')}</span>")
                st.write(a.get("answer", ""))
                st.divider()

# ------------------------------------------------------------------------------------------------ f. audit trail
with tabs[5]:
    with _LOCK:
        trail = service.requirement_trail(conn(), rid)
    if not trail:
        empty("No audit events yet.")
    else:
        c1, c2 = st.columns([3, 1])
        only_h = c1.toggle("Human actions only", value=False)
        newest = c2.toggle("Newest first", value=False)
        items = [e for e in trail if not only_h or e["actor_type"] == "human"]
        if newest:
            items = items[::-1]
        st.caption(f"{len(items)} event(s). Append-only: database triggers reject any UPDATE or DELETE on audit_event.")

        def val(v):
            if v is None:
                return "∅"
            p = loads(v, None)
            if isinstance(p, (dict, list)):
                v = json.dumps(p, ensure_ascii=False)
            return esc(short(v, 220))

        out = ["<div class='tl'>"]
        for e in items[:400]:
            body = []
            if e.get("field") or e.get("old_value") is not None or e.get("new_value") is not None:
                body.append(f"<b>{esc(e.get('field') or '')}</b> {val(e.get('old_value'))} → {val(e.get('new_value'))}")
            if e.get("rationale"):
                body.append(f"<span class='muted'>Rationale:</span> {esc(short(e['rationale'], 400))}")
            out.append(
                f"<div class='tl-item {esc(e['actor_type'])}'><div class='tl-meta'>{esc(str(e['ts'])[:19].replace('T', ' '))} · "
                f"{chip(e['actor_type'])} <b>{esc(e.get('actor_id') or '')}</b> · {esc(e['action'])} · "
                f"{esc(e['entity_type'])} {esc(e['entity_id'])}"
                + (f" · model {esc(e['model'])}" if e.get("model") else "")
                + (f" · run {e['run_id']}" if e.get("run_id") else "")
                + f"</div><div class='tl-body'>{'<br>'.join(body)}</div></div>")
        out.append("</div>")
        md("".join(out))
        if len(items) > 400:
            st.caption("Showing 400 events — use the Audit trail page for the full list and CSV export.")
