"""Tests for the FastAPI dashboard backend."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.running = True
    agent.identity.agent_id = 12345
    agent.identity.generate_agent_card.return_value = {
        "name": "FOUR-LIFE",
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
    }
    agent.chain.account.address = "0x1234567890abcdef1234567890abcdef12345678"
    agent.monitor.state.tokens = {}
    agent.active_concepts = {}
    agent.lifecycle.action_log = []
    agent.myx = None
    agent.myx_strategy = None
    agent.hedge_manager = None

    mem = MagicMock()
    mem.total_launches = 5
    mem.total_graduations = 2
    mem.graduation_rate = 0.4
    mem.avg_peak_holders = 340
    mem.global_learnings = ["Dog tokens work well", "Avoid weekend launches"]
    mem.launches = []
    mem.last_updated = 1712000000
    mem.best_narratives = ["dogs"]
    mem.worst_narratives = ["politics"]
    agent.memory.memory = mem

    return agent


@pytest.fixture
def client(mock_agent):
    with patch("agent.api.agent", mock_agent):
        from agent.api import app
        yield TestClient(app)


class TestStatusEndpoint:
    def test_returns_agent_info(self, client, mock_agent):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] == "FOUR-LIFE"
        assert data["running"] is True
        assert data["total_launches"] == 5
        assert data["total_graduations"] == 2
        assert data["graduation_rate"] == 40.0

    def test_includes_learnings(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert len(data["global_learnings"]) == 2
        assert "Dog tokens" in data["global_learnings"][0]


class TestTokensEndpoint:
    def test_empty_tokens(self, client):
        resp = client.get("/api/tokens")
        assert resp.status_code == 200
        assert resp.json()["tokens"] == []

    def test_with_tracked_token(self, client, mock_agent):
        from agent.fourmeme.monitor import TokenHealth
        health = TokenHealth(
            address="0xtest", name="TestCoin", symbol="TC",
            phase="nurture", health_score=65, graduation_probability=0.45,
            unique_buyers=150, buy_sell_ratio=2.3, top_holder_pct=12.5,
            curve_progress_pct=34.2, holder_velocity=8.5, age_hours=3.2,
        )
        mock_agent.monitor.state.tokens = {"0xtest": health}
        mock_agent.active_concepts = {"0xtest": {"narrative": "AI agents"}}

        resp = client.get("/api/tokens")
        data = resp.json()
        assert len(data["tokens"]) == 1
        token = data["tokens"][0]
        assert token["name"] == "TestCoin"
        assert token["health_score"] == 65
        assert token["narrative"] == "AI agents"


class TestTokenDetailEndpoint:
    def test_not_found(self, client):
        resp = client.get("/api/tokens/0xnonexistent")
        assert resp.status_code == 404

    def test_found(self, client, mock_agent):
        from agent.fourmeme.monitor import TokenHealth
        health = TokenHealth(address="0xdetail", name="DetailCoin", symbol="DC", health_score=80)
        mock_agent.monitor.state.tokens = {"0xdetail": health}
        mock_agent.active_concepts = {"0xdetail": {"personality": "snarky"}}
        mock_agent.lifecycle.get_action_history.return_value = []
        mock_agent.memory.get_launch.return_value = MagicMock(
            launched_at=1712000000, peak_holders=200,
            peak_health_score=85, graduated=False,
            what_worked=[], what_failed=[],
        )

        resp = client.get("/api/tokens/0xdetail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["health"]["name"] == "DetailCoin"
        assert data["concept"]["personality"] == "snarky"


class TestAgentCardEndpoint:
    def test_returns_erc8004_card(self, client):
        resp = client.get("/.well-known/agent-registration.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "FOUR-LIFE"


class TestActionsEndpoint:
    def test_empty_actions(self, client):
        resp = client.get("/api/actions")
        assert resp.status_code == 200
        assert resp.json()["actions"] == []


class TestMemoryEndpoint:
    def test_returns_memory(self, client):
        resp = client.get("/api/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_launches"] == 5
        assert data["graduation_rate"] == 40.0
        assert data["best_narratives"] == ["dogs"]


class TestMYXEndpoint:
    def test_myx_disabled(self, client):
        resp = client.get("/api/myx/status")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_portfolio_disabled(self, client):
        resp = client.get("/api/myx/portfolio")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_positions_disabled(self, client):
        resp = client.get("/api/myx/positions/0xtest")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_evaluate_disabled(self, client):
        resp = client.post("/api/myx/evaluate/0xtest")
        assert resp.status_code == 200
        assert resp.json()["error"] == "MYX not configured"

    def test_signal_disabled(self, client):
        resp = client.get("/api/myx/signal/0xtest")
        assert resp.status_code == 200
        assert resp.json()["error"] == "MYX not configured"
