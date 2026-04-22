"""Notification adapters — Telegram + Discord fan-out on tier/protection transitions.

These sit alongside outbound webhooks. The webhook pipeline delivers raw signed
FOUR-LIFE event JSON. Notifications format the same events into human-readable
messages and send them to consumer-friendly channels (Telegram chat, Discord webhook).

Config via environment (see `agent/config.py`):
    TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — channel enabled when both set
    DISCORD_WEBHOOK_URL                    — channel enabled when set

Transport is injectable so tests never hit the network. Failures are swallowed
and logged — notifications must never affect the core event pipeline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import httpx
from loguru import logger

from agent.config import settings


HTTP_TIMEOUT_SECONDS = 8


# ── Formatting helpers ────────────────────────────────────────────────

# FOUR-LIFE Certified tier labels, single-source-of-truth for message rendering.
_TIER_LABELS = {
    "graduated": "Graduated",
    "graduation_watch": "Graduation Watch",
    "healthy": "Healthy",
    "at_risk": "At Risk",
    "observed": "Observed",
}

_TIER_EMOJI = {
    "graduated": "🎓",
    "graduation_watch": "⚡",
    "healthy": "🌱",
    "at_risk": "🚨",
    "observed": "👁",
}

_LEVEL_EMOJI = {
    "critical": "🚨",
    "warn": "⚠️",
    "safe": "✅",
}


def _short_addr(addr: str) -> str:
    if not addr or len(addr) < 10:
        return addr or ""
    return f"{addr[:6]}…{addr[-4:]}"


def _tier_label(tier: str) -> str:
    return _TIER_LABELS.get(tier, tier)


@dataclass
class FormattedMessage:
    """Rendered message pair: one plain-text, one with markup for chat services."""
    text: str
    markdown: str


def format_tier_changed(event: dict) -> FormattedMessage:
    """Format a `badge.tier_changed` event for human-readable channels.

    Brand differs by ``tier_source``: "certified" (full on-chain data) → the
    headline reads "FOUR-LIFE Certified"; "radar_estimate" (public-ranking
    heuristic) → the headline reads "FOUR-LIFE Radar Estimate" so channel
    subscribers are never told a heuristic transition is Certified.
    """
    token = event.get("token_address") or ""
    frm = event.get("from_tier") or "—"
    to = event.get("to_tier") or "—"
    source = event.get("tier_source") or "certified"
    emoji = _TIER_EMOJI.get(to, "🔔")
    short = _short_addr(token)
    link = f"https://four-life.gudman.xyz/radar?token={token}"
    brand = "FOUR-LIFE Certified" if source == "certified" else "FOUR-LIFE Radar Estimate"

    plain = (
        f"{emoji} {brand} — {_tier_label(frm)} → {_tier_label(to)}\n"
        f"Token: {short}\n"
        f"{link}"
    )
    md = (
        f"{emoji} *{brand}* — _{_tier_label(frm)}_ → *{_tier_label(to)}*\n"
        f"Token: `{short}`\n"
        f"[Open on Radar]({link})"
    )
    return FormattedMessage(text=plain, markdown=md)


def format_protection_level_changed(event: dict) -> FormattedMessage:
    """Format a `protection.level_changed` event for human-readable channels."""
    token = event.get("token_address") or ""
    frm = event.get("from_level") or "—"
    to = event.get("to_level") or "—"
    emoji = _LEVEL_EMOJI.get(to, "🔔")
    short = _short_addr(token)
    link = f"https://four-life.gudman.xyz/radar?token={token}"
    rules = event.get("fired_rules") or []
    rule_summary = ", ".join(r.get("rule", "?") for r in rules[:3]) or "—"

    plain = (
        f"{emoji} Protection Mode — {frm} → {to}\n"
        f"Token: {short}\n"
        f"Rules: {rule_summary}\n"
        f"{link}"
    )
    md = (
        f"{emoji} *Protection Mode* — _{frm}_ → *{to}*\n"
        f"Token: `{short}`\n"
        f"Rules: `{rule_summary}`\n"
        f"[Open on Radar]({link})"
    )
    return FormattedMessage(text=plain, markdown=md)


FORMATTERS: dict[str, Callable[[dict], FormattedMessage]] = {
    "badge.tier_changed": format_tier_changed,
    "protection.level_changed": format_protection_level_changed,
}


# ── Transport abstraction ─────────────────────────────────────────────

# Tests inject this. Default is a real httpx client.
_TRANSPORT_OVERRIDE: Callable[..., Any] | None = None


def set_transport_override(fn: Callable[..., Any] | None) -> None:
    global _TRANSPORT_OVERRIDE
    _TRANSPORT_OVERRIDE = fn


async def _post_json(url: str, payload: dict) -> tuple[int, str]:
    if _TRANSPORT_OVERRIDE is not None:
        return await _TRANSPORT_OVERRIDE(url, payload)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, json=payload)
        return resp.status_code, resp.text[:1000]


# ── Channels ──────────────────────────────────────────────────────────

class NotificationChannel:
    """Base class. Subclasses format + send for a specific channel."""

    name: str = "channel"
    enabled: bool = False

    async def send_event(self, event_type: str, event: dict) -> bool:
        """Format the event and send. Returns True on success."""
        formatter = FORMATTERS.get(event_type)
        if formatter is None or not self.enabled:
            return False
        msg = formatter(event)
        try:
            return await self._send(msg)
        except Exception as e:
            logger.warning("[{}] notification send failed: {}", self.name, e)
            return False

    async def _send(self, msg: FormattedMessage) -> bool:
        raise NotImplementedError


class TelegramChannel(NotificationChannel):
    name = "telegram"

    def __init__(self, *, bot_token: str | None = None, chat_id: str | None = None) -> None:
        self.bot_token = bot_token if bot_token is not None else settings.telegram_bot_token
        self.chat_id = chat_id if chat_id is not None else settings.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

    async def _send(self, msg: FormattedMessage) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": msg.markdown,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        status, body = await _post_json(url, payload)
        ok = 200 <= status < 300
        if not ok:
            logger.warning("[telegram] send failed: {} — {}", status, body[:200])
        return ok


class DiscordChannel(NotificationChannel):
    name = "discord"

    def __init__(self, *, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url if webhook_url is not None else settings.discord_webhook_url
        self.enabled = bool(self.webhook_url)

    async def _send(self, msg: FormattedMessage) -> bool:
        payload = {"content": msg.text}
        status, body = await _post_json(self.webhook_url, payload)
        ok = 200 <= status < 300
        if not ok:
            logger.warning("[discord] send failed: {} — {}", status, body[:200])
        return ok


# ── Module-level channels + dispatch ──────────────────────────────────

_channels: list[NotificationChannel] | None = None


def channels() -> list[NotificationChannel]:
    """Return the active notification channels. Rebuilt once per process; call
    `reset_channels()` to force a re-read of env config (useful for tests)."""
    global _channels
    if _channels is None:
        _channels = [
            c for c in (TelegramChannel(), DiscordChannel()) if c.enabled
        ]
    return _channels


def reset_channels() -> None:
    global _channels
    _channels = None


def dispatch_event(event_type: str, event: dict) -> list[str]:
    """Fan-out a FOUR-LIFE event to every enabled channel.

    Fire-and-forget: schedules async tasks on the running loop. Returns the list
    of channel names that were scheduled. Does nothing outside an event loop.
    """
    active = [c for c in channels() if c.enabled]
    if not active:
        return []
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return []
    scheduled: list[str] = []
    for ch in active:
        loop.create_task(ch.send_event(event_type, event))
        scheduled.append(ch.name)
    return scheduled


async def send_sync(event_type: str, event: dict) -> dict:
    """Send to all channels and await results. Useful for tests + admin "send
    test" endpoints. Returns {channel_name: bool_success}."""
    out: dict[str, bool] = {}
    for ch in channels():
        if not ch.enabled:
            continue
        out[ch.name] = await ch.send_event(event_type, event)
    return out
