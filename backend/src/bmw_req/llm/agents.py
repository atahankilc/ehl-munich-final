"""The AI agents of the checkpoint pipeline (D-055): one entry per kind of model call, matched by its `llm_usage.job` name.

This is the catalogue the "AI agents" page configures. Each agent keeps the defaults its code passes (tier → model,
reasoning effort); the user's overrides live in `app_settings` ("agents") and `LLM.generate()` / `.embed()` apply them on
every call: model, reasoning effort, on/off, and a spend cap (total committed spend of the agent, enforced by the guard).

Jobs of the earlier wave pipeline (D-022 – D-038) match no agent: they stay in the usage log as history and are not
configurable. Order matters — the first pattern that matches a job wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["responses", "embeddings"]
Tier = Literal["fast", "smart", "embed"]


@dataclass(frozen=True)
class Agent:
    key: str
    name: str
    pipeline: str
    description: str
    pattern: str
    kind: Kind = "responses"
    tier: Tier = "fast"
    effort: str | None = "low"   # the reasoning effort its code passes (None for embeddings)
    web_search: bool = False


PIPELINES = [
    ("sources", "Sources", "Web research and price lists: what goes into the evidence."),
    ("structure", "Structure & context", "Comments → signals → clusters → themes → requirement areas (D-043)."),
    ("definition", "Requirement definition", "Areas → requirements with metrics, target ladders and links (D-048)."),
    ("prioritize", "Prioritization", "The fit gate before the deterministic score (D-050)."),
]

AGENTS: list[Agent] = [
    # sources
    Agent("research_web", "Web research agents", "sources",
          "Search the web for competitor, trend, review and market facts; every item cited with URL and quote.",
          r"^research:(?!findings\b|benchmarks\b)", web_search=True),
    Agent("research_findings", "Research summarizer", "sources",
          "Turns cited web items into findings per car line and market.", r"^research:findings\b"),
    Agent("options_reader", "Price-list reader", "sources",
          "Reads BMW's option price lists (PDF pages) into structured options.", r"^ingest:options\b"),
    # structure & context
    Agent("classify", "Comment classifier", "structure",
          "Every customer comment → signals in the shared aspect space (extract-v4).", r"^classify:extract"),
    Agent("context_mapper", "Context mapper", "structure",
          "Maps study items, options and research onto the same aspects as the comments.",
          r"^classify:(study-aspects|option-aspects|research)\b"),
    Agent("standardize", "Insight writer", "structure",
          "Writes one standardized insight per cluster of signals.", r"^contextualize:standardize\b"),
    Agent("duplicates", "Duplicate checker", "structure",
          "Merges insights that say the same thing.", r"^contextualize:duplicates\b"),
    Agent("themes", "Theme namer", "structure", "Names and describes the themes insights group into.",
          r"^contextualize:themes\b"),
    Agent("evidence_linker", "Evidence linker", "structure",
          "Links themes to study, option and research evidence (supports / contradicts / context).",
          r"^contextualize:link\b"),
    Agent("areas", "Area builder", "structure", "Groups themes into potential requirement areas.", r"^areas\b",
          tier="smart", effort="medium"),
    Agent("elicit", "Requirement drafter (areas)", "structure", "Drafts requirements straight from areas (not run yet).",
          r"^elicit\b", tier="smart", effort="medium"),
    Agent("embed_signals", "Signal embeddings", "structure", "Vectors for clustering the signals.",
          r"^embed:signals:v4\b", kind="embeddings", tier="embed", effort=None),
    Agent("embed_context", "Context embeddings", "structure", "Vectors for insights, themes and evidence nodes (RAG).",
          r"^embed:(nodes|insights|themes)\b", kind="embeddings", tier="embed", effort=None),
    Agent("embed_galaxy", "Comment-map embeddings", "structure", "Vectors that lay out the comments in the 3D view.",
          r"^embed:comments:galaxy\b", kind="embeddings", tier="embed", effort=None),
    # requirement definition
    Agent("benchmark_reader", "Benchmark reader", "definition",
          "Pulls cited spec facts (ranges, charge times, screen sizes …) out of research items.", r"^structure\.benchmarks\b"),
    Agent("benchmark_research", "Benchmark researcher", "definition",
          "Searches the web for missing competitor benchmarks.", r"^research:benchmarks\b", web_search=True),
    Agent("define", "Requirement writer", "definition", "Turns requirement areas into requirements.", r"^define\b",
          tier="smart", effort="medium"),
    Agent("specify", "Target setter", "definition",
          "Gives each requirement a customer metric and a baseline / threshold / target / stretch ladder.", r"^specify\b",
          tier="smart", effort="medium"),
    Agent("couple_recheck", "Link reviewer", "definition", "Re-checks the requirement links the first pass flagged.",
          r"^couple:.*:recheck\b", tier="smart"),
    Agent("couple", "Link finder", "definition", "Finds links between requirements (enables / conflicts / shares).",
          r"^couple\b"),
    # prioritization
    Agent("gate_first", "Fit gate, first pass", "prioritize",
          "Checks brand, segment and market fit of every requirement.", r"^gate:luna\b"),
    Agent("gate_recheck", "Fit gate, re-check", "prioritize",
          "Re-checks the requirements the first pass flagged; its verdict is final.", r"^gate:sol\b", tier="smart"),
]
BY_KEY = {a.key: a for a in AGENTS}
EFFORTS = ("low", "medium", "high")
_COMPILED = [(re.compile(a.pattern), a) for a in AGENTS]


def match(job: str) -> Agent | None:
    """The agent behind a usage-log job name, or None for the earlier wave pipeline."""
    return next((a for rx, a in _COMPILED if rx.search(job)), None)
