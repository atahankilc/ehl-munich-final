"""How it works: one requirement followed step by step from the raw customer comment to the PM's decision.

Every step shows, side by side, what happens to *all* data (rule, actor, model, live counts, cost) and what it did to
*this* requirement for one car × market (the real comment, signal, theme, fit verdicts, the score arithmetic and the
decisions). Read-only; everything comes from the same tables as the rest of the app."""

import altair as alt
import pandas as pd
import streamlit as st

from bmw_req.pipeline.scoring import CONFIDENCE, EFFORT_MOD, MARKET_FIT_MOD, PRIORITY_BANDS
from ui.common import (EVIDENCE_HELP, EVIDENCE_LABELS, FACTOR_COLOR, HORIZON_LABELS, KANO_LABELS, NO_DATA_COLOR,
                       chip, empty, esc, evidence_chip, latest_fit, loads, md, nz, open_requirement, page_header,
                       plain_target, priority_chip, q, q1, requirement_options, review_requirement, short, status_chip,
                       targets_df)

page_header("How it works — follow one requirement",
            "Pick a requirement and a car · market. Each step shows the rule applied to all data on the left and what "
            "it did to this requirement on the right — from one customer's words to the PM's decision.")

opts = requirement_options()
if not opts:
    empty("No requirements yet — open wave 1 on the Home page first.")
    st.stop()

# ------------------------------------------------------------------------------------------------ pickers
cur = st.session_state.get("req_id")
c1, c2 = st.columns([3, 2])
idx = next((i for i, o in enumerate(opts) if cur and o.startswith(f"{cur} ·")), 0)
pick = c1.selectbox("Requirement", opts, index=idx)
rid = pick.split(" · ")[0]
st.session_state["req_id"] = rid
req = q("SELECT * FROM requirement WHERE id = ?", (rid,)).iloc[0].to_dict()
deriv = loads(req.get("derivation_json"), {}) or {}
tdf = targets_df()
tdf = tdf[tdf["requirement_id"] == rid].sort_values(["vehicle_model_id", "market_code"]) if not tdf.empty else tdf
if tdf.empty:
    empty("This requirement has no car · market targets yet.")
    st.stop()
tlabels = [plain_target(d, m) for d, m in zip(tdf["vehicle_model_id"], tdf["market_code"])]
t_idx = next((i for i, (d, m) in enumerate(zip(tdf["vehicle_model_id"], tdf["market_code"])) if (d, m) == ("G60", "US")), 0)
tpick = c2.selectbox("Car · market", tlabels, index=t_idx)
t = tdf.iloc[tlabels.index(tpick)].to_dict()
D, M = t["vehicle_model_id"], t["market_code"]
b = loads(t["score_breakdown_json"], {}) or {}

latest_ver = q1("SELECT MAX(extractor_version) FROM verbatim_extraction")
cost = q("""SELECT substr(job, 1, instr(job || ':', ':') - 1) p, COUNT(*) calls, SUM(cost_usd) usd FROM llm_usage
            WHERE status != 'reserved' GROUP BY 1""")
cost_map = {r.p: (int(r.calls), float(r.usd or 0)) for r in cost.itertuples()}


def spend(*prefixes: str) -> str:
    calls = sum(cost_map.get(p, (0, 0))[0] for p in prefixes)
    usd = sum(cost_map.get(p, (0, 0))[1] for p in prefixes)
    return f"{calls:,} AI calls · ${usd:.2f} so far" if calls else "no AI calls"


REL = {"contradicts": "contradicting", "context": "context only"}
WHO = {"ai": ("AI", "proposed"), "system": ("System · no AI", "system"), "human": ("Product manager", "approved")}


def step(n: int, title: str, who: str, model: str | None = None):
    """Step header; returns (left, right) columns inside a bordered card."""
    box = st.container(border=True)
    label, key = WHO[who]
    box.markdown(f"#### {n} · {title}")
    md_ = chip(label, key) + (f" <span class='muted'>{esc(model)}</span>" if model else "")
    with box:
        md(md_)
    return box.columns([2, 3], gap="large")


