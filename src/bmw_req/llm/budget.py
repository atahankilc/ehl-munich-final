"""Budget guard (D-014): reserve worst-case cost before a call, settle with actual usage after.

Thresholds are on total committed spend = settled cost + open reservations.
"""

import logging
import sqlite3

from bmw_req.llm.pricing import (
    CACHE_WRITE_FACTOR,
    FLEX_FACTOR,
    PRICES,
    WEB_SEARCH_CONTENT_TOKENS,
    WEB_SEARCH_PER_CALL,
    Price,
)

log = logging.getLogger(__name__)

WARN_USD = 45.0
BLOCK_NON_DEMO_USD = 70.0
HARD_STOP_USD = 90.0


class BudgetExceeded(RuntimeError):
    pass


def price_for(model: str) -> Price:
    try:
        return PRICES[model]
    except KeyError:
        raise BudgetExceeded(f"No price for model {model!r}; add it to pricing.py before using it") from None


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
    """Insert a reservation row, or raise BudgetExceeded if it would cross a threshold."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        after = committed_usd(conn) + reserved_usd
        if after > HARD_STOP_USD:
            raise BudgetExceeded(f"Hard stop: ${after:.2f} would exceed ${HARD_STOP_USD:.0f} ({job})")
        if not demo and after > BLOCK_NON_DEMO_USD:
            raise BudgetExceeded(f"Non-demo jobs blocked: ${after:.2f} would exceed ${BLOCK_NON_DEMO_USD:.0f} ({job})")
        cur = conn.execute(
            "INSERT INTO llm_usage (job, demo, kind, model, status, reserved_usd) VALUES (?, ?, ?, ?, 'reserved', ?)",
            (job, int(demo), kind, model, reserved_usd),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if after > WARN_USD:
        log.warning("LLM spend warning: committed $%.2f > $%.0f — re-estimate the plan (D-014)", after, WARN_USD)
    return cur.lastrowid


def settle(conn: sqlite3.Connection, usage_id: int, *, status: str, cost_usd: float, **fields) -> None:
    """Replace a reservation with actual usage. `fields` are llm_usage columns (tokens, response_id, error, ...)."""
    cols = ["status", "cost_usd", *fields]
    sets = ", ".join(f"{c} = ?" for c in cols)
    conn.execute(
        f"UPDATE llm_usage SET {sets}, settled_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (status, cost_usd, *fields.values(), usage_id),
    )
