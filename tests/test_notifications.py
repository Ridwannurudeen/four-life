"""Tests for notification adapters (Telegram, Discord)."""

from __future__ import annotations

from typing import Any

import pytest

from agent import notifications as notif
from agent.notifications import (
    DiscordChannel,
    TelegramChannel,
    dispatch_event,
    format_protection_level_changed,
    format_tier_changed,
    reset_channels,
    send_sync,
    set_transport_override,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_channels()
    set_transport_override(None)
    yield
    reset_channels()
    set_transport_override(None)


TIER_EVENT = {
    "type": "badge.tier_changed",
    "token_address": "0xabc0000000000000000000000000000000000001",
    "from_tier": "healthy",
    "to_tier": "at_risk",
    "at": 1_000,
}

PROT_EVENT = {
    "type": "protection.level_changed",
    "token_address": "0xabc0000000000000000000000000000000000001",
    "from_level": "safe",
    "to_level": "critical",
    "fired_rules": [
        {"rule": "whale_concentration_critical", "metric": "top_holder_pct", "value": 70, "severity": "critical"},
    ],
    "at": 2_000,
}


class TestFormatters:
    def test_tier_changed_contains_key_parts(self):
        m = format_tier_changed(TIER_EVENT)
        assert "FOUR-LIFE" in m.text
        assert "Healthy" in m.text
        assert "At Risk" in m.text
        assert "0xabc0…0001" in m.text
        assert "https://four-life.gudman.xyz/radar?token=0xabc" in m.text

    def test_protection_level_shows_rules(self):
        m = format_protection_level_changed(PROT_EVENT)
        assert "Protection Mode" in m.text
        assert "critical" in m.text
        assert "whale_concentration_critical" in m.text

    def test_markdown_has_link_and_emphasis(self):
        m = format_tier_changed(TIER_EVENT)
        assert "*At Risk*" in m.markdown
        assert "[Open on Radar]" in m.markdown


class TestTelegramChannel:
    @pytest.mark.asyncio
    async def test_disabled_without_token(self):
        ch = TelegramChannel(bot_token="", chat_id="abc")
        assert ch.enabled is False
        result = await ch.send_event("badge.tier_changed", TIER_EVENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_hits_telegram_api(self):
        ch = TelegramChannel(bot_token="BOT", chat_id="42")
        assert ch.enabled is True

        captured: dict[str, Any] = {}

        async def stub(url: str, payload: dict) -> tuple[int, str]:
            captured["url"] = url
            captured["payload"] = payload
            return 200, '{"ok":true}'

        set_transport_override(stub)
        ok = await ch.send_event("badge.tier_changed", TIER_EVENT)

        assert ok is True
        assert captured["url"] == "https://api.telegram.org/botBOT/sendMessage"
        assert captured["payload"]["chat_id"] == "42"
        assert captured["payload"]["parse_mode"] == "Markdown"
        assert "At Risk" in captured["payload"]["text"]

    @pytest.mark.asyncio
    async def test_non_2xx_is_failure(self):
        ch = TelegramChannel(bot_token="BOT", chat_id="42")

        async def stub(url: str, payload: dict) -> tuple[int, str]:
            return 403, "forbidden"

        set_transport_override(stub)
        ok = await ch.send_event("badge.tier_changed", TIER_EVENT)
        assert ok is False

    @pytest.mark.asyncio
    async def test_unknown_event_type_is_skipped(self):
        ch = TelegramChannel(bot_token="BOT", chat_id="42")
        ok = await ch.send_event("mystery.event", {})
        assert ok is False


class TestDiscordChannel:
    @pytest.mark.asyncio
    async def test_disabled_without_url(self):
        ch = DiscordChannel(webhook_url="")
        assert ch.enabled is False

    @pytest.mark.asyncio
    async def test_send_posts_content_body(self):
        ch = DiscordChannel(webhook_url="https://discord.example/webhook/abc")
        captured: dict[str, Any] = {}

        async def stub(url: str, payload: dict) -> tuple[int, str]:
            captured["url"] = url
            captured["payload"] = payload
            return 204, ""

        set_transport_override(stub)
        ok = await ch.send_event("protection.level_changed", PROT_EVENT)

        assert ok is True
        assert captured["url"] == "https://discord.example/webhook/abc"
        assert "Protection Mode" in captured["payload"]["content"]
        # Discord uses plain text, not markdown
        assert "*" not in captured["payload"]["content"]


class TestDispatch:
    @pytest.mark.asyncio
    async def test_send_sync_fans_out_to_enabled_channels(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        # Force both channels on for this test
        monkeypatch.setattr(notif, "_channels", [
            TelegramChannel(bot_token="BOT", chat_id="1"),
            DiscordChannel(webhook_url="https://d.example/webhook"),
        ])

        calls: list[str] = []

        async def stub(url: str, payload: dict) -> tuple[int, str]:
            calls.append(url)
            return 200, ""

        set_transport_override(stub)
        results = await send_sync("badge.tier_changed", TIER_EVENT)

        assert results == {"telegram": True, "discord": True}
        assert len(calls) == 2
        assert any("telegram" in c for c in calls)

    def test_channels_cache_rebuilds_on_reset(self):
        a = notif.channels()
        b = notif.channels()
        assert a is b  # same cached list
        reset_channels()
        c = notif.channels()
        assert c is not a

    @pytest.mark.asyncio
    async def test_dispatch_event_outside_event_loop_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        # This tests the error-handling path — without a running loop, nothing is scheduled.
        # We run it via a trick: call from an async test but monkeypatch get_running_loop.
        monkeypatch.setattr(notif, "_channels", [
            TelegramChannel(bot_token="BOT", chat_id="1"),
        ])

        import asyncio as _asyncio

        def no_loop() -> Any:
            raise RuntimeError("no loop")

        monkeypatch.setattr(_asyncio, "get_running_loop", no_loop)
        result = dispatch_event("badge.tier_changed", TIER_EVENT)
        assert result == []

    @pytest.mark.asyncio
    async def test_dispatch_event_schedules_for_each_channel(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(notif, "_channels", [
            TelegramChannel(bot_token="BOT", chat_id="1"),
            DiscordChannel(webhook_url="https://d.example/webhook"),
        ])

        sent: list[tuple[str, dict]] = []

        async def stub(url: str, payload: dict) -> tuple[int, str]:
            sent.append((url, payload))
            return 200, ""

        set_transport_override(stub)
        scheduled = dispatch_event("badge.tier_changed", TIER_EVENT)
        assert set(scheduled) == {"telegram", "discord"}

        # Let scheduled tasks run
        import asyncio
        await asyncio.sleep(0.05)
        assert len(sent) == 2
