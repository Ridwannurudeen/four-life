"""Tests for the MYX signal log + trade attestation chain."""

import pytest

from agent.myx.store import (
    MYX_GENESIS,
    MYXAttestationChain,
    MYXSignalLog,
    get_myx_chain,
    get_signal_log,
    get_position_log,
    reset_myx_for_tests,
    verify_myx_chain,
)


class TestSignalLog:
    def test_append_and_count(self):
        log = MYXSignalLog()
        log.append({"ts_ms": 1, "action": "short"})
        log.append({"ts_ms": 2, "action": "hold"})
        assert log.count() == 2

    def test_read_range_paginates(self):
        log = MYXSignalLog()
        for i in range(20):
            log.append({"ts_ms": i, "action": "test"})
        window = log.read_range(5, 3)
        assert [r["ts_ms"] for r in window] == [5, 6, 7]

    def test_tail_filter_by_token(self):
        log = MYXSignalLog()
        for i in range(10):
            log.append({
                "ts_ms": i,
                "token_address": "0xaaa" if i % 2 == 0 else "0xbbb",
                "action": "x",
            })
        a_rows = log.tail(n=10, token_address="0xaaa")
        assert len(a_rows) == 5
        assert all(r["token_address"] == "0xaaa" for r in a_rows)

    def test_singleton_reset(self):
        log = get_signal_log()
        log.append({"ts_ms": 1, "action": "a"})
        reset_myx_for_tests()
        fresh = get_signal_log()
        assert fresh.count() == 0


class TestAttestationChain:
    def test_starts_at_genesis(self):
        chain = MYXAttestationChain()
        assert chain.tip == MYX_GENESIS
        assert chain.count == 0

    def test_event_digest_is_deterministic(self):
        kwargs = dict(
            kind="open", token_address="0xAAa", pair_index=3, is_long=False,
            collateral_wei=1000000, size_amount=5000000,
            tx_hash="0xTxHash", ts_ms=1700000000000,
        )
        a = MYXAttestationChain.event_digest(**kwargs)
        b = MYXAttestationChain.event_digest(**kwargs)
        assert a == b
        assert len(a) == 64

    def test_event_digest_changes_with_kind(self):
        base = dict(
            token_address="0xA", pair_index=0, is_long=True,
            collateral_wei=1, size_amount=1, tx_hash="0x1", ts_ms=1,
        )
        open_d = MYXAttestationChain.event_digest(kind="open", **base)
        close_d = MYXAttestationChain.event_digest(kind="close", **base)
        assert open_d != close_d

    def test_event_digest_normalizes_address_case(self):
        a = MYXAttestationChain.event_digest(
            kind="open", token_address="0xAAA", pair_index=1, is_long=True,
            collateral_wei=1, size_amount=1, tx_hash="0xABC", ts_ms=1,
        )
        b = MYXAttestationChain.event_digest(
            kind="open", token_address="0xaaa", pair_index=1, is_long=True,
            collateral_wei=1, size_amount=1, tx_hash="0xabc", ts_ms=1,
        )
        # Digests should match because the helper lowercases both addresses.
        assert a == b

    def test_append_advances_tip(self):
        chain = MYXAttestationChain()
        tip1 = chain.append("aa" * 32)
        assert tip1 != MYX_GENESIS
        tip2 = chain.append("bb" * 32)
        assert tip2 != tip1
        assert chain.count == 2


class TestVerifier:
    def test_verifier_round_trip(self):
        chain = MYXAttestationChain()
        events = []
        for i in range(5):
            digest = MYXAttestationChain.event_digest(
                kind="open" if i % 2 == 0 else "close",
                token_address=f"0x{i:040x}",
                pair_index=i, is_long=bool(i % 2),
                collateral_wei=1_000_000 * (i + 1),
                size_amount=5_000_000 * (i + 1),
                tx_hash=f"0x{i:064x}",
                ts_ms=1700000000000 + i,
            )
            events.append({"event_digest": digest})
            chain.append(digest)
        assert verify_myx_chain(events, chain.tip) is True
        # Tampering must be caught
        events[2] = {"event_digest": "ff" * 32}
        assert verify_myx_chain(events, chain.tip) is False

    def test_verifier_rederives_digest_from_fields(self):
        chain = MYXAttestationChain()
        ev = {
            "kind": "open",
            "token_address": "0x123",
            "pair_index": 0,
            "is_long": False,
            "collateral_wei": 100,
            "size_amount": 500,
            "tx_hash": "0xabc",
            "ts_ms": 1700000000000,
        }
        expected = MYXAttestationChain.event_digest(**ev)
        chain.append(expected)
        # Pass the raw fields without call_digest — verifier recomputes.
        assert verify_myx_chain([ev], chain.tip) is True


class TestAPIEndpoints:
    def test_signals_endpoint_empty(self):
        from fastapi.testclient import TestClient
        from agent.api import app
        c = TestClient(app)
        resp = c.get("/api/myx/signals?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data
        assert "total_ever" in data
        assert data["count"] == 0

    def test_audit_endpoint_starts_at_genesis(self):
        from fastapi.testclient import TestClient
        from agent.api import app
        c = TestClient(app)
        resp = c.get("/api/myx/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_root"] == data["genesis"]
        assert data["num_events_chained"] == 0

    def test_audit_events_endpoint_paginates(self):
        from fastapi.testclient import TestClient
        from agent.api import app
        c = TestClient(app)
        resp = c.get("/api/myx/audit/events?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "current_root" in data
        assert "genesis" in data
