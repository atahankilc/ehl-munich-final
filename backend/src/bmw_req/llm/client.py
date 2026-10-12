"""The only path to OpenAI (D-014, D-015, D-020). Every call is reserved, logged and settled."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

import openai
from pydantic import BaseModel

from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req import app_settings
from bmw_req.llm import agents, budget

Tier = Literal["fast", "smart"]
FLEX_TIMEOUT_S = 900.0


@dataclass
class LLMResult:
    text: str
    parsed: Any
    usage_id: int | None     # None on a cache hit
    cost_usd: float
    response: Any            # None on a cache hit
    cached: bool = False


class LLM:
    def __init__(self, conn=None, client=None):
        self.settings = get_settings()
        self.conn = conn if conn is not None else connect()
        self.client = client if client is not None else openai.OpenAI(api_key=app_settings.api_key())   # app key, else .env (D-054)

    def model_for(self, tier: Tier) -> str:
        return app_settings.tier_model(tier)   # set on the AI agents page, else .env (D-055)

    def generate(
        self,
        *,
        job: str,
        tier: Tier,
        input: str | list,
        max_output_tokens: int,
        instructions: str | None = None,
        schema: type[BaseModel] | None = None,
        reasoning_effort: str | None = None,
        tools: list | None = None,
        max_tool_calls: int | None = None,
        flex: bool = False,
        demo: bool = False,
        use_cache: bool = True,
        **kwargs,
    ) -> LLMResult:
        """Call the Responses API. `schema` → structured output parsed into that Pydantic model.

        Identical requests are served from `llm_cache` for free (D-010) unless use_cache=False.
        """
        if not max_output_tokens or max_output_tokens <= 0:
            raise ValueError("max_output_tokens is required on every call (D-014)")
        if tools and not max_tool_calls:
            raise ValueError("Calls with tools need max_tool_calls (D-014 web-search cap)")
        agent = agents.match(job)   # the agent's settings from the AI agents page (D-055)
        cfg = app_settings.agent_config(agent.key) if agent else app_settings.AgentConfig()
        model = cfg.model or self.model_for(tier)
        reasoning_effort = cfg.reasoning_effort or reasoning_effort
        key = kwargs.pop("_cache_key_override", None) or _cache_key(
            model, instructions, input, schema, reasoning_effort, tools, max_tool_calls, max_output_tokens, kwargs)
        if use_cache:
            hit = self.conn.execute("SELECT output_text FROM llm_cache WHERE key = ?", (key,)).fetchone()
            if hit is not None:
                text = hit["output_text"]
                parsed = schema.model_validate_json(text) if schema is not None else None
                return LLMResult(text=text, parsed=parsed, usage_id=None, cost_usd=0.0, response=None, cached=True)
        prompt_text = (instructions or "") + (input if isinstance(input, str) else json.dumps(input, default=str))
        reserved = budget.worst_case_usd(
            model, budget.estimate_tokens(prompt_text), max_output_tokens, max_tool_calls or 0
        )
        usage_id = budget.reserve(self.conn, job=job, kind="responses", model=model, reserved_usd=reserved, demo=demo)

        params: dict[str, Any] = dict(model=model, input=input, max_output_tokens=max_output_tokens, **kwargs)
        if instructions:
            params["instructions"] = instructions
        if reasoning_effort:
            params["reasoning"] = {"effort": reasoning_effort}
        if tools:
            params["tools"] = tools
            params["max_tool_calls"] = max_tool_calls
        if flex:
            params["service_tier"] = "flex"
            params["timeout"] = FLEX_TIMEOUT_S

        try:
            if schema is not None:
                response = self.client.responses.parse(text_format=schema, **params)
            else:
                response = self.client.responses.create(**params)
        except (openai.APIStatusError, openai.APIConnectionError) as e:
            # Request rejected or never reached the API: not billed.
            budget.settle(self.conn, usage_id, status="failed", cost_usd=0.0, error=repr(e)[:2000])
            if flex and isinstance(e, openai.RateLimitError) and "flex" in str(e).lower():
                # Flex capacity unavailable: retry once on standard processing (2× price, still reserved + logged).
                return self.generate(
                    job=job, tier=tier, input=input, max_output_tokens=max_output_tokens, instructions=instructions,
                    schema=schema, reasoning_effort=reasoning_effort, tools=tools, max_tool_calls=max_tool_calls,
                    flex=False, demo=demo, use_cache=use_cache, _cache_key_override=key, **kwargs,
                )
            raise
        except Exception as e:
            # Response may have been billed (e.g. structured-output parse failure): keep the worst case.
            budget.settle(self.conn, usage_id, status="failed", cost_usd=reserved, error=repr(e)[:2000])
            raise

        u = response.usage
        tier_used = getattr(response, "service_tier", None)
        counts = dict(
            input_tokens=u.input_tokens,
            cached_tokens=u.input_tokens_details.cached_tokens or 0,
            cache_write_tokens=getattr(u.input_tokens_details, "cache_write_tokens", 0) or 0,
            output_tokens=u.output_tokens,
            search_calls=sum(1 for item in response.output if item.type == "web_search_call"),
        )
        cost = budget.actual_usd(model, flex=tier_used == "flex", **counts)
        budget.settle(
            self.conn,
            usage_id,
            status="completed",
            cost_usd=cost,
            service_tier=tier_used,
            reasoning_tokens=u.output_tokens_details.reasoning_tokens or 0,
            response_id=response.id,
            **counts,
        )
        if getattr(response, "status", "completed") == "completed":
            self.conn.execute(
                "INSERT INTO llm_cache (key, job, model, output_text, llm_usage_id) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET job = excluded.job, model = excluded.model, output_text = excluded.output_text, "
                "llm_usage_id = excluded.llm_usage_id",
                (key, job, model, response.output_text, usage_id),
            )
        return LLMResult(
            text=response.output_text,
            parsed=getattr(response, "output_parsed", None),
            usage_id=usage_id,
            cost_usd=cost,
            response=response,
        )

    def embed(self, texts: list[str], *, job: str, demo: bool = False) -> list[list[float]]:
        agent = agents.match(job)
        model = (app_settings.agent_config(agent.key).model if agent else None) or app_settings.tier_model("embed")
        reserved = budget.worst_case_usd(model, sum(budget.estimate_tokens(t) for t in texts))
        usage_id = budget.reserve(self.conn, job=job, kind="embeddings", model=model, reserved_usd=reserved, demo=demo)
        try:
            response = self.client.embeddings.create(model=model, input=texts)
        except Exception as e:
            budget.settle(self.conn, usage_id, status="failed", cost_usd=0.0, error=repr(e)[:2000])
            raise
        tokens = response.usage.prompt_tokens
        cost = budget.actual_usd(model, input_tokens=tokens)
        budget.settle(self.conn, usage_id, status="completed", cost_usd=cost, input_tokens=tokens)
        return [d.embedding for d in response.data]


def _cache_key(model, instructions, input, schema, reasoning_effort, tools, max_tool_calls, max_output_tokens, extra) -> str:
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input,
        "schema": schema.model_json_schema() if schema is not None else None,
        "reasoning_effort": reasoning_effort,
        "tools": tools,
        "max_tool_calls": max_tool_calls,
        "max_output_tokens": max_output_tokens,
        "extra": extra,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

