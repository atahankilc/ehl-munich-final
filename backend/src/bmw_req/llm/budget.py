"""Budget guard (D-014, limits adjustable D-054): reserve worst-case cost before a call, settle with actual usage after.

Limits are on total committed spend = settled cost + open reservations, read from `app_settings` on every call:
- above `stop_at_usd` no call is made (BudgetExceeded);
- above `confirm_above_usd` a run must be confirmed once before it spends. In a terminal the run asks (y/N);
  `BUDGET_CONFIRM=1` confirms up front; the API confirms a job with `approved()` when the user said yes in the app.
  Otherwise the call is refused with BudgetNeedsConfirmation.
"""

import logging
import os
import sqlite3
import sys
import threading
from contextlib import contextmanager

from bmw_req import app_settings

from bmw_req.llm import agents
from bmw_req.llm.pricing import (
    CACHE_WRITE_FACTOR,
    FLEX_FACTOR,
    WEB_SEARCH_CONTENT_TOKENS,
    WEB_SEARCH_PER_CALL,
    Price,
    all_prices,
)

log = logging.getLogger(__name__)

# Terminal prompts only where a person is watching the terminal: the API sets this False (its jobs confirm in the app).
INTERACTIVE = True

_CONFIRM_LOCK = threading.Lock()   # pipeline workers share one prompt
_confirmed = False                 # this process may spend past confirm_above (until stop_at)


class BudgetExceeded(RuntimeError):
    pass


class BudgetNeedsConfirmation(BudgetExceeded):
    """Spend would pass the ask-before-spending limit and nobody confirmed this run."""


class AgentBlocked(BudgetExceeded):
    """The agent is switched off or reached its spend cap (D-055). A BudgetExceeded, so pipelines stop the same way."""


def agent_committed_usd(conn: sqlite3.Connection, agent: agents.Agent) -> float:
    rows = conn.execute("""SELECT job, SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END)
                           FROM llm_usage GROUP BY job""").fetchall()
    return sum(v or 0.0 for job, v in rows if agents.match(job) is agent)


@contextmanager
def approved():
    """Spend past the ask-before-spending limit is confirmed for the duration (an API job the user confirmed)."""
    global _confirmed
    prev, _confirmed = _confirmed, True
    try:
        yield
    finally:
        _confirmed = prev


def needs_confirmation(conn: sqlite3.Connection) -> bool:
    """True when the next call would need a confirmation (committed spend is already past the limit)."""
    return committed_usd(conn) > app_settings.budget_limits().confirm_above_usd and not _confirmed


def _confirm(after: float, limits: app_settings.BudgetLimits, job: str) -> None:
    global _confirmed
    with _CONFIRM_LOCK:
        if _confirmed:
            return
        if os.getenv("BUDGET_CONFIRM", "").lower() in ("1", "yes", "true"):
            _confirmed = True
            return
        msg = (f"Committed OpenAI spend would reach ${after:.2f}, past your ask-before-spending limit "
               f"${limits.confirm_above_usd:.2f} (hard stop ${limits.stop_at_usd:.2f}). Job: {job}.")
        if INTERACTIVE and sys.stdin is not None and sys.stdin.isatty():
            answer = input(f"{msg}\nContinue this run? [y/N] ").strip().lower()
            if answer in ("y", "yes"):
                _confirmed = True
                return
            raise BudgetNeedsConfirmation(f"Not confirmed: {msg}")
        raise BudgetNeedsConfirmation(f"{msg} Confirm the run (in the app, or BUDGET_CONFIRM=1 in a terminal).")


def price_for(model: str) -> Price:
    try:
        return all_prices()[model]
    except KeyError:
        raise BudgetExceeded(f"No price for model {model!r}; add it on the AI agents page first") from None


def estimate_tokens(text: str) -> int:
    """Deliberately high input-token estimate: UTF-8 bytes / 2."""
    return len(text.encode("utf-8")) // 2 + 1


def worst_case_usd(model: str, input_tokens: int, max_output_tokens: int = 0, max_tool_calls: int = 0) -> float:
    """List price (no Flex discount, no cache), plus search calls and their content tokens."""
    p = price_for(model)
    tokens_in = input_tokens + max_tool_calls * WEB_SEARCH_CONTENT_TOKENS
    return (tokens_in * p.input + max_output_tokens * p.output) / 1e6 + max_tool_calls * WEB_SEARCH_PER_CALL


def actual_usd(
    model: str,
    *,
    input_tokens: int,
    cached_tokens: int = 0,
    cache_write_tokens: int = 0,
    output_tokens: int = 0,
    search_calls: int = 0,
    flex: bool = False,
) -> float:
    p = price_for(model)
    uncached = max(input_tokens - cached_tokens - cache_write_tokens, 0)
    tokens_usd = (
        uncached * p.input
        + cached_tokens * p.cached_input
        + cache_write_tokens * p.input * CACHE_WRITE_FACTOR
        + output_tokens * p.output
    ) / 1e6
    if flex:
        tokens_usd *= FLEX_FACTOR
    return tokens_usd + search_calls * WEB_SEARCH_PER_CALL


def spent_usd(conn: sqlite3.Connection) -> float:
    return conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE status != 'reserved'").fetchone()[0]


def committed_usd(conn: sqlite3.Connection) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END), 0) FROM llm_usage"
    ).fetchone()[0]


def reserve(conn: sqlite3.Connection, *, job: str, kind: str, model: str, reserved_usd: float, demo: bool) -> int:
    """Insert a reservation row, or raise BudgetExceeded / BudgetNeedsConfirmation if it would cross a limit."""
    limits = app_settings.budget_limits()

    def stop_if_over(after: float) -> None:
        if after > limits.stop_at_usd:
            raise BudgetExceeded(f"Budget stop: ${after:.2f} would exceed ${limits.stop_at_usd:.2f} ({job}). "
                                 "Raise the stop in the app's Usage tab to continue.")

    # stop first (never ask about a call that can't run), then ask — outside the write transaction,
    # so a prompt never holds the DB lock
    after = committed_usd(conn) + reserved_usd
    stop_if_over(after)
    agent = agents.match(job)
    if agent is not None:
        cfg = app_settings.agent_config(agent.key)
        if not cfg.enabled:
            raise AgentBlocked(f"{agent.name} is switched off on the AI agents page ({job}).")
        if cfg.cap_usd is not None and agent_committed_usd(conn, agent) + reserved_usd > cfg.cap_usd:
            raise AgentBlocked(f"{agent.name} would pass its ${cfg.cap_usd:.2f} cap ({job}). "
                               "Raise the cap on the AI agents page to continue.")
    if after > limits.confirm_above_usd:
        _confirm(after, limits, job)
    conn.execute("BEGIN IMMEDIATE")
    try:
        after = committed_usd(conn) + reserved_usd
        stop_if_over(after)
        cur = conn.execute(
            "INSERT INTO llm_usage (job, demo, kind, model, status, reserved_usd) VALUES (?, ?, ?, ?, 'reserved', ?) RETURNING id",
            (job, int(demo), kind, model, reserved_usd),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return cur.fetchone()[0]


def settle(conn: sqlite3.Connection, usage_id: int, *, status: str, cost_usd: float, **fields) -> None:
    """Replace a reservation with actual usage. `fields` are llm_usage columns (tokens, response_id, error, ...)."""
    cols = ["status", "cost_usd", *fields]
    sets = ", ".join(f"{c} = ?" for c in cols)
    conn.execute(
        f"UPDATE llm_usage SET {sets}, settled_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (status, cost_usd, *fields.values(), usage_id),
    )
