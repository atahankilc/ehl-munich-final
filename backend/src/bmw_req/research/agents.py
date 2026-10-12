"""Web research agents (knowledge-base.md): competitor scout, review miner, trend & expectation scout,
market profile scout, market & sales analyst. Each call = OpenAI Responses API with web_search + structured
output via the budget-guarded `LLM` wrapper (D-014, D-020). No BMW raw data is ever put into a prompt.

Anti-hallucination: an item is kept only if its URL appears among the response's url_citation annotations
or web_search_call sources; quotes are then checked against the fetched page (quote_verified 1/0/None).
"""

import html
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx
from pydantic import BaseModel, Field

from bmw_req.llm import LLM
from bmw_req.structure.taxonomy import Category

AGENT_VERSION = "research-v1"
MAX_TOOL_CALLS = 4

EvidenceType = Literal[
    "competitor_feature", "competitor_sales", "market_trend", "customer_expectation",
    "review_criticism", "review_praise", "market_profile",
]


class EvidenceItem(BaseModel):
    claim: str = Field(description="One factual sentence about a customer-facing topic, supported by the quote")
    quote: str = Field(description="Verbatim sentence(s) copied exactly from the cited page (max ~300 chars)")
    url: str = Field(description="URL of the page the quote is from; must be one of the pages you found via web search")
    publisher: str = Field(description="Publication or organisation, e.g. 'Car and Driver', 'Reuters', 'Mercedes-Benz'")
    published_date: str | None = Field(description="Publish date as YYYY-MM-DD or YYYY-MM if shown, else null")
    market_code: Literal["EU", "US", "CN", "RoW", "global"] = Field(description="Market the fact is about")
    vehicle_models: list[str] = Field(description="Vehicle models mentioned, e.g. ['BMW 5 Series', 'Mercedes E-Class']")
    competitor: str | None = Field(description="Competitor brand+model if the item is about a competitor, else null")
    evidence_type: EvidenceType
    category: Category | None = Field(description="Customer-facing category, or null for pure market/sales context")
    trust_tier: Literal["T1", "T2", "T3"] = Field(
        description="T1: OEM press/annual reports/official registration statistics (KBA, ACEA, CPCA); "
                    "T2: reputable press, analysts, professional reviews (Reuters, J.D. Power, McKinsey, Car and Driver, Autocar); "
                    "T3: forums, blogs, aggregators")


class AgentOutput(BaseModel):
    items: list[EvidenceItem]


@dataclass
class Task:
    id: str
    agent: str                     # competitor_scout | review_miner | trend_scout | market_profile_scout | market_analyst
    line: str | None               # e.g. '5 Series'
    vehicle_model_id: str | None   # e.g. 'G60'; None for market-level tasks
    market_code: str
    focus: str
    wave: int = 1
    max_items: int = 6
    context: dict = field(default_factory=dict)


SCOPE_RULES = """Scope: customer-facing topics only — features, equipment, comfort, space, usability, infotainment/digital,
design & quality perception, driving experience, range/charging as experienced, driver assistance as experienced,
variants/packages; sales/market/powertrain-mix facts are allowed as context (evidence_type competitor_sales,
market_trend, market_profile, category null). Never report prices, business cases, regulation/homologation or
engineering specs as customer needs."""

RULES = f"""You are a research agent for a BMW product-requirements team. Use web search to find recent, citable facts.
{SCOPE_RULES}
Rules:
- Every item must come from a page you actually opened via web search; put that exact page URL in `url`.
- `quote` must be copied verbatim from that page (no paraphrase, no ellipsis joins; original language is fine).
- `claim` is one plain English sentence restating only what the quote says — no hedging, commentary, or facts from other pages.
- Prefer sources from 2025-2026; prefer T1/T2 over T3. Never cite Wikipedia or your own knowledge.
- No opinions or recommendations of your own. If the search finds nothing solid, return fewer items (even zero).
- Set market_code to the market the fact is about ('global' if not market-specific)."""

AGENT_BRIEFS = {
    "competitor_scout": "Competitor scout: what competitors offer customers (features, equipment, digital, ADAS, charging, rear-seat comfort) that BMW does not, or does better than BMW, in 2025-2026. Use evidence_type competitor_feature (or competitor_sales for volume context).",
    "review_miner": "Review miner: what professional reviewers (and, if clearly marked, owners) praise or criticise about the named model(s) on customer-facing topics. Use evidence_type review_praise or review_criticism; set competitor for non-BMW models.",
    "trend_scout": "Trend & expectation scout: what premium car buyers in this market will expect by 2029-2031 (software/AI assistant, ADAS experience, charging/range, interior and rear seat, physical controls, personalisation). Prefer surveys and studies (J.D. Power, McKinsey, Deloitte, S&P). Use evidence_type customer_expectation or market_trend.",
    "market_profile_scout": "Market profile scout: climate, real usage (mileage, commuting, chauffeur use, body styles), culture and infrastructure (charging) and powertrain mix of this market, as relevant to premium car buyers. Use evidence_type market_profile.",
    "market_analyst": "Market & sales analyst: volumes and growth by brand/model/powertrain in this segment and market (2025-2026), and which models are in demand. Use evidence_type competitor_sales or market_trend; category null.",
}

MARKET_NAMES = {"EU": "Europe", "US": "the United States", "CN": "China", "RoW": "markets outside EU/US/China (here: Japan, South Korea, UK-adjacent export markets)"}


