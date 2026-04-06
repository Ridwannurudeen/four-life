"""Tests for token health monitoring."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.fourmeme.monitor import TokenMonitor, TokenHealth, MonitorState


@pytest.fixture
def mock_chain():
    chain = AsyncMock()
    chain.get_block_number = AsyncMock(return_value=50000000)
    chain.get_price = AsyncMock(return_value=1000000000000)
    chain.get_token_trades = AsyncMock(return_value={"buys": [], "sells": []})
    return chain


@pytest.fixture
def monitor(mock_chain):
    return TokenMonitor(mock_chain)


class TestTokenHealth:
    def test_defaults(self):
        h = TokenHealth(address="0xtest")
        assert h.health_score == 0
        assert h.graduation_probability == 0
        assert h.phase == "nurture"
        assert h.unique_buyers == 0

    def test_phase_by_age(self):
        h = TokenHealth(address="0x1")
        h.age_hours = 2
        # Phase is set by monitor, but default is nurture
        assert h.phase == "nurture"


class TestTokenMonitor:
    @pytest.mark.asyncio
    async def test_track_token(self, monitor):
        await monitor.track_token("0xtoken1", name="TestCoin", symbol="TC", creator="0xcreator")

        assert "0xtoken1" in monitor.state.tokens
        assert monitor.state.tokens["0xtoken1"].name == "TestCoin"

    @pytest.mark.asyncio
    async def test_update_with_buys(self, monitor, mock_chain):
        await monitor.track_token("0xtoken2", name="BuyTest", symbol="BT", created_block=49999990)

        mock_chain.get_token_trades.return_value = {
            "buys": [
                {"buyer": "0xbuyer1", "amount": 1000000, "cost": 100000000000000000, "block": 50000000},
                {"buyer": "0xbuyer2", "amount": 2000000, "cost": 200000000000000000, "block": 50000001},
                {"buyer": "0xbuyer3", "amount": 500000, "cost": 50000000000000000, "block": 50000002},
            ],
            "sells": [],
        }

        health = await monitor.update_token("0xtoken2")

        assert health.unique_buyers == 3
        assert health.unique_sellers == 0
        assert health.total_buys == 3
        assert health.buy_volume_bnb == pytest.approx(0.35, abs=0.01)
        assert health.buy_sell_ratio == 3.0

    @pytest.mark.asyncio
    async def test_update_with_sells(self, monitor, mock_chain):
        await monitor.track_token("0xtoken3", name="SellTest", symbol="ST", created_block=49999990)

        mock_chain.get_token_trades.return_value = {
            "buys": [
                {"buyer": "0xb1", "amount": 5000000, "cost": 500000000000000000, "block": 50000000},
            ],
            "sells": [
                {"seller": "0xb1", "amount": 2000000, "revenue": 200000000000000000, "block": 50000010},
            ],
        }

        health = await monitor.update_token("0xtoken3")

        assert health.unique_buyers == 1
        assert health.unique_sellers == 1
        assert health.buy_sell_ratio == 1.0

    @pytest.mark.asyncio
    async def test_whale_detection(self, monitor, mock_chain):
        await monitor.track_token("0xtoken4", name="WhaleTest", symbol="WT", created_block=49999990)

        # One whale holding 10% of supply
        mock_chain.get_token_trades.return_value = {
            "buys": [
                {"buyer": "0xwhale", "amount": 100_000_000, "cost": 1000000000000000000, "block": 50000000},
                {"buyer": "0xsmall", "amount": 1_000_000, "cost": 10000000000000000, "block": 50000001},
            ],
            "sells": [],
        }

        health = await monitor.update_token("0xtoken4")

        assert health.top_holder_pct == pytest.approx(10.0, abs=0.1)
        assert health.whale_count == 1  # 0xwhale has >5%

    @pytest.mark.asyncio
    async def test_phase_transitions(self, monitor, mock_chain):
        await monitor.track_token("0xtoken5", name="PhaseTest", symbol="PT", created_block=49999990)

        # Manually set created_at for phase testing
        token = monitor.state.tokens["0xtoken5"]

        # Nurture (0-6h)
        token.created_at = time.time() - 3600  # 1h ago
        mock_chain.get_token_trades.return_value = {"buys": [], "sells": []}
        health = await monitor.update_token("0xtoken5")
        assert health.phase == "nurture"

        # Defend (6-24h)
        token.created_at = time.time() - 12 * 3600  # 12h ago
        health = await monitor.update_token("0xtoken5")
        assert health.phase == "defend"

        # Accelerate (24-72h)
        token.created_at = time.time() - 48 * 3600  # 48h ago
        health = await monitor.update_token("0xtoken5")
        assert health.phase == "accelerate"

    def test_health_score_calculation(self, monitor):
        h = TokenHealth(address="0xscore")

        # Low health — no activity
        h.holder_velocity = 0
        h.buy_sell_ratio = 0
        h.top_holder_pct = 50
        h.curve_progress_pct = 0
        score = monitor._compute_health_score(h)
        assert score < 10

        # High health — strong metrics
        h.holder_velocity = 60
        h.buy_sell_ratio = 3.5
        h.top_holder_pct = 3
        h.curve_progress_pct = 80
        score = monitor._compute_health_score(h)
        assert score >= 80

    def test_graduation_probability(self, monitor):
        h = TokenHealth(address="0xprob")

        # Low probability
        h.curve_progress_pct = 5
        h.unique_buyers = 10
        h.buy_sell_ratio = 0.5
        h.top_holder_pct = 60
        h.holder_velocity = 0.5
        prob = monitor._compute_graduation_prob(h)
        assert prob < 0.2

        # High probability
        h.curve_progress_pct = 85
        h.unique_buyers = 800
        h.buy_sell_ratio = 2.5
        h.top_holder_pct = 5
        h.holder_velocity = 25
        prob = monitor._compute_graduation_prob(h)
        assert prob >= 0.7
