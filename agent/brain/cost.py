"""Per-model USD pricing table for DGrid cost estimation.

Rates are USD per 1M tokens, prompt/completion split. Prices track DGrid's public
pricing for each underlying model provider. When an unknown model is billed we fall
back to ``UNKNOWN_PRICE`` so totals never silently miss — worst case we report a
reasonable-sized estimate that flags the model as untracked.

Updating: when a new model rotates into ``TASK_MODEL_MAP`` (see llm.py), add its rate
here. Rates source: https://dgrid.ai/pricing (and the upstream provider pricing page
for pass-through models).
"""

# (prompt_usd_per_mtok, completion_usd_per_mtok)
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # DGrid-prefixed identifiers (what we send over the wire)
    "google/gemini-2.5-flash":      (0.075, 0.30),
    "google/gemini-2.0-flash-lite": (0.0375, 0.15),
    "google/gemini-2.5-pro":        (1.25, 10.00),
    "anthropic/claude-sonnet-4.5":  (3.00, 15.00),
    "anthropic/claude-haiku-4.5":   (1.00, 5.00),
    "anthropic/claude-opus-4":      (15.00, 75.00),
    "openai/gpt-4o":                (2.50, 10.00),
    "openai/gpt-4o-mini":           (0.15, 0.60),
    "openai/gpt-5":                 (5.00, 15.00),
    "meta/llama-3.1-70b":           (0.72, 0.72),
    # Fallback providers (direct SDK, not DGrid)
    "claude-sonnet-4-5":            (3.00, 15.00),
    "gpt-4o-mini":                  (0.15, 0.60),
}

# Lower-bound guess for unknown models — deliberately mid-range so omissions
# are visible in the cost panel but don't blow up a demo.
UNKNOWN_PRICE: tuple[float, float] = (0.50, 1.50)


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for one LLM call. Returns 0.0 if token counts are zero."""
    if not prompt_tokens and not completion_tokens:
        return 0.0
    rate_p, rate_c = PRICE_PER_MTOK.get(model, UNKNOWN_PRICE)
    cost = (int(prompt_tokens) / 1_000_000) * rate_p + (int(completion_tokens) / 1_000_000) * rate_c
    return round(cost, 6)


def is_tracked(model: str) -> bool:
    """True if the model has a known price (not falling back to UNKNOWN_PRICE)."""
    return model in PRICE_PER_MTOK
