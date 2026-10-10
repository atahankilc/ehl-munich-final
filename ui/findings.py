"""Findings explorer: all findings (verbatim clusters, study, web) with filters, per-market counts, sources and the
requirements that use them; uncovered findings (not used by any requirement)."""

import pandas as pd
import streamlit as st

from ui.common import (TARGETS, chip, current_wave, empty, esc, loads, md, metrics_wave, open_requirement,
                       page_header, q, short)

page_header("Findings explorer",
            "Findings are the consolidated evidence layer between raw sources and requirements. Uncovered findings "
            "show what customers say that no requirement addresses yet.")

raw = q("""SELECT f.id, f.source_kind, f.type, f.category, f.title, f.summary, f.vehicle_model_id, f.market_code,
                  f.metrics_json, f.first_wave, f.polarity,
                  (SELECT COUNT(*) FROM requirement_finding rf WHERE rf.finding_id = f.id) n_req,
                  (SELECT COUNT(*) FROM finding_source fs WHERE fs.finding_id = f.id) n_src
           FROM finding f ORDER BY f.id""")
if raw.empty:
    empty("No findings yet — they are built from extracted signals (clustering), the customer study and web research.")
    st.stop()

wave = current_wave()
mw = metrics_wave()
MK = ["US", "EU", "CN", "RoW"]
df = raw.copy()
for m in MK:
    df[f"v_{m}"] = 0
vals = {m: [] for m in MK}
total = []
for r in df.itertuples():
    mt = loads(r.metrics_json, {}) or {}
    bym = (mt.get("by_wave", {}).get(mw, {}) or {}).get("markets", {}) if r.source_kind == "verbatim" else {}
    for m in MK:
        vals[m].append(int((bym.get(m) or {}).get("verbatims") or 0))
    total.append(int((mt.get("by_wave", {}).get(mw, {}) or {}).get("verbatims") or 0) if r.source_kind == "verbatim" else 0)
for m in MK:
    df[f"v_{m}"] = vals[m]
df["verbatims"] = total
df["scope"] = df["vehicle_model_id"].fillna("line") + " × " + df["market_code"].fillna("all")
df["used"] = df["n_req"] > 0

c = st.columns(4)
c[0].metric("Findings", len(df))
c[1].metric("Used by a requirement", int(df["used"].sum()))
c[2].metric("Uncovered", int((~df["used"]).sum()), help="Not linked to any requirement")
c[3].metric("Verbatim counts as of", f"wave {mw}", help="Cumulative simulated wave (waves are a simulation)")

f1, f2, f3, f4 = st.columns(4)
der = f1.multiselect("Derivative", sorted(TARGETS) + ["line-level"])
mkt = f2.multiselect("Market", MK)
kind = f3.multiselect("Kind", sorted(df["source_kind"].dropna().unique()))
cat = f4.multiselect("Category", sorted(df["category"].dropna().unique()))
f5, f6, f7, f8 = st.columns(4)
typ = f5.multiselect("Type", sorted(df["type"].dropna().unique()))
txt = f6.text_input("Search title / summary")
only_unc = f7.toggle("Only uncovered", value=False)
visible = f8.toggle("Only visible in current wave", value=bool(wave), disabled=not wave)

sel = df
if der:
    sel = sel[sel["vehicle_model_id"].isin([d for d in der if d != "line-level"]) |
              (("line-level" in der) & sel["vehicle_model_id"].isna())]
if mkt:
    mask = sel["market_code"].isin(mkt)
    for m in mkt:
        mask |= sel[f"v_{m}"] > 0
    sel = sel[mask]
if kind:
    sel = sel[sel["source_kind"].isin(kind)]
if cat:
    sel = sel[sel["category"].isin(cat)]
if typ:
    sel = sel[sel["type"].isin(typ)]
if txt:
    sel = sel[sel["title"].str.contains(txt, case=False, na=False) | sel["summary"].str.contains(txt, case=False, na=False)]
if only_unc:
    sel = sel[~sel["used"]]
if visible and wave:
    sel = sel[sel["first_wave"].fillna(1) <= wave]
sel = sel.sort_values(["verbatims", "n_src"], ascending=False)

st.caption(f"{len(sel)} finding(s)")
ev = st.dataframe(
    sel[["id", "source_kind", "type", "category", "title", "scope", "verbatims", "v_US", "v_EU", "v_RoW", "v_CN",
         "n_src", "n_req", "first_wave"]],
    hide_index=True, width="stretch", height=420, on_select="rerun", selection_mode="single-row", key="fx_table",
    column_config={
        "id": st.column_config.NumberColumn("ID", format="F%d", width="small"),
        "source_kind": "Kind", "type": "Type", "category": "Category",
        "title": st.column_config.TextColumn("Finding", width="large"),
        "scope": "Scope", "verbatims": st.column_config.NumberColumn("Verbatims", help="Distinct verbatims (verbatim findings)"),
        "v_US": "US", "v_EU": "EU", "v_RoW": "RoW", "v_CN": "CN",
        "n_src": st.column_config.NumberColumn("Sources"), "n_req": st.column_config.NumberColumn("Used by", help="Requirements linking it"),
        "first_wave": st.column_config.NumberColumn("First wave"),
    })
