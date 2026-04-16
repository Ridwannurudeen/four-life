"""Tests for the ERC-8004 identity + reputation module.

All on-chain writes are mocked. No tx is ever submitted from tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def identity(tmp_path, monkeypatch):
    """Build an AgentIdentity with data/identity.json redirected into tmp_path."""
    # Redirect persistence into the tmp_path BEFORE importing the module to
    # ensure IDENTITY_FILE is frozen to the temp dir.
    import agent.identity.registry as reg

    tmp_dir = tmp_path / "data"
    monkeypatch.setattr(reg, "IDENTITY_DIR", tmp_dir)
    monkeypatch.setattr(reg, "IDENTITY_FILE", tmp_dir / "identity.json")

    # Silent web3 client: we never expect real RPC calls in these tests.
    with patch.object(reg, "AsyncWeb3") as MockW3Class:
        fake_w3 = MagicMock()
        fake_w3.to_checksum_address.side_effect = lambda a: a
        # keccak returns an object whose .hex() yields a hex string
        k = MagicMock()
        k.hex.return_value = "ab" * 32
        fake_w3.keccak.return_value = k
        fake_w3.eth = MagicMock()
        MockW3Class.return_value = fake_w3

        inst = reg.AgentIdentity()
        # Pre-seed a deterministic account address (key comes from conftest)
        yield inst


# ── Agent card ──────────────────────────────────────────────────────


class TestAgentCard:
    def test_card_contains_all_required_fields(self, identity):
        identity.state.agent_id = 42
        card = identity.generate_agent_card("https://four-life.gudman.xyz")

        required = {
            "name", "version", "description", "agent_id", "wallet",
            "registry_contract", "reputation_contract", "chain_id",
            "capabilities", "services", "reputation", "trust_anchors",
        }
        missing = required - set(card.keys())
        assert not missing, f"Agent card missing fields: {missing}"
        assert card["chain_id"] == 56
        assert card["agent_id"] == 42
        assert card["wallet"].startswith("0x")
        assert isinstance(card["capabilities"], list) and card["capabilities"]
        assert isinstance(card["services"], list) and card["services"]
        # Every service entry must have a purpose
        for svc in card["services"]:
            assert "url" in svc and "purpose" in svc
        assert "github" in card["trust_anchors"]

    def test_reputation_summary_counts_only_successful(self, identity):
        from agent.identity.registry import AttestationRecord
        identity.state.attestations = {
            "0xaaa": AttestationRecord(token_address="0xaaa", tx_hash="0x1"),
            "0xbbb": AttestationRecord(token_address="0xbbb", tx_hash=""),  # failed
            "0xccc": AttestationRecord(token_address="0xccc", tx_hash="0x3"),
        }
        card = identity.generate_agent_card("https://four-life.gudman.xyz")
        assert card["reputation"]["attestations_count"] == 2
        assert card["reputation"]["graduations_attested"] == 2
        assert card["reputation"]["last_attestation_tx"] == "0x3"


# ── Attestation pipeline ────────────────────────────────────────────


class TestAttestGraduation:
    @pytest.mark.asyncio
    async def test_constructs_valid_tx_and_persists(self, identity):
        identity.state.agent_id = 7
        identity._send_tx = AsyncMock(return_value=("0xdeadbeef", 12345))

        record = await identity.attest_graduation(
            "0xToken",
            metadata={
                "symbol": "TKN", "name": "TokenName",
                "quote_asset": "BNB", "graduation_time": 1700000000,
                "peak_holders": 420,
            },
        )

        assert record is not None
        assert record.tx_hash == "0xdeadbeef"
        assert record.block_number == 12345
        assert record.tag1 == "graduation"
        assert record.tag2 == "BNB"
        assert record.value == 100
        assert record.feedback_hash.startswith("0x")
        # Persisted under the lowercased token address
        assert "0xtoken" in identity.state.attestations

        # _send_tx was invoked once
        assert identity._send_tx.await_count == 1

    @pytest.mark.asyncio
    async def test_insufficient_bnb_fails_gracefully(self, identity):
        identity.state.agent_id = 7
        identity._send_tx = AsyncMock(side_effect=Exception("insufficient funds for gas"))

        record = await identity.attest_graduation(
            "0xBroke", metadata={"symbol": "B", "quote_asset": "BNB"},
        )

        # Failure is swallowed — None returned, retry record persisted.
        assert record is None
        persisted = identity.state.attestations["0xbroke"]
        assert persisted.tx_hash == ""
        assert persisted.tag1 == "graduation"

    @pytest.mark.asyncio
    async def test_duplicate_attestation_is_suppressed(self, identity):
        identity.state.agent_id = 7
        identity._send_tx = AsyncMock(return_value=("0xfirst", 11))

        # First submission goes through
        first = await identity.attest_graduation("0xDupe", metadata={"symbol": "D"})
        assert first is not None and first.tx_hash == "0xfirst"

        # Second submission must NOT call _send_tx again
        second = await identity.attest_graduation("0xDupe", metadata={"symbol": "D"})
        assert second is not None
        assert second.tx_hash == "0xfirst"  # same record
        assert identity._send_tx.await_count == 1

    @pytest.mark.asyncio
    async def test_no_agent_id_is_handled(self, identity):
        identity.state.agent_id = 0
        # Mock get_agent_id to keep returning None (wallet not registered)
        identity.get_agent_id = AsyncMock(return_value=None)
        identity._send_tx = AsyncMock()

        record = await identity.attest_graduation(
            "0xNoid", metadata={"symbol": "N"},
        )
        assert record is None
        identity._send_tx.assert_not_called()


# ── Persistence ─────────────────────────────────────────────────────


class TestStatePersistence:
    def test_save_and_reload_preserves_attestations(self, identity):
        from agent.identity.registry import AttestationRecord, AgentIdentity
        identity.state.agent_id = 99
        identity.state.registration_tx = "0xregtx"
        identity.state.registration_block = 123
        identity.state.attestations["0xtok"] = AttestationRecord(
            token_address="0xtok", token_symbol="TK",
            tx_hash="0xa", block_number=1, value=100, tag1="graduation", tag2="BNB",
        )
        identity._save_state()

        # Build a second instance — it should re-hydrate the same state.
        with patch("agent.identity.registry.AsyncWeb3") as MockW3:
            fake_w3 = MagicMock()
            fake_w3.to_checksum_address.side_effect = lambda a: a
            MockW3.return_value = fake_w3
            reloaded = AgentIdentity()

        assert reloaded.state.agent_id == 99
        assert reloaded.state.registration_tx == "0xregtx"
        assert "0xtok" in reloaded.state.attestations
        assert reloaded.state.attestations["0xtok"].tx_hash == "0xa"
        assert reloaded.agent_id == 99  # back-compat attribute
