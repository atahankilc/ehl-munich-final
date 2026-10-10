"""Shared UI helpers: cached DB connection, read queries, write wrapper, formatting and colour chips.

Reads go through `q()` (short-TTL cache). Every write goes through `write()`, which calls a function from
`bmw_req.service` / `bmw_req.pipeline.scoring` (never raw SQL from the UI), shows `ActionError`s nicely and
clears the read caches.
"""

import html
import json
import threading
from typing import Any, Callable

import pandas as pd
import streamlit as st

from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req.portfolio import FOCUS_TARGETS, LINES, MIN_MARKET_VERBATIMS, SUCCESSOR_LAUNCH, TARGETS, all_targets  # noqa: F401
from bmw_req.service import ActionError

DEFAULT_PM = "Atahan (PM)"
PRIORITIES = ["Must", "Should", "Could"]
STATUSES = ["proposed", "challenged", "approved", "deferred", "rejected"]
MARKET_NAMES = {"US": "United States", "EU": "Europe", "CN": "China", "RoW": "Rest of world"}
SOURCE_KINDS = ["feedback", "study", "sales", "option_list", "web", "reference"]
_LOCK = threading.RLock()

# ------------------------------------------------------------------------------------------------ plain-language labels
# The data model keeps codes (G60, E1, basic …); everything a PM reads goes through these.
VEHICLE_NAMES = {"F70": "1 Series", "G60": "5 Series", "G68": "5 Series LWB", "G70": "7 Series"}
MARKET_SHORT = {"US": "USA", "EU": "Europe", "CN": "China", "RoW": "Rest of world"}
EVIDENCE_LABELS = {"E1": "Strong evidence", "E2": "Good evidence", "E3": "Limited evidence", "E4": "Assumption only"}
EVIDENCE_HELP = {"E1": "20+ customer comments from 2+ channels, plus study or cited web evidence",
                 "E2": "15+ comments, or comments plus study/web evidence",
                 "E3": "a few comments, or study/web evidence only",
                 "E4": "no direct evidence — forward-looking assumption"}
KANO_LABELS = {"basic": "Expected", "performance": "Differentiator", "delighter": "Delighter"}
HORIZON_LABELS = {"today": "Needed today", "at_successor_launch": "Needed by successor launch"}
STATUS_LABELS = {"proposed": "To review", "challenged": "Challenged", "approved": "Approved", "deferred": "Deferred",
                 "rejected": "Rejected"}


def car(d: Any) -> str:
    return VEHICLE_NAMES.get(str(d), str(d))


def mkt(m: Any) -> str:
    return MARKET_SHORT.get(str(m), str(m))


def plain_target(d: Any, m: Any) -> str:
    """'G60', 'US' → '5 Series · USA'."""
    return f"{car(d)} · {mkt(m)}"


def evidence_chip(level: Any) -> str:
    lv = None if level is None or (isinstance(level, float) and pd.isna(level)) else str(level)
    return chip(EVIDENCE_LABELS.get(lv, "No evidence level"), lv) if lv else chip("–")


def status_chip(status: Any) -> str:
    return chip(STATUS_LABELS.get(str(status), str(status)), str(status))


def priority_chip(p: Any, ai: bool = False) -> str:
    """Priority chip; AI suggestions are marked so they're never mistaken for a PM decision."""
    if p is None or (isinstance(p, float) and pd.isna(p)) or p == "":
        return chip("–")
    return chip(f"{p} · AI suggests" if ai else str(p), str(p))


# ------------------------------------------------------------------------------------------------ colours
COLORS = {
    # priority
    "Must": ("#ffffff", "#1c69d4"), "Should": ("#0b3d7a", "#d6e6fb"), "Could": ("#4a5563", "#eceff3"),
    # status
    "proposed": ("#0b3d7a", "#e3edfb"), "challenged": ("#5b2a86", "#efe5f8"), "approved": ("#0f5132", "#d8f0e2"),
    "deferred": ("#7a4b00", "#fff1d0"), "rejected": ("#842029", "#f8dcdf"),
    # evidence level
    "E1": ("#0f5132", "#cfeedd"), "E2": ("#1d5a3a", "#e3f4ea"), "E3": ("#7a4b00", "#fff1d0"), "E4": ("#842029", "#f8dcdf"),
    # fit results / gates
    "pass": ("#0f5132", "#d8f0e2"), "warn": ("#7a4b00", "#fff1d0"), "fail": ("#842029", "#f8dcdf"),
    "overridden": ("#5b2a86", "#efe5f8"),
    # actor types
    "human": ("#0f5132", "#d8f0e2"), "ai": ("#0b3d7a", "#e3edfb"), "system": ("#4a5563", "#eceff3"),
    # evidence vs assumption
    "EVIDENCE": ("#0f5132", "#d8f0e2"), "ASSUMPTION": ("#7a4b00", "#fff1d0"), "UNCERTAINTY": ("#842029", "#f8dcdf"),
    "CONFLICT": ("#842029", "#f8dcdf"),
    # trust tiers
    "T1": ("#0f5132", "#d8f0e2"), "T2": ("#7a4b00", "#fff1d0"), "T3": ("#842029", "#f8dcdf"),
    # proposal states
    "open": ("#0b3d7a", "#e3edfb"), "accepted": ("#0f5132", "#d8f0e2"), "superseded": ("#4a5563", "#eceff3"),
}
FACTOR_COLOR = "#1c69d4"
NO_DATA_COLOR = "#c9d0d8"

CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px;}
h1 {font-size: 1.75rem !important; font-weight: 650 !important; letter-spacing: -0.01em;}
h2 {font-size: 1.3rem !important; font-weight: 620 !important;}
h3 {font-size: 1.08rem !important; font-weight: 600 !important;}
.chip {display:inline-block; padding: 1px 9px; border-radius: 10px; font-size: 0.78rem; font-weight: 600;
       line-height: 1.55; margin: 0 4px 2px 0; white-space: nowrap; border: 1px solid rgba(0,0,0,0.04);}
.muted {color: #66717f; font-size: 0.86rem;}
.kv {font-size: 0.9rem; color: #1d2733;}
.kv b {color: #4a5563; font-weight: 600;}
.card {border: 1px solid #dde2e8; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; background: #fff;}
.card.conflict {border-left: 4px solid #c0392b; background: #fffafa;}
.card.evidence {border-left: 4px solid #2e8b57;}
.card.assumption {border-left: 4px solid #d99a00;}
.card.uncertainty {border-left: 4px solid #c0392b;}
.card h4 {margin: 0 0 6px 0; font-size: 0.92rem; font-weight: 650;}
.tl {border-left: 2px solid #dde2e8; margin-left: 6px; padding-left: 14px;}
.tl-item {position: relative; margin-bottom: 12px;}
.tl-item:before {content: ""; position: absolute; left: -20px; top: 5px; width: 10px; height: 10px;
                 border-radius: 50%; background: #1c69d4;}
.tl-item.human:before {background: #2e8b57;} .tl-item.system:before {background: #8a94a3;}
.tl-meta {font-size: 0.78rem; color: #66717f;}
.tl-body {font-size: 0.88rem;}
.sim-badge {display:inline-block; background:#fff1d0; color:#7a4b00; border-radius:6px; padding:2px 8px;
            font-size:0.75rem; font-weight:650;}
.quote {border-left: 3px solid #c9d0d8; padding: 2px 10px; color: #333d49; font-style: italic; margin: 2px 0 6px 0;
        font-size: 0.88rem;}
div[data-testid="stMetricValue"] {font-size: 1.55rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def chip(text: Any, key: str | None = None) -> str:
    """HTML chip coloured by `key` (default: the text itself)."""
    if text is None or text == "":
        return '<span class="chip" style="color:#66717f;background:#f3f5f8">–</span>'
    fg, bg = COLORS.get(str(key if key is not None else text), ("#1d2733", "#eceff3"))
    return f'<span class="chip" style="color:{fg};background:{bg}">{html.escape(str(text))}</span>'


def md(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


# ------------------------------------------------------------------------------------------------ DB
@st.cache_resource(show_spinner=False)
def _conn(db_path: str):
    return connect(db_path)


def conn():
    return _conn(str(get_settings().db_path))


@st.cache_data(ttl=20, show_spinner=False)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    with _LOCK:
        return pd.read_sql_query(sql, conn(), params=params)


def q1(sql: str, params: tuple = ()):
    """Single scalar (cached)."""
    df = q(sql, params)
    return None if df.empty else df.iat[0, 0]


def clear_caches() -> None:
    st.cache_data.clear()


def write(fn: Callable, *args, success: str | None = None, **kwargs) -> Any:
    """Run a write action (service/scoring function taking conn first). Shows ActionError as a warning."""
    try:
        with _LOCK:
            out = fn(conn(), *args, **kwargs)
    except ActionError as e:
        st.error(f"Not allowed: {e}")
        return None
    except Exception as e:   # surface, don't crash the page
        st.error(f"Action failed: {type(e).__name__}: {e}")
        return None
    clear_caches()
    if success:
        st.toast(success)
    return out if out is not None else True


def raw_conn():
    """Direct connection for library calls that need it (e.g. service.log_access) — wrap in `write`."""
    return conn()


# ------------------------------------------------------------------------------------------------ app state
def actor() -> str:
    return st.session_state.get("pm") or DEFAULT_PM


def current_wave() -> int:
    v = q1("SELECT value FROM app_state WHERE key = 'current_wave'")
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def metrics_wave(wave: int | None = None) -> str:
    """Key into finding.metrics_json['by_wave'] (waves 1–2 carry verbatims; wave 3 adds web only)."""
    w = current_wave() if wave is None else wave
    return str(min(max(w, 1), 2))


def loads(s: Any, default=None):
    if s is None or (isinstance(s, float) and pd.isna(s)) or s == "":
        return default
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


def tlabel(d: str, m: str) -> str:
    return f"{d} × {m}"


def parse_tlabel(label: str) -> tuple[str, str]:
    d, m = label.split(" × ")
    return d, m


def target_labels() -> list[str]:
    return [tlabel(d, m) for d, m in all_targets()]


def empty(msg: str) -> None:
    st.info(msg, icon=":material/inbox:")


def page_header(title: str, subtitle: str | None = None) -> None:
    inject_css()
    st.title(title)
    if subtitle:
        md(f'<div class="muted" style="margin-top:-0.6rem;margin-bottom:0.8rem">{subtitle}</div>')
    flash()


def has_requirements() -> bool:
    return bool(q1("SELECT COUNT(*) FROM requirement"))


def open_requirement(req_id: str) -> None:
    st.session_state["req_id"] = req_id
    st.switch_page("ui/requirement.py")


def review_requirement(req_id: str) -> None:
    """Open the guided review on one requirement."""
    st.session_state["review_focus"] = req_id
    st.switch_page("ui/review.py")


def requirement_options() -> list[str]:
    df = q("SELECT id, title FROM requirement ORDER BY id")
    return [f"{r.id} · {r.title}" for r in df.itertuples()]


def short(s: Any, n: int = 120) -> str:
    s = "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ------------------------------------------------------------------------------------------------ shared queries
def targets_df() -> pd.DataFrame:
    """All requirement targets with requirement columns, brand gate and override state."""
    df = q("""
        SELECT t.requirement_id, t.vehicle_model_id, t.market_code, t.realization, t.score, t.proposed_priority,
               t.priority AS pm_priority, t.evidence_level AS target_evidence, t.rationale AS market_note,
               t.score_breakdown_json, t.run_id,
               r.title, r.category, r.status, r.horizon, r.kano_class, r.kano_drift, r.must_not_lose, r.effort,
               r.evidence_level, r.version,
               (SELECT f.result FROM fit_check f WHERE f.requirement_id = t.requirement_id
                  AND f.vehicle_model_id = t.vehicle_model_id AND f.market_code = t.market_code
                  AND f.check_type = 'brand' ORDER BY f.id DESC LIMIT 1) AS brand_fit,
               (SELECT COUNT(*) FROM audit_event a WHERE a.action = 'override_gate'
                  AND a.entity_id = t.requirement_id || ':' || t.vehicle_model_id || '×' || t.market_code) AS overrides
        FROM requirement_target t JOIN requirement r ON r.id = t.requirement_id""")
    if df.empty:
        return df
    df["target"] = df["vehicle_model_id"] + " × " + df["market_code"]
    df["brand_gate"] = df.apply(
        lambda r: "overridden" if (r["brand_fit"] == "fail" and r["overrides"]) else (r["brand_fit"] or "–"), axis=1)
    df["must_not_lose"] = df["must_not_lose"].fillna(0).astype(int).astype(bool)
    return df


def latest_fit(req_id: str) -> pd.DataFrame:
    return q("""SELECT f.* FROM fit_check f WHERE f.requirement_id = ? AND f.id = (
                  SELECT MAX(g.id) FROM fit_check g WHERE g.requirement_id = f.requirement_id
                  AND COALESCE(g.vehicle_model_id,'') = COALESCE(f.vehicle_model_id,'')
                  AND COALESCE(g.market_code,'') = COALESCE(f.market_code,'') AND g.check_type = f.check_type)
                ORDER BY f.vehicle_model_id, f.market_code, f.check_type""", (req_id,))


def run_label(run_id, ts=None, trigger=None) -> str:
    parts = [f"Run {int(run_id)}"]
    if trigger:
        parts.append(str(trigger).replace("_", " "))
    if ts:
        parts.append(str(ts)[:16].replace("T", " "))
    return " · ".join(parts)


def log_access_once(action: str, entity_type: str, entity_id: str) -> None:
    """One access event per session per (action, entity) — not on every rerun."""
    from bmw_req import service

    key = f"_logged:{action}:{entity_type}:{entity_id}"
    if st.session_state.get(key):
        return
    try:
        with _LOCK:
            service.log_access(conn(), actor(), action, entity_type, entity_id)
        st.session_state[key] = True
    except Exception:
        pass   # access logging must never break viewing


def log_export(entity_id: str, detail: str | None = None) -> None:
    """Callback for download buttons: every export is an access event."""
    from bmw_req import service

    try:
        with _LOCK:
            service.log_access(conn(), actor(), "export", "export", entity_id, detail)
    except Exception:
        pass


def act(fn: Callable, *args, success: str = "Saved", **kwargs) -> None:
    """Run a write; on success remember a flash message and rerun so every view shows fresh data."""
    if write(fn, *args, **kwargs) is not None:
        st.session_state["_flash"] = success
        st.rerun()


def flash() -> None:
    m = st.session_state.pop("_flash", None)
    if m:
        st.success(m, icon=":material/check_circle:")


def nz(v: Any, default: Any = None) -> Any:
    """None for NaN/None/'' (pandas turns SQL NULLs into NaN in mixed columns)."""
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return default
    return v
