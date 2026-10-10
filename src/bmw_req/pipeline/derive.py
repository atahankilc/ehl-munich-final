"""Requirement derivation from extracted signals (sol). Pilot version."""

import json
from typing import Literal

from pydantic import BaseModel, Field

from bmw_req.llm import LLM
from bmw_req.pipeline.extract import Category


class RequirementDraft(BaseModel):
    title: str
    description: str = Field(description="Customer-facing, solution-neutral where possible")
    category: Category
    target_metric: str
    acceptance_criteria: str
    horizon: Literal["today", "at_successor_launch"]
    horizon_reason: str
    kano_class: Literal["basic", "performance", "delighter"]
    kano_drift: str = Field(description="Expected Kano class at successor launch and why, or 'stable'")
    evidence_verbatim_ids: list[str] = Field(description="IDs of the verbatims that support this requirement")
    conflicting_verbatim_ids: list[str]
    assumptions: str
    uncertainties: str


class DerivationResult(BaseModel):
    requirements: list[RequirementDraft]


INSTRUCTIONS = """You are a product requirements analyst for the successor of a BMW vehicle (launch in 3-5 years).
Input: customer signals extracted from verbatims (with verbatim IDs), for one derivative and market.
Derive exactly {n} customer requirements, the most important ones the evidence supports.
Rules:
- Every requirement must cite the verbatim IDs that support it; use only IDs from the input. Cite contradicting ones too.
- Customer-facing requirements only: no engineering/component specs, no pricing, no regulatory items.
- Must fit a premium BMW in this segment.
- Separate evidence from assumption: put forward-looking beliefs in `assumptions`, and what could make them wrong in `uncertainties`.
- target_metric / acceptance_criteria: measurable from the customer's point of view, with a concrete proposed
  target value (e.g. "≥ 95 % automatic reconnects"). Mark every target value as a proposal in `assumptions`.
- horizon: `today` = a current shortcoming to fix or strength to keep, needed regardless of trends.
  `at_successor_launch` = only when you expect the need itself to grow or change by launch in 3-5 years;
  say why in horizon_reason. Do not default to either one.
- kano_class: `basic` = customers take it for granted and are dissatisfied only by its absence or failure
  (reliability, things that must simply work); `performance` = more is better, satisfaction scales with it
  (range, comfort, speed of response); `delighter` = unexpected, absence goes unnoticed. Classify by how
  customers react today; put the expected change by launch in kano_drift.
- Do not invent customer statements; the evidence base is small, say so in uncertainties where relevant."""


def derive(llm: LLM, context: dict, signals: list[dict], *, n: int, job: str, demo: bool = False):
    res = llm.generate(
        job=job,
        tier="smart",
        instructions=INSTRUCTIONS.format(n=n),
        input=json.dumps({"context": context, "signals": signals}, ensure_ascii=False),
        schema=DerivationResult,
        reasoning_effort="medium",
        max_output_tokens=16_000,
        flex=True,
        demo=demo,
    )
    return res.parsed, res


def check_derivation(result: DerivationResult, known_ids: set[str]) -> dict:
    cited = [i for r in result.requirements for i in r.evidence_verbatim_ids + r.conflicting_verbatim_ids]
    return {
        "requirements": len(result.requirements),
        "unknown_cited_ids": sorted(set(cited) - known_ids),
        "requirements_without_evidence": [r.title for r in result.requirements if not r.evidence_verbatim_ids],
    }