def rule(text: str) -> None:
    md(f"<div class='card' style='margin-top:4px;border-left:4px solid #8a94a3;background:#f7f8fa'><h4>Rule</h4>"
       f"<div class='kv'>{text}</div></div>")


def no_data(text: str) -> None:
    md(f"<div class='card uncertainty'><div class='kv'>{text}</div></div>")


# summary strip
md(" ".join([status_chip(req["status"]), evidence_chip(t["target_evidence"]),
             priority_chip(nz(t["pm_priority"]) or nz(t["proposed_priority"]), ai=not nz(t["pm_priority"])),
             f"<span class='muted'>{esc(rid)} · {esc(req['title'])} · {esc(tpick)}</span>"]))
st.write("")

# ================================================================================================ 1 collect
src = q("SELECT kind, COUNT(*) n FROM source_item GROUP BY kind")
src_map = dict(zip(src["kind"], src["n"])) if not src.empty else {}
ex = q("""SELECT s.id sid, s.external_id, s.ref, s.text, s.country, s.market_code, s.meta_json, s.wave,
                 f.id fid, f.title ftitle, g.id gid
          FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
          JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
          JOIN source_item s ON s.id = g.source_item_id
          WHERE rf.requirement_id = ? AND rf.relation = 'supports' AND s.vehicle_model_id = ? AND s.market_code = ?
          ORDER BY CASE g.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, g.quote_verified DESC,
                   g.support_question, length(s.text) BETWEEN 60 AND 400 DESC, s.id LIMIT 1""", (rid, D, M))
ex_other_market = False
if ex.empty:   # e.g. China: no customer comments — show where the comments for this requirement come from instead
    ex = q("""SELECT s.id sid, s.external_id, s.ref, s.text, s.country, s.market_code, s.meta_json, s.wave,
                     f.id fid, f.title ftitle, g.id gid
              FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id AND f.source_kind = 'verbatim'
              JOIN finding_signal fs ON fs.finding_id = f.id JOIN signal g ON g.id = fs.signal_id
              JOIN source_item s ON s.id = g.source_item_id
              WHERE rf.requirement_id = ? AND rf.relation = 'supports'
              ORDER BY CASE g.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, g.quote_verified DESC,
                       s.id LIMIT 1""", (rid,))
    ex_other_market = not ex.empty
e = ex.iloc[0].to_dict() if not ex.empty else None

left, right = step(1, "Collect the evidence", "system", "deterministic import, no AI")
with left:
    st.markdown("Every source is stored once with its provenance, so anything later can point back to it.")
    st.dataframe(pd.DataFrame([
        ("Customer comments (verbatims)", src_map.get("feedback", 0)), ("Customer study items", src_map.get("study", 0)),
        ("Sales figures", src_map.get("sales", 0)), ("Option-list entries", src_map.get("option_list", 0)),
        ("Web research, cited", src_map.get("web", 0)), ("Reference facts", src_map.get("reference", 0)),
    ], columns=["source", "items"]), hide_index=True, width="stretch")
    rule("Raw BMW files are read-only. Each item keeps file · sheet · row (or URL + date + trust tier T1–T3). "
         "The feedback has no dates, so it is split into simulated waves.")
with right:
    if e is None:
        no_data(f"No customer comment supports this requirement. It rests on the customer study and cited web "
                f"research only — that is why its evidence level is <b>{esc(EVIDENCE_LABELS.get(t['target_evidence'], '–'))}</b>.")
    else:
        meta = loads(e["meta_json"], {}) or {}
        if ex_other_market:
            no_data(f"There are no customer comments for <b>{esc(tpick)}</b> — this market is scored on study and "
                    f"web evidence. The example below comes from {esc(e['market_code'])}, another market of the same "
                    f"requirement, to show the chain.")
        st.markdown(f"**One real comment behind this requirement** — {esc(e['external_id'])}")
        md(f"<div class='quote'>“{esc(short(e['text'], 600))}”</div>")
        md(f"<span class='muted'>{esc(e['country'] or e['market_code'])} · channel {esc(meta.get('channel') or '–')} · "
           f"simulated wave {int(e['wave'])}<br>provenance: <code>{esc(e['ref'])}</code></span>")

