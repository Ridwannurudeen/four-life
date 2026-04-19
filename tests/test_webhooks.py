"""Tests for outbound webhooks — store, signing, dispatcher, auto-disable."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

from agent import webhooks as wh
from agent.webhooks import (
    AUTO_DISABLE_CONSECUTIVE_FAILURES,
    EVENT_BADGE_TIER_CHANGED,
    MAX_DELIVERY_ATTEMPTS,
    WebhookStore,
    deliver,
    fire_tier_changed,
    set_transport_override,
    sign_payload,
    verify_signature,
)


TOKEN = "0xAbC0000000000000000000000000000000000001"


@pytest.fixture
def store(tmp_path: Path) -> WebhookStore:
    return WebhookStore(db_path=tmp_path / "webhooks.db")


@pytest.fixture(autouse=True)
def _zero_retry_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove sleep overhead from retry tests — delays of 0 match semantic behavior
    but keep the suite fast."""
    monkeypatch.setattr(wh, "RETRY_SCHEDULE_SECONDS", (0, 0, 0))


@pytest.fixture(autouse=True)
def _reset_transport() -> None:
    set_transport_override(None)
    yield
    set_transport_override(None)


class TestSubscriptions:
    def test_subscribe_returns_secret_once(self, store: WebhookStore) -> None:
        sub, secret = store.subscribe(
            url="https://example.com/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
        )
        assert sub.id.startswith("whs_")
        assert secret.startswith("whsec_")
        # Secret is not recoverable via any public getter
        assert not hasattr(store.get_subscription(sub.id), "secret")

    def test_subscribe_rejects_unsupported_event(self, store: WebhookStore) -> None:
        with pytest.raises(ValueError, match="Unsupported event type"):
            store.subscribe(url="https://example.com/hook", events=["rug.detected"])

    def test_subscribe_rejects_non_http_url(self, store: WebhookStore) -> None:
        with pytest.raises(ValueError, match="http"):
            store.subscribe(url="ftp://example.com/hook", events=[EVENT_BADGE_TIER_CHANGED])

    def test_subscribe_rejects_ssrf_targets(self, store: WebhookStore) -> None:
        from agent.webhooks import validate_webhook_url
        # Literal private/loopback/link-local IPs — rejected at registration.
        for bad in [
            "http://127.0.0.1/hook",
            "http://10.0.0.5/hook",
            "http://192.168.1.1/hook",
            "http://169.254.169.254/latest/meta-data",  # EC2 / GCP metadata
            "http://[::1]/hook",
            "http://[fe80::1]/hook",
        ]:
            with pytest.raises(ValueError):
                store.subscribe(url=bad, events=[EVENT_BADGE_TIER_CHANGED])
        # Blocked hostname aliases.
        for bad in ["http://localhost/hook", "http://metadata.google.internal/"]:
            with pytest.raises(ValueError):
                validate_webhook_url(bad, require_resolvable=False)

    def test_list_excludes_disabled_by_default(self, store: WebhookStore) -> None:
        sub1, _ = store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        sub2, _ = store.subscribe(url="https://b.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        store.disable_subscription(sub1.id)
        assert [s.id for s in store.list_subscriptions()] == [sub2.id]
        assert {s.id for s in store.list_subscriptions(include_disabled=True)} == {sub1.id, sub2.id}

    def test_delete_subscription(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(url="https://example.com/hook", events=[EVENT_BADGE_TIER_CHANGED])
        assert store.delete_subscription(sub.id) is True
        assert store.get_subscription(sub.id) is None
        assert store.delete_subscription(sub.id) is False

    def test_token_filter_normalizes_casing(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(
            url="https://example.com/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter=TOKEN,
        )
        stored = store.get_subscription(sub.id)
        assert stored is not None
        assert stored.token_filter == TOKEN.lower()


class TestMatching:
    def test_matches_when_event_and_token_align(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(
            url="https://example.com/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter=TOKEN,
        )
        matched = store.subscriptions_for_event(
            event_type=EVENT_BADGE_TIER_CHANGED, token_address=TOKEN,
        )
        assert [s.id for s in matched] == [sub.id]

    def test_no_match_when_token_filter_differs(self, store: WebhookStore) -> None:
        store.subscribe(
            url="https://example.com/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter="0x" + "99" * 20,
        )
        matched = store.subscriptions_for_event(
            event_type=EVENT_BADGE_TIER_CHANGED, token_address=TOKEN,
        )
        assert matched == []

    def test_wildcard_subscription_matches_any_token(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(
            url="https://example.com/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter=None,
        )
        matched = store.subscriptions_for_event(
            event_type=EVENT_BADGE_TIER_CHANGED, token_address=TOKEN,
        )
        assert [s.id for s in matched] == [sub.id]

    def test_disabled_subscription_is_excluded(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(url="https://example.com/hook", events=[EVENT_BADGE_TIER_CHANGED])
        store.disable_subscription(sub.id)
        matched = store.subscriptions_for_event(
            event_type=EVENT_BADGE_TIER_CHANGED, token_address=TOKEN,
        )
        assert matched == []


class TestSigning:
    def test_sign_then_verify_roundtrip(self) -> None:
        secret = "whsec_test_secret"
        body = '{"hello":"world"}'
        ts = 1_700_000_000
        sig = sign_payload(secret=secret, body=body, timestamp=ts)
        assert sig.startswith(f"t={ts},v1=")
        assert verify_signature(secret=secret, body=body, signature_header=sig, now=ts) is True

    def test_tampered_body_fails(self) -> None:
        secret = "whsec_test_secret"
        ts = 1_700_000_000
        sig = sign_payload(secret=secret, body='{"a":1}', timestamp=ts)
        assert verify_signature(secret=secret, body='{"a":2}', signature_header=sig, now=ts) is False

    def test_expired_timestamp_fails(self) -> None:
        secret = "whsec_test_secret"
        body = "{}"
        sig = sign_payload(secret=secret, body=body, timestamp=1_000)
        assert verify_signature(
            secret=secret, body=body, signature_header=sig, now=1_000 + 400,
            tolerance_seconds=300,
        ) is False

    def test_malformed_header_fails(self) -> None:
        assert verify_signature(secret="x", body="{}", signature_header="garbage", now=1) is False


class TestFireAndEnqueue:
    def test_fire_enqueues_delivery_per_match(self, store: WebhookStore) -> None:
        sub_a, _ = store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        sub_b, _ = store.subscribe(
            url="https://b.example/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter=TOKEN,
        )
        # Unrelated subscription — won't match because token filter differs
        store.subscribe(
            url="https://c.example/hook",
            events=[EVENT_BADGE_TIER_CHANGED],
            token_filter="0x" + "ff" * 20,
        )
        delivery_ids = fire_tier_changed(
            token_address=TOKEN,
            from_tier="healthy",
            to_tier="at_risk",
            why=[{"rule": "whale"}],
            metrics={"top_holder_pct": 55},
            data_source="live_monitor",
            store=store,
        )
        assert len(delivery_ids) == 2
        all_subs = {d.subscription_id for d in (store.get_delivery(i) for i in delivery_ids) if d}
        assert all_subs == {sub_a.id, sub_b.id}

    def test_delivery_row_carries_event_payload(self, store: WebhookStore) -> None:
        sub, _ = store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        ids = fire_tier_changed(
            token_address=TOKEN,
            from_tier="healthy",
            to_tier="at_risk",
            why=[{"rule": "whale", "passed": True}],
            metrics={"top_holder_pct": 55},
            store=store,
        )
        payload = store.get_delivery_payload(ids[0])
        assert payload is not None
        event, secret = payload
        assert event["type"] == EVENT_BADGE_TIER_CHANGED
        assert event["from_tier"] == "healthy"
        assert event["to_tier"] == "at_risk"
        assert event["token_address"] == TOKEN.lower()
        assert event["id"].startswith("evt_")
        assert secret.startswith("whsec_")


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_success_marks_delivered(self, store: WebhookStore) -> None:
        captured: dict[str, Any] = {}

        async def ok(url: str, body: str, headers: dict) -> tuple[int, str]:
            captured["url"] = url
            captured["body"] = body
            captured["sig"] = headers.get("X-FourLife-Signature", "")
            return 200, "ok"

        set_transport_override(ok)

        sub, secret = store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        ids = fire_tier_changed(
            token_address=TOKEN, from_tier="healthy", to_tier="at_risk",
            why=[], metrics={}, store=store,
        )
        await deliver(store, ids[0])

        d = store.get_delivery(ids[0])
        assert d is not None
        assert d.status == "success"
        assert d.http_status == 200
        assert d.attempts == 1
        assert d.delivered_at is not None
        # Signature header is well-formed and verifies against the secret
        assert verify_signature(
            secret=secret,
            body=captured["body"],
            signature_header=captured["sig"],
        )

    @pytest.mark.asyncio
    async def test_retry_then_success(self, store: WebhookStore) -> None:
        attempts = {"n": 0}

        async def flaky(url: str, body: str, headers: dict) -> tuple[int, str]:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return 500, "server error"
            return 200, "ok"

        set_transport_override(flaky)

        store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        ids = fire_tier_changed(
            token_address=TOKEN, from_tier="healthy", to_tier="at_risk",
            why=[], metrics={}, store=store,
        )
        await deliver(store, ids[0])

        d = store.get_delivery(ids[0])
        assert d is not None
        assert d.status == "success"
        assert d.attempts == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail_marks_dead(self, store: WebhookStore) -> None:
        async def always_fail(url: str, body: str, headers: dict) -> tuple[int, str]:
            return 500, "down"

        set_transport_override(always_fail)

        store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        ids = fire_tier_changed(
            token_address=TOKEN, from_tier="healthy", to_tier="at_risk",
            why=[], metrics={}, store=store,
        )
        await deliver(store, ids[0])

        d = store.get_delivery(ids[0])
        assert d is not None
        assert d.status == "dead"
        assert d.attempts == MAX_DELIVERY_ATTEMPTS
        assert d.http_status == 500
        assert "exhausted" in (d.last_error or "")

    @pytest.mark.asyncio
    async def test_transport_exception_counts_as_failure(self, store: WebhookStore) -> None:
        async def boom(url: str, body: str, headers: dict) -> tuple[int, str]:
            raise RuntimeError("dns failure")

        set_transport_override(boom)

        store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])
        ids = fire_tier_changed(
            token_address=TOKEN, from_tier="healthy", to_tier="at_risk",
            why=[], metrics={}, store=store,
        )
        await deliver(store, ids[0])

        d = store.get_delivery(ids[0])
        assert d is not None
        assert d.status == "dead"
        assert d.attempts == MAX_DELIVERY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_auto_disable_after_consecutive_dead_deliveries(
        self, store: WebhookStore,
    ) -> None:
        async def always_fail(url: str, body: str, headers: dict) -> tuple[int, str]:
            return 502, "bad gateway"

        set_transport_override(always_fail)

        sub, _ = store.subscribe(url="https://a.example/hook", events=[EVENT_BADGE_TIER_CHANGED])

        # Push 10 events through → 10 dead deliveries → subscription disabled.
        for i in range(AUTO_DISABLE_CONSECUTIVE_FAILURES):
            ids = fire_tier_changed(
                token_address=TOKEN,
                from_tier="healthy" if i % 2 == 0 else "at_risk",
                to_tier="at_risk" if i % 2 == 0 else "healthy",
                why=[], metrics={}, store=store,
            )
            assert len(ids) == 1
            await deliver(store, ids[0])

        # Subscription should now be auto-disabled.
        stored = store.get_subscription(sub.id)
        assert stored is not None
        assert stored.disabled_at is not None
        assert stored.is_active() is False

        # No new deliveries are enqueued for subsequent events.
        new_ids = fire_tier_changed(
            token_address=TOKEN, from_tier="healthy", to_tier="at_risk",
            why=[], metrics={}, store=store,
        )
        assert new_ids == []
