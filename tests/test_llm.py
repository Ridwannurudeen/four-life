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
