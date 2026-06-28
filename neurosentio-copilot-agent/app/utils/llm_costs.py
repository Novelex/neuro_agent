"""
LLM cost estimation utility (Day 9).

Provides approximate cost per call based on provider, model, and token counts.
Prices are approximate and subject to change — treat as estimates only.
Do NOT present these as exact billing figures.

To customise pricing, override the PRICING_TABLE or set up a config-driven approach.
"""

from typing import Optional

# Approximate pricing in USD per 1M tokens (input / output)
# Source: provider public pricing pages as of 2025-06.
# These are estimates — always verify against the provider's current pricing.
PRICING_TABLE: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {
        "claude-3-5-sonnet-latest":  (3.00, 15.00),   # per 1M tokens: input, output
        "claude-3-haiku-20240307":   (0.25,  1.25),
        "claude-3-opus-20240229":    (15.00, 75.00),
    },
    "openai": {
        "gpt-4o":                    (5.00,  15.00),
        "gpt-4o-mini":               (0.15,   0.60),
        "gpt-4-turbo":               (10.00, 30.00),
    },
    "mock": {
        # Mock is free — no real tokens, no real cost
        "_default": (0.0, 0.0),
    },
}


def estimate_llm_cost(
    provider: str,
    model: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> Optional[float]:
    """
    Estimate approximate cost in USD for an LLM call.

    Returns:
        0.0 for mock provider (no real cost)
        float estimate for known provider/model combination
        None if tokens are missing or provider/model is unknown
    """
    provider_lower = (provider or "").lower()

    # Mock is always free
    if provider_lower == "mock":
        return 0.0

    # Cannot estimate without token counts
    if input_tokens is None or output_tokens is None:
        return None

    provider_pricing = PRICING_TABLE.get(provider_lower)
    if not provider_pricing:
        return None

    model_key = (model or "").lower()
    if model_key not in provider_pricing:
        # Try to find a partial match
        for k in provider_pricing:
            if k in model_key or model_key in k:
                model_key = k
                break
        else:
            return None

    input_price_per_m, output_price_per_m = provider_pricing[model_key]
    cost = (input_tokens / 1_000_000) * input_price_per_m + \
           (output_tokens / 1_000_000) * output_price_per_m

    return round(cost, 8)
