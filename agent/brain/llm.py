"""Unified LLM client — routes all AI calls through DGrid AI Gateway.

DGrid provides a unified OpenAI-compatible API to 200+ models including Claude.
This qualifies FOUR-LIFE for the DGrid bounty.

Falls back to direct Anthropic API if DGrid is not configured.
"""

import json
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from loguru import logger

from agent.config import settings

# DGrid uses OpenAI SDK format with provider/model naming
DGRID_BASE_URL = "https://api.dgrid.ai/v1"


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
            self.model = settings.dgrid_model
            logger.info("LLM: DGrid AI Gateway ({})", self.model)
        else:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = "claude-sonnet-4-20250514"
            logger.info("LLM: Direct Anthropic ({})", self.model)

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request. Returns the text response."""
        if self.use_dgrid:
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
            return response.choices[0].message.content
        else:
            # Anthropic expects system message separate from user/assistant messages
            system = None
            api_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    api_messages.append(msg)
            kwargs = dict(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=api_messages,
            )
            if system:
                kwargs["system"] = system
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text

    async def chat_json(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
    ) -> dict:
        """Send a chat request and parse the response as JSON."""
        if self.use_dgrid:
            # Use response_format for structured JSON output
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.7,
                messages=messages,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content
        else:
            text = await self.chat(messages, max_tokens)
        if not text or not text.strip():
            raise ValueError("LLM returned empty response")
        # Strip markdown code fences (```json ... ```)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON object from the response
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end])
            # Try array
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end])
            raise


# Singleton instance
_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
