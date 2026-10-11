"""OpenAI list prices in USD per 1M tokens (D-014, checked 2026-10-10 on
developers.openai.com/api/docs/pricing). Models added in the app (D-055) carry their own prices; a model missing from
both is refused by the guard."""

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

EMBEDDING_MODELS = {"text-embedding-3-small"}


def all_prices() -> dict[str, Price]:
    """Built-in prices plus models added in the app (built-in wins on a clash)."""
    from bmw_req import app_settings

    extra = {m: Price(float(s["input"]), float(s["cached_input"]), float(s["output"]))
             for m, s in app_settings.custom_models().items()}
    return {**extra, **PRICES}


def kind_of(model: str) -> str | None:
    """'responses' / 'embeddings' for a priced model, None if it has no price."""
    if model in PRICES:
        return "embeddings" if model in EMBEDDING_MODELS else "responses"
    from bmw_req import app_settings

    spec = app_settings.custom_models().get(model)
    return spec.get("kind") if spec else None


FLEX_FACTOR = 0.5            # Flex = Batch = -50%
CACHE_WRITE_FACTOR = 1.25    # cache writes cost 1.25x input
WEB_SEARCH_PER_CALL = 10.0 / 1000
# D-014 web-research assumption: ~20k content tokens per billed search call (input rate).
WEB_SEARCH_CONTENT_TOKENS = 20_000
