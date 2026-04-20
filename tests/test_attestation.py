"""Tests for the DGrid attestation hash chain."""

import hashlib
import json

import pytest

from agent.brain.attestation import (
    AttestationChain,
    AttestationLog,
    GENESIS_HASH,
    get_chain,
    get_log,
    reset_chain_for_tests,
    sha256_hex,
    verify_chain,
)


class TestCallDigest:
    def test_digest_is_deterministic(self):
        kwargs = dict(
            provider="dgrid", model="google/gemini-2.5-flash", task="risk",
            prompt_hash="ab" * 32, response_hash="cd" * 32,
            prompt_tokens=100, completion_tokens=200, ts_ms=1700000000000,
        )
        a = AttestationChain.call_digest(**kwargs)
        b = AttestationChain.call_digest(**kwargs)
        assert a == b
        assert len(a) == 64

    def test_digest_changes_with_each_field(self):
        base = dict(
            provider="dgrid", model="google/gemini-2.5-flash", task="risk",
            prompt_hash="ab" * 32, response_hash="cd" * 32,
            prompt_tokens=100, completion_tokens=200, ts_ms=1700000000000,
        )
        seen = {AttestationChain.call_digest(**base)}
        for field, mutation in [
            ("provider", "openai"),
            ("model", "openai/gpt-4o"),
            ("task", "narrative"),
            ("prompt_hash", "ff" * 32),
            ("response_hash", "ff" * 32),
            ("prompt_tokens", 101),
            ("completion_tokens", 201),
            ("ts_ms", 1700000000001),
        ]:
            modified = {**base, field: mutation}
            d = AttestationChain.call_digest(**modified)
            assert d not in seen, f"mutating {field} did not change digest"
            seen.add(d)


class TestChain:
    def test_starts_at_genesis(self):
        chain = AttestationChain()
        assert chain.tip == GENESIS_HASH
        assert chain.count == 0

    def test_append_advances_tip_and_count(self):
        chain = AttestationChain()
        tip1 = chain.append("aa" * 32)
        assert tip1 != GENESIS_HASH
        assert chain.count == 1
        tip2 = chain.append("bb" * 32)
        assert tip2 != tip1
        assert chain.count == 2

    def test_chain_is_reproducible(self):
        digests = ["aa" * 32, "bb" * 32, "cc" * 32]
        # Build independently.
        expected = GENESIS_HASH
        for d in digests:
            expected = sha256_hex((expected + d).encode())

        chain = AttestationChain()
        final = None
        for d in digests:
            final = chain.append(d)
        assert final == expected

    def test_record_attestation_updates_snapshot(self):
        chain = AttestationChain()
        chain.append("aa" * 32)
        chain.append("bb" * 32)
        root = chain.tip
        chain.record_attestation(root, "0xdeadbeef", count=2)
        snap = chain.snapshot()
        assert snap["last_published_root"] == root
        assert snap["last_published_txhash"] == "0xdeadbeef"
        assert snap["last_published_count"] == 2
        assert snap["unpublished_calls"] == 0
        # Append another call → unpublished goes up by 1
        chain.append("cc" * 32)
        snap = chain.snapshot()
        assert snap["unpublished_calls"] == 1

    def test_singleton_reset_returns_genesis(self):
        chain = get_chain()
        chain.append("aa" * 32)
        assert chain.tip != GENESIS_HASH
        reset_chain_for_tests()
        fresh = get_chain()
        assert fresh.tip == GENESIS_HASH
        assert fresh.count == 0


class TestAttestationLog:
    def test_in_memory_append_and_read(self):
        log = AttestationLog()
        log.append({"seq": 1, "call_digest": "aa"})
        log.append({"seq": 2, "call_digest": "bb"})
        assert log.count() == 2
        entries = log.read_range(0, 10)
        assert len(entries) == 2
        assert entries[0]["seq"] == 1
        assert entries[1]["seq"] == 2

    def test_pagination(self):
        log = AttestationLog()
        for i in range(10):
            log.append({"seq": i, "call_digest": f"{i:02d}"})
        window = log.read_range(5, 3)
        assert [e["seq"] for e in window] == [5, 6, 7]

    def test_clear_resets_log(self):
        log = AttestationLog()
        log.append({"seq": 1})
        log.clear_for_tests()
        assert log.count() == 0


class TestVerifier:
    def test_verifier_accepts_matching_root(self):
        chain = AttestationChain()
        digests = []
        for i in range(5):
            d = AttestationChain.call_digest(
                provider="dgrid", model="m", task="t",
                prompt_hash="aa" * 32, response_hash="bb" * 32,
                prompt_tokens=i, completion_tokens=i,
                ts_ms=1700000000000 + i,
            )
            digests.append(d)
            chain.append(d)
        calls = [{"call_digest": d} for d in digests]
        assert verify_chain(calls, chain.tip) is True

    def test_verifier_rejects_wrong_root(self):
        chain = AttestationChain()
        d = AttestationChain.call_digest(
            provider="dgrid", model="m", task="t",
            prompt_hash="", response_hash="",
            prompt_tokens=1, completion_tokens=1, ts_ms=0,
        )
        chain.append(d)
        calls = [{"call_digest": d}]
        # A different root must NOT verify.
        assert verify_chain(calls, "ff" * 32) is False

    def test_verifier_rederives_digest_from_fields(self):
        # If a caller only has the raw fields (no call_digest), verify_chain
        # should still be able to reconstruct and verify.
        chain = AttestationChain()
        call = {
            "provider": "dgrid", "model": "m", "task": "t",
            "prompt_hash": "aa" * 32, "response_hash": "bb" * 32,
            "prompt_tokens": 10, "completion_tokens": 20,
            "ts_ms": 1700000000000,
        }
        expected_digest = AttestationChain.call_digest(**call)
        chain.append(expected_digest)
        # Pass the call WITHOUT call_digest — verifier should recompute.
        assert verify_chain([call], chain.tip) is True

    def test_verifier_detects_tampering(self):
        chain = AttestationChain()
        digests = []
        for i in range(3):
            d = AttestationChain.call_digest(
                provider="dgrid", model="m", task="t",
                prompt_hash="", response_hash="",
                prompt_tokens=i, completion_tokens=i, ts_ms=i,
            )
            digests.append(d)
            chain.append(d)
        # Modify one digest — verifier must reject.
        calls = [{"call_digest": d} for d in digests]
        calls[1] = {"call_digest": "ff" * 32}
        assert verify_chain(calls, chain.tip) is False
