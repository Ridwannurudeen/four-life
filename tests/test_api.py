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
    mem.tracked_launches = 2
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


def _make_launch(creator: str, *, graduated: bool, peak_curve: float = 50, peak_holders: int = 100, launched_at: float = 0, symbol: str = "X"):
    from agent.memory.store import LaunchRecord
    return LaunchRecord(
        token_address="0x" + symbol.lower().zfill(40).replace(" ", "0"),
        name=symbol,
        symbol=symbol,
        narrative="test",
        creator=creator,
        quote_asset="BNB",
        graduated=graduated,
        peak_curve_progress=peak_curve,
        peak_holders=peak_holders,
        launched_at=launched_at,
    )


class TestCreatorsLeaderboard:
    def test_empty_returns_zero_creators(self, client):
        resp = client.get("/api/creators/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["total_creators"] == 0
        assert data["creators"] == []

    def test_aggregates_multi_creator_launches(self, client, mock_agent):
        proven_creator = "0x" + "a1" * 20
        emerging_creator = "0x" + "b2" * 20
        # proven: 4 launches, 3 graduations, high holders → trust_tier=proven
        proven_launches = [
            _make_launch(proven_creator, graduated=True, peak_curve=100, peak_holders=500, launched_at=3000, symbol="PROVEN1"),
            _make_launch(proven_creator, graduated=True, peak_curve=95, peak_holders=400, launched_at=2000, symbol="PROVEN2"),
            _make_launch(proven_creator, graduated=True, peak_curve=100, peak_holders=600, launched_at=1500, symbol="PROVEN3"),
            _make_launch(proven_creator, graduated=False, peak_curve=45, peak_holders=120, launched_at=1000, symbol="PROVEN4"),
        ]
        # emerging: 4 launches, 1 graduation, decent curve
        emerging_launches = [
            _make_launch(emerging_creator, graduated=False, peak_curve=55, peak_holders=120, launched_at=2500, symbol="EM1"),
            _make_launch(emerging_creator, graduated=True, peak_curve=100, peak_holders=200, launched_at=2200, symbol="EM2"),
            _make_launch(emerging_creator, graduated=False, peak_curve=40, peak_holders=80, launched_at=2100, symbol="EM3"),
            _make_launch(emerging_creator, graduated=False, peak_curve=30, peak_holders=50, launched_at=2000, symbol="EM4"),
        ]
        mock_agent.memory.memory.launches = proven_launches + emerging_launches

        resp = client.get("/api/creators/leaderboard")
        data = resp.json()
        assert data["total_creators"] == 2
        wallets = [c["wallet"] for c in data["creators"]]
        assert proven_creator in wallets and emerging_creator in wallets

        proven_row = next(c for c in data["creators"] if c["wallet"] == proven_creator)
        assert proven_row["trust_tier"] == "proven"
        assert proven_row["graduations"] == 3
        assert proven_row["graduation_rate"] == 0.75
        # Default sort = trust_tier → proven comes before emerging
        assert wallets[0] == proven_creator

    def test_filters_by_trust_tier(self, client, mock_agent):
        a = "0x" + "aa" * 20
        b = "0x" + "bb" * 20
        mock_agent.memory.memory.launches = [
            _make_launch(a, graduated=True, peak_curve=100, peak_holders=400, symbol="A1"),
            _make_launch(a, graduated=True, peak_curve=100, peak_holders=500, symbol="A2"),
            _make_launch(a, graduated=True, peak_curve=100, peak_holders=600, symbol="A3"),
            # Only 1 launch → new_creator
            _make_launch(b, graduated=False, peak_curve=10, peak_holders=20, symbol="B1"),
        ]
        resp = client.get("/api/creators/leaderboard?trust_tier=proven")
        data = resp.json()
        assert data["total_creators"] == 1
        assert data["creators"][0]["wallet"] == a

    def test_min_launches_filter(self, client, mock_agent):
        a = "0x" + "aa" * 20
        b = "0x" + "bb" * 20
        mock_agent.memory.memory.launches = [
            _make_launch(a, graduated=False, symbol="A1"),
            _make_launch(a, graduated=False, symbol="A2"),
            _make_launch(a, graduated=False, symbol="A3"),
            _make_launch(b, graduated=False, symbol="B1"),
        ]
        resp = client.get("/api/creators/leaderboard?min_launches=3")
        assert resp.json()["total_creators"] == 1
        assert resp.json()["creators"][0]["wallet"] == a

    def test_limit_caps_result(self, client, mock_agent):
        launches = []
        for i in range(5):
            w = "0x" + str(i) * 40
            launches.append(_make_launch(w, graduated=False, symbol=f"T{i}"))
        mock_agent.memory.memory.launches = launches
        resp = client.get("/api/creators/leaderboard?limit=3")
        data = resp.json()
        assert data["count"] == 3
        assert data["total_creators"] == 5  # total_creators reflects filters, not limit

    def test_rejects_unknown_sort_by(self, client):
        resp = client.get("/api/creators/leaderboard?sort_by=bogus")
        assert resp.status_code == 400

    def test_sort_by_recent_orders_by_last_launch(self, client, mock_agent):
        a = "0x" + "aa" * 20
        b = "0x" + "bb" * 20
        mock_agent.memory.memory.launches = [
            _make_launch(a, graduated=False, launched_at=1_000, symbol="A1"),
            _make_launch(b, graduated=False, launched_at=5_000, symbol="B1"),
        ]
        resp = client.get("/api/creators/leaderboard?sort_by=recent")
        wallets = [c["wallet"] for c in resp.json()["creators"]]
        assert wallets == [b, a]


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


class TestContractRiskEndpoint:
    def _stub_risk(self, mock_agent, score=25, flags=None, has_mint=False, has_blacklist=False):
        from agent.security.contract_analyzer import ContractRisk
        return ContractRisk(
            token_address="0xcontract",
            analyzed_at=1700000000.0,
            has_mint_function=has_mint,
            has_blacklist=has_blacklist,
            is_proxy=False,
            has_pause=False,
            has_ownership=True,
            owner_address="0x" + "00" * 20,
            owner_is_renounced=True,
            is_verified_on_bscscan=True,
            risk_score=score,
            flags=flags or [],
            raw_bytecode_hash="abc123",
            confidence="high",
        )

    def test_contract_risk_endpoint_returns_payload(self, client, mock_agent):
        from agent import api as api_module
        api_module._contract_risk_cache.clear()

        risk = self._stub_risk(mock_agent, score=40, has_mint=True, flags=[
            {"id": "mint_function", "severity": "critical", "evidence": "abi", "message": "m"},
        ])
        with patch.object(
            api_module.ContractAnalyzer, "analyze", AsyncMock(return_value=risk)
        ):
            resp = client.get("/api/token/0xcontract/contract-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] == 40
        assert data["has_mint_function"] is True
        assert any(f["id"] == "mint_function" for f in data["flags"])
        assert data["confidence"] == "high"

    def test_contract_risk_endpoint_caches_across_requests(self, client, mock_agent):
        from agent import api as api_module
        api_module._contract_risk_cache.clear()

        risk = self._stub_risk(mock_agent, score=10)
        analyze_mock = AsyncMock(return_value=risk)
        with patch.object(api_module.ContractAnalyzer, "analyze", analyze_mock):
            r1 = client.get("/api/token/0xcache/contract-risk")
            r2 = client.get("/api/token/0xcache/contract-risk")
        assert r1.status_code == 200 and r2.status_code == 200
        assert analyze_mock.call_count == 1  # second call used cache

    def test_contract_risk_endpoint_returns_502_when_analyzer_fails(self, client, mock_agent):
        from agent import api as api_module
        api_module._contract_risk_cache.clear()

        with patch.object(
            api_module.ContractAnalyzer,
            "analyze",
            AsyncMock(side_effect=RuntimeError("rpc down")),
        ):
            resp = client.get("/api/token/0xfail/contract-risk")
        assert resp.status_code == 502

    def test_risk_snapshot_merges_contract_flags(self, client, mock_agent):
        """The legacy /risk-snapshot endpoint should include contract-analyzer flags."""
        from agent import api as api_module
        from agent.fourmeme.monitor import TokenHealth
        api_module._contract_risk_cache.clear()

        health = TokenHealth(
            address="0xmerge", name="M", symbol="M", phase="defend",
            top_holder_pct=5, buy_sell_ratio=1.2, holder_velocity=2, age_hours=5,
            curve_progress_pct=10, whale_count=0, unique_buyers=100,
            graduation_confidence="high", graduation_target=18.0,
        )
        mock_agent.monitor.state.tokens = {"0xmerge": health}
        risk = self._stub_risk(mock_agent, score=70, has_mint=True, has_blacklist=True, flags=[
            {"id": "mint_function", "severity": "critical", "evidence": "abi", "message": "mint"},
            {"id": "blacklist", "severity": "high", "evidence": "abi", "message": "bl"},
        ])
        with patch.object(
            api_module.ContractAnalyzer, "analyze", AsyncMock(return_value=risk)
        ):
            resp = client.get("/api/token/0xmerge/risk-snapshot")
        assert resp.status_code == 200
        data = resp.json()
        ids = {f["id"] for f in data["evidence"]}
        assert "mint_function" in ids
        assert "blacklist" in ids
        assert data["metrics"]["contract_risk_score"] == 70
        assert data["contract_risk"]["risk_score"] == 70

    def test_badge_at_risk_when_contract_risk_high(self, client, mock_agent):
        """Badge endpoint should force at_risk when contract_risk_score >= 60."""
        from agent import api as api_module
        from agent.fourmeme.monitor import TokenHealth
        api_module._contract_risk_cache.clear()

        # Otherwise this token would be 'healthy' — mint override must flip it to 'at_risk'.
        health = TokenHealth(
            address="0xoverride", name="O", symbol="O", phase="nurture",
            health_score=80, buy_sell_ratio=2.0, holder_velocity=10,
            top_holder_pct=5, curve_progress_pct=30, age_hours=3,
            unique_buyers=200, whale_count=0, graduation_confidence="high",
            graduation_target=18.0,
        )
        mock_agent.monitor.state.tokens = {"0xoverride": health}
        risk = self._stub_risk(mock_agent, score=70, has_mint=True)
        with patch.object(
            api_module.ContractAnalyzer, "analyze", AsyncMock(return_value=risk)
        ):
            resp = client.get("/api/token/0xoverride/badge")
        assert resp.status_code == 200
        badge = resp.json()["badge"]
        assert badge["tier"] == "at_risk"
        rules = {r["rule"] for r in badge["why"]}
        assert "contract_rug_risk" in rules


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


class TestDGridStatsEndpoint:
    def test_returns_llm_config_and_counters(self, client):
        resp = client.get("/api/dgrid/stats")
        assert resp.status_code == 200
        data = resp.json()
        # Config surface
        assert "providers_configured" in data
        assert "primary_order" in data
        assert "default_dgrid_model" in data
        assert "task_model_map" in data
        # Task mapping includes the four task types
        tm = data["task_model_map"]
        assert "narrative" in tm
        assert "content" in tm
        assert "risk" in tm
        assert "vision" in tm
        # Counters are present (possibly empty — that's fine)
        assert "usage_by_provider" in data
        assert "usage_by_task" in data
        assert "usage_by_model" in data
        assert "fallback_events" in data
        assert "last_dgrid_error" in data
        assert "uptime_seconds" in data
        assert "session_started_at" in data
        assert "llm_provider" in data

    def test_stats_available_without_agent(self):
        """Endpoint must respond even when the agent failed to initialize."""
        from fastapi.testclient import TestClient
        with patch("agent.api.agent", None):
            from agent.api import app
            c = TestClient(app)
            resp = c.get("/api/dgrid/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "primary_order" in data

    def test_stats_includes_cost_and_breaker_surface(self, client):
        resp = client.get("/api/dgrid/stats")
        assert resp.status_code == 200
        data = resp.json()
        # Cost dashboard surface
        assert "cost_usd" in data
        assert "total" in data["cost_usd"]
        assert "by_provider" in data["cost_usd"]
        assert "by_task" in data["cost_usd"]
        assert "by_model" in data["cost_usd"]
        # Circuit breaker state
        assert "breaker" in data
        assert data["breaker"]["state"] in ("closed", "open", "half_open")
        assert "failure_threshold" in data["breaker"]
        # Chaos + counters
        assert "chaos_enabled" in data
        assert "breaker_skips" in data
        assert "transient_retries" in data
        assert "trace_count" in data


class TestDGridTraceEndpoint:
    def test_trace_shape(self, client):
        resp = client.get("/api/dgrid/trace?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "limit" in data
        assert "trace" in data
        assert data["limit"] == 5

    def test_limit_is_capped(self, client):
        # Hard cap at 200 — passing 99999 should not explode.
        resp = client.get("/api/dgrid/trace?limit=99999")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 200


class TestDGridHealthEndpoint:
    def test_health_shape(self, client):
        resp = client.get("/api/dgrid/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("green", "amber", "red")
        assert "dgrid_configured" in data
        assert "primary_model" in data


class TestDGridLeaderboard:
    def test_leaderboard_shape(self, client):
        resp = client.get("/api/dgrid/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "auto_tune_enabled" in data
        assert "current_task_map" in data
        # Empty rows are fine for a fresh client
        assert isinstance(data["rows"], list)


class TestDGridAudit:
    def test_audit_starts_at_genesis(self, client):
        resp = client.get("/api/dgrid/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_root" in data
        assert "num_calls_chained" in data
        assert "genesis" in data
        # On a fresh client, current_root should equal genesis.
        assert data["current_root"] == data["genesis"]

    def test_attest_requires_flag_enabled(self, client):
        # DGRID_ATTEST_ONCHAIN defaults to False — endpoint must refuse.
        resp = client.post(
            "/api/dgrid/attest",
            headers={"Authorization": "Bearer test-secret"},
        )
        # Either 401 (no API_SECRET set → require_auth lets it through) or 403
        # (attest disabled). We accept either as "did not publish".
        assert resp.status_code in (401, 403)

    def test_audit_calls_endpoint_shape(self, client):
        resp = client.get("/api/dgrid/audit/calls?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "offset" in data
        assert "limit" in data
        assert "count" in data
        assert "total" in data
        assert "calls" in data
        assert "current_root" in data
        assert "genesis" in data
        assert isinstance(data["calls"], list)

    def test_audit_calls_limit_is_capped(self, client):
        resp = client.get("/api/dgrid/audit/calls?limit=99999")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 10000

    def test_audit_calls_pagination_hint(self, client):
        # Response must advertise next_offset + has_more so integrators can
        # paginate deterministically without hitting either bound.
        resp = client.get("/api/dgrid/audit/calls?limit=10")
        data = resp.json()
        assert "next_offset" in data
        assert "has_more" in data
        assert isinstance(data["has_more"], bool)


class TestDGridChaos:
    def test_chaos_toggle_updates_state(self, client):
        # With API_SECRET unset in test env, require_auth is a no-op.
        resp = client.post(
            "/api/dgrid/chaos",
            json={"enabled": True, "reason": "unit test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chaos_enabled"] is True
        assert data["reason"] == "unit test"
        # Disable
        resp = client.post("/api/dgrid/chaos", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["chaos_enabled"] is False

    def test_chaos_requires_enabled_field(self, client):
        resp = client.post("/api/dgrid/chaos", json={})
        assert resp.status_code == 422  # pydantic validation


class TestDGridConsensus:
    def test_consensus_rejects_empty_prompt(self, client):
        resp = client.post("/api/dgrid/consensus", json={"prompt": "   "})
        assert resp.status_code == 400
