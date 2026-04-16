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
