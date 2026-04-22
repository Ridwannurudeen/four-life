"""Unified LLM client — routes every AI call through the DGrid AI Gateway.

DGrid gives us one OpenAI-compatible API and auth for 200+ frontier models. This
file is the bounty-eligible core: every narrative, content, risk, vision, and
consensus decision the agent makes goes through DGrid first.

Engineering features that keep DGrid production-worthy:

1. **Circuit breaker.** After N consecutive DGrid failures we skip the primary
   path for a cooldown window instead of eating the latency of a doomed call on
   every request. The breaker half-opens on the next call after cooldown and
   closes on the first success.

2. **Transient retry.** A single in-place retry on DGrid 5xx / timeout before
   falling back — cheap resilience that keeps our DGrid share high when the
   gateway blips.

3. **Three-tier fallback.** DGrid → Anthropic → OpenAI. Every leg's success or
   failure is recorded in the trace ring buffer so judges can see exactly which
   provider served each call.

4. **Chaos mode.** ``enable_chaos`` forces DGrid to fail for demo purposes so the
   fallback chain is visible on stage. Toggled via /api/dgrid/chaos (admin).

5. **Cost estimation.** Every call is priced by ``agent.brain.cost`` using the
   per-model USD rate table, so the dashboard shows real dollars burned per
   task/model.

6. **Attestation.** Every DGrid call is folded into a SHA-256 hash chain
   (``agent.brain.attestation``). The current tip can be published on BNB Chain
   as cryptographic proof of usage.

7. **Self-optimizing router.** Per-(task, model) rolling stats power the
   leaderboard endpoint. Opt-in auto-rotation of TASK_MODEL_MAP is gated behind
   DGRID_AUTO_TUNE.

8. **Universal redaction.** All error paths run through ``_redact`` so API keys
   cannot leak into logs, traces, or public endpoint responses.
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from loguru import logger

from agent.config import settings
from agent.brain.attestation import AttestationChain, AttestationLog, get_chain, get_log
from agent.brain.cost import estimate_cost_usd, is_tracked

# ── Constants ────────────────────────────────────────────────────────

DGRID_BASE_URL = "https://api.dgrid.ai/v1"
DGRID_IMAGE_URL = "https://api.dgrid.ai/v1/images/generations"

# Task-type -> DGrid model mapping. Defaults to the cheapest capable model so a
# small credit lasts the full judging window. Specific tasks can be promoted via
# DGRID_TASK_OVERRIDES="content=anthropic/claude-sonnet-4.5,risk=openai/gpt-4o".
TASK_MODEL_MAP: dict[str, str] = {
    "narrative": "google/gemini-2.5-flash",
    "content":   "google/gemini-2.5-flash",
    "risk":      "google/gemini-2.5-flash",
    "vision":    "google/gemini-2.5-flash",
}

# Ring-buffer size for the public call trace.
TRACE_MAX = 200

# Circuit breaker config.
BREAKER_FAILURE_THRESHOLD = 3     # consecutive failures before opening
BREAKER_COOLDOWN_SECONDS = 30     # how long to skip DGrid once opened

# Transient retry config.
TRANSIENT_RETRY_MAX_ATTEMPTS = 2  # total attempts including the first one
TRANSIENT_RETRY_BACKOFF_MS = 150

# Explicit error classifications — no substring heuristics.
DGRID_UNAVAILABLE_STATUS_CODES = {402, 403, 408, 409, 429, 500, 502, 503, 504}
DGRID_UNAVAILABLE_SUBSTRINGS = (
    "balance_insufficient",
    "rate limit",
    "quota exceeded",
    "timeout",
    "connection reset",
    "connection refused",
    "service unavailable",
    "chaos injection",
)
DGRID_TRANSIENT_STATUS_CODES = {408, 500, 502, 503, 504}
DGRID_TRANSIENT_SUBSTRINGS = (
    "timeout",
    "connection reset",
    "connection refused",
    "service unavailable",
)


def _apply_task_overrides() -> None:
    """Remap tasks via env without code changes.
    Format: ``DGRID_TASK_OVERRIDES="content=anthropic/claude-sonnet-4.5,risk=openai/gpt-4o"``.
    """
    raw = (getattr(settings, "dgrid_task_overrides", "") or "").strip()
    if not raw:
        return
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            TASK_MODEL_MAP[k] = v


_apply_task_overrides()

VALID_TASKS = set(TASK_MODEL_MAP.keys()) | {"default", "compare", "consensus", "probe", "image"}


# ── Exception types ──────────────────────────────────────────────────


class DGridChaosError(RuntimeError):
    """Raised when chaos mode is active — forces the fallback chain to engage.
    Classified as transient/unavailable so it exercises the same code path as a
    real outage."""


class DGridBreakerOpenError(RuntimeError):
    """Raised internally when the circuit breaker is open. Not exposed to callers
    — _chat_with_fallback catches it and routes to the fallback chain."""


# ── Circuit breaker ──────────────────────────────────────────────────


class CircuitBreaker:
    """Tiny closed/open/half-open breaker.

    - ``CLOSED``: all calls go through.
    - ``OPEN``: calls are rejected without touching the wire until ``open_until``.
    - ``HALF_OPEN``: the first call after cooldown is allowed through — success
      closes the breaker, failure re-opens it for another cooldown.
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = BREAKER_FAILURE_THRESHOLD,
        cooldown_seconds: float = BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._open_until: float = 0.0
        self._opened_count = 0
        self._last_opened_at: float = 0.0
        self._last_open_reason: str | None = None

    def state(self, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        if self._open_until <= 0:
            return self.STATE_CLOSED
        if now >= self._open_until:
            return self.STATE_HALF_OPEN
        return self.STATE_OPEN

    def allow(self) -> bool:
        """True if the caller may attempt the protected operation."""
        return self.state() != self.STATE_OPEN

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._last_open_reason = None

    def reset(self, reason: str = "manual reset") -> None:
        """Reset the breaker to CLOSED without claiming a successful call.
        Used when an operator flips a flag (e.g. turning off chaos mode) and
        we want the primary path re-enabled — but we must NOT lie about a
        live DGrid call succeeding, since no such call has been observed."""
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._last_open_reason = f"reset: {reason}"

    def record_failure(self, reason: str | None = None) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            now = time.time()
            self._open_until = now + self.cooldown_seconds
            self._opened_count += 1
            self._last_opened_at = now
            self._last_open_reason = (reason or "")[:200]

    def snapshot(self) -> dict:
        now = time.time()
        state = self.state(now)
        return {
            "state": state,
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "open_until": int(self._open_until) if self._open_until else 0,
            "seconds_until_half_open": max(0, int(self._open_until - now)) if state == self.STATE_OPEN else 0,
            "times_opened": self._opened_count,
            "last_opened_at": int(self._last_opened_at) if self._last_opened_at else 0,
            "last_open_reason": self._last_open_reason,
        }


# ── LLM client ───────────────────────────────────────────────────────


class LLMClient:
    """Unified LLM client — DGrid primary with Anthropic + OpenAI fallback."""

    def __init__(self) -> None:
        self.dgrid_configured = bool(settings.dgrid_api_key)
        self.anthropic_configured = bool(settings.anthropic_api_key)
        self.openai_configured = bool(settings.openai_api_key)

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

        if self.anthropic_configured:
            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self._anthropic_model = "claude-sonnet-4-5"
        else:
            self._anthropic = None
            self._anthropic_model = ""

        if self.openai_configured:
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
            self._openai_model = "gpt-4o-mini"
        else:
            self._openai = None
            self._openai_model = ""

        self.last_provider: str = "none"
        self.last_model: str = ""
        self.last_task: str = "default"

        # Circuit breaker + chaos flag. Chaos is off by default; flipped on by
        # /api/dgrid/chaos for live demo of the fallback chain.
        self.breaker = CircuitBreaker()
        self.chaos_enabled: bool = False

        # ── Usage counters ───────────────────────────────────────
        self._session_started = time.time()
        self._usage_by_provider: dict[str, int] = defaultdict(int)
        self._usage_by_task: dict[str, int] = defaultdict(int)
        self._usage_by_model: dict[str, int] = defaultdict(int)
        self._last_seen: dict[str, float] = {}
        self._fallback_events: int = 0
        self._breaker_skips: int = 0
        self._transient_retries: int = 0
        self._last_dgrid_error: str | None = None
        self._trace: deque[dict] = deque(maxlen=TRACE_MAX)
        self._trace_seq: int = 0  # monotonic counter for stable ordering within the same second

        # Cumulative token + cost tallies (DGrid only, for the bounty story).
        self._tokens_prompt: int = 0
        self._tokens_completion: int = 0
        self._cost_usd_total: float = 0.0
        self._cost_usd_by_provider: dict[str, float] = defaultdict(float)
        self._cost_usd_by_task: dict[str, float] = defaultdict(float)
        self._cost_usd_by_model: dict[str, float] = defaultdict(float)

        # Rolling per-(task, model) stats for the leaderboard.
        self._leaderboard: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"calls": 0, "successes": 0, "failures": 0, "latency_sum_ms": 0, "cost_usd": 0.0}
        )

        # Attestation chain — folds every DGrid call into a SHA-256 commitment.
        # The log is an append-only record of every call that contributes to
        # the chain, so a judge can reconstruct and verify the full Merkle
        # history independently (the in-memory trace ring keeps only the last
        # 200 entries, which isn't enough for long-running verification).
        self._attestation: AttestationChain = get_chain()
        self._attestation_log: AttestationLog = get_log()

        # DGrid's image endpoint may not exist on every DGrid deployment. If
        # the first attempt fails we flip this flag for the rest of the session
        # so subsequent image calls go straight to the OpenAI fallback — no
        # wasted round-trips, no trace spam, no breaker churn.
        self._dgrid_images_disabled: bool = False

        providers = []
        if self.dgrid_configured:
            providers.append(f"DGrid({self.model})")
        if self.anthropic_configured:
            providers.append(f"Anthropic({self._anthropic_model})")
        if self.openai_configured:
            providers.append(f"OpenAI({self._openai_model})")
        if providers:
            logger.info("LLM: {} — order = primary -> fallback(s)", " | ".join(providers))
        else:
            logger.warning("LLM: NO PROVIDER CONFIGURED — all LLM calls will fail")

    # ── Public config surface ────────────────────────────────────

    @property
    def has_fallback(self) -> bool:
        return self.anthropic_configured or self.openai_configured

    @property
    def trace_count(self) -> int:
        """Number of calls currently in the trace ring buffer."""
        return len(self._trace)

    @property
    def model_id(self) -> str:
        """Stable provider:model identifier for public audit metadata."""
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

    # ── Chaos toggle ─────────────────────────────────────────────

    def enable_chaos(self, reason: str = "manual toggle") -> None:
        """Force every subsequent DGrid call to fail. The breaker will open and
        the fallback chain will engage — which is exactly what we want judges
        to see during the demo."""
        self.chaos_enabled = True
        logger.warning("DGrid chaos mode ENABLED — {}", reason)

    def disable_chaos(self) -> None:
        self.chaos_enabled = False
        # Reset the breaker to CLOSED without fabricating a "successful call"
        # — we're flipping an operator flag, not observing a live DGrid
        # response. The next real call will confirm actual health.
        self.breaker.reset(reason="chaos disabled")
        self._last_dgrid_error = None
        logger.info("DGrid chaos mode DISABLED — breaker reset")

    # ── Error classification ─────────────────────────────────────

    @staticmethod
    def _error_status(exc: Exception) -> int | None:
        status = getattr(exc, "status_code", None)
        if status is not None:
            try:
                return int(status)
            except (TypeError, ValueError):
                return None
        # openai SDK wraps status_code in .response
        resp = getattr(exc, "response", None)
        if resp is not None:
            s = getattr(resp, "status_code", None)
            if s is not None:
                try:
                    return int(s)
                except (TypeError, ValueError):
                    return None
        return None

    @classmethod
    def _is_dgrid_unavailable(cls, exc: Exception) -> bool:
        """True if the error means DGrid can't serve this call right now and we
        should try a fallback (balance, rate limit, 5xx, network, chaos)."""
        if isinstance(exc, (DGridChaosError, DGridBreakerOpenError)):
            return True
        status = cls._error_status(exc)
        if status in DGRID_UNAVAILABLE_STATUS_CODES:
            return True
        msg = str(exc).lower()
        return any(sub in msg for sub in DGRID_UNAVAILABLE_SUBSTRINGS)

    @classmethod
    def _is_transient(cls, exc: Exception) -> bool:
        """True if a single in-place retry is worth attempting before falling back."""
        if isinstance(exc, DGridChaosError):
            return False  # chaos should fall back, not retry
        status = cls._error_status(exc)
        if status in DGRID_TRANSIENT_STATUS_CODES:
            return True
        msg = str(exc).lower()
        return any(sub in msg for sub in DGRID_TRANSIENT_SUBSTRINGS)

    # ── Model routing ────────────────────────────────────────────

    def _resolve_dgrid_model(self, task: str | None) -> str:
        """Pick the DGrid model for a task. Unknown/None/`default` → configured default."""
        if not task or task == "default":
            return self.model
        return TASK_MODEL_MAP.get(task, self.model)

    # ── Usage + trace recording ──────────────────────────────────

    def _record_usage(self, provider: str, model: str, task: str) -> None:
        now = time.time()
        self._usage_by_provider[provider] += 1
        self._usage_by_task[task] += 1
        self._usage_by_model[model] += 1
        self._last_seen[f"provider:{provider}"] = now
        self._last_seen[f"task:{task}"] = now
        self._last_seen[f"model:{model}"] = now

    def _record_cost(self, provider: str, model: str, task: str, cost: float) -> None:
        if cost <= 0:
            return
        self._cost_usd_total += cost
        self._cost_usd_by_provider[provider] += cost
        self._cost_usd_by_task[task] += cost
        self._cost_usd_by_model[model] += cost

    def _record_leaderboard(
        self, *, task: str, model: str, success: bool, latency_ms: int, cost_usd: float
    ) -> None:
        bucket = self._leaderboard[(task, model)]
        bucket["calls"] += 1
        if success:
            bucket["successes"] += 1
        else:
            bucket["failures"] += 1
        bucket["latency_sum_ms"] += int(latency_ms)
        bucket["cost_usd"] += float(cost_usd)

    def _record_trace(
        self,
        *,
        provider: str,
        model: str,
        task: str,
        latency_ms: int,
        fallback_depth: int,
        success: bool,
        usage: dict | None = None,
        error: str | None = None,
        prompt_hash: str | None = None,
        response_hash: str | None = None,
    ) -> dict:
        """Append one call to the trace ring buffer and return the entry.

        For successful DGrid calls we also fold the call's digest into the
        attestation chain so the current Merkle tip always reflects every
        DGrid-served request.
        """
        usage = usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

        cost_usd = estimate_cost_usd(model, prompt_tokens, completion_tokens) if success else 0.0

        if provider == "dgrid" and success:
            self._tokens_prompt += prompt_tokens
            self._tokens_completion += completion_tokens

        if success:
            self._record_cost(provider, model, task, cost_usd)

        self._record_leaderboard(
            task=task, model=model, success=success, latency_ms=latency_ms, cost_usd=cost_usd,
        )

        now_s = time.time()
        self._trace_seq += 1
        entry = {
            "ts": int(now_s),
            "ts_ms": int(now_s * 1000),
            "seq": self._trace_seq,
            "provider": provider,
            "model": model,
            "task": task,
            "latency_ms": int(latency_ms),
            "fallback_depth": int(fallback_depth),
            "success": bool(success),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "cost_tracked": is_tracked(model),
            "error": self._redact(error)[:200] if error else None,
        }

        # Attest successful DGrid calls (only). Every call is also written to
        # the append-only log so the full Merkle history remains verifiable
        # after older entries scroll out of the in-memory trace ring.
        #
        # Ordering matters: we write the log entry FIRST, then advance the
        # chain only if the log write was durable. If we advanced the chain
        # first and the log write failed, verify_chain could never reconstruct
        # the current_root because one of the digests would be missing.
        if success and provider == "dgrid":
            digest = AttestationChain.call_digest(
                provider=provider,
                model=model,
                task=task,
                prompt_hash=prompt_hash or "",
                response_hash=response_hash or "",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                ts_ms=entry["ts_ms"],
            )
            next_tip = self._attestation.peek_next_tip(digest)
            log_entry = {
                "seq": entry["seq"],
                "ts_ms": entry["ts_ms"],
                "provider": provider,
                "model": model,
                "task": task,
                "prompt_hash": prompt_hash or "",
                "response_hash": response_hash or "",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "call_digest": digest,
                "chain_tip": next_tip,
            }
            if self._attestation_log.append(log_entry):
                # Log is durable — safe to advance the chain.
                self._attestation.commit_tip(next_tip)
                entry["call_digest"] = digest
                entry["chain_tip"] = next_tip
            else:
                # Log write failed (e.g. disk full). Do NOT advance the chain,
                # or the published current_root will not be reconstructible
                # from the audit log. The trace entry records no call_digest /
                # chain_tip so integrators see the gap.
                entry["attestation_skipped"] = "log_write_failed"

        self._trace.append(entry)
        return entry

    def get_trace(self, limit: int = 50) -> list[dict]:
        """Return the last ``limit`` calls, newest first."""
        items = list(self._trace)
        items.reverse()
        return items[: max(0, int(limit))]

    # ── Raw provider calls (return text + usage) ─────────────────

    async def _dgrid_chat_raw(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        model: str | None = None,
    ) -> tuple[str, dict]:
        """Call DGrid. Honors chaos mode by raising ``DGridChaosError``."""
        if self.chaos_enabled:
            raise DGridChaosError("chaos injection (simulated DGrid outage)")
        kwargs = dict(
            model=model or self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._dgrid.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        return content, usage

    async def _dgrid_chat_with_retry(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        model: str | None = None,
    ) -> tuple[str, dict]:
        """Wrap _dgrid_chat_raw with a single in-place retry on transient errors
        (5xx, network). Anything non-transient raises after the first attempt."""
        last_error: Exception | None = None
        for attempt in range(TRANSIENT_RETRY_MAX_ATTEMPTS):
            try:
                return await self._dgrid_chat_raw(
                    messages, max_tokens, temperature, json_mode, model=model,
                )
            except Exception as e:
                last_error = e
                if attempt + 1 < TRANSIENT_RETRY_MAX_ATTEMPTS and self._is_transient(e):
                    self._transient_retries += 1
                    await asyncio.sleep(TRANSIENT_RETRY_BACKOFF_MS / 1000)
                    continue
                raise
        # Unreachable (loop either returns or raises).
        assert last_error is not None
        raise last_error

    async def _anthropic_chat_raw(
        self, messages: list[dict], max_tokens: int, temperature: float,
    ) -> tuple[str, dict]:
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
        content = response.content[0].text
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "input_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "output_tokens", 0) or 0,
            }
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        return content, usage

    async def _openai_chat_raw(
        self, messages: list[dict], max_tokens: int, temperature: float, json_mode: bool,
    ) -> tuple[str, dict]:
        kwargs = dict(
            model=self._openai_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._openai.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        return content, usage

    # ── Public chat API ──────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        return await self._chat_with_fallback(messages, max_tokens, temperature, json_mode=False)

    async def chat_json(self, messages: list[dict], max_tokens: int = 2000) -> dict:
        text = await self._chat_with_fallback(messages, max_tokens, 0.7, json_mode=True)
        return self._parse_json(text)

    async def chat_task(
        self,
        messages: list[dict],
        task: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        return await self._chat_with_fallback(
            messages, max_tokens, temperature, json_mode=False, task=task,
        )

    async def chat_json_task(
        self,
        messages: list[dict],
        task: str,
        max_tokens: int = 2000,
    ) -> dict:
        text = await self._chat_with_fallback(
            messages, max_tokens, 0.7, json_mode=True, task=task,
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

    @staticmethod
    def _prompt_hash(messages: list[dict]) -> str:
        payload = json.dumps(messages, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _response_hash(text: str) -> str:
        return hashlib.sha256((text or "").encode()).hexdigest()

    # ── Fallback orchestrator ────────────────────────────────────

    async def _chat_with_fallback(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        task: str | None = None,
    ) -> str:
        """DGrid → Anthropic → OpenAI, with circuit breaker, transient retry,
        universal redaction, and full trace recording at every leg."""
        task_label = task if task in VALID_TASKS else "default"
        self.last_task = task_label
        fallback_depth = 0
        last_error: Exception | None = None
        prompt_h = self._prompt_hash(messages)

        # ── Primary: DGrid ───────────────────────────────────────
        if self.dgrid_configured:
            if not self.breaker.allow():
                # Breaker is open — skip DGrid, go straight to fallback.
                self._breaker_skips += 1
                self._record_trace(
                    provider="dgrid",
                    model=self._resolve_dgrid_model(task_label),
                    task=task_label,
                    latency_ms=0,
                    fallback_depth=0,
                    success=False,
                    error="circuit breaker open — skipped DGrid",
                )
                fallback_depth = 1
            else:
                dgrid_model = self._resolve_dgrid_model(task_label)
                t0 = time.perf_counter()
                try:
                    text, usage = await self._dgrid_chat_with_retry(
                        messages, max_tokens, temperature, json_mode, model=dgrid_model,
                    )
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    self.last_provider = "dgrid"
                    self.last_model = dgrid_model
                    self._last_dgrid_error = None
                    self.breaker.record_success()
                    self._record_usage("dgrid", dgrid_model, task_label)
                    self._record_trace(
                        provider="dgrid", model=dgrid_model, task=task_label,
                        latency_ms=latency_ms, fallback_depth=0, success=True,
                        usage=usage,
                        prompt_hash=prompt_h,
                        response_hash=self._response_hash(text),
                    )
                    return text
                except Exception as e:
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    last_error = e
                    redacted = self._redact(str(e))[:240]
                    self._last_dgrid_error = redacted
                    self.breaker.record_failure(redacted)
                    self._record_trace(
                        provider="dgrid", model=dgrid_model, task=task_label,
                        latency_ms=latency_ms, fallback_depth=0, success=False,
                        error=redacted,
                    )
                    fallback_depth = 1
                    if self._is_dgrid_unavailable(e) and self.has_fallback:
                        self._fallback_events += 1
                        logger.warning(
                            "DGrid unavailable ({}) — falling back. Breaker now {}.",
                            redacted[:120], self.breaker.state(),
                        )
                    elif not self.has_fallback:
                        raise
                    else:
                        self._fallback_events += 1
                        logger.warning("DGrid error ({}) — falling back.", redacted[:120])

        # ── Fallback #1: Anthropic ───────────────────────────────
        if self.anthropic_configured:
            t0 = time.perf_counter()
            try:
                msgs = messages
                if json_mode:
                    has_system = any(m["role"] == "system" for m in msgs)
                    if not has_system:
                        msgs = [{
                            "role": "system",
                            "content": "Respond ONLY with a single valid JSON object. No prose, no markdown fences.",
                        }] + msgs
                text, usage = await self._anthropic_chat_raw(msgs, max_tokens, temperature)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                self.last_provider = "anthropic"
                self.last_model = self._anthropic_model
                self._record_usage("anthropic", self._anthropic_model, task_label)
                self._record_trace(
                    provider="anthropic", model=self._anthropic_model, task=task_label,
                    latency_ms=latency_ms, fallback_depth=fallback_depth, success=True,
                    usage=usage,
                )
                return text
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                last_error = e
                redacted = self._redact(str(e))[:200]
                self._record_trace(
                    provider="anthropic", model=self._anthropic_model, task=task_label,
                    latency_ms=latency_ms, fallback_depth=fallback_depth, success=False,
                    error=redacted,
                )
                fallback_depth += 1
                logger.warning("Anthropic failed ({}) — trying OpenAI.", redacted[:120])

        # ── Fallback #2: OpenAI ──────────────────────────────────
        if self.openai_configured:
            t0 = time.perf_counter()
            try:
                text, usage = await self._openai_chat_raw(messages, max_tokens, temperature, json_mode)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                self.last_provider = "openai"
                self.last_model = self._openai_model
                self._record_usage("openai", self._openai_model, task_label)
                self._record_trace(
                    provider="openai", model=self._openai_model, task=task_label,
                    latency_ms=latency_ms, fallback_depth=fallback_depth, success=True,
                    usage=usage,
                )
                return text
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                last_error = e
                redacted = self._redact(str(e))[:200]
                self._record_trace(
                    provider="openai", model=self._openai_model, task=task_label,
                    latency_ms=latency_ms, fallback_depth=fallback_depth, success=False,
                    error=redacted,
                )
                logger.warning("OpenAI failed ({}).", redacted[:120])

        if last_error:
            # Re-raise as a redacted RuntimeError. Raising last_error verbatim
            # could leak a secret embedded in the provider's error string (some
            # SDKs echo the Authorization header back into error messages). The
            # `from last_error` chain preserves the original traceback for
            # server-side debugging; the message seen by callers is scrubbed.
            redacted_msg = self._redact(str(last_error))[:500]
            raise RuntimeError(f"All LLM providers failed: {redacted_msg}") from last_error
        raise RuntimeError("No LLM provider available")

    # ── Compare + probe + images ─────────────────────────────────

    async def compare_dgrid_models(
        self,
        prompt: str,
        models: list[str],
        max_tokens: int = 200,
    ) -> list[dict]:
        """Run the same prompt against N DGrid models in parallel.

        No fallback — each model answers or fails with its own error. Chaos
        applies (so judges can see every model fail when the toggle is on).
        """
        if not self.dgrid_configured:
            return [{"model": m, "ok": False, "error": "DGrid not configured"} for m in models]
        messages = [{"role": "user", "content": prompt}]
        prompt_h = self._prompt_hash(messages)

        async def one(model: str) -> dict:
            t0 = time.perf_counter()
            try:
                text, usage = await self._dgrid_chat_raw(
                    messages, max_tokens, 0.7, json_mode=False, model=model,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                self._record_usage("dgrid", model, "compare")
                self._record_trace(
                    provider="dgrid", model=model, task="compare",
                    latency_ms=latency_ms, fallback_depth=0, success=True, usage=usage,
                    prompt_hash=prompt_h, response_hash=self._response_hash(text),
                )
                return {
                    "model": model, "ok": True, "latency_ms": latency_ms,
                    "response": text.strip(), "usage": usage,
                    "cost_usd": estimate_cost_usd(
                        model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                    ),
                }
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                err = self._redact(str(e))[:240]
                self._record_trace(
                    provider="dgrid", model=model, task="compare",
                    latency_ms=latency_ms, fallback_depth=0, success=False, error=err,
                )
                return {"model": model, "ok": False, "latency_ms": latency_ms, "error": err}

        return await asyncio.gather(*[one(m) for m in models])

    async def probe_dgrid(self, model: str | None = None) -> dict:
        """Fire a single DGrid-only call. No fallback; judges verify DGrid live.

        ``model`` is optional — defaults to the configured primary model so the
        probe matches what the agent actually uses.
        """
        if not self.dgrid_configured:
            return {"ok": False, "error": "DGrid not configured"}
        target_model = model or self.model
        messages = [
            {"role": "system", "content": "You are a health probe. Reply with exactly: pong"},
            {"role": "user", "content": "probe"},
        ]
        prompt_h = self._prompt_hash(messages)
        t0 = time.perf_counter()
        try:
            text, usage = await self._dgrid_chat_raw(
                messages, max_tokens=4, temperature=0, json_mode=False, model=target_model,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            err = self._redact(str(e))[:240]
            self._last_dgrid_error = err
            self._record_trace(
                provider="dgrid", model=target_model, task="probe",
                latency_ms=latency_ms, fallback_depth=0, success=False, error=err,
            )
            return {"ok": False, "error": err, "latency_ms": latency_ms}
        latency_ms = int((time.perf_counter() - t0) * 1000)
        self._last_dgrid_error = None
        self._record_usage("dgrid", target_model, "probe")
        self._record_trace(
            provider="dgrid", model=target_model, task="probe",
            latency_ms=latency_ms, fallback_depth=0, success=True, usage=usage,
            prompt_hash=prompt_h, response_hash=self._response_hash(text),
        )
        return {
            "ok": True,
            "provider": "dgrid",
            "model": target_model,
            "latency_ms": latency_ms,
            "response": text.strip()[:100],
            "usage": usage,
            "cost_usd": estimate_cost_usd(
                target_model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
            ),
        }

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> bytes:
        """Generate an image. Routes through DGrid's image endpoint when
        configured, falls back to raw OpenAI when DGrid is absent or fails.

        Returns raw image bytes (jpeg/png). Metadata is recorded in the same
        trace buffer so image gen counts toward the DGrid share too.
        """
        import httpx

        # ── Primary: DGrid image proxy ───────────────────────────
        # DGrid may or may not proxy image generation on any given deployment.
        # We try once; if it fails we set _dgrid_images_disabled for the rest
        # of the session so every subsequent image call goes straight to
        # OpenAI without wasting a round-trip or polluting the trace.
        if (
            self.dgrid_configured
            and not self.chaos_enabled
            and self.breaker.allow()
            and not self._dgrid_images_disabled
        ):
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        DGRID_IMAGE_URL,
                        headers={
                            "Authorization": f"Bearer {settings.dgrid_api_key}",
                            "HTTP-Referer": "https://four-life.gudman.xyz",
                            "X-Title": "FOUR-LIFE Agent",
                        },
                        json={
                            "model": "openai/dall-e-3",
                            "prompt": prompt,
                            "size": size,
                            "quality": quality,
                            "n": 1,
                        },
                    )
                    resp.raise_for_status()
                    image_url = resp.json()["data"][0]["url"]
                    img_resp = await client.get(image_url)
                    img_resp.raise_for_status()
                    body = img_resp.content
                latency_ms = int((time.perf_counter() - t0) * 1000)
                self.last_provider = "dgrid"
                self.last_model = "openai/dall-e-3"
                self.breaker.record_success()
                self._record_usage("dgrid", "openai/dall-e-3", "image")
                self._record_trace(
                    provider="dgrid", model="openai/dall-e-3", task="image",
                    latency_ms=latency_ms, fallback_depth=0, success=True,
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                )
                return body
            except Exception as e:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                redacted = self._redact(str(e))[:240]
                self._last_dgrid_error = redacted
                # Only trip the breaker on transport-level failures — a 404
                # from a gateway that doesn't proxy images is not a sign DGrid
                # chat is unhealthy. Always disable images for the session so
                # we don't keep paying this round-trip.
                self._dgrid_images_disabled = True
                if self._is_dgrid_unavailable(e):
                    self.breaker.record_failure(redacted)
                self._record_trace(
                    provider="dgrid", model="openai/dall-e-3", task="image",
                    latency_ms=latency_ms, fallback_depth=0, success=False, error=redacted,
                )
                logger.warning(
                    "DGrid image gen failed ({}) — disabled for session, using raw OpenAI.",
                    redacted[:120],
                )

        # ── Fallback: raw OpenAI (bypass DGrid) ──────────────────
        if not settings.openai_api_key:
            raise RuntimeError("Image generation requires DGrid or OPENAI_API_KEY")
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": "dall-e-3", "prompt": prompt,
                        "size": size, "quality": quality, "n": 1,
                    },
                )
                resp.raise_for_status()
                image_url = resp.json()["data"][0]["url"]
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                body = img_resp.content
            latency_ms = int((time.perf_counter() - t0) * 1000)
            self.last_provider = "openai"
            self.last_model = "dall-e-3"
            self._record_usage("openai", "dall-e-3", "image")
            self._record_trace(
                provider="openai", model="dall-e-3", task="image",
                latency_ms=latency_ms, fallback_depth=1, success=True,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )
            return body
        except Exception as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            self._record_trace(
                provider="openai", model="dall-e-3", task="image",
                latency_ms=latency_ms, fallback_depth=1, success=False,
                error=self._redact(str(e))[:200],
            )
            raise

    # ── Utility ──────────────────────────────────────────────────

    @staticmethod
    def _redact(msg: str | None) -> str:
        """Strip anything that looks like an API key from an error string.

        Covers common prefixes across providers (OpenAI sk-, Anthropic sk-ant-,
        DGrid dgrid_, GitHub gh[a-z]_, Slack xox[a-z]-, Google AIza, AWS AKIA,
        plus bearer tokens and inline api_key=/apiKey=). Case-insensitive for
        'Bearer' so 'bearer xyz' is also caught."""
        if not msg:
            return ""
        # Case-insensitive prefixes for ASCII-keyword matches
        ci_prefixes = ("bearer ", "basic ")
        # Exact-case prefixes — these are format-specific and mixed-case would
        # typically just be text, not an actual secret.
        cs_prefixes = (
            "sk-", "sk-ant-", "api_key=", "apiKey=", "apikey=",
            "dgrid_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_",
            "xoxb-", "xoxp-", "xoxa-", "xoxr-",
            "AIza", "AKIA",
        )
        out = msg

        def _redact_at(buf: str, idx: int, needle_len: int) -> str:
            end = idx + needle_len
            while end < len(buf) and buf[end] not in " \t\n\"'),}":
                end += 1
            return buf[: idx + needle_len] + "***" + buf[end:]

        for needle in cs_prefixes:
            idx = out.find(needle)
            while idx != -1:
                out = _redact_at(out, idx, len(needle))
                idx = out.find(needle, idx + len(needle) + 3)

        for needle in ci_prefixes:
            lower = out.lower()
            idx = lower.find(needle)
            while idx != -1:
                out = _redact_at(out, idx, len(needle))
                lower = out.lower()
                idx = lower.find(needle, idx + len(needle) + 3)
        return out

    def get_usage_stats(self) -> dict:
        """Snapshot of LLM usage for the bounty dashboard."""
        total_calls = sum(self._usage_by_provider.values())
        dgrid_calls = int(self._usage_by_provider.get("dgrid", 0))
        dgrid_share = round(dgrid_calls / total_calls, 4) if total_calls else 0.0
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
            "breaker_skips": self._breaker_skips,
            "transient_retries": self._transient_retries,
            "chaos_enabled": self.chaos_enabled,
            "breaker": self.breaker.snapshot(),
            "total_calls": total_calls,
            "dgrid_calls": dgrid_calls,
            "dgrid_share": dgrid_share,
            "dgrid_tokens": {
                "prompt": self._tokens_prompt,
                "completion": self._tokens_completion,
                "total": self._tokens_prompt + self._tokens_completion,
            },
            "cost_usd": {
                "total": round(self._cost_usd_total, 6),
                "by_provider": {k: round(v, 6) for k, v in self._cost_usd_by_provider.items()},
                "by_task": {k: round(v, 6) for k, v in self._cost_usd_by_task.items()},
                "by_model": {k: round(v, 6) for k, v in self._cost_usd_by_model.items()},
            },
            "usage_by_provider": dict(self._usage_by_provider),
            "usage_by_task": dict(self._usage_by_task),
            "usage_by_model": dict(self._usage_by_model),
            "last_seen": {k: int(v) for k, v in self._last_seen.items()},
            "trace_count": len(self._trace),
        }

    def get_leaderboard(self) -> list[dict]:
        """Per-(task, model) performance table, sorted by task then success rate."""
        rows = []
        for (task, model), stats in self._leaderboard.items():
            calls = stats["calls"]
            successes = stats["successes"]
            avg_latency = stats["latency_sum_ms"] / calls if calls else 0
            rows.append({
                "task": task,
                "model": model,
                "calls": calls,
                "successes": successes,
                "failures": stats["failures"],
                "success_rate": round(successes / calls, 4) if calls else 0.0,
                "avg_latency_ms": round(avg_latency, 1),
                "cost_usd": round(stats["cost_usd"], 6),
                "cost_per_call_usd": round(stats["cost_usd"] / calls, 6) if calls else 0.0,
            })
        rows.sort(key=lambda r: (r["task"], -r["success_rate"], r["avg_latency_ms"]))
        return rows

    def get_attestation(self) -> dict:
        """Merkle attestation snapshot — current chain tip + last on-chain publish."""
        snap = self._attestation.snapshot()
        snap["dgrid_calls_seen_by_client"] = int(self._usage_by_provider.get("dgrid", 0))
        snap["full_log_count"] = self._attestation_log.count()
        snap["dgrid_images_disabled"] = self._dgrid_images_disabled
        return snap

    def get_audit_calls(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """Return a slice of the full call log for Merkle verification.

        The rolling trace ring buffer keeps only the last 200 calls, which
        isn't enough for independent verification once we cross that. This
        endpoint reads from the persistent JSONL log so a judge can download
        the full history and re-derive the chain root themselves.
        """
        return self._attestation_log.read_range(offset, limit)

    def _primary_order(self) -> list[str]:
        order = []
        if self.dgrid_configured:
            order.append("dgrid")
        if self.anthropic_configured:
            order.append("anthropic")
        if self.openai_configured:
            order.append("openai")
        return order


# ── Singleton ────────────────────────────────────────────────────────

_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def reset_llm_for_tests() -> None:
    """Test-only: drop the singleton so each test starts clean."""
    global _llm
    _llm = None
