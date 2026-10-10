"""Review: one AI-drafted requirement at a time, in plain language — the need, the evidence, the AI's suggested
priority per car × market — and the PM's decision (approve / reject / defer, with a reason). The full detail
(score maths, evidence chain, fit checks, audit) stays one click away on the Requirement details page."""

import re

import streamlit as st

from bmw_req import service
from ui.common import (EVIDENCE_HELP, HORIZON_LABELS, KANO_LABELS, _LOCK, actor, chip, clear_caches, conn, esc,
                       evidence_chip, loads, log_access_once, md, mkt, nz, open_requirement, page_header, plain_target,
                       priority_chip, q, short, status_chip, targets_df, write)

page_header("Review requirements",
            "One requirement at a time: what customers need, the evidence behind it, and what the AI suggests per car "
            "and market. You decide — with a reason, recorded in the audit trail.")

df = targets_df()
if df.empty:
    st.info("No requirements yet — open wave 1 on the Home page.")
    st.stop()

# ------------------------------------------------------------------------------------------------ queue
labels = {plain_target(d, m): (d, m) for d, m in df[["vehicle_model_id", "market_code"]].drop_duplicates()
          .sort_values(["vehicle_model_id", "market_code"]).itertuples(index=False)}
c1, c2 = st.columns([2, 3])
scope = c1.selectbox("Market", ["All markets", *labels], help="Review only requirements that target this car · market.")
show_all = c2.toggle("Include decided requirements", value=False,
                     help="Off: only requirements still waiting for a decision (to review / challenged).")

g = df if scope == "All markets" else df[(df["vehicle_model_id"] == labels[scope][0]) & (df["market_code"] == labels[scope][1])]
best = g.groupby("requirement_id").agg(score=("score", "max"), status=("status", "first"), title=("title", "first"))
if not show_all:
    best = best[best["status"].isin(["proposed", "challenged"])]
queue = list(best.sort_values("score", ascending=False).index)

focus = st.session_state.pop("review_focus", None)
if focus:
    if focus not in queue:
        queue.insert(0, focus)
    st.session_state["review_pos"] = queue.index(focus)
if not queue:
    st.success("Nothing left to review here.", icon=":material/done_all:")
    if st.button("See priorities by market", icon=":material/view_kanban:"):
        st.switch_page("ui/board.py")
    st.stop()
pos = min(st.session_state.get("review_pos", 0), len(queue) - 1)
rid = queue[pos]
log_access_once("view", "requirement", rid)

nav = st.columns([1, 4, 1])
if nav[0].button("Previous", icon=":material/arrow_back:", disabled=pos == 0, width="stretch"):
    st.session_state["review_pos"] = pos - 1
    st.rerun()
nav[1].progress((pos + 1) / len(queue), text=f"Requirement {pos + 1} of {len(queue)}"
                + ("" if show_all else " waiting for your decision"))
if nav[2].button("Next", icon=":material/arrow_forward:", disabled=pos >= len(queue) - 1, width="stretch"):
    st.session_state["review_pos"] = pos + 1
    st.rerun()

req = q("SELECT * FROM requirement WHERE id = ?", (rid,)).iloc[0].to_dict()
tg = df[df["requirement_id"] == rid].sort_values("score", ascending=False)

# ------------------------------------------------------------------------------------------------ the need
st.markdown(f"## {esc(req['title'])}")
md(" ".join([status_chip(req["status"]), evidence_chip(req.get("evidence_level")),
             chip(HORIZON_LABELS.get(req.get("horizon"), req.get("horizon") or "–"), "proposed"),
             chip(KANO_LABELS.get(req.get("kano_class"), req.get("kano_class") or "–"), "system"),
             chip("Protects a strength", "approved") if req.get("must_not_lose") else "",
             f"<span class='muted'>{esc(req.get('category') or '')} · {esc(rid)}</span>"]))
st.write(req.get("description") or "–")
with st.expander("How we would measure it"):
    st.markdown(f"**Target:** {req.get('target_metric') or '–'}")
    st.markdown(f"**Test:** {req.get('acceptance_criteria') or '–'}")

