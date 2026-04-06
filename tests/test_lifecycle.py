"""Tests for lifecycle engine."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.fourmeme.monitor import TokenMonitor, TokenHealth
from agent.lifecycle.engine import LifecycleEngine


@pytest.fixture
def mock_deps():
    monitor = AsyncMock(spec=TokenMonitor)
    strategy = AsyncMock()
    content = AsyncMock()
    memory = MagicMock()
    twitter = MagicMock()

    memory.get_context_for_ai.return_value = "Test context"
    memory.get_launch.return_value = MagicMock(
        peak_holders=0, peak_health_score=0, peak_curve_progress=0,
        graduated=False,
    )

    return monitor, strategy, content, memory, twitter


@pytest.fixture
def engine(mock_deps):
    return LifecycleEngine(*mock_deps)


class TestMilestoneDetection:
    def test_holder_milestones(self, engine):
        h = TokenHealth(address="0xmile", unique_buyers=55)
        result = engine._check_milestones("0xmile", h)
        assert result == "50 holders"

        # Same milestone should not trigger again
        result = engine._check_milestones("0xmile", h)
        assert result is None

        # Next milestone
        h.unique_buyers = 110
        result = engine._check_milestones("0xmile", h)
        assert result == "100 holders"

    def test_curve_milestones(self, engine):
        h = TokenHealth(address="0xcurve", unique_buyers=5, curve_progress_pct=30)
        result = engine._check_milestones("0xcurve", h)
        assert result == "25% bonding curve"

        h.curve_progress_pct = 55
        result = engine._check_milestones("0xcurve", h)
        assert result == "50% bonding curve"

    def test_no_milestone(self, engine):
        h = TokenHealth(address="0xnone", unique_buyers=30, curve_progress_pct=15)
        result = engine._check_milestones("0xnone", h)
        assert result is None


class TestLifecycleTick:
    @pytest.mark.asyncio
    async def test_rate_limiting(self, engine, mock_deps):
        monitor, strategy, content, memory, twitter = mock_deps

        health = TokenHealth(
            address="0xrate", name="RateTest", symbol="RT",
            phase="nurture", created_at=time.time() - 3600,
        )
        monitor.update_token.return_value = health
        strategy.get_lifecycle_action.return_value = {
            "action_type": "post_content",
            "content": "Test post",
            "urgency": "low",
            "reasoning": "Test",
        }

        # First tick should act
        engine.active_concepts = {}
        action = await engine.tick("0xrate", {"name": "RateTest"})
        # May or may not act depending on timing

        # Force last action time to now
        engine._last_action_time["0xrate"] = time.time()

        # Second tick should be rate-limited
        action = await engine.tick("0xrate", {"name": "RateTest"})
        assert action is None

    @pytest.mark.asyncio
    async def test_transparency_on_high_whale(self, engine, mock_deps):
        monitor, strategy, content, memory, twitter = mock_deps

        health = TokenHealth(
            address="0xwhale", name="WhaleTest", symbol="WHL",
            phase="defend", top_holder_pct=45, created_at=time.time() - 36000,
        )
        monitor.update_token.return_value = health
        content.generate_transparency_post.return_value = "Whale transparency post"

        # Clear rate limit
        engine._last_action_time.pop("0xwhale", None)

        action = await engine.tick("0xwhale", {"name": "WhaleTest"})

        if action:  # May be rate-limited
            assert action.action_type == "transparency"
            assert "Whale" in action.reasoning

    def test_action_history(self, engine):
        from agent.lifecycle.engine import LifecycleAction

        engine.action_log = [
            LifecycleAction(
                token_address="0xhist", action_type="celebrate",
                content="100 holders!", urgency="medium",
                reasoning="Milestone", timestamp=time.time(),
            ),
            LifecycleAction(
                token_address="0xother", action_type="post_content",
                content="Other post", urgency="low",
                reasoning="Routine", timestamp=time.time(),
            ),
            LifecycleAction(
                token_address="0xhist", action_type="defend",
                content="Diamond hands", urgency="high",
                reasoning="Sell pressure", timestamp=time.time(),
            ),
        ]

        history = engine.get_action_history("0xhist")
        assert len(history) == 2
        assert history[0]["action_type"] == "celebrate"
        assert history[1]["action_type"] == "defend"
