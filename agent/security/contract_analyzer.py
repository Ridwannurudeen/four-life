"""Contract-level rug-risk analyzer for Four.meme tokens.

Deterministic bytecode/ABI inspection — no LLM. Detects mint, blacklist, pause,
proxy (EIP-1967), ownership status, and BscScan verification. Produces a 0-100
risk score and a flag list suitable for merging into the risk snapshot.

Public surface:
    ContractAnalyzer(w3, bscscan_api_key="").analyze(token_address) -> ContractRisk
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

import httpx
from eth_utils import keccak
from loguru import logger

# Four.meme TokenManager2 deployer — tokens whose `owner()` points here are
# considered platform-owned (not a rug signal).
FOURMEME_DEPLOYER = "0x5c952063c7fc8610ffdb798152d69f0b9550762b"

# EIP-1967 implementation slot: bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1)
EIP1967_IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"

# 4-byte function selectors (verified via keccak256 on the canonical signatures).
MINT_SELECTORS: dict[str, str] = {
    "0x40c10f19": "mint(address,uint256)",
    "0x449a52f8": "mintTo(address,uint256)",
    "0xa0712d68": "mint(uint256)",
}
BLACKLIST_SELECTORS: dict[str, str] = {
    "0xf9f92be4": "blacklist(address)",
    "0x537df3b6": "blacklistUpdate",
}
PAUSE_SELECTORS: dict[str, str] = {
    "0x8456cb59": "pause()",
    "0x3f4ba83a": "unpause()",
}
OWNER_SELECTOR = "0x8da5cb5b"  # owner()

BSCSCAN_API = "https://api.bscscan.com/api"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class ContractRisk:
    token_address: str
    analyzed_at: float
    has_mint_function: bool
    has_blacklist: bool
    is_proxy: bool
    has_pause: bool
    has_ownership: bool
    owner_address: str | None
    owner_is_renounced: bool
    is_verified_on_bscscan: bool
    risk_score: int
    flags: list[dict] = field(default_factory=list)
    raw_bytecode_hash: str = ""
    confidence: str = "high"

    def to_dict(self) -> dict:
        return {
            "token_address": self.token_address,
            "analyzed_at": self.analyzed_at,
            "has_mint_function": self.has_mint_function,
            "has_blacklist": self.has_blacklist,
            "is_proxy": self.is_proxy,
            "has_pause": self.has_pause,
            "has_ownership": self.has_ownership,
            "owner_address": self.owner_address,
            "owner_is_renounced": self.owner_is_renounced,
            "is_verified_on_bscscan": self.is_verified_on_bscscan,
            "risk_score": self.risk_score,
            "flags": self.flags,
            "raw_bytecode_hash": self.raw_bytecode_hash,
            "confidence": self.confidence,
        }


def _flag(id: str, severity: str, evidence: str, message: str) -> dict:
    return {"id": id, "severity": severity, "evidence": evidence, "message": message}


def _scan_bytecode_for_selectors(bytecode_hex: str, selectors: dict[str, str]) -> list[str]:
    """Return selectors (without 0x) found in the runtime bytecode."""
    found = []
    lowered = bytecode_hex.lower()
    for sel in selectors:
        if sel.lower().removeprefix("0x") in lowered:
            found.append(sel)
    return found


def _abi_function_names(abi: list[dict]) -> list[str]:
    return [item.get("name", "") for item in abi if item.get("type") == "function"]


def _abi_has_selector(abi: list[dict], selector: str) -> bool:
    """Check whether any ABI function produces the given selector."""
    target = selector.lower().removeprefix("0x")
    for item in abi:
        if item.get("type") != "function":
            continue
        name = item.get("name", "")
        inputs = ",".join(i.get("type", "") for i in item.get("inputs", []))
        sig = f"{name}({inputs})"
        sel = keccak(text=sig)[:4].hex()
        if sel == target:
            return True
    return False


class ContractAnalyzer:
    """Inspect a deployed BSC token for rug-pull signals.

    All detection is deterministic — bytecode selector scanning, storage reads,
    `eth_call` for `owner()`, and the BscScan `getsourcecode` endpoint.
    """

    def __init__(self, w3, bscscan_api_key: str = "") -> None:
        self.w3 = w3
        self.bscscan_api_key = bscscan_api_key

    async def analyze(self, token_address: str) -> ContractRisk:
        addr = self.w3.to_checksum_address(token_address)
        bytecode_hex = ""
        bytecode_hash = ""
        confidence = "high"

        # 1. Fetch bytecode
        try:
            code = await self.w3.eth.get_code(addr)
            bytecode_hex = code.hex() if hasattr(code, "hex") else str(code)
            if not bytecode_hex.startswith("0x"):
                bytecode_hex = "0x" + bytecode_hex
            bytecode_hash = hashlib.sha256(bytecode_hex.encode()).hexdigest()
        except Exception as e:
            logger.warning("get_code failed for {}: {}", addr, e)
            confidence = "low"

        # 2. BscScan source lookup (verified?)
        abi: list[dict] = []
        source_code = ""
        is_verified = False
        bscscan_ok = False
        try:
            abi, source_code, is_verified = await self._fetch_bscscan_source(addr)
            bscscan_ok = True
        except Exception as e:
            logger.warning("BscScan lookup failed for {}: {}", addr, e)

        if not bscscan_ok and not bytecode_hex:
            confidence = "low"
        elif not bscscan_ok:
            confidence = "medium"
        elif bytecode_hex:
            confidence = "high"
        else:
            confidence = "medium"

        flags: list[dict] = []

        # 3. Mint detection — ABI first, then bytecode
        has_mint = False
        if abi:
            for name in _abi_function_names(abi):
                lname = name.lower()
                if lname == "mint" or lname == "_mint" or lname == "mintto":
                    has_mint = True
                    break
        if not has_mint and bytecode_hex:
            if _scan_bytecode_for_selectors(bytecode_hex, MINT_SELECTORS):
                has_mint = True
        if has_mint:
            flags.append(_flag(
                "mint_function",
                "critical",
                "abi" if abi else "bytecode_selector",
                "Contract exposes a mint function — owner can inflate supply.",
            ))

        # 4. Blacklist / Denylist / Ban
        has_blacklist = False
        if abi:
            for name in _abi_function_names(abi):
                lname = name.lower()
                if "blacklist" in lname or "denylist" in lname or lname.startswith("ban") or "deny" in lname:
                    has_blacklist = True
                    break
        if not has_blacklist and bytecode_hex:
            if _scan_bytecode_for_selectors(bytecode_hex, BLACKLIST_SELECTORS):
                has_blacklist = True
        if has_blacklist:
            flags.append(_flag(
                "blacklist",
                "high",
                "abi" if abi else "bytecode_selector",
                "Contract can blacklist/deny/ban holders — freezes victim wallets.",
            ))

        # 5. Pausable
        has_pause = False
        if abi:
            for name in _abi_function_names(abi):
                lname = name.lower()
                if lname == "pause" or lname == "unpause":
                    has_pause = True
                    break
        if not has_pause and bytecode_hex:
            if _scan_bytecode_for_selectors(bytecode_hex, PAUSE_SELECTORS):
                has_pause = True
        if has_pause:
            flags.append(_flag(
                "pausable",
                "medium",
                "abi" if abi else "bytecode_selector",
                "Contract is pausable — owner can halt all transfers.",
            ))

        # 6. Proxy via EIP-1967 storage slot
        is_proxy = False
        try:
            raw = await self.w3.eth.get_storage_at(addr, EIP1967_IMPL_SLOT)
            slot_bytes = bytes(raw) if not isinstance(raw, (bytes, bytearray)) else raw
            if any(b != 0 for b in slot_bytes):
                is_proxy = True
        except Exception as e:
            logger.debug("storage read failed for {}: {}", addr, e)
        if is_proxy:
            flags.append(_flag(
                "proxy_pattern",
                "high",
                "eip1967_slot",
                "Contract is an EIP-1967 proxy — implementation can be upgraded.",
            ))

        # 7. Ownership — call owner() if the selector is reachable
        has_ownership = False
        owner_address: str | None = None
        owner_is_renounced = False
        owner_selector_present = (
            _abi_has_selector(abi, OWNER_SELECTOR) if abi
            else (OWNER_SELECTOR.removeprefix("0x") in bytecode_hex.lower() if bytecode_hex else False)
        )
        if owner_selector_present:
            has_ownership = True
            try:
                raw = await self.w3.eth.call({"to": addr, "data": OWNER_SELECTOR})
                raw_bytes = bytes(raw) if not isinstance(raw, (bytes, bytearray)) else raw
                if len(raw_bytes) >= 32:
                    owner_hex = "0x" + raw_bytes[-20:].hex()
                    owner_address = owner_hex
                    if owner_hex.lower() == ZERO_ADDRESS:
                        owner_is_renounced = True
            except Exception as e:
                logger.debug("owner() call failed for {}: {}", addr, e)

        # 8. Verification flag
        if not is_verified:
            flags.append(_flag(
                "unverified_source",
                "medium",
                "bscscan",
                "Source code is not verified on BscScan — bytecode opacity increases risk.",
            ))

        # 9. Honeypot-literal scan on verified source (weak signal, info)
        if is_verified and source_code:
            src_compact = source_code.lower().replace(" ", "")
            if "_transfer" in src_compact and "require(from==owner" in src_compact:
                flags.append(_flag(
                    "honeypot_transfer_hint",
                    "info",
                    "source_literal",
                    "Transfer override gated on `from == owner` — possible sell-blocking honeypot.",
                ))

        # 10. Owner still holds (non-renounced + not the Four.meme deployer)
        owner_flag_triggered = False
        if has_ownership and not owner_is_renounced and owner_address:
            if owner_address.lower() != FOURMEME_DEPLOYER.lower():
                owner_flag_triggered = True

        # 11. Risk score — deterministic additive
        score = 0
        if has_mint:
            score += 40
        if has_blacklist:
            score += 30
        if is_proxy:
            score += 20
        if has_pause:
            score += 10
        if not is_verified:
            score += 10
        if owner_flag_triggered:
            score += 10
        score = max(0, min(100, score))

        return ContractRisk(
            token_address=token_address,
            analyzed_at=time.time(),
            has_mint_function=has_mint,
            has_blacklist=has_blacklist,
            is_proxy=is_proxy,
            has_pause=has_pause,
            has_ownership=has_ownership,
            owner_address=owner_address,
            owner_is_renounced=owner_is_renounced,
            is_verified_on_bscscan=is_verified,
            risk_score=score,
            flags=flags,
            raw_bytecode_hash=bytecode_hash,
            confidence=confidence,
        )

    async def _fetch_bscscan_source(
        self, address: str
    ) -> tuple[list[dict], str, bool]:
        """Call BscScan getsourcecode. Returns (abi_list, source_code, is_verified)."""
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
        if self.bscscan_api_key:
            params["apikey"] = self.bscscan_api_key

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BSCSCAN_API, params=params)
            resp.raise_for_status()
            payload = resp.json()

        if str(payload.get("status")) != "1":
            return [], "", False

        result = payload.get("result", [])
        if not result or not isinstance(result, list):
            return [], "", False

        entry = result[0]
        source_code = entry.get("SourceCode", "") or ""
        abi_str = entry.get("ABI", "") or ""
        is_verified = bool(source_code.strip())

        abi: list[dict] = []
        if abi_str and abi_str != "Contract source code not verified":
            try:
                abi = json.loads(abi_str)
                if not isinstance(abi, list):
                    abi = []
            except (json.JSONDecodeError, ValueError):
                abi = []

        return abi, source_code, is_verified
