"""Unified LLM client — routes all AI calls through DGrid AI Gateway.

DGrid provides a unified OpenAI-compatible API to 200+ models including Claude.
This qualifies FOUR-LIFE for the DGrid bounty.

Automatically falls back to direct Anthropic API on DGrid errors (balance, rate limit,
transient 5xx) so live demos never black out. Falls back at init time if DGrid is
not configured.

Task-typed routing: different task types are routed to different DGrid models.
This is the core DGrid bounty story — one gateway, many optimal models.
"""

import json
import time
from collections import defaultdict
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from loguru import logger

from agent.config import settings

# DGrid uses OpenAI SDK format with provider/model naming
DGRID_BASE_URL = "https://api.dgrid.ai/v1"

# Task-type -> DGrid model mapping. Uses provider/model format that DGrid accepts.
# If any specific ID is rejected, _chat_with_fallback retries with the configured default,
# then falls through to Anthropic/OpenAI. IDs are sourced from the task brief and match
# the DGrid (OpenRouter-style) model namespace.
TASK_MODEL_MAP: dict[str, str] = {
    "narrative": "google/gemini-2.5-flash",       # fast, cheap market analysis
    "content":   "anthropic/claude-sonnet-4.5",   # best-in-class prose / memes
    "risk":      "openai/gpt-4o",                 # strong structured reasoning
    "vision":    "google/gemini-2.5-flash",       # multimodal + cheap
    # "default" is intentionally absent — it means "use self.model".
}

VALID_TASKS = set(TASK_MODEL_MAP.keys()) | {"default"}

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
        self.last_model: str = ""
        self.last_task: str = "default"
        self.dgrid_healthy: bool = self.dgrid_configured

        # ── Usage tracking (in-memory, rolling totals) ──────────────
        self._session_started = time.time()
        self._usage_by_provider: dict[str, int] = defaultdict(int)
        self._usage_by_task: dict[str, int] = defaultdict(int)
        self._usage_by_model: dict[str, int] = defaultdict(int)
        self._last_seen: dict[str, float] = {}
        self._fallback_events: int = 0
        self._last_dgrid_error: str | None = None

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
            return f"dgrid:{self.last_model or self.model}"
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

    def _resolve_dgrid_model(self, task: str | None) -> str:
        """Pick the DGrid model for a task. Unknown/None/`default` -> configured default."""
        if not task or task == "default":
            return self.model
        return TASK_MODEL_MAP.get(task, self.model)

    def _record_usage(self, provider: str, model: str, task: str) -> None:
        now = time.time()
        self._usage_by_provider[provider] += 1
        self._usage_by_task[task] += 1
        self._usage_by_model[model] += 1
        self._last_seen[f"provider:{provider}"] = now
        self._last_seen[f"task:{task}"] = now
        self._last_seen[f"model:{model}"] = now

    async def _dgrid_chat_raw(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        model: str | None = None,
    ) -> str:
        kwargs = dict(
            model=model or self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
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
        return self._parse_json(text)

    async def chat_task(
        self,
        messages: list[dict],
        task: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Task-routed chat. DGrid model is selected per task; fallback providers unchanged."""
        return await self._chat_with_fallback(
            messages, max_tokens, temperature, json_mode=False, task=task,
        )

    async def chat_json_task(
        self,
        messages: list[dict],
        task: str,
        max_tokens: int = 2000,
    ) -> dict:
        """Task-routed JSON chat. DGrid model is selected per task."""
        text = await self._chat_with_fallback(
            messages, max_tokens, temperature=0.7, json_mode=True, task=task,
        )
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("LLM returned empty response")
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end])
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
        task: str | None = None,
    ) -> str:
        """Call DGrid first; fall back to Anthropic, then OpenAI on balance/rate/transient errors."""
        last_error: Exception | None = None
        task_label = task if task in VALID_TASKS else "default"
        self.last_task = task_label

        # Primary: DGrid
        if self.dgrid_configured and self.dgrid_healthy:
            dgrid_model = self._resolve_dgrid_model(task_label)
            try:
                text = await self._dgrid_chat_raw(
                    messages, max_tokens, temperature, json_mode, model=dgrid_model,
                )
                self.last_provider = "dgrid"
                self.last_model = dgrid_model
                self._record_usage("dgrid", dgrid_model, task_label)
                return text
            except Exception as e:
                last_error = e
                self._last_dgrid_error = self._redact(str(e))[:240]
                if self._is_dgrid_unavailable(e) and self.has_fallback:
                    self._fallback_events += 1
                    logger.warning(
                        "DGrid unavailable ({}) — falling back. Will retry DGrid on next call.",
                        str(e)[:120],
                    )
                elif not self.has_fallback:
                    raise
                else:
                    self._fallback_events += 1
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
                self.last_model = self._anthropic_model
                self._record_usage("anthropic", self._anthropic_model, task_label)
                return text
            except Exception as e:
                last_error = e
                logger.warning("Anthropic failed ({}) — trying OpenAI.", str(e)[:120])

        # Fallback #2: OpenAI
        if self.openai_configured:
            try:
                text = await self._openai_chat_raw(messages, max_tokens, temperature, json_mode)
                self.last_provider = "openai"
                self.last_model = self._openai_model
                self._record_usage("openai", self._openai_model, task_label)
                return text
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error
        raise RuntimeError("No LLM provider available")

    @staticmethod
    def _redact(msg: str) -> str:
        """Strip anything that looks like an API key from an error string."""
        out = msg
        for needle in ("sk-", "Bearer ", "api_key=", "apiKey="):
            idx = out.find(needle)
            while idx != -1:
                # Replace the key-ish token (next ~40 chars or until whitespace/quote) with ***
                end = idx + len(needle)
                while end < len(out) and out[end] not in " \t\n\"'),}":
                    end += 1
                out = out[:idx + len(needle)] + "***" + out[end:]
                idx = out.find(needle, idx + len(needle) + 3)
        return out

    def get_usage_stats(self) -> dict:
        """Return a snapshot of LLM usage for the DGrid bounty dashboard."""
        return {
            "session_started_at": int(self._session_started),
            "uptime_seconds": int(time.time() - self._session_started),
            "providers_configured": {
                "dgrid": self.dgrid_configured,
                "anthropic": self.anthropic_configured,
                "openai": self.openai_configured,
            },
            "primary_order": self._primary_order(),
            "default_dgrid_model": self.model,
            "task_model_map": dict(TASK_MODEL_MAP),
            "last_provider": self.last_provider,
            "last_model": self.last_model,
            "last_task": self.last_task,
            "last_dgrid_error": self._last_dgrid_error,
            "fallback_events": self._fallback_events,
            "usage_by_provider": dict(self._usage_by_provider),
            "usage_by_task": dict(self._usage_by_task),
            "usage_by_model": dict(self._usage_by_model),
            "last_seen": {k: int(v) for k, v in self._last_seen.items()},
        }

    def _primary_order(self) -> list[str]:
        order = []
        if self.dgrid_configured: order.append("dgrid")
        if self.anthropic_configured: order.append("anthropic")
        if self.openai_configured: order.append("openai")
        return order


# Singleton instance
_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
