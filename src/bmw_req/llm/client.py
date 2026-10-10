"""The only path to OpenAI (D-014, D-015, D-020). Every call is reserved, logged and settled."""

import json
from dataclasses import dataclass
from typing import Any, Literal

import openai
from pydantic import BaseModel

from bmw_req.config import get_settings
from bmw_req.db import connect
from bmw_req.llm import budget

Tier = Literal["fast", "smart"]
FLEX_TIMEOUT_S = 900.0


@dataclass
class LLMResult:
    text: str
    parsed: Any
    usage_id: int
    cost_usd: float
    response: Any


class LLM:
    def __init__(self, conn=None, client=None):
        self.settings = get_settings()
        self.conn = conn if conn is not None else connect()
        self.client = client if client is not None else openai.OpenAI(api_key=self.settings.openai_api_key)

    def model_for(self, tier: Tier) -> str:
        return {"fast": self.settings.model_fast, "smart": self.settings.model_smart}[tier]

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
        **kwargs,
    ) -> LLMResult:
        """Call the Responses API. `schema` → structured output parsed into that Pydantic model."""
        if not max_output_tokens or max_output_tokens <= 0:
            raise ValueError("max_output_tokens is required on every call (D-014)")
        if tools and not max_tool_calls:
            raise ValueError("Calls with tools need max_tool_calls (D-014 web-search cap)")
        model = self.model_for(tier)
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
        return LLMResult(
            text=response.output_text,
            parsed=getattr(response, "output_parsed", None),
            usage_id=usage_id,
            cost_usd=cost,
            response=response,
        )

    def embed(self, texts: list[str], *, job: str, demo: bool = False) -> list[list[float]]:
        model = self.settings.model_embed
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
