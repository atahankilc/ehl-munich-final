"""Export: the structured requirement list (the BMW deliverable) as JSON, CSV (one row per target) and a
Markdown report. Every download is logged as an access event."""

import json

import pandas as pd
import streamlit as st

from bmw_req import service
from ui.common import _LOCK, conn, empty, log_export, page_header

page_header("Export",
            "The structured requirement list: ID, description, linked findings and sources, score and rationale per "
            "market, evidence level, assumptions and uncertainties, decision status.")


@st.cache_data(ttl=20, show_spinner="Building export …")
def build() -> list[dict]:
    with _LOCK:
        return service.export_requirements(conn())


data = build()
if not data:
    empty("No requirements to export yet.")
    st.stop()

statuses = sorted({r["status"] for r in data})
sel = st.multiselect("Include status", statuses, default=[s for s in statuses if s != "rejected"] or statuses)
data = [r for r in data if r["status"] in sel]

rows = []
for r in data:
    for t in r["targets"] or [{}]:
        rows.append({
            "id": r["id"], "title": r["title"], "category": r["category"], "status": r["status"], "version": r["version"],
            "target": t.get("target"), "realization": t.get("realization"), "score": t.get("score"),
            "ai_proposed_priority": t.get("ai_proposed_priority"), "pm_priority": t.get("pm_priority"),
            "evidence_level_target": t.get("evidence_level"), "evidence_level": r["evidence_level"],
            "horizon": r["horizon"], "kano_class": r["kano_class"], "kano_drift": r["kano_drift"],
            "must_not_lose": r["must_not_lose"], "effort": r["effort"], "description": r["description"],
            "target_metric": r["target_metric"], "acceptance_criteria": r["acceptance_criteria"],
            "prioritization_rationale": t.get("rationale"), "market_note": t.get("market_note"),
            "assumptions": r["assumptions"], "uncertainties": r["uncertainties"],
            "conflicting_evidence": r["conflicting_evidence"],
            "findings": "; ".join(f"F{f['id']} ({f['source_kind']}, {f['relation']}, {f['n_sources']} src)" for f in r["findings"]),
            "n_sources": sum(f["n_sources"] for f in r["findings"]),
        })
flat = pd.DataFrame(rows)


def markdown_report(items: list[dict]) -> str:
    out = ["# Customer requirements — successor BMW vehicles", "",
           "AI-derived, PM-reviewed. Evidence and assumptions are listed separately. Scores are per derivative × market.", ""]
    for r in items:
        out += [f"## {r['id']} · {r['title']}", "",
                f"- **Status:** {r['status']} (v{r['version']}) · **Evidence level:** {r['evidence_level'] or '–'} · "
                f"**Horizon:** {r['horizon']} · **Kano:** {r['kano_class']} ({r['kano_drift'] or 'stable'}) · "
                f"**Effort:** {r['effort'] or '–'}" + (" · **Must-not-lose**" if r["must_not_lose"] else ""),
                f"- **Category:** {r['category']}", "", r["description"] or "", "",
                f"**Target metric:** {r['target_metric'] or '–'}  ", f"**Acceptance criteria:** {r['acceptance_criteria'] or '–'}", "",
                "| Target | Realization | Score | AI priority | PM priority | Evidence |", "|---|---|---|---|---|---|"]
        for t in r["targets"]:
            sc = f"{t['score']:.0f}" if t.get("score") is not None else "–"
            out.append(f"| {t['target']} | {t['realization'] or '–'} | {sc} | {t['ai_proposed_priority'] or '–'} | "
                       f"{t['pm_priority'] or 'not set'} | {t['evidence_level'] or '–'} |")
        out.append("")
        for t in r["targets"]:
            if t.get("rationale"):
                out.append(f"- *{t['target']}:* {t['rationale']}")
        out += ["", "**Evidence (linked findings)**", ""]
        for f in r["findings"]:
            out.append(f"- F{f['id']} [{f['source_kind']}, {f['relation']}] {f['title']} — {f['n_sources']} source(s)")
            for s in f["sources_sample"][:3]:
                ref = s.get("external_id") or s.get("url") or s.get("ref")
                q = (s.get("quote") or "").replace("\n", " ")
                out.append(f"  - {ref}" + (f": “{q[:200]}”" if q else ""))
        out += ["", "**Assumptions (forward-looking)**", "", r["assumptions"] or "–", "",
                "**Uncertainties**", "", r["uncertainties"] or "–", "",
                "**Conflicting evidence**", "", r["conflicting_evidence"] or "–", "", "---", ""]
    return "\n".join(out)


c = st.columns(4)
c[0].metric("Requirements", len(data))
c[1].metric("Targets", len(flat))
c[2].metric("Approved", sum(r["status"] == "approved" for r in data))
c[3].metric("PM-confirmed priorities", int(flat["pm_priority"].notna().sum()) if not flat.empty else 0)

d1, d2, d3 = st.columns(3)
d1.download_button("JSON (full, with sources)", json.dumps(data, ensure_ascii=False, indent=1, default=str).encode("utf-8"),
                   file_name="requirements.json", mime="application/json", icon=":material/data_object:",
                   on_click=log_export, args=("requirements.json", f"{len(data)} requirements"), width="stretch")
d2.download_button("CSV (one row per target)", flat.to_csv(index=False).encode("utf-8"), file_name="requirements.csv",
                   mime="text/csv", icon=":material/table:", on_click=log_export,
                   args=("requirements.csv", f"{len(flat)} rows"), width="stretch")
report = markdown_report(data)
d3.download_button("Markdown report", report.encode("utf-8"), file_name="requirements.md", mime="text/markdown",
                   icon=":material/article:", on_click=log_export, args=("requirements.md", f"{len(data)} requirements"),
                   width="stretch")
st.caption("Every download is recorded as an access event in the audit trail.")

tab1, tab2 = st.tabs(["Table preview", "Report preview"])
with tab1:
    st.dataframe(flat, hide_index=True, width="stretch", height=480,
                 column_config={"score": st.column_config.NumberColumn(format="%.0f")})
with tab2:
    st.markdown(report[:60000])
    if len(report) > 60000:
        st.caption("Preview truncated — download for the full report.")
