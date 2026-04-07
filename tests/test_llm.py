"""Tests for unified LLM client."""

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


class TestLLMClient:
    def test_dgrid_mode_when_key_set(self):
        from agent.brain.llm import LLMClient
        with patch("agent.brain.llm.settings") as mock_settings:
            mock_settings.dgrid_api_key = "sk-test-dgrid"
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.dgrid_model = "google/gemini-2.5-flash"
            client = LLMClient()
            assert client.use_dgrid is True
            assert client.model == "google/gemini-2.5-flash"

    def test_fallback_mode_when_no_dgrid(self):
        with patch.dict(os.environ, {"DGRID_API_KEY": ""}):
            from agent.brain.llm import LLMClient
            client = LLMClient()
            assert client.use_dgrid is False

    @pytest.mark.asyncio
    async def test_chat_returns_string_dgrid(self):
        from agent.brain.llm import LLMClient
        with patch("agent.brain.llm.settings") as mock_settings:
            mock_settings.dgrid_api_key = "sk-test"
            mock_settings.dgrid_model = "test/model"
            client = LLMClient()

        client._client = AsyncMock()
        client._client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("Hello world")
        )

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_chat_returns_string_anthropic(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()  # Falls back to Anthropic (no DGRID_API_KEY)

        client._client = AsyncMock()
        client._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("Hello world")
        )

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_chat_anthropic_extracts_system(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        client._client = AsyncMock()
        client._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("response")
        )

        await client.chat([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "test"},
        ])

        call_kwargs = client._client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are helpful"
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    @pytest.mark.asyncio
    async def test_chat_json_parses(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        client._client = AsyncMock()
        client._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response('{"key": "value", "num": 42}')
        )

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value", "num": 42}

    @pytest.mark.asyncio
    async def test_chat_json_extracts_from_text(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        client._client = AsyncMock()
        client._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response('Here is the result: {"action": "launch"} end')
        )

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"action": "launch"}

    @pytest.mark.asyncio
    async def test_chat_json_extracts_array(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        client._client = AsyncMock()
        client._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response('Tweets: ["first", "second", "third"]')
        )

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == ["first", "second", "third"]
