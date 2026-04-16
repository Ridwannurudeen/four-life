"""Unified LLM client — routes all AI calls through DGrid AI Gateway.

DGrid provides a unified OpenAI-compatible API to 200+ models including Claude.
This qualifies FOUR-LIFE for the DGrid bounty.

Automatically falls back to direct Anthropic API on DGrid errors (balance, rate limit,
transient 5xx) so live demos never black out. Falls back at init time if DGrid is
not configured.
"""

import json
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from loguru import logger

from agent.config import settings

# DGrid uses OpenAI SDK format with provider/model naming
DGRID_BASE_URL = "https://api.dgrid.ai/v1"

# Model identifier reported in public API responses for trust/auditing.
# Exposed via get_llm().model_id for public endpoints.


class LLMClient:
    """Unified LLM client — DGrid AI Gateway (primary) with Anthropic fallback."""

    def __init__(self) -> None:
        self.dgrid_configured = bool(settings.dgrid_api_key)
        self.anthropic_configured = bool(settings.anthropic_api_key)
        self.openai_configured = bool(settings.openai_api_key)

        # DGrid primary (for bounty eligibility + unified routing)
        if self.dgrid_configured:
            self._dgrid = AsyncOpenAI(
                base_url=DGRID_BASE_URL,
                api_key=settings.dgrid_api_key,
                default_headers={
                    "HTTP-Referer": "https://four-life.gudman.xyz",
                    "X-Title": "FOUR-LIFE Agent",
                },
            )
            self.model = settings.dgrid_model
        else:
            self._dgrid = None
            self.model = ""

        # Anthropic as resilient fallback
        if self.anthropic_configured:
            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self._anthropic_model = "claude-sonnet-4-5"
        else:
            self._anthropic = None
            self._anthropic_model = ""

        # OpenAI as additional fallback (same SDK as DGrid, different base URL)
        if self.openai_configured:
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
            self._openai_model = "gpt-4o-mini"
        else:
            self._openai = None
            self._openai_model = ""

        # Track last-used provider for observability
        self.last_provider: str = "none"
        self.dgrid_healthy: bool = self.dgrid_configured

        providers = []
        if self.dgrid_configured: providers.append(f"DGrid({self.model})")
        if self.anthropic_configured: providers.append(f"Anthropic({self._anthropic_model})")
        if self.openai_configured: providers.append(f"OpenAI({self._openai_model})")
        if providers:
            logger.info("LLM: {} — order = primary -> fallback(s)", " | ".join(providers))
        else:
            logger.warning("LLM: NO PROVIDER CONFIGURED — all LLM calls will fail")

    @property
    def has_fallback(self) -> bool:
        """True if at least one non-DGrid provider is configured."""
        return self.anthropic_configured or self.openai_configured

    @property
    def model_id(self) -> str:
        """Stable identifier for the current provider+model (for public audit metadata)."""
        if self.last_provider == "dgrid":
            return f"dgrid:{self.model}"
        if self.last_provider == "anthropic":
            return f"anthropic:{self._anthropic_model}"
        if self.last_provider == "openai":
            return f"openai:{self._openai_model}"
        if self.dgrid_configured:
            return f"dgrid:{self.model}"
        if self.anthropic_configured:
            return f"anthropic:{self._anthropic_model}"
        if self.openai_configured:
            return f"openai:{self._openai_model}"
        return "none"

    @staticmethod
    def _is_dgrid_unavailable(exc: Exception) -> bool:
        """Classify DGrid errors that warrant fallback: balance, rate limit, 5xx, network."""
        msg = str(exc).lower()
        if "balance_insufficient" in msg or "insufficient" in msg:
            return True
        status = getattr(exc, "status_code", None)
        if status in (402, 403, 429, 500, 502, 503, 504):
            return True
        if "timeout" in msg or "connection" in msg:
            return True
        return False

    async def _dgrid_chat_raw(self, messages: list[dict], max_tokens: int, temperature: float, json_mode: bool) -> str:
        kwargs = dict(model=self.model, max_tokens=max_tokens, temperature=temperature, messages=messages)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._dgrid.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _anthropic_chat_raw(self, messages: list[dict], max_tokens: int, temperature: float) -> str:
        system = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                api_messages.append(msg)
        kwargs = dict(
            model=self._anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=api_messages,
        )
        if system:
            kwargs["system"] = system
        response = await self._anthropic.messages.create(**kwargs)
        return response.content[0].text

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request. Returns the text response.

        Tries DGrid first, falls back to Anthropic on balance/rate/transient errors.
        """
        return await self._chat_with_fallback(messages, max_tokens, temperature, json_mode=False)

    async def chat_json(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
    ) -> dict:
        """Send a chat request and parse the response as JSON."""
        text = await self._chat_with_fallback(messages, max_tokens, temperature=0.7, json_mode=True)
        if not text or not text.strip():
            raise ValueError("LLM returned empty response")
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

    async def _openai_chat_raw(self, messages: list[dict], max_tokens: int, temperature: float, json_mode: bool) -> str:
        kwargs = dict(
            model=self._openai_model, max_tokens=max_tokens, temperature=temperature, messages=messages,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._openai.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _chat_with_fallback(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> str:
        """Call DGrid first; fall back to Anthropic, then OpenAI on balance/rate/transient errors."""
        last_error: Exception | None = None

        # Primary: DGrid
        if self.dgrid_configured and self.dgrid_healthy:
            try:
                text = await self._dgrid_chat_raw(messages, max_tokens, temperature, json_mode)
                self.last_provider = "dgrid"
                return text
            except Exception as e:
                last_error = e
                if self._is_dgrid_unavailable(e) and self.has_fallback:
                    logger.warning(
                        "DGrid unavailable ({}) — falling back. Will retry DGrid on next call.",
                        str(e)[:120],
                    )
                elif not self.has_fallback:
                    raise
                else:
                    logger.warning("DGrid error ({}) — falling back.", str(e)[:120])

        # Fallback #1: Anthropic
        if self.anthropic_configured:
            try:
                # Anthropic has no native response_format — inject a system hint for JSON mode
                msgs = messages
                if json_mode:
                    has_system = any(m["role"] == "system" for m in msgs)
                    if not has_system:
                        msgs = [{"role": "system", "content": "Respond ONLY with a single valid JSON object. No prose, no markdown fences."}] + msgs
                text = await self._anthropic_chat_raw(msgs, max_tokens, temperature)
                self.last_provider = "anthropic"
                return text
            except Exception as e:
                last_error = e
                logger.warning("Anthropic failed ({}) — trying OpenAI.", str(e)[:120])

        # Fallback #2: OpenAI
        if self.openai_configured:
            try:
                text = await self._openai_chat_raw(messages, max_tokens, temperature, json_mode)
                self.last_provider = "openai"
                return text
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error
        raise RuntimeError("No LLM provider available")


# Singleton instance
_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
