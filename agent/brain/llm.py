"""Unified LLM client — routes all AI calls through DGrid AI Gateway.

DGrid provides a unified OpenAI-compatible API to 200+ models including Claude.
This qualifies FOUR-LIFE for the DGrid bounty.

Falls back to direct Anthropic API if DGrid is not configured.
"""

import json
from openai import AsyncOpenAI
from loguru import logger

from agent.config import settings

# DGrid uses OpenAI SDK format with provider/model naming
DGRID_BASE_URL = "https://api.dgrid.ai/api/v1"
DGRID_MODEL = "anthropic/claude-sonnet-4-20250514"


class LLMClient:
    """Unified LLM client — DGrid AI Gateway (primary) or direct Anthropic (fallback)."""

    def __init__(self) -> None:
        self.use_dgrid = bool(settings.dgrid_api_key)

        if self.use_dgrid:
            self._client = AsyncOpenAI(
                base_url=DGRID_BASE_URL,
                api_key=settings.dgrid_api_key,
                default_headers={
                    "HTTP-Referer": "https://four-life.gudman.xyz",
                    "X-Title": "FOUR-LIFE Agent",
                },
            )
            self.model = DGRID_MODEL
            logger.info("LLM: DGrid AI Gateway ({})", self.model)
        else:
            self._client = AsyncOpenAI(
                base_url="https://api.anthropic.com/v1/",
                api_key=settings.anthropic_api_key,
            )
            self.model = "claude-sonnet-4-20250514"
            logger.info("LLM: Direct Anthropic ({})", self.model)

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request. Returns the text response."""
        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        return response.choices[0].message.content

    async def chat_json(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
    ) -> dict:
        """Send a chat request and parse the response as JSON."""
        text = await self.chat(messages, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            # Try array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise


# Singleton instance
_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