rows = ev.selection.rows if ev and ev.selection else []
if not rows:
    st.caption("Select a row to see its sources and the requirements that use it.")
    st.stop()

f = sel.iloc[rows[0]]
fid = int(f["id"])
st.divider()
st.markdown(f"### F{fid} · {esc(f['title'])}")
md(" ".join([chip(f["source_kind"], "proposed"), chip(f["type"] or "–", "system"), chip(f["category"] or "–", "system"),
             chip(f"{'used by ' + str(int(f['n_req'])) + ' requirement(s)' if f['used'] else 'uncovered'}",
                  "pass" if f["used"] else "warn"),
             f"<span class='muted'>scope {esc(f['scope'])} · first wave {int(f['first_wave'] or 1)}</span>"]))
st.write(f["summary"] or "")
mt = loads(f["metrics_json"], {}) or {}
if f["source_kind"] == "verbatim":
    bym = (mt.get("by_wave", {}).get(mw, {}) or {}).get("markets", {}) or {}
    if bym:
        st.dataframe(pd.DataFrame([{"market": k, "verbatims": v.get("verbatims"), "share": v.get("share"),
                                    "base": v.get("base"), "severity-weighted": v.get("severity_weighted"),
                                    "types": ", ".join(f"{a} {b}" for a, b in (v.get("types") or {}).items()),
                                    "countries": ", ".join(f"{a} {b}" for a, b in (v.get("countries") or {}).items())}
                                   for k, v in bym.items()]),
                     hide_index=True, width="stretch",
                     column_config={"share": st.column_config.NumberColumn("share of market", format="percent")})
elif mt:
    st.caption("Metrics: " + ", ".join(f"{k} = {v}" for k, v in mt.items()))

left, right = st.columns([3, 2], gap="large")
with left:
    st.markdown("**Sources** (up to 30)")
    srcs = q("""SELECT s.kind, s.external_id, s.ref, s.country, s.market_code, s.url, s.published_at, s.trust_tier,
                       s.text, s.meta_json, COALESCE(fs.quote, s.quote) quote, fs.relation
                FROM finding_source fs JOIN source_item s ON s.id = fs.source_item_id WHERE fs.finding_id = ? LIMIT 30""",
             (fid,))
    for s in srcs.itertuples():
        meta = loads(s.meta_json, {}) or {}
        if s.kind == "feedback":
            head = f"<b>{esc(s.external_id)}</b> · {esc(s.country or s.market_code)} · {esc(meta.get('channel') or '–')}"
        elif s.kind == "web":
            head = (f"{chip(s.trust_tier or 'T?', s.trust_tier)} <b>{esc(meta.get('publisher') or '–')}</b> · "
                    f"{esc(s.published_at or 'n/a')} · <a href='{esc(s.url)}' target='_blank'>{esc(short(s.url, 60))}</a>")
        else:
            head = f"<b>{esc(s.kind)}</b> · {esc(s.external_id or s.ref)} · {esc(s.market_code or '')}"
        rel = f" {chip('contradicts', 'fail')}" if s.relation == "contradicts" else ""
        md(f"<span class='muted'>{head}</span>{rel}<div class='quote'>{esc(s.quote or short(s.text, 300))}</div>")
    if int(f["n_src"]) > 30:
        st.caption(f"Showing 30 of {int(f['n_src'])} sources.")
with right:
    st.markdown("**Used by requirements**")
    used = q("""SELECT r.id, r.title, r.status, rf.relation FROM requirement_finding rf JOIN requirement r ON r.id = rf.requirement_id
                WHERE rf.finding_id = ? ORDER BY r.id""", (fid,))
    if used.empty:
        st.warning("Uncovered — no requirement uses this finding. Challenge a related requirement or wait for the "
                   "next derivation run.", icon=":material/help:")
    else:
        for u in used.itertuples():
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            c1.markdown(f"{chip(u.status)} {chip(u.relation, 'fail' if u.relation == 'contradicts' else 'pass')} "
                        f"**{esc(u.id)}** {esc(short(u.title, 70))}", unsafe_allow_html=True)
            if c2.button("Open", key=f"fx_open_{u.id}"):
                open_requirement(u.id)