# ------------------------------------------------------------------------------------------------ the evidence
st.markdown("### The evidence")
wave = int(q("SELECT COALESCE(MAX(CAST(value AS INTEGER)), 1) v FROM app_state WHERE key = 'current_wave'").iloc[0]["v"])
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**What customers say**")
    voice, silent = [], []
    for t in tg.itertuples():
        b = loads(t.score_breakdown_json, {}) or {}
        cv = (b.get("factors") or {}).get("customer_voice", {})
        name = plain_target(t.vehicle_model_id, t.market_code)
        if not cv.get("available"):
            silent.append(name)
            continue
        n = (b.get("verbatims") or {}).get("verbatims", 0)
        base = re.search(r"of (\d[\d,]*) in-scope", cv.get("explanation", ""))
        voice.append((n, name, base.group(1) if base else None))
    any_voice = any(n for n, _, _ in voice)
    for n, name, base in sorted(voice, reverse=True):
        share = f" of {base} ({100 * n / int(base.replace(',', '')):.1f}%)" if base and int(base.replace(",", "")) else ""
        small = (" <span class='muted'>— small sample; its score leans on the other markets</span>"
                 if 0 < n < 5 else "")
        md(f"<b>{n}</b> comment(s){share} <span class='muted'>· {esc(name)}</span>{small}")
    if silent:
        md(f"<span class='muted'>No customer comments exist for {esc(', '.join(silent))} — there the suggestion "
           "rests on the customer study and web evidence.</span>")
    top = tg.iloc[0]
    quotes = q("""SELECT s.external_id, s.market_code, fs.quote FROM requirement_finding rf
                  JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
                  JOIN finding_source fs ON fs.finding_id = f.id JOIN source_item s ON s.id = fs.source_item_id
                  WHERE rf.requirement_id = ? AND rf.relation = 'supports' AND fs.quote IS NOT NULL AND s.wave <= ?
                  ORDER BY (SELECT COUNT(*) FROM finding_source x WHERE x.finding_id = f.id) DESC, s.id LIMIT 3""",
               (rid, wave))
    for r in quotes.itertuples():
        md(f"<div class='quote'>“{esc(short(r.quote, 220))}” <span class='muted'>— {esc(r.external_id)}, "
           f"{esc(mkt(r.market_code))}</span></div>")
    if not any_voice and quotes.empty:
        st.caption("No direct customer comments support this requirement.")
with right:
    links = q("""SELECT f.id, f.source_kind, f.type, f.title, f.metrics_json, rf.relation FROM requirement_finding rf
                 JOIN finding f ON f.id = rf.finding_id WHERE rf.requirement_id = ? AND COALESCE(f.first_wave, 1) <= ?""",
              (rid, wave))
    study = links[(links["source_kind"] == "study") & (links["relation"] == "supports")]
    web = links[(links["source_kind"] == "web") & (links["relation"] == "supports")]
    st.markdown("**Customer study**")
    if study.empty:
        st.caption("No study item points to a gap here" + (" (the study arrives in wave 2)." if wave < 2 else "."))
    for r in study.head(4).itertuples():
        md(f"- {esc(r.title)}")
    st.markdown("**Competitors, reviews and trends (web, cited)**")
    if web.empty:
        st.caption("No web evidence linked.")
    for r in web.head(4).itertuples():
        tiers = (loads(r.metrics_json, {}) or {}).get("tiers") or {}
        tier = min(tiers) if isinstance(tiers, dict) and tiers else None
        md(f"- {esc(r.title)} {chip(tier, tier) if tier else ''}")

against = links[links["relation"] == "contradicts"]
ce = nz(req.get("conflicting_evidence"), "")
if len(against) or (ce and ce.strip().lower() not in ("none", "none found")):
    md(f"<div class='card conflict'><h4>{chip('CONFLICT')} {len(against)} finding(s) point the other way</h4>"
       f"<div class='kv'>{esc(short(ce, 600))}</div></div>")

# ------------------------------------------------------------------------------------------------ AI suggestion
st.markdown("### What the AI suggests")
rows = ["<table style='width:100%;border-collapse:collapse;font-size:0.92rem'><tr style='text-align:left;color:#4a5563'>"
        "<th style='padding:6px'>Car · market</th><th>AI suggests</th><th>Score</th><th>Evidence</th>"
        "<th>Your priority</th></tr>"]
for t in tg.itertuples():
    lv = nz(t.target_evidence)
    rows.append(
        f"<tr style='border-top:1px solid #eceff3'><td style='padding:6px'><b>{esc(plain_target(t.vehicle_model_id, t.market_code))}</b></td>"
        f"<td>{priority_chip(t.proposed_priority)}</td><td>{'–' if nz(t.score) is None else f'{t.score:.0f} / 100'}</td>"
        f"<td title='{esc(EVIDENCE_HELP.get(lv, ''))}'>{evidence_chip(lv)}</td>"
        f"<td>{priority_chip(t.pm_priority) if isinstance(t.pm_priority, str) else '<span class=muted>not set</span>'}</td></tr>")
