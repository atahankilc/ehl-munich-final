"""Verbatim signal extraction (luna, structured output). Pilot version — schema may change after D-014 pilot."""

import json
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.llm import LLM

Category = Literal[
    "Exterior", "Interior", "Comfort & Space", "Infotainment & Digital", "Driving Experience",
    "Powertrain (as experienced)", "Range & Charging", "Driver Assistance (as experienced)",
    "Variants & Packages", "Design & Quality Perception",
]


class Signal(BaseModel):
    category: Category
    topic: str = Field(description="Short component/topic, e.g. 'Touch screen', 'Rear seat legroom'")
    feedback_type: Literal["like", "defect", "difficult_to_use", "want"]
    severity: Literal["low", "medium", "high"]
    need_statement: str = Field(description="The underlying customer need, solution-neutral, one sentence")
    quote: str = Field(description="Exact substring of the verbatim that supports this signal")


class VerbatimResult(BaseModel):
    verbatim_id: str
    in_scope: bool = Field(description="False if the verbatim only concerns out-of-scope topics or has no usable content")
    out_of_scope_reason: str | None
    signals: list[Signal]


class BatchResult(BaseModel):
    results: list[VerbatimResult]


INSTRUCTIONS = """You analyse customer feedback verbatims about a BMW vehicle for product requirements work.
For EVERY verbatim in the input return exactly one result with its verbatim_id.

Extract each distinct customer signal (a verbatim can contain several, or none).
- Scope: customer-facing topics only (features, equipment, comfort, space, usability, infotainment/digital,
  design & quality perception, driving experience, powertrain and range/charging as experienced,
  driver assistance as experienced, variants/packages).
- Out of scope: dealer/service/sales experience, pricing, financing, regulatory/homologation,
  engineering/component specifications. If a verbatim has only out-of-scope content, set in_scope=false,
  give out_of_scope_reason and return no signals.
- feedback_type: like = praise; defect = something broken/faulty; difficult_to_use = works but hard to use;
  want = request for something missing.
- severity: how much it affects the ownership experience (high = safety-relevant or makes a function unusable).
- need_statement: the underlying need in customer terms, not a technical solution.
- quote: copy an exact substring of the verbatim text, do not paraphrase.
Do not invent facts that are not in the verbatim."""


def extract_batch(llm: LLM, verbatims: list[dict], *, job: str, flex: bool = True, demo: bool = False):
    """verbatims: [{'id', 'text', 'engine', ...}] → (BatchResult, LLMResult)."""
    payload = [{"verbatim_id": v["id"], "engine": v.get("engine"), "text": v["text"]} for v in verbatims]
    res = llm.generate(
        job=job,
        tier="fast",
        instructions=INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False),
        schema=BatchResult,
        reasoning_effort="low",
        max_output_tokens=12_000,
        flex=flex,
        demo=demo,
    )
    return res.parsed, res


def check_batch(verbatims: list[dict], batch: BatchResult) -> dict:
    """Deterministic quality checks: coverage, invented IDs, quotes that are not exact substrings."""
    by_id = {v["id"]: v for v in verbatims}
    returned = [r.verbatim_id for r in batch.results]
    bad_quotes = [
        (r.verbatim_id, s.quote)
        for r in batch.results if r.verbatim_id in by_id
        for s in r.signals if s.quote not in by_id[r.verbatim_id]["text"]
    ]
    return {
        "missing_ids": sorted(set(by_id) - set(returned)),
        "invented_ids": sorted(set(returned) - set(by_id)),
        "duplicate_ids": sorted({i for i in returned if returned.count(i) > 1}),
        "signals": sum(len(r.signals) for r in batch.results),
        "out_of_scope": sum(not r.in_scope for r in batch.results),
        "bad_quotes": bad_quotes,
    }
