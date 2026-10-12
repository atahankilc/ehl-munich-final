"""The fit check shared by the prioritization gate (D-008, D-030, D-050), carried over unchanged from the score-v3 fit
check (`fit-v1`) when the wave pipeline was retired (D-057): the instructions, the second-opinion text and the luna → sol
re-check. Prompt texts are kept byte-identical so cached answers stay valid."""

import json
from typing import Literal

from pydantic import BaseModel

from bmw_req.llm import LLM

Result = Literal["pass", "warn", "fail"]


INSTRUCTIONS = """You check whether a proposed customer requirement for a BMW successor vehicle fits.
Return pass / warn / fail with a short, specific rationale for:
- brand: BMW brand fit, judged ONLY against the given brand guardrails (pass/warn/fail lists). fail only if it
  clearly contradicts a fail guardrail (e.g. paywalling hardware already in the car, touch-only core driving
  controls, soft numb chassis as default). Comfort-only features without driving-pleasure link are at most warn.
- segment: fit with the vehicle line's segment and its customers (no budget features in luxury, no luxury
  gadgets that break the compact segment's positioning).
- per target market: does the market profile (climate, usage, culture, infrastructure, powertrain mix) support
  the need? warn if the need is weaker or different there, fail if it contradicts the market.
- per target feasibility (context only): given the platform, its successor (Neue Klasse timing) and plants
  serving that market, is realization plausible by successor launch? Use only the given reference data; when
  data is missing say so and use warn. Never output component specifications.
Be strict but fair; most solid requirements pass."""

RECHECK = """\n\nSECOND OPINION: a first reviewer returned the verdicts in `first_pass`. Re-examine every warn/fail
carefully and return your own final verdicts for all checks (you may confirm, soften or harden them)."""


def luna_then_sol(llm: LLM, *, job: str, instructions: str, ctx: dict, schema: type[BaseModel], flagged,
                  generate=None, sol_effort: str = "medium") -> tuple[BaseModel, list]:
    """luna checks; if `flagged(result)` (any warn/fail that matters) sol re-checks with the first pass in view and its
    verdict is final (D-010). `generate` may wrap `llm.generate` (e.g. waiting for Flex capacity)."""
    gen = generate or (lambda **kw: llm.generate(**kw))
    usage = []
    first = gen(job=f"{job}:luna", tier="fast", instructions=instructions, input=json.dumps(ctx, ensure_ascii=False, default=str),
                schema=schema, reasoning_effort="low", max_output_tokens=6000, flex=True)
    usage.append((first.usage_id, llm.model_for("fast")))
    res = first.parsed
    if flagged(res):
        second = gen(job=f"{job}:sol", tier="smart", instructions=instructions + RECHECK,
                     input=json.dumps({**ctx, "first_pass": res.model_dump()}, ensure_ascii=False, default=str),
                     schema=schema, reasoning_effort=sol_effort, max_output_tokens=8000, flex=True)
        usage.append((second.usage_id, llm.model_for("smart")))
        res = second.parsed
    return res, usage
