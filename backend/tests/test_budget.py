"""Budget guard tests with a fake OpenAI client — no paid calls."""

from types import SimpleNamespace as NS

import httpx
import openai
import pytest

from bmw_req.db import connect
from bmw_req import app_settings
from bmw_req.llm import LLM, BudgetExceeded, BudgetNeedsConfirmation, budget


def fake_response(input_tokens=1000, cached=0, cache_write=0, output=200, reasoning=50, tier="default", searches=0):
    return NS(
        id="resp_test",
        status="completed",
        model="gpt-6-luna",
        service_tier=tier,
        output_text="ok",
        output=[NS(type="web_search_call")] * searches + [NS(type="message")],
        usage=NS(
            input_tokens=input_tokens,
            input_tokens_details=NS(cached_tokens=cached, cache_write_tokens=cache_write),
            output_tokens=output,
            output_tokens_details=NS(reasoning_tokens=reasoning),
        ),
    )


class FakeResponses:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create(self, **params):
        self.calls.append(params)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    parse = create


@pytest.fixture
def conn():
    return connect(":memory:")


def make_llm(conn, result=None):
    client = NS(responses=FakeResponses(result or fake_response()))
    return LLM(conn=conn, client=client)


def preload(conn, usd, status="completed"):
    conn.execute(
        "INSERT INTO llm_usage (job, kind, model, status, reserved_usd, cost_usd) VALUES ('seed', 'responses', 'gpt-6-luna', ?, ?, ?)",
        (status, usd, usd),
    )


def test_actual_cost_standard():
    # 800 uncached + 200 cached input, 200 output on luna
    usd = budget.actual_usd("gpt-6-luna", input_tokens=1000, cached_tokens=200, output_tokens=200)
    assert usd == pytest.approx((800 * 0.10 + 200 * 0.01 + 200 * 0.50) / 1e6)


def test_actual_cost_flex_cache_write_and_search():
    usd = budget.actual_usd(
        "gpt-6.1-sol", input_tokens=2000, cache_write_tokens=1000, output_tokens=100, search_calls=2, flex=True
    )
    tokens = (1000 * 2.00 + 1000 * 2.00 * 1.25 + 100 * 10.00) / 1e6 * 0.5
    assert usd == pytest.approx(tokens + 2 * 0.01)


def test_unknown_model_refused():
    with pytest.raises(BudgetExceeded):
        budget.worst_case_usd("gpt-6-astra", 100, 100)


def test_call_is_reserved_then_settled(conn):
    llm = make_llm(conn)
    res = llm.generate(job="t", tier="fast", input="hello", max_output_tokens=500, use_cache=False)
    row = conn.execute("SELECT * FROM llm_usage WHERE id = ?", (res.usage_id,)).fetchone()
    assert row["status"] == "completed"
    assert row["reserved_usd"] > row["cost_usd"] > 0
    assert row["input_tokens"] == 1000 and row["reasoning_tokens"] == 50
    assert llm.client.responses.calls[0]["max_output_tokens"] == 500


def test_max_output_tokens_required(conn):
    with pytest.raises(ValueError):
        make_llm(conn).generate(job="t", tier="fast", input="x", max_output_tokens=0)


def test_tools_need_max_tool_calls(conn):
    with pytest.raises(ValueError):
        make_llm(conn).generate(job="t", tier="fast", input="x", max_output_tokens=10, tools=[{"type": "web_search"}])


def test_past_confirm_limit_needs_confirmation(conn):
    preload(conn, 45.5)   # default ask-before-spending limit is $45
    llm = make_llm(conn)
    with pytest.raises(BudgetNeedsConfirmation, match="ask-before-spending"):
        llm.generate(job="t", tier="smart", input="x", max_output_tokens=100, use_cache=False)
    assert conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0] == 1   # nothing reserved
    with budget.approved():   # an API job the user confirmed in the app
        llm.generate(job="t", tier="smart", input="x", max_output_tokens=100, use_cache=False)


def test_budget_confirm_env_confirms_up_front(conn, monkeypatch):
    preload(conn, 45.5)
    monkeypatch.setenv("BUDGET_CONFIRM", "1")
    make_llm(conn).generate(job="t", tier="smart", input="x", max_output_tokens=100)