# ================================================================================================ 2 read
n_ext = q1("SELECT COUNT(*) FROM verbatim_extraction WHERE extractor_version = ?", (latest_ver,)) or 0
n_in = q1("SELECT COALESCE(SUM(in_scope), 0) FROM verbatim_extraction WHERE extractor_version = ?", (latest_ver,)) or 0
n_sig = q1("SELECT COUNT(*) FROM signal WHERE extractor_version = ?", (latest_ver,)) or 0
n_unver = q1("SELECT COUNT(*) FROM signal WHERE extractor_version = ? AND quote_verified = 0", (latest_ver,)) or 0

left, right = step(2, "Read each comment and pull out signals", "ai", "cheap model (gpt-6-luna), one prompt for 25 comments")
with left:
    a, b_, c = st.columns(3)
    a.metric("Comments read", f"{n_ext:,}")
    b_.metric("In scope", f"{n_in:,}", help="Out of scope: regulatory, engineering specs, pricing, dealer/service, "
              "or generic praise with no product topic.")
    c.metric("Signals", f"{n_sig:,}", help="One comment can carry several needs.")
    rule("Keep only customer-facing topics (features, comfort, usability, digital, design, driving, charging). "
         "Each signal gets a category, a type (defect · hard to use · complaint · want · like), a severity and a quote. "
         f"The quote must be found word for word in the comment — {n_unver:,} that aren't are flagged, not dropped.")
    st.caption(spend("extract", "recheck"))
with right:
    if e is None:
        st.caption("No comment to show for this requirement.")
    else:
        sigs = q("""SELECT category, topic, feedback_type, severity, need_statement, quote, quote_verified, support_question
                    FROM signal WHERE source_item_id = ? AND extractor_version = ?""", (int(e["sid"]), latest_ver))
        st.markdown(f"**What the AI pulled out of {esc(e['external_id'])}** — {len(sigs)} signal(s)")
        for s in sigs.itertuples():
            md(f"<div class='card evidence'>"
               f"{chip(s.feedback_type.replace('_', ' '), 'proposed')}{chip('severity ' + str(s.severity), 'system')}"
               f"{chip(s.category, 'system')}{chip('quote verified', 'pass') if s.quote_verified else chip('quote not verbatim', 'warn')}"
               f"{chip('support question · counts half', 'warn') if s.support_question else ''}"
               f"<div class='kv' style='margin-top:4px'><b>Need:</b> {esc(s.need_statement)}</div>"
               f"<div class='quote'>“{esc(s.quote)}”</div></div>")

# ================================================================================================ 3 group
fk = q("SELECT COALESCE(source_kind, 'other') k, COUNT(*) n FROM finding GROUP BY 1")
fk_map = dict(zip(fk["k"], fk["n"])) if not fk.empty else {}
links = q("""SELECT f.source_kind k, rf.relation, COUNT(*) n FROM requirement_finding rf JOIN finding f ON f.id = rf.finding_id
             WHERE rf.requirement_id = ? GROUP BY 1, 2""", (rid,))

left, right = step(3, "Group signals into themes (findings)", "ai", "embeddings + clustering; luna writes the theme title")
with left:
    a, b_, c = st.columns(3)
    a.metric("Comment themes", f"{fk_map.get('verbatim', 0):,}")
    b_.metric("Study findings", f"{fk_map.get('study', 0):,}")
    c.metric("Web findings", f"{fk_map.get('web', 0):,}")
    rule("Signals of one car line are grouped by meaning (cosine distance ≤ 0.35, same category and polarity). "
         "A theme needs ≥ 3 different comments; smaller groups stay searchable. Study items become findings with a "
         "z-score against the other items; web findings carry their citations and trust tier.")
    st.caption(spend("embed", "findings", "research"))
