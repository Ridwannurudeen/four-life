"""Tests for the FOUR-LIFE Radar Bot — deterministic tier-transition broadcaster."""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.social.radar_bot import (
    BotState,
    RadarBot,
    TIER_RANK,
    derive_tier,
    tweet_for_transition,
    TWEET_LIMIT,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tmp_state_file(tmp_path):
    return tmp_path / "radar_state.json"


@pytest.fixture
def tmp_status_file(tmp_path, monkeypatch):
    # Redirect STATE_DIR to tmp_path so the bot doesn't touch the real data/ dir
    from agent.social import radar_bot as rb
    monkeypatch.setattr(rb, "STATE_DIR", tmp_path)
    monkeypatch.setattr(rb, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(rb, "STATUS_FILE", tmp_path / "status.json")
    return tmp_path / "status.json"


@pytest.fixture
def mock_twitter():
    t = MagicMock()
    t.enabled = True
    t.post_tweet = MagicMock(return_value="fake_tweet_id_123")
    return t


def _entry(tier="observed", **overrides):
    """Build a radar entry that derives to the given tier by default."""
    presets = {
        "observed": {"curve_progress": 10, "confidence_score": "high", "increase_pct": 0},
        "healthy":  {"curve_progress": 30, "confidence_score": "high", "increase_pct": 10},
        "graduation_watch": {"curve_progress": 75, "confidence_score": "high", "increase_pct": 5},
        "graduated":        {"curve_progress": 100, "confidence_score": "high", "increase_pct": 0},
        "at_risk":          {"curve_progress": 5, "confidence_score": "high", "increase_pct": -80},
    }
    base = {
        "token_address": "0xabc" + tier[:4].ljust(37, "0"),
        "symbol": tier.upper()[:5],
        "name": f"Token {tier}",
        "holders": 100,
        "quote_asset": "BNB",
        "graduation_target": 18,
        "top_holder_pct": 10,
        "buy_sell_ratio": 1.5,
        "health_score": 65,
    }
    base.update(presets[tier])
    base.update(overrides)
    return base


# ── derive_tier ──────────────────────────────────────────────────────


class TestDeriveTier:
    def test_graduated_by_curve(self):
        assert derive_tier({"curve_progress": 100, "confidence_score": "high", "increase_pct": 0}) == "graduated"

    def test_graduation_watch(self):
        assert derive_tier({"curve_progress": 75, "confidence_score": "high", "increase_pct": 10}) == "graduation_watch"

    def test_graduation_watch_requires_high_confidence(self):
        assert derive_tier({"curve_progress": 80, "confidence_score": "low", "increase_pct": 10}) != "graduation_watch"

    def test_at_risk_big_drop(self):
        assert derive_tier({"curve_progress": 5, "confidence_score": "high", "increase_pct": -80}) == "at_risk"

    def test_observed_default(self):
        assert derive_tier({"curve_progress": 20, "confidence_score": "high", "increase_pct": 5}) == "observed"


# ── Tweet templates ──────────────────────────────────────────────────


class TestTweetTemplates:
    def test_graduated_template(self):
        text = tweet_for_transition("graduated", _entry("graduated", symbol="DOG"))
        assert text is not None
        assert "🎓" in text
        assert "DOG" in text
        assert "@fourmeme_official" in text
        assert len(text) <= TWEET_LIMIT

    def test_graduation_watch_template(self):
        text = tweet_for_transition("graduation_watch", _entry("graduation_watch", symbol="PEPE"))
        assert text is not None
        assert "⚡" in text
        assert "PEPE" in text
        assert "Graduation Watch" in text
        assert len(text) <= TWEET_LIMIT

    def test_at_risk_template(self):
        text = tweet_for_transition("at_risk", _entry("at_risk", symbol="RUG", top_holder_pct=45))
        assert text is not None
        assert "🚨" in text
        assert "RUG" in text
        assert "At Risk" in text
        assert "top holder 45%" in text
        assert len(text) <= TWEET_LIMIT

    def test_healthy_template(self):
        text = tweet_for_transition("healthy", _entry("healthy", symbol="OK"))
        assert text is not None
        assert "🌱" in text
        assert "OK" in text
        assert "Healthy" in text
        assert len(text) <= TWEET_LIMIT

    def test_unknown_transition_returns_none(self):
        assert tweet_for_transition("someinventedtier", _entry("healthy")) is None

    def test_all_templates_fit_with_long_symbol(self):
        # Max 20-char symbol — templates should still fit
        long_sym = "A" * 20
        for tier in ("graduated", "graduation_watch", "at_risk", "healthy"):
            text = tweet_for_transition(tier, _entry(tier, symbol=long_sym))
            assert text is not None
            assert len(text) <= TWEET_LIMIT, f"{tier} template too long"


# ── BotState ─────────────────────────────────────────────────────────


class TestBotState:
    def test_load_missing_file_returns_empty(self, tmp_state_file):
        s = BotState.load(tmp_state_file)
        assert s.last_seen_tier == {}
        assert s.posted_transitions == {}

    def test_save_and_load_roundtrip(self, tmp_state_file):
        s = BotState()
        s.last_seen_tier = {"0xabc": "healthy"}
        s.posted_transitions = {"0xabc:healthy": time.time()}
        s.recent_post_times = [time.time()]
        s.save(tmp_state_file)

        s2 = BotState.load(tmp_state_file)
        assert s2.last_seen_tier == s.last_seen_tier
        assert "0xabc:healthy" in s2.posted_transitions

    def test_posts_last_hour(self):
        s = BotState()
        now = time.time()
        s.recent_post_times = [now - 30, now - 60, now - 7200]  # 2 recent, 1 old
        assert s.posts_last_hour() == 2

    def test_prune_drops_old_transitions(self):
        s = BotState()
        now = time.time()
        s.transitions_log = [
            {"at": now, "token_address": "0xnew"},
            {"at": now - 90000, "token_address": "0xold"},  # >24h ago
        ]
        s.prune()
        assert len(s.transitions_log) == 1
        assert s.transitions_log[0]["token_address"] == "0xnew"
        assert s.transitions_24h == 1


# ── Bot behavior ─────────────────────────────────────────────────────


class TestBotTick:
    @pytest.mark.asyncio
    async def test_first_sighting_at_graduation_watch_posts(self, tmp_status_file, mock_twitter):
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([_entry("graduation_watch", token_address="0xa1")])

        summary = await bot.tick()
        assert summary["transitions"] == 1
        assert summary["posted"] == 1
        assert mock_twitter.post_tweet.called
        assert "0xa1:graduation_watch" in bot.state.posted_transitions

    @pytest.mark.asyncio
    async def test_observed_token_does_not_post(self, tmp_status_file, mock_twitter):
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([_entry("observed", token_address="0xa2")])

        summary = await bot.tick()
        assert summary["transitions"] == 0
        assert summary["posted"] == 0
        assert not mock_twitter.post_tweet.called

    @pytest.mark.asyncio
    async def test_transition_observed_to_graduation_watch(self, tmp_status_file, mock_twitter):
        state = BotState()
        state.last_seen_tier = {"0xa3": "observed"}
        bot = RadarBot(twitter=mock_twitter, state=state)
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([_entry("graduation_watch", token_address="0xa3")])

        summary = await bot.tick()
        assert summary["posted"] == 1
        assert mock_twitter.post_tweet.call_count == 1

    @pytest.mark.asyncio
    async def test_dedup_same_transition_not_posted_twice(self, tmp_status_file, mock_twitter):
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        fut1 = asyncio.Future(); fut1.set_result([_entry("graduation_watch", token_address="0xa4")])
        fut2 = asyncio.Future(); fut2.set_result([_entry("graduation_watch", token_address="0xa4")])
        bot.fetch_radar = MagicMock(side_effect=[fut1, fut2])

        s1 = await bot.tick()
        s2 = await bot.tick()
        assert s1["posted"] == 1
        assert s2["posted"] == 0
        assert mock_twitter.post_tweet.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_caps_hourly_posts(self, tmp_status_file, mock_twitter):
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        # Pre-fill recent_post_times up to the limit
        bot.state.recent_post_times = [time.time() - i for i in range(6)]
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([
            _entry("graduation_watch", token_address="0x" + f"{i:039x}") for i in range(3)
        ])

        summary = await bot.tick()
        # Already at 6 posts; none of the 3 new transitions should be posted.
        assert summary["posted"] == 0

    @pytest.mark.asyncio
    async def test_twitter_error_pauses_bot(self, tmp_status_file, mock_twitter):
        mock_twitter.post_tweet.side_effect = Exception("X API down")
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([_entry("graduation_watch", token_address="0xa5")])

        summary = await bot.tick()
        assert summary["posted"] == 0
        assert bot.state.pause_until > time.time()
        assert "X API down" in bot.state.last_error_message

    @pytest.mark.asyncio
    async def test_fetch_error_pauses_bot(self, tmp_status_file, mock_twitter):
        bot = RadarBot(twitter=mock_twitter, state=BotState())
        fut = asyncio.Future()
        fut.set_exception(RuntimeError("radar unreachable"))
        bot.fetch_radar = MagicMock(return_value=fut)

        summary = await bot.tick()
        assert "error" in summary
        assert bot.state.pause_until > time.time()
        assert not mock_twitter.post_tweet.called

    @pytest.mark.asyncio
    async def test_graduated_takes_priority_over_upgrade(self, tmp_status_file, mock_twitter):
        state = BotState()
        state.last_seen_tier = {"0xa6": "graduation_watch"}
        bot = RadarBot(twitter=mock_twitter, state=state)
        bot.fetch_radar = MagicMock(return_value=asyncio.Future())
        bot.fetch_radar.return_value.set_result([_entry("graduated", token_address="0xa6")])

        summary = await bot.tick()
        assert summary["posted"] == 1
        tweet_text = mock_twitter.post_tweet.call_args[0][0]
        assert "graduated" in tweet_text.lower()


class TestTierRank:
    def test_rank_ordering(self):
        assert TIER_RANK["observed"] < TIER_RANK["healthy"] < TIER_RANK["graduation_watch"] < TIER_RANK["graduated"]
        # at_risk is special-cased
        assert TIER_RANK["at_risk"] < TIER_RANK["observed"]
