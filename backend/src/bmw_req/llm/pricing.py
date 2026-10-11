"""OpenAI list prices in USD per 1M tokens (D-014, checked 2026-10-10 on
developers.openai.com/api/docs/pricing). A model missing here is refused by the guard."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    cached_input: float
    output: float


PRICES: dict[str, Price] = {
    "gpt-6-luna": Price(input=0.10, cached_input=0.01, output=0.50),
    "gpt-6.1-sol": Price(input=2.00, cached_input=0.10, output=10.00),
    "text-embedding-3-small": Price(input=0.02, cached_input=0.02, output=0.0),
}

FLEX_FACTOR = 0.5            # Flex = Batch = -50%
CACHE_WRITE_FACTOR = 1.25    # cache writes cost 1.25x input
WEB_SEARCH_PER_CALL = 10.0 / 1000
# D-014 web-research assumption: ~20k content tokens per billed search call (input rate).
WEB_SEARCH_CONTENT_TOKENS = 20_000