with right:
    if e is not None:
        fid = int(e["fid"])
        f = q("SELECT title, summary, metrics_json FROM finding WHERE id = ?", (fid,)).iloc[0]
        n_s = q1("SELECT COUNT(*) FROM finding_signal WHERE finding_id = ?", (fid,)) or 0
        st.markdown(f"**The signal landed in theme F{fid}** — {n_s} signals")
        md(f"<div class='card evidence'><h4>{esc(f['title'])}</h4><div class='kv'>{esc(short(f['summary'], 400))}</div></div>")
        mk = (((loads(f["metrics_json"], {}) or {}).get("by_wave", {}) or {}).get("2", {}) or {}).get("markets", {}) or {}
        if mk:
            st.dataframe(pd.DataFrame([{"market": plain_target(D, k).split(" · ")[1], "comments": v.get("verbatims"),
                                        "share of that market's comments": v.get("share")} for k, v in mk.items()]),
                         hide_index=True, width="stretch",
                         column_config={"share of that market's comments": st.column_config.NumberColumn(format="percent")})
    if not links.empty:
        md("**All findings linked to this requirement:** " + " ".join(
            chip(f"{int(r.n)} {r.k}" + ("" if r.relation == "supports" else f" · {REL.get(r.relation, r.relation)}"),
                 {"contradicts": "fail", "context": "system"}.get(r.relation, "proposed")) for r in links.itertuples())
           + " <span class='muted'>contradicting evidence is shown, never hidden</span>")

# ================================================================================================ 4 draft
n_req = q1("SELECT COUNT(*) FROM requirement") or 0
merges = q1("SELECT COUNT(*) FROM audit_event WHERE action = 'match_existing'") or 0
left, right = step(4, "Draft the requirement", "ai", "reasoning model (gpt-6.1-sol), per car line, then merged across lines")
with left:
    a, b_ = st.columns(2)
    a.metric("Requirements drafted", n_req)
    b_.metric("Duplicates caught", merges, help="Later waves compare new drafts with the whole backlog; a duplicate "
              "becomes a 'merge into existing' suggestion instead of a new requirement.")
    rule("Every requirement must cite ≥ 1 finding, say what customers need (not how to engineer it), separate "
         "<b>evidence</b> from <b>assumptions</b>, and tag when it is needed and its Kano class. It must name a "
         "<b>product decision</b> BMW could trade off — 'it must work reliably' is quality, not a requirement: "
         "defect-dominated themes go to the <b>Quality hand-over</b> list instead. Lines are merged only when one "
         "decision satisfies all of them. Created as <b>To review</b> — the AI can never approve it.")
    st.caption(spend("derive", "consolidate", "match_existing", "link"))
with right:
    st.markdown(f"**{esc(req['title'])}**")
    st.write(short(req.get("description"), 500))
    md(" ".join([chip(HORIZON_LABELS.get(req.get("horizon"), req.get("horizon") or "–"), "proposed"),
                 chip(KANO_LABELS.get(req.get("kano_class"), req.get("kano_class") or "–"), "system"),
                 chip(f"effort {req.get('effort') or '–'}", "system"),
                 f"<span class='muted'>drafted by {esc(req.get('created_by') or '–')}"
                 f" from {len(deriv.get('supporting_finding_ids') or [])} finding(s)</span>"]))
    if deriv.get("product_decision"):
        md(f"<div class='card'><h4>Product decision it asks for</h4><div class='kv'>{esc(deriv['product_decision'])}</div></div>")
    ev = deriv.get("evidence_summary")
    asm = nz(req.get("assumptions")) or deriv.get("assumptions")
    if ev:
        md(f"<div class='card evidence'><h4>Evidence (what the data shows)</h4><div class='kv'>{esc(short(ev if isinstance(ev, str) else '; '.join(map(str, ev)), 500))}</div></div>")
    if asm:
        md(f"<div class='card assumption'><h4>Assumption (forward-looking)</h4><div class='kv'>{esc(short(asm if isinstance(asm, str) else '; '.join(map(str, asm)), 400))}</div></div>")
    if deriv.get("horizon_reason"):
        st.caption(f"Why '{HORIZON_LABELS.get(req.get('horizon'), '')}': {deriv['horizon_reason']}")

