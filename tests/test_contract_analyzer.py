"""Tests for the deterministic contract rug-risk analyzer."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.security.contract_analyzer import (
    ContractAnalyzer,
    ContractRisk,
    EIP1967_IMPL_SLOT,
    MINT_SELECTORS,
    BLACKLIST_SELECTORS,
    PAUSE_SELECTORS,
    OWNER_SELECTOR,
    ZERO_ADDRESS,
)


# ── fixtures ────────────────────────────────────────────────────────

def _build_w3(
    *,
    bytecode: str = "0x6001",
    storage_slot: bytes = b"\x00" * 32,
    owner_return: bytes | None = None,
):
    """Build an AsyncWeb3-like mock with only the methods the analyzer touches."""
    w3 = MagicMock()
    w3.to_checksum_address = lambda a: a if a.startswith("0x") and len(a) == 42 else "0x" + a.replace("0x", "").rjust(40, "0")

    code_bytes = bytes.fromhex(bytecode.removeprefix("0x"))
    code_mock = MagicMock()
    code_mock.hex.return_value = bytecode.removeprefix("0x")

    w3.eth = MagicMock()
    w3.eth.get_code = AsyncMock(return_value=code_mock)
    w3.eth.get_storage_at = AsyncMock(return_value=storage_slot)

    if owner_return is not None:
        w3.eth.call = AsyncMock(return_value=owner_return)
    else:
        w3.eth.call = AsyncMock(side_effect=RuntimeError("owner() not implemented"))

    return w3


def _bscscan_ok(abi: str, source_code: str = "contract X {}"):
    """Return a mock httpx response dict for BscScan getsourcecode success."""
    return {
        "status": "1",
        "result": [{"SourceCode": source_code, "ABI": abi}],
    }


def _bscscan_unverified():
    return {
        "status": "0",
        "result": [{"SourceCode": "", "ABI": "Contract source code not verified"}],
    }


class _MockHttpxResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _MockHttpxClient:
    def __init__(self, payload: dict | Exception):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, url, params=None):
        if isinstance(self._payload, Exception):
            raise self._payload
        return _MockHttpxResponse(self._payload)


def _patch_httpx(monkeypatch, payload):
    monkeypatch.setattr(
        "agent.security.contract_analyzer.httpx.AsyncClient",
        lambda timeout=10.0: _MockHttpxClient(payload),
    )


# ── basic detection ─────────────────────────────────────────────────

ADDR = "0x0000000000000000000000000000000000000001"


@pytest.mark.asyncio
async def test_clean_contract_has_low_score(monkeypatch):
    """A minimal runtime bytecode with no mint/blacklist/pause and a verified empty ABI."""
    w3 = _build_w3(bytecode="0x6001")
    abi = "[]"
    _patch_httpx(monkeypatch, _bscscan_ok(abi))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_mint_function is False
    assert risk.has_blacklist is False
    assert risk.has_pause is False
    assert risk.is_proxy is False
    assert risk.is_verified_on_bscscan is True
    assert risk.risk_score == 0
    assert risk.confidence == "high"


@pytest.mark.asyncio
async def test_detects_mint_via_bytecode(monkeypatch):
    # mint selector 0x40c10f19 embedded in bytecode
    bytecode = "0x6080604052" + "40c10f19" + "00000000"
    w3 = _build_w3(bytecode=bytecode)
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_mint_function is True
    assert any(f["id"] == "mint_function" for f in risk.flags)
    # mint=40 + unverified=10
    assert risk.risk_score == 50


@pytest.mark.asyncio
async def test_detects_mint_via_abi(monkeypatch):
    w3 = _build_w3(bytecode="0x00")
    abi = '[{"type":"function","name":"mint","inputs":[{"type":"address"},{"type":"uint256"}],"outputs":[]}]'
    _patch_httpx(monkeypatch, _bscscan_ok(abi))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_mint_function is True
    assert risk.is_verified_on_bscscan is True
    # mint=40, verified → no +10
    assert risk.risk_score == 40


@pytest.mark.asyncio
async def test_detects_blacklist_via_abi(monkeypatch):
    w3 = _build_w3(bytecode="0x00")
    abi = '[{"type":"function","name":"blacklist","inputs":[{"type":"address"}],"outputs":[]}]'
    _patch_httpx(monkeypatch, _bscscan_ok(abi))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_blacklist is True
    assert any(f["id"] == "blacklist" for f in risk.flags)
    assert risk.risk_score == 30


@pytest.mark.asyncio
async def test_detects_pause_via_bytecode(monkeypatch):
    # pause() = 0x8456cb59
    bytecode = "0x6080" + "8456cb59"
    w3 = _build_w3(bytecode=bytecode)
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_pause is True
    # pause=10 + unverified=10
    assert risk.risk_score == 20


@pytest.mark.asyncio
async def test_detects_proxy_via_eip1967_slot(monkeypatch):
    impl_addr_bytes = (0x1234).to_bytes(32, "big")
    w3 = _build_w3(bytecode="0x00", storage_slot=impl_addr_bytes)
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.is_proxy is True
    # proxy=20 + unverified=10
    assert risk.risk_score == 30


@pytest.mark.asyncio
async def test_owner_renounced_flagged_safe(monkeypatch):
    # bytecode contains owner() selector so we try to call it
    bytecode = "0x" + OWNER_SELECTOR.removeprefix("0x")
    zero_owner = b"\x00" * 32
    w3 = _build_w3(bytecode=bytecode, owner_return=zero_owner)
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.has_ownership is True
    assert risk.owner_is_renounced is True
    assert risk.owner_address == ZERO_ADDRESS
    # unverified=10, renounced → no owner penalty
    assert risk.risk_score == 10


@pytest.mark.asyncio
async def test_owner_non_renounced_non_deployer_adds_score(monkeypatch):
    bytecode = "0x" + OWNER_SELECTOR.removeprefix("0x")
    owner_bytes = (0xDE).to_bytes(1, "big").rjust(32, b"\x00")
    w3 = _build_w3(bytecode=bytecode, owner_return=owner_bytes)
    # Verified with no flags on ABI side
    _patch_httpx(monkeypatch, _bscscan_ok("[]"))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.owner_is_renounced is False
    assert risk.owner_address is not None
    assert risk.owner_address.endswith("de")
    # owner+non-deployer=10, verified → 10 total
    assert risk.risk_score == 10


@pytest.mark.asyncio
async def test_unverified_source_adds_flag(monkeypatch):
    w3 = _build_w3(bytecode="0x00")
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.is_verified_on_bscscan is False
    assert any(f["id"] == "unverified_source" for f in risk.flags)


@pytest.mark.asyncio
async def test_risk_score_capped_at_100(monkeypatch):
    """All the rug signals stacked — score clamps to 100."""
    # mint + blacklist + pause selectors all present in bytecode
    parts = ["0x"]
    for sel in list(MINT_SELECTORS) + list(BLACKLIST_SELECTORS) + list(PAUSE_SELECTORS) + [OWNER_SELECTOR]:
        parts.append(sel.removeprefix("0x"))
    bytecode = "".join(parts)

    impl = (0x99).to_bytes(32, "big")
    owner_bytes = (0xAB).to_bytes(1, "big").rjust(32, b"\x00")
    w3 = _build_w3(bytecode=bytecode, storage_slot=impl, owner_return=owner_bytes)
    _patch_httpx(monkeypatch, _bscscan_unverified())

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.risk_score == 100  # capped
    assert risk.has_mint_function and risk.has_blacklist and risk.is_proxy and risk.has_pause


@pytest.mark.asyncio
async def test_confidence_downgrades_when_bscscan_unreachable(monkeypatch):
    w3 = _build_w3(bytecode="0x00")
    _patch_httpx(monkeypatch, RuntimeError("bscscan down"))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.confidence == "medium"
    assert risk.is_verified_on_bscscan is False


@pytest.mark.asyncio
async def test_confidence_low_when_everything_fails(monkeypatch):
    w3 = MagicMock()
    w3.to_checksum_address = lambda a: a
    w3.eth = MagicMock()
    w3.eth.get_code = AsyncMock(side_effect=RuntimeError("rpc down"))
    w3.eth.get_storage_at = AsyncMock(side_effect=RuntimeError("rpc down"))
    w3.eth.call = AsyncMock(side_effect=RuntimeError("rpc down"))
    _patch_httpx(monkeypatch, RuntimeError("bscscan down"))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert risk.confidence == "low"


@pytest.mark.asyncio
async def test_honeypot_literal_hint_on_verified_source(monkeypatch):
    w3 = _build_w3(bytecode="0x00")
    source = """
    function _transfer(address from, address to, uint256 amount) internal {
        require(from == owner(), "locked");
    }
    """
    _patch_httpx(monkeypatch, _bscscan_ok("[]", source_code=source))

    risk = await ContractAnalyzer(w3).analyze(ADDR)

    assert any(f["id"] == "honeypot_transfer_hint" for f in risk.flags)


@pytest.mark.asyncio
async def test_bytecode_hash_is_deterministic(monkeypatch):
    w3 = _build_w3(bytecode="0xaabbcc")
    _patch_httpx(monkeypatch, _bscscan_unverified())

    r1 = await ContractAnalyzer(w3).analyze(ADDR)
    r2 = await ContractAnalyzer(w3).analyze(ADDR)

    assert r1.raw_bytecode_hash == r2.raw_bytecode_hash
    assert len(r1.raw_bytecode_hash) == 64  # sha256 hex


# ── cache behavior (via api._get_contract_risk) ─────────────────────

@pytest.mark.asyncio
async def test_cache_hits_once_for_same_token(monkeypatch):
    """Two back-to-back calls via the api cache only trigger one analyzer run."""
    from agent import api as api_module

    # Clear the cache
    api_module._contract_risk_cache.clear()

    # Stub agent so _get_contract_risk will run
    fake_agent = MagicMock()
    fake_agent.chain.w3 = MagicMock()
    monkeypatch.setattr(api_module, "agent", fake_agent)

    call_count = {"n": 0}

    async def fake_analyze(self, addr):
        call_count["n"] += 1
        return ContractRisk(
            token_address=addr,
            analyzed_at=0.0,
            has_mint_function=False,
            has_blacklist=False,
            is_proxy=False,
            has_pause=False,
            has_ownership=False,
            owner_address=None,
            owner_is_renounced=False,
            is_verified_on_bscscan=True,
            risk_score=0,
            flags=[],
            raw_bytecode_hash="abc",
            confidence="high",
        )

    monkeypatch.setattr(ContractAnalyzer, "analyze", fake_analyze)

    r1 = await api_module._get_contract_risk("0xabc")
    r2 = await api_module._get_contract_risk("0xabc")

    assert r1 is not None and r2 is not None
    assert call_count["n"] == 1  # second call hit the cache
    assert r1 is r2
