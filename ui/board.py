"""Priorities by market: Must / Should / Could columns for one car × market, plus a side-by-side comparison with a
second market — the same need can rank differently per market (D-011)."""

import streamlit as st

from ui.common import (FOCUS_TARGETS, chip, esc, evidence_chip, md, page_header, plain_target, priority_chip,
                       review_requirement, short, status_chip, targets_df)

page_header("Priorities by market",
            "Each market is its own customer group: climate, usage and culture differ, so the same need can be a Must "
            "in one market and a Could in another.")

df = targets_df()
if df.empty:
    st.info("No requirements yet — open wave 1 on the Home page.")
    st.stop()
df = df[df["status"] != "rejected"].copy()
df["eff"] = df["pm_priority"].where(df["pm_priority"].notna(), df["proposed_priority"])
df["ai_only"] = df["pm_priority"].isna()

pairs = sorted({(d, m) for d, m in zip(df["vehicle_model_id"], df["market_code"])})
names = {plain_target(d, m): (d, m) for d, m in pairs}
focus = [plain_target(d, m) for d, m in FOCUS_TARGETS if (d, m) in pairs]
c1, c2 = st.columns(2)
main = c1.selectbox("Car · market", list(names), index=list(names).index(focus[0]) if focus else 0)
other_opts = ["— none —", *[n for n in names if n != main]]
other = c2.selectbox("Compare with", other_opts,
                     index=other_opts.index(focus[1]) if len(focus) > 1 and focus[1] in other_opts else 0)


def board(label: str, key: str) -> None:
    d, m = names[label]
    g = df[(df["vehicle_model_id"] == d) & (df["market_code"] == m)].sort_values("score", ascending=False)
    n_pm = int((~g["ai_only"]).sum())
    st.caption(f"{len(g)} requirement(s) · {n_pm} with your confirmed priority, {len(g) - n_pm} AI suggestion(s)")
    cols = st.columns(3)
    for col, p in zip(cols, ["Must", "Should", "Could"]):
        sub = g[g["eff"] == p]
        with col:
            md(f"{chip(p, p)} <span class='muted'>{len(sub)}</span>")
            for r in sub.itertuples():
                with st.container(border=True):
                    md(f"<b>{esc(short(r.title, 80))}</b><br>"
                       f"{priority_chip(r.eff, r.ai_only)} {evidence_chip(r.target_evidence)} {status_chip(r.status)}"
                       f"<br><span class='muted'>score {r.score:.0f}</span>")
                    if st.button("Review", key=f"{key}_{r.requirement_id}", type="tertiary", icon=":material/arrow_forward:"):
                        review_requirement(r.requirement_id)


if other == "— none —":
    board(main, "a")
else:
    st.subheader(main)
    board(main, "a")
    st.divider()
    st.subheader(f"{main} vs {other}")
    (d1, m1), (d2, m2) = names[main], names[other]
    a = df[(df["vehicle_model_id"] == d1) & (df["market_code"] == m1)].set_index("requirement_id")
    b = df[(df["vehicle_model_id"] == d2) & (df["market_code"] == m2)].set_index("requirement_id")
    both = a.index.intersection(b.index)
    diff = [r for r in both if a.loc[r, "eff"] != b.loc[r, "eff"]]
    st.caption(f"{len(both)} requirement(s) target both · {len(diff)} ranked differently · "
               f"{len(a.index.difference(b.index))} only in {main} · {len(b.index.difference(a.index))} only in {other}")
    rows = ["<table style='width:100%;border-collapse:collapse;font-size:0.9rem'><tr style='text-align:left;color:#4a5563'>"
            f"<th style='padding:6px'>Requirement</th><th>{esc(main)}</th><th>{esc(other)}</th><th>Why the difference (AI note for {esc(other)})</th></tr>"]
    for r in sorted(both, key=lambda x: (x not in diff, -(a.loc[x, "score"] or 0))):
        rows.append(
            f"<tr style='border-top:1px solid #eceff3;{'background:#fffafa' if r in diff else ''}'>"
            f"<td style='padding:6px'>{esc(short(a.loc[r, 'title'], 70))}</td>"
            f"<td>{priority_chip(a.loc[r, 'eff'], a.loc[r, 'ai_only'])} {a.loc[r, 'score']:.0f}</td>"
            f"<td>{priority_chip(b.loc[r, 'eff'], b.loc[r, 'ai_only'])} {b.loc[r, 'score']:.0f}</td>"
            f"<td class='muted'>{esc(short(b.loc[r, 'market_note'], 160))}</td></tr>")
    md("".join(rows) + "</table>")
    st.caption("Highlighted rows rank differently. Options: different priorities per market, a market variant or "
               "package, or defer where evidence is thin.")