# ================================================================================================ 5 fit
fit = latest_fit(rid)
fit_t = fit[(fit["vehicle_model_id"] == D) & (fit["market_code"] == M)] if not fit.empty else fit
left, right = step(5, "Check that it fits the brand, segment, market and plant", "ai",
                   "luna checks everything; every warn/fail is re-checked by sol")
with left:
    agg = q("SELECT check_type, result, COUNT(*) n FROM fit_check GROUP BY 1, 2")
    if not agg.empty:
        pv = agg.pivot_table(index="check_type", columns="result", values="n", fill_value=0).reset_index()
        st.dataframe(pv.rename(columns={"check_type": "check"}), hide_index=True, width="stretch")
    rule("<b>Brand</b> fail blocks approval unless the PM overrides it with a reason. "
         "<b>Market</b> fit nudges the score (pass +2, warn −5, fail −10). <b>Segment</b> is shown. "
         "<b>Feasibility</b> (platform + a plant that serves this market in time) is context only — never blocks, never scored.")
    st.caption(spend("fit"))
with right:
    if fit_t.empty:
        st.caption("No fit checks for this car · market yet.")
    for r in fit_t.itertuples():
        effect = {"brand": "gate", "market": "score modifier", "segment": "shown", "feasibility": "context"}.get(r.check_type, "")
        md(f"<div class='card'>{chip(r.result.upper(), r.result)} <b>{esc(r.check_type.title())}</b> "
           f"<span class='muted'>· {effect} · checked by {esc(r.checked_by)}</span>"
           f"<div class='kv' style='margin-top:4px'>{esc(short(r.rationale, 320))}</div></div>")

# ================================================================================================ 6 score
left, right = step(6, "Score it for this car · market and suggest a priority", "system",
                   "deterministic formula, no AI — same inputs always give the same score")
with left:
    rule("Six factors, each 0–1, weighted. A market without its own comments (e.g. China) borrows the car line's "
         "comment rate at half value; other factors without data are left out and the weights rescaled. It can't "
         "outrank the markets that have comments unless it has its own study gap <i>and</i> competitor evidence. "
         "'Expected' needs get one priority in every market. The result is multiplied by an evidence confidence "
         f"({', '.join(f'{EVIDENCE_LABELS[k].split()[0]} ×{v}' for k, v in CONFIDENCE.items())}) so thin evidence "
         f"still costs points. Effort: {', '.join(f'{k} {v:+.0f}' for k, v in EFFORT_MOD.items())}. "
         f"Bands: <b>Must ≥ {PRIORITY_BANDS[0][1]:.0f}</b>, <b>Should ≥ {PRIORITY_BANDS[1][1]:.0f}</b>, else Could.")
    lv = b.get("evidence_level")
    if lv:
        md(f"**Evidence level here:** {evidence_chip(lv)} <span class='muted'>{esc(EVIDENCE_HELP.get(lv, ''))}</span>")
