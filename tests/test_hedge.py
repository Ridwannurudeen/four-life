"""Tests for MYX V2 hedge manager."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.myx.hedge import (
    HedgeManager,
    HedgePosition,
    HedgeState,
    SIGNAL_COOLDOWN,
)


@pytest.fixture
def mock_myx():
    myx = AsyncMock()
    myx.get_markets.return_value = [
        {"pair": "BNB/USDT", "pairIndex": 0},
        {"pair": "BTC/USDT", "pairIndex": 1},
    ]
    myx.open_position.return_value = "0xopen123"
    myx.close_position.return_value = "0xclose456"
    myx.get_pair_index.return_value = 0
    return myx


@pytest.fixture
def mock_strategy():
    strategy = AsyncMock()
    strategy.generate_signal.return_value = {
        "action": "hold",
        "confidence": 0.5,
        "reasoning": "Stable conditions",
        "size_pct": 0.05,
    }
    return strategy


@pytest.fixture
def manager(mock_myx, mock_strategy):
    # Existing behavioural tests assume execution happens — enable it explicitly so the
    # default signal_only guard doesn't suppress on-chain actions in unit tests.
    return HedgeManager(mock_myx, mock_strategy, execution_enabled=True)


@pytest.fixture
def signal_only_manager(mock_myx, mock_strategy):
    """Default-safe manager with execution disabled (matches production default)."""
    return HedgeManager(mock_myx, mock_strategy, execution_enabled=False)


@pytest.fixture
def token_health():
    return {
        "name": "TestToken",
        "symbol": "TT",
        "health_score": 45,
        "phase": "defend",
        "buy_sell_ratio": 0.8,
        "holder_velocity": -2.0,
        "curve_progress": 30.0,
        "top_holder_pct": 25.0,
    }


class TestHedgeState:
    def test_initial_state(self):
        state = HedgeState(token_address="0xtest")
        assert state.active_positions == []
        assert state.has_active_hedge is False
        assert state.total_hedged == 0
        assert state.signals_generated == 0

    def test_active_positions_filters_closed(self):
        state = HedgeState(token_address="0xtest")
        state.positions = [
            HedgePosition(
                token_address="0xtest", pair_index=0, is_long=False,
                collateral_wei=10**16, size_amount=5 * 10**16,
                open_price=int(600e30), open_tx="0xaaa",
                opened_at=time.time(), reason="test",
            ),
            HedgePosition(
                token_address="0xtest", pair_index=0, is_long=True,
                collateral_wei=10**16, size_amount=5 * 10**16,
                open_price=int(600e30), open_tx="0xbbb",
                opened_at=time.time(), reason="test",
                close_tx="0xccc", closed_at=time.time(),
            ),
        ]
        assert len(state.active_positions) == 1
        assert state.has_active_hedge is True
        assert state.active_positions[0].open_tx == "0xaaa"


class TestHedgeManagerInit:
    def test_creates_state_on_demand(self, manager):
        state = manager._get_state("0xnew")
        assert state.token_address == "0xnew"
        assert "0xnew" in manager.states

    def test_reuses_existing_state(self, manager):
        s1 = manager._get_state("0xsame")
        s1.signals_generated = 5
        s2 = manager._get_state("0xsame")
        assert s2.signals_generated == 5


class TestResolvePairIndex:
    @pytest.mark.asyncio
    async def test_resolves_from_contract(self, manager, mock_myx):
        mock_myx.get_pair_index.return_value = 3
        idx = await manager.resolve_pair_index()
        assert idx == 3
        mock_myx.get_pair_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_caches_result(self, manager, mock_myx):
        mock_myx.get_pair_index.return_value = 3
        await manager.resolve_pair_index()
        await manager.resolve_pair_index()
        # Only called once due to cache
        assert mock_myx.get_pair_index.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, manager, mock_myx):
        mock_myx.get_pair_index.side_effect = Exception("no pair")
        idx = await manager.resolve_pair_index()
        assert idx == 0  # DEFAULT_HEDGE_PAIR


class TestEvaluateAndAct:
    @pytest.mark.asyncio
    async def test_nurture_phase_monitors_only(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.return_value = {
            "action": "short", "confidence": 0.9, "reasoning": "x", "size_pct": 0.05,
        }
        result = await manager.evaluate_and_act("0xnurt", token_health, "nurture")
        assert result["action"] == "monitor"
        assert "Nurture" in result["reason"]

    @pytest.mark.asyncio
    async def test_graduated_closes_hedges(self, manager, token_health):
        # Set up an active position
        state = manager._get_state("0xgrad")
        state.positions.append(HedgePosition(
            token_address="0xgrad", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xactive",
            opened_at=time.time(), reason="test",
        ))

        result = await manager.evaluate_and_act("0xgrad", token_health, "graduated")
        assert result["action"] == "close_all"
        assert result["closed_count"] == 1

    @pytest.mark.asyncio
    async def test_defend_opens_short_on_high_confidence(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.return_value = {
            "action": "short", "confidence": 0.8, "reasoning": "Sell pressure", "size_pct": 0.05,
        }
        result = await manager.evaluate_and_act("0xdef", token_health, "defend")
        assert result["action"] == "open_short"
        assert "tx_hash" in result

    @pytest.mark.asyncio
    async def test_no_duplicate_hedge(self, manager, token_health, mock_strategy):
        """Don't open a second hedge if one is already active."""
        mock_strategy.generate_signal.return_value = {
            "action": "short", "confidence": 0.9, "reasoning": "x", "size_pct": 0.05,
        }
        # Pre-existing active position
        state = manager._get_state("0xdup")
        state.positions.append(HedgePosition(
            token_address="0xdup", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xexist",
            opened_at=time.time(), reason="existing",
        ))

        result = await manager.evaluate_and_act("0xdup", token_health, "defend")
        assert result["action"] == "hold"  # Should not open another

    @pytest.mark.asyncio
    async def test_low_confidence_holds(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.return_value = {
            "action": "short", "confidence": 0.3, "reasoning": "Weak", "size_pct": 0.02,
        }
        result = await manager.evaluate_and_act("0xlow", token_health, "defend")
        assert result["action"] == "hold"

    @pytest.mark.asyncio
    async def test_close_signal_closes_positions(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.return_value = {
            "action": "close", "confidence": 0.7, "reasoning": "Recovery", "size_pct": 0,
        }
        state = manager._get_state("0xcls")
        state.positions.append(HedgePosition(
            token_address="0xcls", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xtoclose",
            opened_at=time.time(), reason="test",
        ))

        result = await manager.evaluate_and_act("0xcls", token_health, "defend")
        assert result["action"] == "close_all"

    @pytest.mark.asyncio
    async def test_signal_cooldown(self, manager, token_health, mock_strategy):
        """Second call within cooldown reuses last signal."""
        mock_strategy.generate_signal.return_value = {
            "action": "hold", "confidence": 0.5, "reasoning": "Stable", "size_pct": 0,
        }
        await manager.evaluate_and_act("0xcd", token_health, "defend")
        await manager.evaluate_and_act("0xcd", token_health, "defend")
        # Signal generated only once
        assert mock_strategy.generate_signal.call_count == 1

    @pytest.mark.asyncio
    async def test_signal_failure_returns_none(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.side_effect = Exception("LLM down")
        result = await manager.evaluate_and_act("0xfail", token_health, "defend")
        assert result is None

    @pytest.mark.asyncio
    async def test_long_signal_with_high_confidence(self, manager, token_health, mock_strategy):
        mock_strategy.generate_signal.return_value = {
            "action": "long", "confidence": 0.85, "reasoning": "Bullish momentum", "size_pct": 0.08,
        }
        result = await manager.evaluate_and_act("0xlong", token_health, "accelerate")
        assert result["action"] == "open_long"
        assert result["leverage"] == "5x"


class TestOpenHedge:
    @pytest.mark.asyncio
    async def test_open_records_position(self, manager, mock_myx):
        signal = {"action": "short", "confidence": 0.8, "reasoning": "test", "size_pct": 0.05}
        result = await manager._open_hedge("0xrec", {}, signal, is_long=False)
        assert result["action"] == "open_short"

        state = manager._get_state("0xrec")
        assert len(state.positions) == 1
        assert state.positions[0].is_long is False
        assert state.total_hedged > 0

    @pytest.mark.asyncio
    async def test_open_caps_size_pct(self, manager, mock_myx):
        signal = {"action": "long", "confidence": 0.9, "reasoning": "test", "size_pct": 0.50}
        await manager._open_hedge("0xcap", {}, signal, is_long=True)
        state = manager._get_state("0xcap")
        # size_pct should be capped at 0.10
        pos = state.positions[0]
        expected_collateral = int(0.01 * 1e18 * (0.10 / 0.05))
        assert pos.collateral_wei == expected_collateral

    @pytest.mark.asyncio
    async def test_open_failure_returns_error(self, manager, mock_myx):
        mock_myx.open_position.side_effect = Exception("tx reverted")
        signal = {"action": "short", "confidence": 0.8, "reasoning": "test", "size_pct": 0.05}
        result = await manager._open_hedge("0xerr", {}, signal, is_long=False)
        assert result["action"] == "open_failed"
        assert "tx reverted" in result["error"]


class TestCloseAllHedges:
    @pytest.mark.asyncio
    async def test_closes_multiple_positions(self, manager, mock_myx):
        state = manager._get_state("0xmulti")
        for i in range(3):
            state.positions.append(HedgePosition(
                token_address="0xmulti", pair_index=0, is_long=False,
                collateral_wei=10**16, size_amount=5 * 10**16,
                open_price=int(600e30), open_tx=f"0x{i}",
                opened_at=time.time(), reason="test",
            ))

        result = await manager._close_all_hedges("0xmulti", "graduation")
        assert result["closed_count"] == 3
        assert len(result["tx_hashes"]) == 3
        assert all(p.close_tx is not None for p in state.positions)

    @pytest.mark.asyncio
    async def test_close_skips_already_closed(self, manager, mock_myx):
        state = manager._get_state("0xskip")
        state.positions.append(HedgePosition(
            token_address="0xskip", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xold",
            opened_at=time.time(), reason="test",
            close_tx="0xclosed", closed_at=time.time(),
        ))

        result = await manager._close_all_hedges("0xskip", "test")
        assert result["closed_count"] == 0

    @pytest.mark.asyncio
    async def test_close_handles_partial_failure(self, manager, mock_myx):
        state = manager._get_state("0xpart")
        for i in range(2):
            state.positions.append(HedgePosition(
                token_address="0xpart", pair_index=0, is_long=False,
                collateral_wei=10**16, size_amount=5 * 10**16,
                open_price=int(600e30), open_tx=f"0x{i}",
                opened_at=time.time(), reason="test",
            ))

        # First close succeeds, second fails
        mock_myx.close_position.side_effect = ["0xclosed1", Exception("fail")]
        result = await manager._close_all_hedges("0xpart", "test")
        assert result["closed_count"] == 1


class TestSignalOnlyMode:
    """The default execution_mode should be 'signal_only' so demos never submit on-chain
    orders with hardcoded collateral / placeholder oracle prices."""

    def test_default_mode_is_signal_only(self, signal_only_manager):
        assert signal_only_manager.execution_mode == "signal_only"

    def test_enabled_mode_is_executable(self, manager):
        assert manager.execution_mode == "executable"

    @pytest.mark.asyncio
    async def test_signal_only_does_not_open_on_short(self, signal_only_manager, token_health, mock_strategy, mock_myx):
        mock_strategy.generate_signal.return_value = {
            "action": "short", "confidence": 0.9, "reasoning": "x", "size_pct": 0.05,
        }
        result = await signal_only_manager.evaluate_and_act("0xsig", token_health, "defend")
        assert result["action"] == "signal_only"
        assert result["execution_mode"] == "signal_only"
        assert result["would_execute"] == "short"
        mock_myx.open_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_signal_only_emits_execution_mode_in_portfolio(self, signal_only_manager):
        summary = signal_only_manager.get_portfolio_summary()
        assert summary["execution_mode"] == "signal_only"


class TestPortfolioSummary:
    def test_empty_portfolio(self, manager):
        summary = manager.get_portfolio_summary()
        assert summary["total_active_positions"] == 0
        assert summary["tokens_hedged"] == 0

    def test_summary_with_positions(self, manager):
        state = manager._get_state("0xsum")
        state.positions.append(HedgePosition(
            token_address="0xsum", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xactive",
            opened_at=time.time(), reason="test",
        ))
        state.total_hedged = 10**16
        state.signals_generated = 5

        summary = manager.get_portfolio_summary()
        assert summary["total_active_positions"] == 1
        assert summary["tokens_hedged"] == 1
        assert summary["total_signals_generated"] == 5
        assert len(summary["token_summaries"]) == 1


class TestTokenPositions:
    def test_returns_formatted_positions(self, manager):
        state = manager._get_state("0xfmt")
        state.positions.append(HedgePosition(
            token_address="0xfmt", pair_index=0, is_long=False,
            collateral_wei=10**16, size_amount=5 * 10**16,
            open_price=int(600e30), open_tx="0xfmt1",
            opened_at=time.time(), reason="AI signal",
        ))

        positions = manager.get_token_positions("0xfmt")
        assert len(positions) == 1
        assert positions[0]["status"] == "active"
        assert positions[0]["is_long"] is False
        assert positions[0]["reason"] == "AI signal"

    def test_empty_for_unknown_token(self, manager):
        positions = manager.get_token_positions("0xunknown")
        assert positions == []
