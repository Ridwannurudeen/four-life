"""Tests for the per-model USD pricing table."""

from agent.brain.cost import PRICE_PER_MTOK, UNKNOWN_PRICE, estimate_cost_usd, is_tracked


class TestCost:
    def test_known_model_is_tracked(self):
        assert is_tracked("google/gemini-2.5-flash") is True
        assert is_tracked("anthropic/claude-sonnet-4.5") is True

    def test_unknown_model_is_not_tracked(self):
        assert is_tracked("nobody/nothing") is False

    def test_zero_tokens_costs_zero(self):
        assert estimate_cost_usd("google/gemini-2.5-flash", 0, 0) == 0.0

    def test_known_model_uses_its_rate(self):
        # gemini-2.5-flash: $0.075/MTok prompt, $0.30/MTok completion
        cost = estimate_cost_usd("google/gemini-2.5-flash", 1_000_000, 1_000_000)
        assert round(cost, 2) == round(0.075 + 0.30, 2)

    def test_unknown_model_uses_fallback_rate(self):
        known = estimate_cost_usd("google/gemini-2.5-flash", 1_000_000, 0)
        unknown = estimate_cost_usd("nobody/nothing", 1_000_000, 0)
        # Unknown should fall back to UNKNOWN_PRICE[0] (0.50) — clearly different from flash (0.075)
        assert unknown != known
        assert unknown == UNKNOWN_PRICE[0]

    def test_rate_split_prompt_vs_completion(self):
        # Prompt and completion are priced separately — swapping them
        # should change the total on an asymmetric model.
        a = estimate_cost_usd("anthropic/claude-sonnet-4.5", 1_000_000, 0)
        b = estimate_cost_usd("anthropic/claude-sonnet-4.5", 0, 1_000_000)
        assert a != b
        # Completion is 5x prompt for Sonnet 4.5
        assert round(b / a, 1) == 5.0

    def test_result_is_rounded(self):
        # Output is rounded to 6 decimals to keep JSON payloads clean.
        cost = estimate_cost_usd("google/gemini-2.5-flash", 17, 23)
        assert isinstance(cost, float)
        # Not more than 6 decimals of precision.
        assert round(cost, 6) == cost

    def test_every_task_default_model_is_priced(self):
        # If we ever add a model to TASK_MODEL_MAP without adding a price,
        # the dashboard will fall back to UNKNOWN_PRICE silently — this test
        # catches that before a demo.
        from agent.brain.llm import TASK_MODEL_MAP
        for task, model in TASK_MODEL_MAP.items():
            assert model in PRICE_PER_MTOK, f"task {task!r} routes to {model!r} but that model has no price"
