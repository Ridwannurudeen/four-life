"""Trust-consistency tests.

Guards the invariants that an external audit flagged as the highest-risk
failure mode for the project: the SAME token must receive the SAME badge
from every public surface, and provenance (tier_source, observation_status,
quote_asset_source) must be threaded honestly so a judge inspecting any
endpoint can always tell how strong the claim is.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from agent.badge import (
    badge_from_ranking,
    OBS_FULL_HISTORY,
    OBS_PARTIAL_HISTORY,
    OBS_RANKING_ONLY,
    SOURCE_CERTIFIED,
    SOURCE_RADAR_ESTIMATE,
)


# ─── Direct badge tests (no API client) ────────────────────────────────


def test_badge_from_ranking_stamps_ranking_only_observation():
    """Ranking-only data can never produce a full_history claim."""
    b = badge_from_ranking(
        curve_progress_pct=45, holders=120, increase_pct=5, graduation_confidence="high",
    )
    assert b.tier_source == SOURCE_RADAR_ESTIMATE
    assert b.observation_status == OBS_RANKING_ONLY
    # And a radar_estimate can never claim full_history elsewhere either.
    assert b.observation_status != OBS_FULL_HISTORY


def test_badge_from_health_defaults_full_history():
    from agent.badge import badge_from_health
    from agent.fourmeme.monitor import TokenHealth

    h = TokenHealth(
        address="0x" + "a" * 40, name="X", symbol="X", phase="nurture",
        unique_buyers=100, buy_sell_ratio=1.5, holder_velocity=8,
        top_holder_pct=10, curve_progress_pct=20, age_hours=3,
        graduation_confidence="high", graduation_target=18.0,
    )
    b = badge_from_health(h)  # no explicit observation_status
    assert b.tier_source == SOURCE_CERTIFIED
    assert b.observation_status == OBS_FULL_HISTORY


def test_badge_from_health_accepts_partial_history_override():
    """Restored tokens (clamped scan window) must be markable as partial."""
    from agent.badge import badge_from_health
    from agent.fourmeme.monitor import TokenHealth

    h = TokenHealth(
        address="0x" + "b" * 40, name="Y", symbol="Y", phase="nurture",
        unique_buyers=50, buy_sell_ratio=1.1, holder_velocity=2,
        top_holder_pct=8, curve_progress_pct=15, age_hours=5,
        graduation_confidence="high", graduation_target=18.0,
    )
    b = badge_from_health(h, observation_status=OBS_PARTIAL_HISTORY)
    assert b.tier_source == SOURCE_CERTIFIED
    assert b.observation_status == OBS_PARTIAL_HISTORY


# ─── Cross-endpoint consistency tests (require API client) ─────────────


@pytest.fixture
def mock_ranking_agent():
    """Agent with a known Four.meme ranking snapshot the radar + badge paths
    can both resolve the same untracked token from."""
    # Don't use spec= — the API reaches through nested mocks (agent.chain,
    # agent.api, agent.graduation_registry, agent.memory, agent.lifecycle)
    # that spec-mode blocks with AttributeError.
    agent = MagicMock()
    agent.running = True
    agent.active_concepts = {}
    agent.chain.account.address = "0x" + "01" * 20

    # A single token, present in the ranking snapshot, NOT tracked on-chain.
    known_token = {
        "tokenAddress": "0xcafecafecafecafecafecafecafecafecafecafe",
        "shortName": "KNOWN",
        "name": "Known Token",
        "symbol": "BNB",
        "hold": 250,
        "progress": 0.4,
        "volume": 2.5,
        "increase": 0.1,
        "status": "TRADING",
    }
    agent.api._client.post = AsyncMock(return_value=MagicMock(
        json=MagicMock(return_value={"data": [known_token]}),
    ))
    agent.api.get_trending = AsyncMock(return_value=[known_token])
    agent.api.get_new_tokens = AsyncMock(return_value=[])
    agent.monitor.state.tokens = {}

    # Graduation registry returns a deterministic high-confidence BNB target.
    async def fake_registry_get(asset):
        from types import SimpleNamespace
        return SimpleNamespace(
            quote_asset="BNB", target_amount=18.0,
            confidence="high", source="fourmeme_config",
        )
    agent.graduation_registry.get = fake_registry_get
    agent.graduation_registry.known_assets = MagicMock(return_value=["BNB"])

    mem = MagicMock()
    mem.total_launches = 0
    mem.total_graduations = 0
    mem.graduation_rate = 0.0
    mem.avg_peak_holders = 0.0
    mem.tracked_launches = 0
    mem.launches = []
    agent.memory.memory = mem
    agent.lifecycle.action_log = []
    agent.myx = None
    return agent


@pytest.fixture
def client(mock_ranking_agent):
    with patch("agent.api.agent", mock_ranking_agent):
        from agent.api import app
        yield TestClient(app)


def test_radar_and_badge_agree_on_same_token(client):
    """THE invariant: the same untracked token scored via /api/graduation-radar
    and /api/token/{addr}/badge must return the same tier AND same
    tier_source. A drift here is the exact failure mode the external audit
    flagged — two surfaces labelling one token differently."""
    addr = "0xcafecafecafecafecafecafecafecafecafecafe"

    radar = client.get("/api/graduation-radar?limit=10&min_confidence=low")
    assert radar.status_code == 200
    rows = radar.json().get("radar", [])
    radar_row = next((r for r in rows if r["token_address"].lower() == addr), None)
    assert radar_row is not None, "seeded ranking token must appear on the radar"

    direct = client.get(f"/api/token/{addr}/badge")
    assert direct.status_code == 200
    direct_badge = direct.json()["badge"]

    # Invariant: tier + tier_source agree across surfaces.
    assert radar_row["badge_tier"] == direct_badge["tier"]
    assert radar_row["tier_source"] == direct_badge["tier_source"]
    # Both surfaces should report ranking_only for the same untracked token.
    assert radar_row["observation_status"] == "ranking_only"
    assert direct.json()["observation_status"] == "ranking_only"


def test_badge_endpoint_surfaces_quote_asset_source(client):
    """Quote-asset provenance must be observable, not silent."""
    addr = "0xcafecafecafecafecafecafecafecafecafecafe"
    direct = client.get(f"/api/token/{addr}/badge")
    assert direct.status_code == 200
    # Seeded ranking payload had symbol=BNB → fourmeme_api.
    assert direct.json()["quote_asset_source"] == "fourmeme_api"


def test_radar_row_carries_observation_and_quote_provenance(client):
    """Radar rows must include the same provenance fields as the direct
    badge endpoint so integrators have one contract, not two."""
    radar = client.get("/api/graduation-radar?limit=10&min_confidence=low")
    rows = radar.json().get("radar", [])
    assert rows, "expected at least one radar row"
    row = rows[0]
    for field in ("badge_tier", "tier_source", "observation_status", "quote_asset_source"):
        assert field in row, f"radar row missing {field}"