md("".join(rows) + "</table>")
st.caption("Must ≥ 60 · Should ≥ 45 · Could below. Weak evidence lowers the score; missing data is shown, never guessed.")
with st.expander("Why these scores?"):
    for t in tg.itertuples():
        b = loads(t.score_breakdown_json, {}) or {}
        md(f"<b>{esc(plain_target(t.vehicle_model_id, t.market_code))}</b> — {esc(b.get('rationale', '–'))}")
    if st.button("Full score breakdown and evidence chain", icon=":material/open_in_new:"):
        open_requirement(rid)
with st.expander("What the AI assumes about the next 3–5 years, and what could make it wrong"):
    a, u = st.columns(2)
    a.markdown("**Assumptions**")
    a.markdown(req.get("assumptions") or "–")
    u.markdown("**Uncertainties**")
    u.markdown(req.get("uncertainties") or "–")

# ------------------------------------------------------------------------------------------------ decision
st.markdown("### Your decision")
me = actor()
with _LOCK:
    blocked = service.brand_blocked(conn(), rid)
if blocked:
    st.warning(f"Brand fit failed for {', '.join(blocked)} — approval needs a documented override first (details page "
               "→ PM decision).", icon=":material/block:")
unset = [(t.vehicle_model_id, t.market_code, t.proposed_priority) for t in tg.itertuples()
         if not isinstance(t.pm_priority, str) and isinstance(t.proposed_priority, str)]
with st.form(f"review_{rid}", clear_on_submit=True):
    c1, c2 = st.columns([1, 2])
    decision = c1.radio("Decision", ["approved", "deferred", "rejected"], horizontal=False,
                        format_func={"approved": "Approve", "deferred": "Defer (decide later)", "rejected": "Reject"}.get)
    why = c2.text_area("Reason (required)", placeholder="e.g. strong US evidence and a study gap; China needs a variant")
    confirm = c2.checkbox(f"Also accept the AI-suggested priority for the {len(unset)} market(s) you haven't set yet",
                          value=bool(unset), disabled=not unset)
    st.caption(f"Recorded as **{me}** (change it in the sidebar).")
    if st.form_submit_button("Record decision", type="primary"):
        ok = write(service.set_status, rid, decision, me, why)
        if ok is not None and confirm and decision != "rejected":
            for d, m, p in unset:
                if write(service.set_priority, rid, d, m, p, me, f"Accepted the AI suggestion with the decision: {why}") is None:
                    break
        if ok is not None:
            st.session_state["_flash"] = f"Recorded: {req['title']} → {decision}"
            if show_all:
                st.session_state["review_pos"] = min(pos + 1, len(queue) - 1)
            st.rerun()

with st.expander("Not convinced? Ask the AI (costs a few cents)"):
    st.caption("The AI answers from the linked evidence and a search over all customer comments. If it thinks the "
               "requirement should change, that becomes a suggestion for you — it never edits on its own.")
    with st.form(f"ask_{rid}", clear_on_submit=False):
        question = st.text_area("Your question or objection", placeholder="e.g. Is this really a US need, or do US owners praise the opposite?")
        go = st.form_submit_button("Ask", icon=":material/forum:")
    if go:
        if not question or len(question.strip()) < 5:
            st.error("Write the question first.")
        else:
            try:
                from bmw_req.llm import LLM
                from bmw_req.pipeline import challenge as ch

                with st.spinner("The AI analyst is reviewing the evidence …"), _LOCK:
                    st.session_state[f"challenge:{rid}"] = ch.challenge(conn(), LLM(conn=conn()), rid, question.strip(), me)
                clear_caches()
            except Exception as e:
                st.error(f"That didn't work: {type(e).__name__}: {e}")
    res = st.session_state.get(f"challenge:{rid}")
    if res:
        a = res["answer"]
        verdict = {"upheld": "You're right", "partially_upheld": "Partly right", "not_upheld": "The evidence holds"}
        md(f"**{verdict.get(a.get('verdict'), a.get('verdict', '–'))}** "
           f"<span class='muted'>· cost ${res.get('cost') or 0:.3f}</span>")
        st.write(a.get("answer"))
        n_p = len(a.get("proposed_edits") or []) + len(a.get("link_finding_ids") or [])
        if n_p:
            st.info(f"The AI suggests {n_p} change(s) — decide them under AI suggestions.", icon=":material/inbox:")
            if st.button("Open AI suggestions"):
                st.switch_page("ui/inbox.py")

if st.button("All details for this requirement", icon=":material/open_in_new:", type="tertiary"):
    open_requirement(rid)