@pytest.mark.parametrize("answer, ok", [("y", True), ("", False), ("n", False)])
def test_terminal_asks_once_per_run(conn, monkeypatch, answer, ok):
    preload(conn, 45.5)
    asked = []
    monkeypatch.setattr(budget, "INTERACTIVE", True)
    monkeypatch.setattr(budget.sys, "stdin", NS(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or answer)
    llm = make_llm(conn)
    if ok:
        llm.generate(job="t", tier="smart", input="a", max_output_tokens=100, use_cache=False)
        llm.generate(job="t", tier="smart", input="b", max_output_tokens=100, use_cache=False)
        assert len(asked) == 1   # the yes covers the rest of the run
    else:
        with pytest.raises(BudgetNeedsConfirmation, match="Not confirmed"):
            llm.generate(job="t", tier="smart", input="a", max_output_tokens=100, use_cache=False)


def test_limits_come_from_settings(conn):
    app_settings.set_budget_limits(5, 10)
    preload(conn, 9.999)
    with pytest.raises(BudgetExceeded, match="Budget stop"):   # stop wins: no question for a call that can't run
        make_llm(conn).generate(job="t", tier="smart", input="x", max_output_tokens=1000)


def test_invalid_limits_refused():
    with pytest.raises(ValueError):
        app_settings.set_budget_limits(20, 10)
    with pytest.raises(ValueError):
        app_settings.set_budget_limits(5, 0)


def test_app_key_wins_over_env_and_is_masked(monkeypatch):
    monkeypatch.setattr(app_settings, "get_settings", lambda: NS(openai_api_key="sk-env-0000000000000000000", data_dir=None))
    assert app_settings.key_source() == "env"
    app_settings.set_api_key("sk-app-1111111111111111abcd")
    assert app_settings.api_key() == "sk-app-1111111111111111abcd" and app_settings.key_source() == "app"
    assert app_settings.mask(app_settings.api_key()) == "sk-…abcd"
    app_settings.set_api_key(None)
    assert app_settings.api_key() == "sk-env-0000000000000000000"


def test_identical_request_served_from_cache(conn):
    llm = make_llm(conn)
    first = llm.generate(job="t", tier="fast", input="same", max_output_tokens=10)
    second = llm.generate(job="t", tier="fast", input="same", max_output_tokens=10)
    assert not first.cached and second.cached and second.cost_usd == 0
    assert len(llm.client.responses.calls) == 1
    assert conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0] == 1


def test_stop_applies_even_when_confirmed(conn):
    preload(conn, 89.999)
    with budget.approved(), pytest.raises(BudgetExceeded, match="Budget stop"):
        make_llm(conn).generate(job="t", tier="smart", input="x", max_output_tokens=1000, demo=True)


def test_open_reservations_count(conn):
    preload(conn, 69.999, status="reserved")
    assert budget.committed_usd(conn) == pytest.approx(69.999)
    assert budget.spent_usd(conn) == 0


def test_flex_priced_only_when_confirmed(conn):
    llm = make_llm(conn, fake_response(tier="default"))
    std = llm.generate(job="t", tier="fast", input="x", max_output_tokens=10, flex=True, use_cache=False)
    assert llm.client.responses.calls[0]["service_tier"] == "flex"
    flex = make_llm(conn, fake_response(tier="flex")).generate(
        job="t", tier="fast", input="x", max_output_tokens=10, flex=True, use_cache=False
    )
    assert flex.cost_usd == pytest.approx(std.cost_usd * 0.5)


def test_api_error_not_billed(conn):
    err = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(openai.APIConnectionError):
        make_llm(conn, err).generate(job="t", tier="fast", input="x", max_output_tokens=10)
    row = conn.execute("SELECT status, cost_usd FROM llm_usage").fetchone()
    assert (row["status"], row["cost_usd"]) == ("failed", 0.0)


def test_parse_error_keeps_worst_case(conn):
    with pytest.raises(ValueError):
        make_llm(conn, ValueError("bad json")).generate(job="t", tier="fast", input="x", max_output_tokens=10)
    row = conn.execute("SELECT status, cost_usd, reserved_usd FROM llm_usage").fetchone()
    assert row["status"] == "failed" and row["cost_usd"] == row["reserved_usd"]
