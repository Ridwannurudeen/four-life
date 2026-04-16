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


class TestBadgeEndpoint:
    def test_returns_badge_for_tracked_token(self, client, mock_agent):
        from agent.fourmeme.monitor import TokenHealth
        health = TokenHealth(
            address="0xbadge", name="B", symbol="B",
            health_score=70, phase="nurture",
            unique_buyers=200, buy_sell_ratio=1.5, holder_velocity=8,
            top_holder_pct=15, curve_progress_pct=30, age_hours=2,
            graduation_confidence="high", graduation_target=18.0,
        )
        mock_agent.monitor.state.tokens = {"0xbadge": health}
        resp = client.get("/api/token/0xbadge/badge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["badge"]["tier"] in {"graduated", "graduation_watch", "healthy", "at_risk", "observed"}
        assert "why" in data["badge"]
        assert data["data_source"] == "live_monitor"

    def test_returns_404_when_unknown(self, client, mock_agent):
        mock_agent.api._client.post = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value={"data": []}),
        ))
        resp = client.get("/api/token/0xmissing/badge")
        assert resp.status_code == 404


class TestRiskSnapshotEndpoint:
    def test_returns_risk_snapshot(self, client, mock_agent):
        from agent.fourmeme.monitor import TokenHealth
        health = TokenHealth(
            address="0xrs", name="RS", symbol="RS", phase="defend",
            top_holder_pct=45, buy_sell_ratio=0.4, holder_velocity=0.5, age_hours=5,
            curve_progress_pct=10, whale_count=4, unique_buyers=100,
            graduation_confidence="high", graduation_target=18.0,
        )
        mock_agent.monitor.state.tokens = {"0xrs": health}
        resp = client.get("/api/token/0xrs/risk-snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] in {"critical", "high", "medium", "info", "low"}
        assert isinstance(data["evidence"], list)
        assert data["confidence_score"] == "high"

    def test_untracked_token_returns_404(self, client):
        resp = client.get("/api/token/0xunknown/risk-snapshot")
        assert resp.status_code == 404


class TestCreatorSurvivalScore:
    def test_new_creator_returns_tracked_false(self, client):
        resp = client.get("/api/creator/0xnever/survival-score")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tracked"] is False
        assert data["trust_tier"] == "unknown"


class TestOperatorChecklist:
    def test_returns_checklist_for_tracked_token(self, client, mock_agent):
        from agent.fourmeme.monitor import TokenHealth
        health = TokenHealth(
            address="0xck", name="CK", symbol="CK", phase="defend",
            age_hours=12, top_holder_pct=25, buy_sell_ratio=0.9,
            curve_progress_pct=30,
        )
        mock_agent.monitor.state.tokens = {"0xck": health}
        resp = client.get("/api/token/0xck/operator-checklist")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["checklist"], list)
        assert data["item_count"] == len(data["checklist"])
        # Defend-phase token with whale concentration should have a defend-phase item
        phases = {item["phase"] for item in data["checklist"]}
        assert "defend" in phases


class TestPlatformCohorts:
    def test_empty_returns_structure(self, client):
        resp = client.get("/api/platform/cohorts")
        assert resp.status_code == 200
        data = resp.json()
        assert "cohorts_by_age" in data
        assert "by_narrative" in data
        assert "whale_risk_distribution" in data


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
