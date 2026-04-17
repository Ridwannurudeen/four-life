"""Tests for FourLife + AsyncFourLife clients. Uses respx to mock httpx transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from four_life import AsyncFourLife, FourLife, FourLifeError


BASE = "https://four-life.test"
TOKEN = "0xAbC0000000000000000000000000000000000001"


@pytest.fixture
def client():
    with FourLife(base_url=BASE, timeout=5.0) as c:
        yield c


# ── Sync client ───────────────────────────────────────────────────────


class TestSyncReads:
    @respx.mock
    def test_get_badge_normalizes_address(self, client: FourLife):
        route = respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
            return_value=httpx.Response(200, json={"badge": {"tier": "healthy"}}),
        )
        r = client.get_badge(TOKEN)
        assert r["badge"]["tier"] == "healthy"
        assert route.called

    @respx.mock
    def test_get_badge_rejects_invalid_address(self, client: FourLife):
        with pytest.raises(FourLifeError, match="Invalid address"):
            client.get_badge("not-an-address")

    @respx.mock
    def test_get_graduation_radar_passes_filters(self, client: FourLife):
        route = respx.get(f"{BASE}/api/graduation-radar").mock(
            return_value=httpx.Response(200, json={"radar": []}),
        )
        client.get_graduation_radar(
            limit=50, quote_asset="BNB", min_confidence="high", sort_by="graduation_probability",
        )
        assert route.called
        qs = route.calls[0].request.url.params
        assert qs["limit"] == "50"
        assert qs["quote_asset"] == "BNB"
        assert qs["min_confidence"] == "high"
        assert qs["sort_by"] == "graduation_probability"

    @respx.mock
    def test_http_500_raises_with_status_and_body(self, client: FourLife):
        respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
            return_value=httpx.Response(500, json={"error": "boom"}),
        )
        with pytest.raises(FourLifeError) as exc_info:
            client.get_badge(TOKEN)
        assert exc_info.value.status == 500
        assert exc_info.value.body == {"error": "boom"}

    @respx.mock
    def test_risk_snapshot(self, client: FourLife):
        respx.get(f"{BASE}/api/token/{TOKEN.lower()}/risk-snapshot").mock(
            return_value=httpx.Response(200, json={"risk_level": "low"}),
        )
        assert client.get_risk_snapshot(TOKEN)["risk_level"] == "low"

    @respx.mock
    def test_operator_checklist(self, client: FourLife):
        respx.get(f"{BASE}/api/token/{TOKEN.lower()}/operator-checklist").mock(
            return_value=httpx.Response(200, json={"checklist": [], "item_count": 0}),
        )
        assert client.get_operator_checklist(TOKEN)["item_count"] == 0

    @respx.mock
    def test_creator_score(self, client: FourLife):
        respx.get(f"{BASE}/api/creator/{TOKEN.lower()}/survival-score").mock(
            return_value=httpx.Response(200, json={"tracked": False, "trust_tier": "unknown"}),
        )
        assert client.get_creator_score(TOKEN)["trust_tier"] == "unknown"

    @respx.mock
    def test_creators_leaderboard_query_string(self, client: FourLife):
        route = respx.get(f"{BASE}/api/creators/leaderboard").mock(
            return_value=httpx.Response(200, json={"count": 0, "creators": []}),
        )
        client.get_creators_leaderboard(sort_by="trust_tier", min_launches=3, limit=50)
        qs = route.calls[0].request.url.params
        assert qs["sort_by"] == "trust_tier"
        assert qs["min_launches"] == "3"
        assert qs["limit"] == "50"


class TestSyncHistory:
    @respx.mock
    def test_get_history_params(self, client: FourLife):
        route = respx.get(f"{BASE}/api/token/{TOKEN.lower()}/history").mock(
            return_value=httpx.Response(200, json={"snapshots": [], "count": 0}),
        )
        client.get_history(TOKEN, limit=10, since=1_000, transitions_only=True)
        qs = route.calls[0].request.url.params
        assert qs["limit"] == "10"
        assert qs["since"] == "1000"
        assert qs["transitions_only"] == "true"

    @respx.mock
    def test_get_diff_requires_since(self, client: FourLife):
        respx.get(f"{BASE}/api/token/{TOKEN.lower()}/diff").mock(
            return_value=httpx.Response(200, json={"tier_changes": []}),
        )
        assert client.get_diff(TOKEN, since=1_000)["tier_changes"] == []

    @respx.mock
    def test_iter_history_export_parses_ndjson(self, client: FourLife):
        payload = (
            b'{"token_address":"0xabc","tier":"healthy","recorded_at":1000}\n'
            b'{"token_address":"0xabc","tier":"at_risk","recorded_at":2000}\n'
        )
        respx.get(f"{BASE}/api/history/export.ndjson").mock(
            return_value=httpx.Response(200, content=payload),
        )
        snapshots = list(client.iter_history_export())
        assert len(snapshots) == 2
        assert snapshots[0]["tier"] == "healthy"
        assert snapshots[1]["tier"] == "at_risk"


class TestSyncWrites:
    @respx.mock
    def test_track_token_sends_auth_and_body(self):
        with FourLife(base_url=BASE, api_secret="test-secret") as c:
            route = respx.post(f"{BASE}/api/agent/track").mock(
                return_value=httpx.Response(200, json={"status": "tracking", "token_address": TOKEN.lower(), "name": "X", "symbol": "X", "message": "ok"}),
            )
            c.track_token(token_address=TOKEN, name="Test", symbol="TST", quote_asset="usdt")
            req = route.calls[0].request
            assert req.headers["Authorization"] == "Bearer test-secret"
            body = req.read().decode()
            assert '"quote_asset":"USDT"' in body
            assert '"token_address":"' + TOKEN.lower() in body

    @respx.mock
    def test_set_protection_policy_strips_none_fields(self):
        with FourLife(base_url=BASE, api_secret="test") as c:
            route = respx.put(f"{BASE}/api/protection/{TOKEN.lower()}").mock(
                return_value=httpx.Response(200, json={"active": True, "thresholds": {}}),
            )
            c.set_protection_policy(
                TOKEN, max_whale_concentration=28, critical_contract_risk=70,
            )
            body = route.calls[0].request.read().decode()
            assert '"active":true' in body
            assert '"max_whale_concentration":28.0' in body
            assert '"critical_contract_risk":70' in body
            assert "critical_buy_sell_ratio" not in body  # None field omitted

    @respx.mock
    def test_create_webhook_validates_url(self):
        with FourLife(base_url=BASE, api_secret="test") as c:
            with pytest.raises(FourLifeError, match="http"):
                c.create_webhook(url="ftp://nope")

    @respx.mock
    def test_create_webhook_sends_events(self):
        with FourLife(base_url=BASE, api_secret="test") as c:
            route = respx.post(f"{BASE}/api/webhooks").mock(
                return_value=httpx.Response(200, json={"id": "whs_x", "secret": "whsec_y", "active": True}),
            )
            c.create_webhook(
                url="https://example.com/hook",
                events=["badge.tier_changed", "protection.level_changed"],
                token_filter=TOKEN,
            )
            body = route.calls[0].request.read().decode()
            assert '"badge.tier_changed"' in body
            assert '"protection.level_changed"' in body
            assert '"token_filter":"' + TOKEN.lower() in body

    @respx.mock
    def test_delete_webhook_hits_path(self):
        with FourLife(base_url=BASE, api_secret="test") as c:
            respx.delete(f"{BASE}/api/webhooks/whs_xyz").mock(
                return_value=httpx.Response(200, json={"deleted": True}),
            )
            assert c.delete_webhook("whs_xyz")["deleted"] is True


class TestSyncWatch:
    @respx.mock
    def test_watch_token_invokes_callback(self, client: FourLife):
        import threading

        respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
            return_value=httpx.Response(200, json={"badge": {"tier": "healthy"}}),
        )

        received: list[dict] = []
        done = threading.Event()

        def on_update(b: dict):
            received.append(b)
            done.set()

        unwatch = client.watch_token(TOKEN, on_update, interval_seconds=0.05)
        try:
            assert done.wait(2.0) is True
            assert received[0]["badge"]["tier"] == "healthy"
        finally:
            unwatch()


# ── Async client ──────────────────────────────────────────────────────


class TestAsyncClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_async_get_badge(self):
        async with AsyncFourLife(base_url=BASE) as c:
            respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
                return_value=httpx.Response(200, json={"badge": {"tier": "graduation_watch"}}),
            )
            r = await c.get_badge(TOKEN)
            assert r["badge"]["tier"] == "graduation_watch"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_http_error_raises(self):
        async with AsyncFourLife(base_url=BASE) as c:
            respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
                return_value=httpx.Response(404, json={"error": "not found"}),
            )
            with pytest.raises(FourLifeError) as exc_info:
                await c.get_badge(TOKEN)
            assert exc_info.value.status == 404

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_timeout_raises_fourlife_error(self):
        async with AsyncFourLife(base_url=BASE, timeout=0.1) as c:
            respx.get(f"{BASE}/api/token/{TOKEN.lower()}/badge").mock(
                side_effect=httpx.TimeoutException("slow"),
            )
            with pytest.raises(FourLifeError, match="timed out"):
                await c.get_badge(TOKEN)

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_set_protection_policy(self):
        async with AsyncFourLife(base_url=BASE, api_secret="t") as c:
            route = respx.put(f"{BASE}/api/protection/{TOKEN.lower()}").mock(
                return_value=httpx.Response(200, json={"active": True}),
            )
            await c.set_protection_policy(TOKEN, active=False)
            body = route.calls[0].request.read().decode()
            assert '"active":false' in body