with right:
    facs = b.get("factors", {})
    if not facs:
        st.caption("Not scored yet.")
    else:
        conf = float(b.get("confidence") or 1.0)
        rows, run = [], 0.0
        wsum = sum(f["weight"] for f in facs.values() if f.get("available")) or 1
        for f in facs.values():
            if not f.get("available"):
                continue
            pts = 100 * f["weight"] * (f["value"] or 0) / wsum
            rows.append((f["label"], run, run + pts, "factor"))
            run += pts
        cut = run * (1 - conf)
        if cut >= 0.05:
            rows.append((f"Evidence confidence ×{conf}", run - cut, run, "minus"))
            run -= cut
        for k, v in (b.get("modifiers") or {}).items():
            if v:
                rows.append((f"{k.replace('_', ' ').capitalize()} {v:+.0f}", min(run, run + v), max(run, run + v),
                             "plus" if v > 0 else "minus"))
                run += v
        score = float(b.get("score", run))
        rows.append(("Score", 0, score, "total"))
        wf = pd.DataFrame(rows, columns=["step", "start", "end", "kind"])
        wf["delta"] = wf.apply(lambda r: r["end"] - r["start"] if r["kind"] != "minus" else -(r["end"] - r["start"]), axis=1)
        order = list(wf["step"])
        base = alt.Chart(wf).encode(y=alt.Y("step:N", sort=order, title=None, axis=alt.Axis(labelLimit=240)))
        bars = base.mark_bar(cornerRadius=3, height=16).encode(
            x=alt.X("start:Q", title="points (0–100)", scale=alt.Scale(domain=[0, 100])), x2="end:Q",
            color=alt.Color("kind:N", legend=None, scale=alt.Scale(
                domain=["factor", "plus", "minus", "total"], range=[FACTOR_COLOR, "#2e8b57", "#c0392b", "#0b3d7a"])),
            tooltip=["step", alt.Tooltip("delta:Q", title="points", format="+.1f")])
        labels = base.mark_text(align="left", dx=4, fontSize=11, color="#4a5563").encode(
            x="end:Q", text=alt.Text("delta:Q", format="+.1f"))
        bands = alt.Chart(pd.DataFrame({"x": [lo for _, lo in PRIORITY_BANDS if lo > 0],
                                        "band": [n for n, lo in PRIORITY_BANDS if lo > 0]})).mark_rule(
            strokeDash=[4, 3], color="#8a94a3").encode(x="x:Q", tooltip=["band", "x"])
        st.altair_chart((bars + labels + bands).properties(height=30 * len(wf) + 30), width="stretch")
        prio = t["proposed_priority"]
        st.markdown(f"**{score:.0f} points → AI suggests {esc(nz(prio, '–'))}** "
                    f"<span class='muted'>(dashed lines: Should ≥ 45, Must ≥ 60)</span>", unsafe_allow_html=True)
        for note in (b.get("cap_note"), b.get("priority_note")):
            if note:
                st.caption(note[0].upper() + note[1:] + ".")
        gaps = [f["label"] for f in facs.values() if not f.get("available")]
        st.dataframe(pd.DataFrame([{
            "factor": f["label"], "weight": f["weight"],
            "value 0–1": f["value"] if f.get("available") else None,
            "points": round(100 * f["weight"] * (f["value"] or 0) / wsum, 1) if f.get("available") else None,
            "why": f["explanation"]} for f in facs.values()]), hide_index=True, width="stretch",
            column_config={"value 0–1": st.column_config.NumberColumn(format="%.2f"),
                           "why": st.column_config.TextColumn(width="large")})
        if gaps:
            md("**No data here:** " + " ".join(chip(g, "warn") for g in gaps)
               + " <span class='muted'>— left out, weights rescaled; the evidence level carries the penalty.</span>")

# ================================================================================================ 7 decide
ev_all = q("""SELECT ts, actor_type, actor_id, action, entity_id, field, old_value, new_value, rationale
              FROM audit_event WHERE (entity_id = ? OR entity_id LIKE ?) AND action != 'view' ORDER BY id""",
           (rid, f"{rid}:%"))
left, right = step(7, "The product manager decides", "human", "named person + written reason, every time")
with left:
    rule("Only a person can approve, reject or defer, or confirm a priority — always with a reason. The PM can "
         "edit, challenge (the AI must answer), or accept the AI's priority. Brand-fit fail needs an explicit override.")
    by = ev_all["actor_type"].value_counts().to_dict() if not ev_all.empty else {}
    md("**Everything that happened to this requirement:** " + " ".join(
        chip(f"{by[k]} by {WHO[k][0].split(' ·')[0]}", WHO[k][1]) for k in ("ai", "system", "human") if by.get(k)))
    a, b_ = st.columns(2)
    if a.button("Review this requirement", type="primary", icon=":material/fact_check:"):
        review_requirement(rid)
    if b_.button("Full details & audit", icon=":material/description:"):
        open_requirement(rid)
