"""Verbatim signal extraction (luna, structured output). v2 = Q-018 fixes after the D-014 pilot;
v3 = one consistent scope rule for mixed verbatims and support-call questions (Q-020, D-024)."""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.llm import LLM

EXTRACTOR_VERSION = "extract-v3"

Category = Literal[
    "Exterior", "Interior", "Comfort & Space", "Infotainment & Digital", "Driving Experience",
    "Powertrain (as experienced)", "Range & Charging", "Driver Assistance (as experienced)",
    "Variants & Packages", "Design & Quality Perception",
]


class Signal(BaseModel):
    category: Category
    topic: str = Field(description="Short component/topic, e.g. 'Touch screen', 'Rear seat legroom'")
    feedback_type: Literal["like", "defect", "difficult_to_use", "complaint", "want"]
    severity: Literal["low", "medium", "high"]
    need_statement: str = Field(description="The underlying customer need, solution-neutral, one sentence")
    quote: str = Field(description="Exact substring of the verbatim that supports this signal")
    support_question: bool = Field(
        description="True if the signal only shows the customer needed help or asked how a function works"
    )


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

Scope: customer-facing topics only. Out of scope: dealer/service/sales experience, pricing, financing,
regulatory/homologation, engineering/component specifications. Many verbatims mix out-of-scope content
(dealer, service, recall handling, charging network) with a real product signal: extract every in-scope
signal even if most of the verbatim is out of scope. If a verbatim has only out-of-scope content or no usable
content (e.g. generic praise without a topic, unspecified "some issues"), set in_scope=false, give
out_of_scope_reason and return no signals.

Support questions: when the customer asked how a vehicle function works, or needed help to set it up
(e.g. "Customer asked which regen setting to use"), extract a difficult_to_use signal with severity low
and support_question=true. It is weak usability evidence. For every other signal support_question=false.

feedback_type:
- like: praise.
- defect: something is broken, faulty or behaves wrongly (e.g. a connection drops, a part opens by itself, a warning without cause).
- difficult_to_use: it works as designed but is hard to understand or operate.
- complaint: it works as designed but the customer is dissatisfied with how good it is (e.g. seats less comfortable than expected, cabin cools too slowly, too noisy).
- want: request for something the vehicle does not have.

category (where the customer experiences it):
- Exterior: body, doors, trunk/tailgate and their opening/closing, lights, wheels, paint, mirrors, exterior styling.
- Interior: cabin materials, storage, cupholders, interior lighting, controls' physical layout.
- Comfort & Space: seats, roominess, climate/HVAC, noise and vibration in the cabin, ride comfort.
- Infotainment & Digital: screens, menus, voice, navigation, phone integration (CarPlay/Android Auto/Bluetooth), app, connected services, audio.
- Driving Experience: handling, steering, acceleration feel, braking feel, driving modes.
- Powertrain (as experienced): engine/motor sound, smoothness, gearbox, fuel consumption, powertrain faults and warnings.
- Range & Charging: electric range, charging speed, charging port and cable, charging planning.
- Driver Assistance (as experienced): parking aids, cameras, cruise control, lane keeping, cross-traffic and other warnings.
- Variants & Packages: availability of equipment, trims, packages, body styles, powertrain choices.
- Design & Quality Perception: overall look, perceived quality, fit and finish, squeaks/rattles, material wear.

severity: how much it affects the ownership experience (high = safety-relevant or makes a function unusable).
need_statement: the underlying need in customer terms, not a technical solution.
quote: copy a contiguous span of the verbatim character for character. Do not add, drop or change any word.
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
        # Prompt prefix is below the 1,024-token cache minimum and inputs never repeat: don't pay for cache writes (Q-018).
        prompt_cache_options={"mode": "explicit"},
    )
    return res.parsed, res


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_ok(quote: str, text: str) -> bool:
    """Quote is a contiguous span of the text (whitespace and case normalized)."""
    return bool(quote.strip()) and _norm(quote) in _norm(text)


def check_batch(verbatims: list[dict], batch: BatchResult) -> dict:
    """Deterministic quality checks: coverage, invented IDs, quotes that are not exact spans."""
    by_id = {v["id"]: v for v in verbatims}
    returned = [r.verbatim_id for r in batch.results]
    bad_quotes = [
        (r.verbatim_id, s.quote)
        for r in batch.results if r.verbatim_id in by_id
        for s in r.signals if not quote_ok(s.quote, by_id[r.verbatim_id]["text"])
    ]
    return {
        "missing_ids": sorted(set(by_id) - set(returned)),
        "invented_ids": sorted(set(returned) - set(by_id)),
        "duplicate_ids": sorted({i for i in returned if returned.count(i) > 1}),
        "signals": sum(len(r.signals) for r in batch.results),
        "out_of_scope": sum(not r.in_scope for r in batch.results),
        "bad_quotes": bad_quotes,
    }
