"""Tests for the unified LLM client — DGrid primary with Anthropic fallback."""

import os
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


def _mock_anthropic_response(text: str):
    """Create a mock Anthropic messages.create response."""
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = text
    mock_response.content = [mock_block]
    return mock_response


def _mock_openai_response(text: str):
    """Create a mock OpenAI chat.completions.create response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = text
    return mock_response


def _make_client(*, dgrid=True, anthropic=True):
    """Build an LLMClient instance with deterministic settings for testing."""
    from agent.brain.llm import LLMClient
    with patch("agent.brain.llm.settings") as mock_settings:
        mock_settings.dgrid_api_key = "sk-test-dgrid" if dgrid else ""
        mock_settings.anthropic_api_key = "sk-ant-test" if anthropic else ""
        mock_settings.dgrid_model = "google/gemini-2.5-flash"
        client = LLMClient()
    # Swap clients for mocks to avoid real network
    if dgrid:
        client._dgrid = AsyncMock()
        client._dgrid.chat = MagicMock()
        client._dgrid.chat.completions = MagicMock()
        client._dgrid.chat.completions.create = AsyncMock()
    if anthropic:
        client._anthropic = AsyncMock()
        client._anthropic.messages = MagicMock()
        client._anthropic.messages.create = AsyncMock()
    return client


class TestLLMConfiguration:
    def test_dgrid_configured_when_key_set(self):
        client = _make_client(dgrid=True, anthropic=True)
        assert client.dgrid_configured is True
        assert client.anthropic_configured is True
        assert client.model == "google/gemini-2.5-flash"

    def test_no_dgrid_when_key_missing(self):
        client = _make_client(dgrid=False, anthropic=True)
        assert client.dgrid_configured is False
        assert client.anthropic_configured is True

    def test_model_id_tracks_provider(self):
        client = _make_client(dgrid=True, anthropic=True)
        # Before any call, model_id reflects the primary
        assert client.model_id.startswith("dgrid:")

    def test_classifies_balance_error_as_unavailable(self):
        from agent.brain.llm import LLMClient
        exc = Exception("403 BALANCE_INSUFFICIENT")
        assert LLMClient._is_dgrid_unavailable(exc) is True

    def test_classifies_403_status_as_unavailable(self):
        from agent.brain.llm import LLMClient
        class E(Exception):
            status_code = 403
        assert LLMClient._is_dgrid_unavailable(E("forbidden")) is True

    def test_classifies_200_unrelated_error_as_not_unavailable(self):
        from agent.brain.llm import LLMClient
        exc = Exception("some parsing error")
        assert LLMClient._is_dgrid_unavailable(exc) is False


class TestChatRouting:
    @pytest.mark.asyncio
    async def test_primary_path_dgrid(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("from dgrid")
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "from dgrid"
        assert client.last_provider == "dgrid"

    @pytest.mark.asyncio
    async def test_anthropic_only_when_no_dgrid(self):
        client = _make_client(dgrid=False, anthropic=True)
        client._anthropic.messages.create.return_value = _mock_anthropic_response("from anthropic")
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "from anthropic"
        assert client.last_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_fallback_on_balance_insufficient(self):
        """DGrid 403/BALANCE_INSUFFICIENT must transparently fall back to Anthropic."""
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception(
            "Error code: 403 - {'message': 'BALANCE_INSUFFICIENT'}"
        )
        client._anthropic.messages.create.return_value = _mock_anthropic_response("recovered")
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "recovered"
        assert client.last_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self):
        client = _make_client(dgrid=True, anthropic=True)
        class E(Exception):
            status_code = 429
        client._dgrid.chat.completions.create.side_effect = E("rate limited")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("recovered")
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_reraises_when_both_unavailable(self):
        client = _make_client(dgrid=True, anthropic=False)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        with pytest.raises(Exception):
            await client.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_anthropic_extracts_system_message(self):
        client = _make_client(dgrid=False, anthropic=True)
        client._anthropic.messages.create.return_value = _mock_anthropic_response("ok")
        await client.chat([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "test"},
        ])
        kwargs = client._anthropic.messages.create.call_args[1]
        assert kwargs["system"] == "You are helpful"
        assert all(m["role"] != "system" for m in kwargs["messages"])


class TestChatJson:
    @pytest.mark.asyncio
    async def test_parses_dgrid_json(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response(
            '{"key": "value", "num": 42}'
        )
        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value", "num": 42}

    @pytest.mark.asyncio
    async def test_parses_anthropic_json(self):
        client = _make_client(dgrid=False, anthropic=True)
        client._anthropic.messages.create.return_value = _mock_anthropic_response(
            '{"key": "value", "num": 42}'
        )
        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value", "num": 42}

    @pytest.mark.asyncio
    async def test_extracts_json_from_prose(self):
        client = _make_client(dgrid=False, anthropic=True)
        client._anthropic.messages.create.return_value = _mock_anthropic_response(
            'Here is the result: {"action": "launch"} end'
        )
        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"action": "launch"}

    @pytest.mark.asyncio
    async def test_extracts_array_from_prose(self):
        client = _make_client(dgrid=False, anthropic=True)
        client._anthropic.messages.create.return_value = _mock_anthropic_response(
            'Tweets: ["first", "second", "third"]'
        )
        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_json_fallback_preserved(self):
        """JSON mode must still fall back to Anthropic on DGrid balance error."""
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response('{"ok": true}')
        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"ok": True}


class TestTaskRouting:
    @pytest.mark.asyncio
    async def test_narrative_task_uses_gemini(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="narrative")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"
        assert client.last_model == "google/gemini-2.5-flash"
        assert client.last_task == "narrative"

    @pytest.mark.asyncio
    async def test_content_task_defaults_to_gemini_flash(self):
        # Every task now defaults to google/gemini-2.5-flash so a small DGrid
        # credit lasts the full judging window. Promotion to a heavier model
        # is opt-in via DGRID_TASK_OVERRIDES.
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="content")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_risk_task_defaults_to_gemini_flash(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="risk")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"

    def test_task_override_env_remaps_task(self, monkeypatch):
        # Operators can remap a task to a stronger model via env without
        # touching code: DGRID_TASK_OVERRIDES="content=anthropic/claude-sonnet-4.5"
        from agent.brain import llm as llm_mod
        original = dict(llm_mod.TASK_MODEL_MAP)
        try:
            monkeypatch.setattr(llm_mod.settings, "dgrid_task_overrides", "content=anthropic/claude-sonnet-4.5")
            llm_mod._apply_task_overrides()
            assert llm_mod.TASK_MODEL_MAP["content"] == "anthropic/claude-sonnet-4.5"
            # Non-overridden tasks stay on Flash
            assert llm_mod.TASK_MODEL_MAP["risk"] == "google/gemini-2.5-flash"
        finally:
            llm_mod.TASK_MODEL_MAP.clear()
            llm_mod.TASK_MODEL_MAP.update(original)

    @pytest.mark.asyncio
    async def test_vision_task_uses_gemini(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="vision")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_unknown_task_falls_back_to_default_model(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="does-not-exist")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        # Falls back to the configured default (settings.dgrid_model in the fixture).
        assert kwargs["model"] == "google/gemini-2.5-flash"
        assert client.last_task == "default"

    @pytest.mark.asyncio
    async def test_default_task_uses_configured_model(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="default")
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_plain_chat_uses_default_model(self):
        """Existing call sites (no task) must keep using self.model."""
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat([{"role": "user", "content": "hi"}])
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        assert kwargs["model"] == "google/gemini-2.5-flash"
        assert client.last_task == "default"

    @pytest.mark.asyncio
    async def test_task_routing_does_not_affect_anthropic_fallback(self):
        """When DGrid is down, Anthropic fallback uses its configured model regardless of task."""
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("ok")
        await client.chat_task([{"role": "user", "content": "hi"}], task="risk")
        kwargs = client._anthropic.messages.create.call_args[1]
        assert kwargs["model"] == "claude-sonnet-4-5"
        assert client.last_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_task_routing_does_not_affect_openai_fallback(self):
        """OpenAI fallback keeps its configured model even with task routing."""
        from unittest.mock import patch as _patch
        from agent.brain.llm import LLMClient
        with _patch("agent.brain.llm.settings") as mock_settings:
            mock_settings.dgrid_api_key = "sk-test"
            mock_settings.anthropic_api_key = ""
            mock_settings.openai_api_key = "sk-openai"
            mock_settings.dgrid_model = "google/gemini-2.5-flash"
            client = LLMClient()
        client._dgrid = AsyncMock()
        client._dgrid.chat = MagicMock()
        client._dgrid.chat.completions = MagicMock()
        client._dgrid.chat.completions.create = AsyncMock(
            side_effect=Exception("BALANCE_INSUFFICIENT"),
        )
        client._openai = AsyncMock()
        client._openai.chat = MagicMock()
        client._openai.chat.completions = MagicMock()
        client._openai.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("ok"),
        )
        await client.chat_task([{"role": "user", "content": "hi"}], task="content")
        kwargs = client._openai.chat.completions.create.call_args[1]
        assert kwargs["model"] == "gpt-4o-mini"  # OpenAI fallback model unchanged
        assert client.last_provider == "openai"

    @pytest.mark.asyncio
    async def test_chat_json_task_parses_response(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response(
            '{"action": "hold"}'
        )
        result = await client.chat_json_task(
            [{"role": "user", "content": "x"}], task="risk",
        )
        assert result == {"action": "hold"}
        kwargs = client._dgrid.chat.completions.create.call_args[1]
        # Default routing — all tasks go to gemini-2.5-flash for cost efficiency.
        assert kwargs["model"] == "google/gemini-2.5-flash"


class TestUsageStats:
    @pytest.mark.asyncio
    async def test_usage_counts_per_provider_and_task(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "x"}], task="narrative")
        await client.chat_task([{"role": "user", "content": "x"}], task="content")
        await client.chat_task([{"role": "user", "content": "x"}], task="content")
        stats = client.get_usage_stats()
        assert stats["usage_by_provider"]["dgrid"] == 3
        assert stats["usage_by_task"]["narrative"] == 1
        assert stats["usage_by_task"]["content"] == 2
        # All tasks default to gemini-2.5-flash (cost-aware), so usage_by_model
        # collapses onto one key — which is exactly the "one API, many tasks,
        # one cheap model" story we want the DGrid panel to show.
        assert stats["usage_by_model"]["google/gemini-2.5-flash"] == 3

    @pytest.mark.asyncio
    async def test_fallback_events_counted(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("ok")
        await client.chat_task([{"role": "user", "content": "x"}], task="risk")
        await client.chat_task([{"role": "user", "content": "x"}], task="narrative")
        stats = client.get_usage_stats()
        assert stats["fallback_events"] == 2
        assert stats["usage_by_provider"]["anthropic"] == 2
        assert stats["usage_by_provider"].get("dgrid", 0) == 0
        # Last DGrid error should be recorded (redacted but not empty).
        assert stats["last_dgrid_error"] is not None

    @pytest.mark.asyncio
    async def test_default_task_recorded_when_no_task_given(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat([{"role": "user", "content": "x"}])
        stats = client.get_usage_stats()
        assert stats["usage_by_task"]["default"] == 1

    def test_stats_include_config_surface(self):
        client = _make_client(dgrid=True, anthropic=True)
        stats = client.get_usage_stats()
        assert stats["providers_configured"]["dgrid"] is True
        assert stats["providers_configured"]["anthropic"] is True
        assert stats["primary_order"][0] == "dgrid"
        assert stats["default_dgrid_model"] == "google/gemini-2.5-flash"
        assert "narrative" in stats["task_model_map"]
        assert "uptime_seconds" in stats

    def test_error_redaction_strips_api_keys(self):
        from agent.brain.llm import LLMClient
        redacted = LLMClient._redact("Auth failed: sk-dg-abc123xyz invalid")
        assert "abc123xyz" not in redacted
        assert "sk-***" in redacted

    def test_redaction_handles_none(self):
        from agent.brain.llm import LLMClient
        assert LLMClient._redact(None) == ""
        assert LLMClient._redact("") == ""

    def test_redaction_strips_bearer_token(self):
        from agent.brain.llm import LLMClient
        redacted = LLMClient._redact("Authorization: Bearer sk-dgrid_abc123xyz")
        assert "abc123" not in redacted


# ── Circuit breaker ─────────────────────────────────────────────────


class TestCircuitBreaker:
    def test_starts_closed(self):
        from agent.brain.llm import CircuitBreaker
        b = CircuitBreaker()
        assert b.state() == "closed"
        assert b.allow() is True

    def test_opens_after_threshold_failures(self):
        from agent.brain.llm import CircuitBreaker
        b = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        b.record_failure("err")
        b.record_failure("err")
        assert b.state() == "closed"  # not yet
        b.record_failure("err")
        assert b.state() == "open"
        assert b.allow() is False

    def test_half_open_after_cooldown(self):
        from agent.brain.llm import CircuitBreaker
        b = CircuitBreaker(failure_threshold=2, cooldown_seconds=0)
        b.record_failure("err")
        b.record_failure("err")
        # cooldown=0 means immediately half-open
        assert b.state() == "half_open"
        # Half-open is not "open" → allow
        assert b.allow() is True

    def test_success_closes_the_breaker(self):
        from agent.brain.llm import CircuitBreaker
        b = CircuitBreaker(failure_threshold=2, cooldown_seconds=0)
        b.record_failure("err")
        b.record_failure("err")
        b.record_success()
        assert b.state() == "closed"

    def test_snapshot_shape(self):
        from agent.brain.llm import CircuitBreaker
        b = CircuitBreaker()
        snap = b.snapshot()
        for key in ("state", "consecutive_failures", "failure_threshold",
                    "cooldown_seconds", "times_opened"):
            assert key in snap

    @pytest.mark.asyncio
    async def test_breaker_skips_dgrid_after_threshold(self):
        client = _make_client(dgrid=True, anthropic=True)
        # Force the breaker open by injecting repeated failures
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("ok")
        for _ in range(3):
            await client.chat([{"role": "user", "content": "hi"}])
        # Breaker should be open now
        assert client.breaker.state() == "open"
        # Reset the side effect — even if DGrid would work, breaker skips it
        client._dgrid.chat.completions.create.side_effect = None
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("dgrid works again")
        result = await client.chat([{"role": "user", "content": "hi"}])
        # Because the breaker is open, we should have gone straight to anthropic
        assert result == "ok"
        assert client.last_provider == "anthropic"
        # breaker_skips counter should be incremented
        assert client._breaker_skips >= 1


# ── Transient retry ─────────────────────────────────────────────────


class TestTransientRetry:
    @pytest.mark.asyncio
    async def test_retries_once_on_5xx(self):
        client = _make_client(dgrid=True, anthropic=True)

        class Transient(Exception):
            status_code = 503

        calls = []

        async def flaky(**kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise Transient("service unavailable")
            return _mock_openai_response("recovered on retry")

        client._dgrid.chat.completions.create.side_effect = flaky
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "recovered on retry"
        assert len(calls) == 2  # first call + one retry
        assert client.last_provider == "dgrid"
        assert client._transient_retries == 1

    @pytest.mark.asyncio
    async def test_does_not_retry_balance_error(self):
        client = _make_client(dgrid=True, anthropic=True)
        calls = []

        async def failing(**kwargs):
            calls.append(1)
            raise Exception("BALANCE_INSUFFICIENT")

        client._dgrid.chat.completions.create.side_effect = failing
        client._anthropic.messages.create.return_value = _mock_anthropic_response("fallback ok")
        await client.chat([{"role": "user", "content": "hi"}])
        # Balance errors are unavailable but NOT transient → no retry
        assert len(calls) == 1
        assert client._transient_retries == 0

    def test_error_status_reads_openai_response(self):
        from agent.brain.llm import LLMClient

        class ResponseLike:
            status_code = 429

        class WrappedErr(Exception):
            def __init__(self):
                super().__init__("rate limit")
                self.response = ResponseLike()

        exc = WrappedErr()
        assert LLMClient._error_status(exc) == 429
        assert LLMClient._is_dgrid_unavailable(exc) is True


# ── Chaos mode ──────────────────────────────────────────────────────


class TestChaos:
    @pytest.mark.asyncio
    async def test_chaos_forces_fallback(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("would-be-dgrid")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("chaos fallback")
        client.enable_chaos("test")
        result = await client.chat([{"role": "user", "content": "hi"}])
        # DGrid is mocked and would succeed — but chaos short-circuits before
        # the mock is ever reached, so we land on Anthropic.
        assert result == "chaos fallback"
        assert client.last_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_disable_chaos_restores_dgrid(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("real dgrid")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("chaos fallback")
        client.enable_chaos("test")
        await client.chat([{"role": "user", "content": "hi"}])
        client.disable_chaos()
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "real dgrid"
        assert client.last_provider == "dgrid"
        # Disable chaos should reset the breaker so we hit DGrid cleanly
        assert client.breaker.state() == "closed"

    def test_chaos_error_is_classified_unavailable(self):
        from agent.brain.llm import LLMClient, DGridChaosError
        assert LLMClient._is_dgrid_unavailable(DGridChaosError("boom")) is True
        # But not transient → no retry on chaos
        assert LLMClient._is_transient(DGridChaosError("boom")) is False


# ── Cost tracking ───────────────────────────────────────────────────


def _mock_openai_response_with_usage(text: str, prompt_tokens: int, completion_tokens: int):
    """OpenAI-shaped mock with explicit usage (not MagicMock auto-attrs).
    Needed for cost assertions — MagicMock's auto-generated numeric attrs don't
    convert cleanly to int on all Python versions."""
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = text
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    r.usage = usage
    return r


class TestCostTracking:
    @pytest.mark.asyncio
    async def test_cost_appears_in_trace_entry(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response_with_usage(
            "ok", prompt_tokens=100, completion_tokens=50,
        )
        await client.chat_task([{"role": "user", "content": "hi"}], task="narrative")
        trace = client.get_trace(limit=5)
        assert trace[0]["success"] is True
        assert trace[0]["cost_usd"] > 0
        assert trace[0]["cost_tracked"] is True

    @pytest.mark.asyncio
    async def test_cost_totals_accumulate_in_stats(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response_with_usage(
            "ok", prompt_tokens=1000, completion_tokens=500,
        )
        await client.chat_task([{"role": "user", "content": "hi"}], task="narrative")
        await client.chat_task([{"role": "user", "content": "hi"}], task="content")
        stats = client.get_usage_stats()
        assert "cost_usd" in stats
        assert stats["cost_usd"]["total"] > 0
        assert "narrative" in stats["cost_usd"]["by_task"]
        assert "content" in stats["cost_usd"]["by_task"]
        assert "google/gemini-2.5-flash" in stats["cost_usd"]["by_model"]

    @pytest.mark.asyncio
    async def test_failures_do_not_count_cost(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("ok")
        await client.chat([{"role": "user", "content": "hi"}])
        stats = client.get_usage_stats()
        # DGrid failed → zero DGrid cost accrued regardless of fallback success
        assert stats["cost_usd"]["by_provider"].get("dgrid", 0) == 0


# ── Attestation hooks ───────────────────────────────────────────────


class TestAttestation:
    @pytest.mark.asyncio
    async def test_successful_dgrid_call_appends_to_chain(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        before = client.get_attestation()
        await client.chat([{"role": "user", "content": "hi"}])
        after = client.get_attestation()
        assert after["num_calls_chained"] == before["num_calls_chained"] + 1
        assert after["current_root"] != before["current_root"]

    @pytest.mark.asyncio
    async def test_failed_dgrid_call_does_not_append(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.side_effect = Exception("BALANCE_INSUFFICIENT")
        client._anthropic.messages.create.return_value = _mock_anthropic_response("fallback")
        before = client.get_attestation()
        await client.chat([{"role": "user", "content": "hi"}])
        after = client.get_attestation()
        # Fallback landed on Anthropic; DGrid failed → chain unchanged
        assert after["num_calls_chained"] == before["num_calls_chained"]
        assert after["current_root"] == before["current_root"]

    @pytest.mark.asyncio
    async def test_trace_entry_carries_chain_tip(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat([{"role": "user", "content": "hi"}])
        trace = client.get_trace(limit=1)
        assert trace[0]["provider"] == "dgrid"
        assert trace[0]["success"] is True
        assert "chain_tip" in trace[0]
        assert "call_digest" in trace[0]
        assert len(trace[0]["chain_tip"]) == 64

    @pytest.mark.asyncio
    async def test_full_log_persists_every_dgrid_call(self):
        """The append-only log must retain every DGrid call for Merkle
        verification even after the ring buffer rotates."""
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        for _ in range(3):
            await client.chat([{"role": "user", "content": "hi"}])
        # audit/calls slice
        calls = client.get_audit_calls(offset=0, limit=100)
        assert len(calls) == 3
        # Each entry must carry the fields a judge needs to re-derive the chain
        for c in calls:
            assert c["provider"] == "dgrid"
            assert "call_digest" in c
            assert "chain_tip" in c
            assert "seq" in c

    @pytest.mark.asyncio
    async def test_full_log_is_independently_verifiable(self):
        """A judge with only the call log + current_root can verify the chain."""
        from agent.brain.attestation import verify_chain
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        for _ in range(4):
            await client.chat([{"role": "user", "content": "hi"}])
        snap = client.get_attestation()
        calls = client.get_audit_calls(offset=0, limit=100)
        assert verify_chain(calls, snap["current_root"]) is True
        # Tampered log must NOT verify.
        calls[0] = {**calls[0], "call_digest": "ff" * 32}
        assert verify_chain(calls, snap["current_root"]) is False


# ── Image generation routing ────────────────────────────────────────


class TestImageGen:
    @pytest.mark.asyncio
    async def test_image_gen_disables_dgrid_after_first_failure(self, monkeypatch):
        """If DGrid's image endpoint 404s we should never waste another
        request on it this session."""
        import httpx
        client = _make_client(dgrid=True, anthropic=True)

        call_count = {"dgrid": 0, "openai": 0}
        # Fake AsyncClient that returns 404 for DGrid URL, 200 for OpenAI URL
        class _FakeResp:
            def __init__(self, status: int, body: dict | bytes):
                self.status_code = status
                self._body = body
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise httpx.HTTPStatusError("error", request=None, response=None)
            def json(self):
                return self._body
            @property
            def content(self):
                return self._body if isinstance(self._body, bytes) else b""

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def post(self, url, **kwargs):
                if "dgrid.ai" in url:
                    call_count["dgrid"] += 1
                    return _FakeResp(404, {"error": "not found"})
                call_count["openai"] += 1
                return _FakeResp(200, {"data": [{"url": "https://cdn.openai.com/x.png"}]})
            async def get(self, url):
                return _FakeResp(200, b"PNGBYTES")

        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

        # First call — DGrid fails, fallback to OpenAI succeeds
        body = await client.generate_image("a test")
        assert body == b"PNGBYTES"
        assert call_count["dgrid"] == 1
        assert call_count["openai"] == 1
        assert client._dgrid_images_disabled is True

        # Second call — DGrid must be skipped (still disabled)
        body = await client.generate_image("another test")
        assert body == b"PNGBYTES"
        assert call_count["dgrid"] == 1  # unchanged
        assert call_count["openai"] == 2


# ── Trace ordering + trace_count ────────────────────────────────────


class TestTraceShape:
    @pytest.mark.asyncio
    async def test_trace_entries_have_ts_ms_and_seq(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat([{"role": "user", "content": "a"}])
        await client.chat([{"role": "user", "content": "b"}])
        trace = client.get_trace(limit=5)
        assert len(trace) >= 2
        for t in trace:
            assert "ts_ms" in t
            assert "seq" in t
            assert isinstance(t["seq"], int)
        # Newest first — seq should strictly decrease
        assert trace[0]["seq"] > trace[1]["seq"]

    @pytest.mark.asyncio
    async def test_trace_count_property_matches_buffer(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        assert client.trace_count == 0
        await client.chat([{"role": "user", "content": "x"}])
        assert client.trace_count == 1


# ── Leaderboard ─────────────────────────────────────────────────────


class TestLeaderboard:
    @pytest.mark.asyncio
    async def test_leaderboard_populated_after_calls(self):
        client = _make_client(dgrid=True, anthropic=True)
        client._dgrid.chat.completions.create.return_value = _mock_openai_response("ok")
        await client.chat_task([{"role": "user", "content": "x"}], task="narrative")
        await client.chat_task([{"role": "user", "content": "x"}], task="risk")
        rows = client.get_leaderboard()
        tasks_seen = {r["task"] for r in rows}
        assert "narrative" in tasks_seen
        assert "risk" in tasks_seen
        for r in rows:
            assert 0 <= r["success_rate"] <= 1.0
            assert r["calls"] >= 1