def build_prompt(task: Task) -> str:
    lines = [AGENT_BRIEFS[task.agent], f"Market: {MARKET_NAMES.get(task.market_code, task.market_code)} ({task.market_code})."]
    if task.line:
        lines.append(f"BMW vehicle line: BMW {task.line} ({task.vehicle_model_id}).")
    for k, v in task.context.items():
        lines.append(f"{k}: {v}")
    lines.append(f"Focus: {task.focus}")
    lines.append(f"Return at most {task.max_items} items. Today is 2026-10-10.")
    return "\n".join(lines)


# --- URL handling ------------------------------------------------------------------------------------------

def norm_url(url: str) -> str:
    """Canonical form for matching: no scheme, no www, no tracking params, no fragment, no trailing slash."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = p.netloc.lower().removeprefix("www.")
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = p.path.rstrip("/")
    return host + path + ("?" + urlencode(q) if q else "")


def clean_url(url: str) -> str:
    """Strip tracking params (e.g. utm_source=openai) but keep the URL usable."""
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return p._replace(query=urlencode(q), fragment="").geturl()


def cited_urls(response) -> dict[str, str]:
    """{normalized url: url} from url_citation annotations and web_search_call sources of a Responses API result."""
    out = {}
    for item in getattr(response, "output", None) or []:
        t = getattr(item, "type", None)
        if t == "message":
            for c in getattr(item, "content", None) or []:
                for a in getattr(c, "annotations", None) or []:
                    if getattr(a, "type", None) == "url_citation" and getattr(a, "url", None):
                        out[norm_url(a.url)] = a.url
        elif t == "web_search_call":
            action = getattr(item, "action", None)
            for s in getattr(action, "sources", None) or []:
                u = getattr(s, "url", None) or (s.get("url") if isinstance(s, dict) else None)
                if u:
                    out[norm_url(u)] = u
    return out


def search_queries(response) -> list[str]:
    qs = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) == "web_search_call":
            action = getattr(item, "action", None)
            q = getattr(action, "query", None)
            if q:
                qs.append(q)
    return qs


def filter_cited(items: list[EvidenceItem], cited: dict[str, str]) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    """Split items into (kept, dropped) by whether their URL was actually returned by web search."""
    kept, dropped = [], []
    for it in items:
        (kept if norm_url(it.url) in cited else dropped).append(it)
    return kept, dropped


# --- Quote verification ---------------------------------------------------------------------------------------

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def norm_text(s: str) -> str:
    s = html.unescape(s).translate(_QUOTES).lower()
    s = re.sub(r"[^\w%$€£¥.,'\"-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def page_text(raw_html: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return norm_text(s)


def quote_in_text(quote: str, text: str) -> bool:
    q = norm_text(quote).strip(" .\"'")
    if not q:
        return False
    if q in text:
        return True
    squashed = text.replace(" ", "")
    if q.replace(" ", "") in squashed:   # CJK text / spacing differences around tags
        return True
    parts = [norm_text(p).strip(" .\"'") for p in re.split(r"\.\.\.|…|\n", quote)]
    parts = [p for p in parts if len(p) >= 4]
    return len(parts) > 1 and all(p.replace(" ", "") in squashed for p in parts)


def verify_quote(url: str, quote: str, *, client: httpx.Client | None = None, timeout: float = 8.0) -> int | None:
    """1 = quote found on the page, 0 = page fetched but quote not found, None = page not fetchable/parseable."""
    own = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=timeout,
                                    headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    try:
        r = client.get(url)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return None
        text = page_text(r.text)
        if len(text) < 500:   # JS shell / bot wall
            return None
        return 1 if quote_in_text(quote, text) else 0
    except (httpx.HTTPError, UnicodeDecodeError, ValueError):
        return None
    finally:
        if own:
            client.close()


# --- Agent entry points -------------------------------------------------------------------------------------

@dataclass
class AgentResult:
    task: Task
    kept: list[EvidenceItem]
    dropped: list[EvidenceItem]
    cited: dict[str, str]
    queries: list[str]
    usage_id: int | None
    cost_usd: float
    model: str


def run_agent(llm: LLM, task: Task, *, job: str = "research") -> AgentResult:
    res = llm.generate(
        job=f"{job}:{task.agent}",
        tier="fast",
        instructions=RULES,
        input=build_prompt(task),
        schema=AgentOutput,
        reasoning_effort="low",
        tools=[{"type": "web_search"}],
        max_tool_calls=MAX_TOOL_CALLS,
        max_output_tokens=6000,
        include=["web_search_call.action.sources"],
        use_cache=False,   # citations are not cached; task-level idempotency lives in run.py
    )
    parsed: AgentOutput = res.parsed or AgentOutput(items=[])
    cited = cited_urls(res.response)
    kept, dropped = filter_cited(parsed.items, cited)
    return AgentResult(task, kept, dropped, cited, search_queries(res.response), res.usage_id, res.cost_usd,
                       llm.model_for("fast"))


def competitor_scout(llm: LLM, task: Task) -> AgentResult:
    return run_agent(llm, task)


def review_miner(llm: LLM, task: Task) -> AgentResult:
    return run_agent(llm, task)


def trend_scout(llm: LLM, task: Task) -> AgentResult:
    return run_agent(llm, task)


def market_profile_scout(llm: LLM, task: Task) -> AgentResult:
    return run_agent(llm, task)


def market_analyst(llm: LLM, task: Task) -> AgentResult:
    return run_agent(llm, task)


AGENTS = {
    "competitor_scout": competitor_scout,
    "review_miner": review_miner,
    "trend_scout": trend_scout,
    "market_profile_scout": market_profile_scout,
    "market_analyst": market_analyst,
}
