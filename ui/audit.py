"""Global audit trail: every action, change and access event (append-only), filterable, CSV export."""

import datetime as dt

import streamlit as st

from ui.common import empty, log_export, page_header, q

page_header("Audit trail",
            "Complete chronological record of AI, system and human actions — content, scores, priorities, evidence, "
            "status, and access events. Append-only: the database rejects updates and deletes.")

total = int(q("SELECT COUNT(*) n FROM audit_event").iat[0, 0])
if not total:
    empty("No audit events yet.")
    st.stop()

facets = q("SELECT actor_type, actor_id, action, entity_type, MIN(ts) mn, MAX(ts) mx FROM audit_event "
           "GROUP BY 1, 2, 3, 4")
c1, c2, c3, c4 = st.columns(4)
at = c1.multiselect("Actor type", sorted(facets["actor_type"].dropna().unique()))
ac = c2.multiselect("Actor", sorted(facets["actor_id"].dropna().unique()))
an = c3.multiselect("Action", sorted(facets["action"].dropna().unique()))
et = c4.multiselect("Entity type", sorted(facets["entity_type"].dropna().unique()))
c5, c6, c7 = st.columns([2, 3, 1])
mn = dt.date.fromisoformat(str(facets["mn"].min())[:10])
mx = dt.date.fromisoformat(str(facets["mx"].max())[:10])
rng = c5.date_input("Date range", value=(mn, mx), min_value=mn, max_value=mx)
txt = c6.text_input("Search (entity, rationale, values)", placeholder="e.g. REQ-0003 or brand")
limit = c7.selectbox("Max rows", [500, 2000, 10000], index=1)

where, params = [], []
for col, vals in (("actor_type", at), ("actor_id", ac), ("action", an), ("entity_type", et)):
    if vals:
        where.append(f"{col} IN ({','.join('?' * len(vals))})")
        params += list(vals)
if isinstance(rng, (tuple, list)) and len(rng) == 2:
    where.append("substr(ts, 1, 10) BETWEEN ? AND ?")
    params += [rng[0].isoformat(), rng[1].isoformat()]
if txt:
    where.append("(entity_id LIKE ? OR rationale LIKE ? OR old_value LIKE ? OR new_value LIKE ? OR field LIKE ?)")
    params += [f"%{txt}%"] * 5
sql = ("SELECT id, ts, actor_type, actor_id, action, entity_type, entity_id, field, old_value, new_value, rationale, "
       "model, prompt_ref, run_id FROM audit_event" + (" WHERE " + " AND ".join(where) if where else "")
       + f" ORDER BY id DESC LIMIT {int(limit)}")
df = q(sql, tuple(params))

m = st.columns(4)
m[0].metric("Matching events (shown)", f"{len(df):,}", help=f"{total:,} events in total")
m[1].metric("Human", int((df["actor_type"] == "human").sum()))
m[2].metric("AI", int((df["actor_type"] == "ai").sum()))
m[3].metric("System", int((df["actor_type"] == "system").sum()))

st.dataframe(df, hide_index=True, width="stretch", height=560, column_config={
    "id": st.column_config.NumberColumn("#", format="%d", width="small"),
    "ts": st.column_config.TextColumn("When (UTC)"),
    "old_value": st.column_config.TextColumn("Before", width="medium"),
    "new_value": st.column_config.TextColumn("After", width="medium"),
    "rationale": st.column_config.TextColumn("Rationale", width="large")})

st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="audit_trail.csv",
                   mime="text/csv", icon=":material/download:", on_click=log_export,
                   args=("audit_trail.csv", f"{len(df)} rows; filters: {' AND '.join(where) or 'none'}"))
st.caption("Downloading is itself logged as an access event.")
