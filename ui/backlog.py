"""Ranked backlog per derivative × market, side by side for 2–3 targets, with filters and jump to detail."""

import streamlit as st

from ui.common import (PRIORITIES, STATUSES, empty, esc, md, open_requirement, page_header, parse_tlabel, requirement_options,
                       target_labels, targets_df)

page_header("Backlog",
            "Ranked per derivative × market — the same requirement can rank differently in each market. "
            "AI proposes a priority from the score; the PM confirms it.")

labels = target_labels()
default = [t for t in ["G60 × US", "G68 × CN", "G60 × EU"] if t in labels]
sel = st.multiselect("Targets (derivative × market)", labels, default=default,
                     help="Pick 2–3 to compare markets side by side.")
df = targets_df()
if df.empty:
    empty("No requirements yet. They are drafted by the AI when a wave is opened (Overview → Timeline).")
    st.stop()

f1, f2, f3, f4 = st.columns([2, 3, 2, 2])
status_f = f1.multiselect("Status", STATUSES, default=[s for s in STATUSES if s != "rejected"])
cats = sorted(c for c in df["category"].dropna().unique())
cat_f = f2.multiselect("Category", cats)
prio_f = f3.multiselect("Priority (AI or PM)", PRIORITIES)
search = f4.text_input("Search title", placeholder="e.g. CarPlay")

# rank within target over all non-rejected requirements (true rank), then filter for display
df = df.copy()
live = df["status"] != "rejected"
df.loc[live, "rank"] = df[live].groupby("target")["score"].rank(ascending=False, method="min")
if status_f:
    df = df[df["status"].isin(status_f)]
if cat_f:
    df = df[df["category"].isin(cat_f)]
if prio_f:
    df = df[df["proposed_priority"].isin(prio_f) | df["pm_priority"].isin(prio_f)]
if search:
    df = df[df["title"].str.contains(search, case=False, na=False)]

if not sel:
    st.info("Select at least one target.")
    st.stop()

FULL = ["rank", "requirement_id", "title", "category", "score", "proposed_priority", "pm_priority", "target_evidence",
        "status", "horizon", "kano_class", "must_not_lose", "brand_gate"]
CFG = {
    "rank": st.column_config.NumberColumn("#", format="%d", width="small"),
    "requirement_id": st.column_config.TextColumn("ID", width="small"),
    "title": st.column_config.TextColumn("Requirement", width="large"),
    "category": st.column_config.TextColumn("Category"),
    "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f",
                                             help="0–100; factor breakdown on the requirement page"),
    "proposed_priority": st.column_config.TextColumn("AI prio", help="AI proposal from score bands (Must ≥ 60, Should ≥ 45)"),
    "pm_priority": st.column_config.TextColumn("PM prio", help="Confirmed by the PM (empty = not yet reviewed)"),
    "target_evidence": st.column_config.TextColumn("Evid.", help="Evidence level for this market: E1 strongest … E4 assumption only"),
    "status": st.column_config.TextColumn("Status"),
    "horizon": st.column_config.TextColumn("Horizon"),
    "kano_class": st.column_config.TextColumn("Kano"),
    "must_not_lose": st.column_config.CheckboxColumn("Must-not-lose", help="Protects a praised strength"),
    "brand_gate": st.column_config.TextColumn("Brand", help="Brand-fit gate: fail blocks approval unless overridden"),
}
chosen = []

# summary line per target
md(" &nbsp; ".join(
    f"<b>{esc(t)}</b> <span class='muted'>{int((df['target'] == t).sum())} req. · "
    f"{int(((df['target'] == t) & (df['proposed_priority'] == 'Must')).sum())} AI Must · "
    f"{int(((df['target'] == t) & df['pm_priority'].notna()).sum())} PM-confirmed</span>" for t in sel))

if 2 <= len(sel) <= 3:
    # side by side: one row per requirement, rank / score / AI / PM per market
    sub = df[df["target"].isin(sel)]
    if sub.empty:
        st.caption("No requirements for these targets with the current filters.")
    else:
        base = sub.drop_duplicates("requirement_id").set_index("requirement_id")[["title", "status", "evidence_level"]]
        cfg = {"title": st.column_config.TextColumn("Requirement", width="medium"),
               "status": st.column_config.TextColumn("Status"), "evidence_level": st.column_config.TextColumn("Evid.")}
        order = []
        for t in sel:
            part = sub[sub["target"] == t].set_index("requirement_id")
            short_t = t.replace(" × ", "·")
            base[f"{short_t} #"] = part["rank"]
            base[f"{short_t} score"] = part["score"]
            base[f"{short_t} AI"] = part["proposed_priority"]
            base[f"{short_t} PM"] = part["pm_priority"]
            cfg[f"{short_t} #"] = st.column_config.NumberColumn(f"{short_t} #", format="%d", help=f"Rank in {t}")
            cfg[f"{short_t} score"] = st.column_config.NumberColumn(f"{short_t} score", format="%.0f",
                                                                    help=f"Score 0–100 in {t}")
            cfg[f"{short_t} AI"] = st.column_config.TextColumn(f"{short_t} AI", help=f"AI-proposed priority in {t}")
            cfg[f"{short_t} PM"] = st.column_config.TextColumn(f"{short_t} PM", help=f"PM-confirmed priority in {t}")
            order.append(f"{short_t} #")
        base = base.reset_index().sort_values(order, na_position="last")
        st.caption("Empty = the requirement does not target that market. Sorted by rank in the first selected target.")
        ev = st.dataframe(base, hide_index=True, width="stretch", column_config={
            "requirement_id": st.column_config.TextColumn("ID"), **cfg},
            on_select="rerun", selection_mode="single-row", key="bl_side", height=min(38 + 35 * len(base), 680))
        rows = ev.selection.rows if ev and ev.selection else []
        if rows:
            chosen.append(base.iloc[rows[0]]["requirement_id"])
else:
    for t in sel:
        sub = df[df["target"] == t].sort_values(["rank", "requirement_id"])
        st.markdown(f"**{t}**")
        if sub.empty:
            st.caption("No requirements for this target with the current filters.")
            continue
        ev = st.dataframe(sub[FULL], hide_index=True, width="stretch", column_config=CFG, on_select="rerun",
                          selection_mode="single-row", key=f"bl_{t}", height=min(38 + 35 * len(sub), 640))
        rows = ev.selection.rows if ev and ev.selection else []
        if rows:
            chosen.append(sub.iloc[rows[0]]["requirement_id"])

st.divider()
c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
opts = requirement_options()
pre = next((o for o in opts if chosen and o.startswith(chosen[-1])), None)
pick = c1.selectbox("Open a requirement", opts, index=opts.index(pre) if pre in opts else 0,
                    help="Select a row in a table above, or pick here.")
if c2.button("Open", type="primary", width="stretch", icon=":material/open_in_new:"):
    open_requirement(pick.split(" · ")[0])