with right:
    md(f"**Status:** {status_chip(req['status'])} &nbsp; **Priority for {esc(tpick)}:** "
       + (f"{priority_chip(t['pm_priority'])} <span class='muted'>(PM)</span> · AI suggested {esc(nz(t['proposed_priority'], '–'))}"
          if nz(t["pm_priority"]) else f"{priority_chip(t['proposed_priority'], ai=True)} <span class='muted'>— not confirmed yet</span>"))
    hum = ev_all[ev_all["actor_type"] == "human"] if not ev_all.empty else ev_all
    if hum.empty:
        st.caption("No human decision yet — this is still an AI proposal.")
    else:
        items = []
        for r in hum.tail(8).itertuples():
            what = r.action.replace("_", " ") + (f" {r.field}" if r.field else "") + (
                f": {short(r.old_value, 30)} → {short(r.new_value, 40)}" if r.new_value and r.action != "edit_evidence" else "")
            items.append(f"<div class='tl-item human'><div class='tl-meta'>{esc(str(r.ts)[:16].replace('T', ' '))} · "
                         f"{esc(r.actor_id)} · {esc(r.entity_id)}</div><div class='tl-body'><b>{esc(what)}</b><br>"
                         f"{esc(short(r.rationale, 200))}</div></div>")
        md("<div class='tl'>" + "".join(items) + "</div>")

# ================================================================================================ 8 repeat
left, right = step(8, "New evidence arrives → the AI re-scores and suggests changes", "ai",
                   "scores recomputed automatically; priority changes are only suggestions")
with left:
    rule("Each wave adds evidence and re-runs steps 2–6. The AI may update <b>scores</b> (logged). If a score crosses "
         "a band and the PM had already confirmed a priority, the AI opens a <b>suggestion</b> with its cause — the "
         "PM accepts or rejects it. Every run is kept as a snapshot.")
    props = q("""SELECT kind, field, old_value, proposed_value, status, reason, vehicle_model_id, market_code
                 FROM change_proposal WHERE requirement_id = ? ORDER BY id""", (rid,))
    if not props.empty:
        md("**AI suggestions on this requirement:** " + " ".join(
            chip(f"{n} {s}", s) for s, n in props["status"].value_counts().items()))
with right:
    hist = q("""SELECT s.run_id, s.score, s.priority, r.ts FROM score_snapshot s JOIN prioritization_run r ON r.id = s.run_id
                WHERE s.requirement_id = ? AND s.vehicle_model_id = ? AND s.market_code = ? ORDER BY s.run_id""", (rid, D, M))
    causes = q("""SELECT run_id, rationale FROM audit_event WHERE action = 'rescore' AND entity_id = ? ORDER BY id""",
               (f"{rid}:{D}×{M}",))
    if hist.empty:
        st.caption("Not scored in any run yet.")
    else:
        cmap = dict(zip(causes["run_id"], causes["rationale"])) if not causes.empty else {}
        items = []
        for r in hist.itertuples():
            items.append(f"<div class='tl-item system'><div class='tl-meta'>Wave run {int(r.run_id)} · "
                         f"{esc(str(r.ts)[:16].replace('T', ' '))}</div><div class='tl-body'>{chip(r.priority, r.priority)} "
                         f"<b>{r.score:.0f}</b> points<br><span class='muted'>{esc(short(cmap.get(r.run_id, 'unchanged'), 260))}</span>"
                         f"</div></div>")
        md(f"**Score of {esc(tpick)} across the waves**<div class='tl'>" + "".join(items) + "</div>")
    if not props.empty:
        for p in props.tail(3).itertuples():
            tgt = f" · {plain_target(p.vehicle_model_id, p.market_code)}" if nz(p.vehicle_model_id) else ""
            md(f"<div class='card'>{chip(p.status, p.status)} <b>{esc((p.kind or p.field).replace('_', ' '))}{esc(tgt)}</b> "
               f"<span class='muted'>{esc(short(p.old_value, 30) if nz(p.old_value) else '')} → "
               f"{esc(short(p.proposed_value, 60))}</span><div class='kv'>{esc(short(p.reason, 240))}</div></div>")
