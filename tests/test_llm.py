"""Tests for unified LLM client."""

import os
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


class TestLLMClient:
    def test_dgrid_mode_when_key_set(self):
        from agent.brain.llm import LLMClient
        with patch("agent.brain.llm.settings") as mock_settings:
            mock_settings.dgrid_api_key = "sk-test-dgrid"
            mock_settings.anthropic_api_key = "sk-ant-test"
            client = LLMClient()
            assert client.use_dgrid is True
            assert "anthropic/" in client.model

    def test_fallback_mode_when_no_dgrid(self):
        with patch.dict(os.environ, {"DGRID_API_KEY": ""}):
            from agent.brain.llm import LLMClient
            client = LLMClient()
            assert client.use_dgrid is False

    @pytest.mark.asyncio
    async def test_chat_returns_string(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"

        client._client = AsyncMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_chat_json_parses(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value", "num": 42}'

        client._client = AsyncMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value", "num": 42}

    @pytest.mark.asyncio
    async def test_chat_json_extracts_from_text(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Here is the result: {"action": "launch"} end'

        client._client = AsyncMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"action": "launch"}

    @pytest.mark.asyncio
    async def test_chat_json_extracts_array(self):
        from agent.brain.llm import LLMClient
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Tweets: ["first", "second", "third"]'

        client._client = AsyncMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.chat_json([{"role": "user", "content": "test"}])
        assert result == ["first", "second", "third"]
