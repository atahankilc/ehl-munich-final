"""Weights & runs: adjust scoring weights (with rationale) and re-run prioritization (deterministic, no LLM);
run history; "what changed" between two runs."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from bmw_req.pipeline import scoring
from bmw_req.service import ActionError
from ui.common import act, actor, current_wave, empty, has_requirements, loads, page_header, q, run_label

page_header("Weights & runs",
            "Prioritization is a transparent formula, not a black box. Change the weights, re-run, and see exactly "
            "what moved — every run is snapshotted.")

HELP = {
    "customer_voice": "Severity-weighted share of this market's in-scope feedback that supports the requirement.",
    "satisfaction_gap": "Customer study: item weak vs. other items (or strong, for must-not-lose).",
    "market_volume": "BMW sales of the derivative in the market + 2030 momentum (relative only, Q-015).",
    "competitive_pressure": "Cited competitor advantages / review criticism in this market (trust-tier weighted).",
    "future_relevance": "Horizon, Kano drift towards basic, cited trends and expectations.",
    "portfolio_leverage": "How many derivative × market targets benefit; platform-wide realization.",
}

cur = q("SELECT id, weights_json, created_by, created_at, rationale FROM weights_version ORDER BY id DESC LIMIT 1")
weights = loads(cur.iloc[0]["weights_json"], None) if not cur.empty else None
weights = {**scoring.DEFAULT_WEIGHTS, **(weights or {})}

st.subheader("Scoring weights")
if cur.empty:
    st.caption("Default weights (D-029) — no weight version stored yet.")
else:
    r = cur.iloc[0]
    st.caption(f"Current: weights version {int(r['id'])} by {r['created_by']} · {str(r['created_at'])[:16].replace('T', ' ')}"
               + (f" — “{r['rationale']}”" if r["rationale"] else ""))

left, right = st.columns([3, 2], gap="large")
with left:
    with st.form("weights"):
        new = {}
        for k, default in scoring.DEFAULT_WEIGHTS.items():
            new[k] = st.slider(scoring.FACTOR_LABELS.get(k, k), 0, 60, int(weights.get(k, default)), help=HELP.get(k))
        why = st.text_input("Rationale (required)", placeholder="e.g. Board wants more weight on competitive pressure in CN")
        wave = max(current_wave(), 1)
        submitted = st.form_submit_button(f"Save weights & re-run prioritization (wave {wave})", type="primary",
                                          disabled=not has_requirements())
        if not has_requirements():
            st.caption("Available once requirements exist.")
        if submitted:
            def apply(c, w, who, rationale, wv):
                if not rationale or len(rationale.strip()) < 5:
                    raise ActionError("A rationale is required for a weight change.")
                if sum(w.values()) <= 0:
                    raise ActionError("At least one weight must be > 0.")
                scoring.set_weights(c, w, who, rationale.strip())
                return scoring.run_prioritization(c, wave=wv, trigger="weight_change", initiated_by=who, note=rationale.strip())

            if new == weights:
                st.info("Weights unchanged — nothing to re-run.")
            else:
                act(apply, new, actor(), why, wave, success="Weights saved and prioritization re-run (no LLM cost).")
with right:
    tot = sum(new.values()) or 1
    wdf = pd.DataFrame([{"factor": scoring.FACTOR_LABELS.get(k, k), "share": v / tot,
                         "current": weights.get(k, 0) / (sum(weights.values()) or 1)} for k, v in new.items()])
    st.altair_chart(alt.Chart(wdf).mark_bar(color="#1c69d4", cornerRadiusEnd=3).encode(
        y=alt.Y("factor:N", sort=None, title=None), x=alt.X("share:Q", axis=alt.Axis(format="%"), title="share of base score"),
        tooltip=["factor", alt.Tooltip("share:Q", format=".0%"), alt.Tooltip("current:Q", format=".0%", title="saved")],
    ).properties(height=230), width="stretch")
    st.caption("Weights are relative. Factors without data for a target are left out and the rest renormalized; the "
               "evidence level then lowers confidence (E1 ×1.0 … E4 ×0.65). Brand fit is a gate, not a factor.")

# ------------------------------------------------------------------------------------------------ runs
st.subheader("Prioritization runs")
runs = q("""SELECT r.id, r.ts, r.trigger, r.initiated_by, r.weights_version_id, r.model,
                   (SELECT COUNT(*) FROM score_snapshot s WHERE s.run_id = r.id) targets_scored,
                   (SELECT COUNT(*) FROM change_proposal p WHERE p.run_id = r.id) proposals,
                   (SELECT a.new_value FROM audit_event a WHERE a.action = 'start_run' AND a.entity_type = 'prioritization_run'
                      AND a.entity_id = CAST(r.id AS TEXT) LIMIT 1) start,
                   (SELECT a.rationale FROM audit_event a WHERE a.action = 'start_run' AND a.entity_type = 'prioritization_run'
                      AND a.entity_id = CAST(r.id AS TEXT) LIMIT 1) note
            FROM prioritization_run r ORDER BY r.id DESC""")
if runs.empty:
    empty("No prioritization runs yet.")
    st.stop()
runs["wave"] = runs["start"].map(lambda s: (loads(s, {}) or {}).get("wave"))
st.dataframe(runs.drop(columns=["start"]), hide_index=True, width="stretch", column_config={
    "id": st.column_config.NumberColumn("Run", format="%d"), "weights_version_id": "Weights v.",
    "model": "Scoring version", "targets_scored": "Targets scored", "proposals": "Change proposals",
    "note": st.column_config.TextColumn("Note / rationale", width="large")})

st.subheader("What changed between two runs")
if len(runs) < 2:
    st.caption("Needs at least two runs.")
    st.stop()
labels = {int(r.id): run_label(r.id, r.ts, r.trigger) + (f" · wave {int(r.wave)}" if pd.notna(r.wave) else "")
          for r in runs.itertuples()}
ids = list(labels)
c1, c2, c3 = st.columns([2, 2, 2])
b_id = c2.selectbox("Newer run", ids, index=0, format_func=labels.get)
a_id = c1.selectbox("Older run", [i for i in ids if i < b_id] or ids, index=0, format_func=labels.get)
snaps = q("""SELECT s.run_id, s.requirement_id, s.vehicle_model_id || ' × ' || s.market_code target, s.score, s.rank,
                    s.priority, r.title FROM score_snapshot s JOIN requirement r ON r.id = s.requirement_id
             WHERE s.run_id IN (?, ?)""", (int(a_id), int(b_id)))
A = snaps[snaps["run_id"] == a_id].drop(columns="run_id")
B = snaps[snaps["run_id"] == b_id].drop(columns="run_id")
diff = A.merge(B, on=["requirement_id", "target", "title"], how="outer", suffixes=("_old", "_new"))
diff["Δ score"] = diff["score_new"] - diff["score_old"]
diff["rank move"] = diff["rank_old"] - diff["rank_new"]
diff["change"] = diff.apply(lambda r: "new" if pd.isna(r["score_old"]) else ("dropped" if pd.isna(r["score_new"]) else (
    f"{r['priority_old']} → {r['priority_new']}" if r["priority_old"] != r["priority_new"] else "")), axis=1)
tsel = c3.multiselect("Targets", sorted(diff["target"].dropna().unique()))
if tsel:
    diff = diff[diff["target"].isin(tsel)]
moved = diff[(diff["Δ score"].abs() >= 0.5) | (diff["change"] != "") | diff["Δ score"].isna()]
m = st.columns(4)
m[0].metric("Targets compared", len(diff))
m[1].metric("Score moved ≥ 0.5", int((diff["Δ score"].abs() >= 0.5).sum()))
m[2].metric("AI priority changed", int(diff["change"].str.contains("→").sum()))
m[3].metric("New / dropped", int(diff["change"].isin(["new", "dropped"]).sum()))
wa = runs.set_index("id").loc[[a_id, b_id], "weights_version_id"].tolist()
if wa[0] != wa[1]:
    wv = q("SELECT id, weights_json FROM weights_version WHERE id IN (?, ?)", (int(wa[0] or 0), int(wa[1] or 0)))
    wmap = {int(r.id): loads(r.weights_json, {}) for r in wv.itertuples()}
    st.caption("Weights changed between the runs: " + ", ".join(
        f"{scoring.FACTOR_LABELS.get(k, k)} {wmap.get(int(wa[0] or 0), {}).get(k)} → {v}"
        for k, v in wmap.get(int(wa[1] or 0), {}).items() if wmap.get(int(wa[0] or 0), {}).get(k) != v) or "—")
if moved.empty:
    st.success("Nothing moved between these runs.")
else:
    top = moved.dropna(subset=["Δ score"]).reindex(moved["Δ score"].abs().sort_values(ascending=False).index).head(25)
    if not top.empty:
        top = top.assign(label=top["requirement_id"] + " · " + top["target"])
        st.altair_chart(alt.Chart(top).mark_bar(cornerRadiusEnd=2).encode(
            y=alt.Y("label:N", sort=None, title=None), x=alt.X("Δ score:Q", title="score change (points)"),
            color=alt.condition(alt.datum["Δ score"] > 0, alt.value("#1c69d4"), alt.value("#c0392b")),
            tooltip=["requirement_id", "title", "target", alt.Tooltip("score_old:Q", format=".1f"),
                     alt.Tooltip("score_new:Q", format=".1f"), "rank_old", "rank_new", "change"],
        ).properties(height=22 * len(top) + 30), width="stretch")
    causes = q("""SELECT entity_id, rationale FROM audit_event WHERE action = 'rescore' AND run_id = ?""", (int(b_id),))
    cmap = dict(zip(causes["entity_id"], causes["rationale"])) if not causes.empty else {}
    moved = moved.assign(cause=[cmap.get(f"{r.requirement_id}:{str(r.target).replace(' × ', '×')}", "")
                                for r in moved.itertuples()])
    st.dataframe(moved.sort_values("Δ score", key=lambda s: -s.abs())[
        ["requirement_id", "title", "target", "score_old", "score_new", "Δ score", "rank_old", "rank_new", "rank move",
         "change", "cause"]], hide_index=True, width="stretch", column_config={
        "score_old": st.column_config.NumberColumn("old", format="%.1f"),
        "score_new": st.column_config.NumberColumn("new", format="%.1f"),
        "Δ score": st.column_config.NumberColumn(format="%+.1f"),
        "rank move": st.column_config.NumberColumn(format="%+d", help="positive = moved up"),
        "cause": st.column_config.TextColumn("Cause (factor delta)", width="large")})
