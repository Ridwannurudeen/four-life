"""Tests for the pair-aware graduation registry."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.fourmeme.graduation import GraduationRegistry, GraduationTarget


def _mock_client(config_data):
    """Build a mock httpx client whose GET returns the given config payload."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"code": 0, "data": config_data})
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    return client


BNB_USD1_CONFIG = [
    {"symbol": "BNB", "totalBAmount": "18", "b0Amount": "8", "status": "PUBLISH"},
    {"symbol": "USD1", "totalBAmount": "12000", "b0Amount": "4000", "status": "PUBLISH"},
    {"symbol": "USDT", "totalBAmount": "12000", "b0Amount": "4000", "status": "PUBLISH"},
    {"symbol": "CAKE", "totalBAmount": "10000", "b0Amount": "2000", "status": "PUBLISH"},
]


class TestGraduationRegistry:
    @pytest.mark.asyncio
    async def test_bnb_target_from_live_config(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        target = await reg.get("BNB")
        assert target.quote_asset == "BNB"
        assert target.target_amount == 18.0
        assert target.confidence == "high"
        assert target.source == "fourmeme_config"

    @pytest.mark.asyncio
    async def test_usd1_target_from_live_config(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        target = await reg.get("USD1")
        assert target.target_amount == 12000.0
        assert target.confidence == "high"

    @pytest.mark.asyncio
    async def test_case_insensitive_lookup(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        t1 = await reg.get("bnb")
        t2 = await reg.get("BNB")
        assert t1.target_amount == t2.target_amount == 18.0

    @pytest.mark.asyncio
    async def test_unknown_asset_is_low_confidence(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        target = await reg.get("NONEXISTENT")
        assert target.confidence == "low"
        assert target.target_amount == 0.0
        assert target.source == "fallback"

    @pytest.mark.asyncio
    async def test_empty_quote_asset_is_low_confidence(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        target = await reg.get("")
        assert target.confidence == "low"
        assert target.target_amount == 0.0

    @pytest.mark.asyncio
    async def test_refresh_failure_falls_back_to_low_confidence(self):
        client = AsyncMock()
        client.get.side_effect = Exception("network down")
        reg = GraduationRegistry(http_client=client)
        target = await reg.get("BNB")
        # Refresh failed, cache is empty — must not fabricate a number
        assert target.confidence == "low"
        assert target.target_amount == 0.0

    @pytest.mark.asyncio
    async def test_known_assets_list(self):
        reg = GraduationRegistry(http_client=_mock_client(BNB_USD1_CONFIG))
        await reg.refresh()
        assets = reg.known_assets()
        assert "BNB" in assets
        assert "USD1" in assets
        assert assets == sorted(assets)

    @pytest.mark.asyncio
    async def test_invalid_total_is_skipped(self):
        bad_config = [
            {"symbol": "BAD", "totalBAmount": "not_a_number", "b0Amount": "0"},
            {"symbol": "OK", "totalBAmount": "100", "b0Amount": "10"},
        ]
        reg = GraduationRegistry(http_client=_mock_client(bad_config))
        await reg.refresh()
        assert "OK" in reg.known_assets()
        assert "BAD" not in reg.known_assets()

    @pytest.mark.asyncio
    async def test_zero_target_is_skipped(self):
        config = [{"symbol": "ZERO", "totalBAmount": "0", "b0Amount": "0"}]
        reg = GraduationRegistry(http_client=_mock_client(config))
        await reg.refresh()
        # Zero-target entries are not cached — they'd produce meaningless progress math
        assert "ZERO" not in reg.known_assets()
