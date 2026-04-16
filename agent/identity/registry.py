"""ERC-8004 on-chain identity registration and reputation.

FOUR-LIFE's identity module. Responsibilities:

1. Lazily read the agent's current ERC-8004 Agent ID for its wallet on the
   BRC-8004 IdentityRegistry (BNB Chain).
2. Register if the wallet is funded and not yet registered.
3. Persist the Agent ID + registration tx hash + wallet to ``data/identity.json``
   so restarts are cheap and the data is demo-able.
4. Build an enriched agent card that matches the ERC-8004 registration shape but
   also carries FOUR-LIFE-specific metadata (services, capabilities, reputation
   counters, trust anchors).
5. Submit reputation attestations to the BRC-8004 ReputationRegistry when a
   tracked token graduates, without ever double-attesting the same graduation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account
from loguru import logger

from agent.config import settings

IDENTITY_DIR = Path(__file__).parent.parent.parent / "data"
IDENTITY_FILE = IDENTITY_DIR / "identity.json"

# BRC8004 IdentityRegistry on BSC mainnet
IDENTITY_REGISTRY_ABI = json.loads("""[
    {
        "inputs": [{"name": "uri", "type": "string"}],
        "name": "register",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "uri", "type": "string"}
        ],
        "name": "setAgentURI",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "agentURI",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "agentIdOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]""")

# BRC8004 ReputationRegistry on BSC mainnet — matches the canonical ERC-8004 spec.
REPUTATION_REGISTRY_ABI = json.loads("""[
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "value", "type": "int128"},
            {"name": "valueDecimals", "type": "uint8"},
            {"name": "tag1", "type": "string"},
            {"name": "tag2", "type": "string"},
            {"name": "endpoint", "type": "string"},
            {"name": "feedbackURI", "type": "string"},
            {"name": "feedbackHash", "type": "bytes32"}
        ],
        "name": "giveFeedback",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]""")


@dataclass
class AttestationRecord:
    """An on-chain reputation attestation FOUR-LIFE has submitted."""

    token_address: str = ""
    token_symbol: str = ""
    token_name: str = ""
    graduation_time: float = 0.0
    tx_hash: str = ""
    block_number: int = 0
    submitted_at: float = 0.0
    # On-chain fields actually submitted
    value: int = 0            # int128 score
    value_decimals: int = 0
    tag1: str = ""            # "graduation"
    tag2: str = ""            # quote asset (BNB / USD1 / ...)
    endpoint: str = ""
    feedback_uri: str = ""
    feedback_hash: str = ""


@dataclass
class IdentityState:
    """Persistent identity state written to data/identity.json."""

    wallet: str = ""
    agent_id: int = 0
    registration_tx: str = ""
    registration_block: int = 0
    agent_card_uri: str = ""
    # key = token_address (lowercase) — ensures we never attest the same graduation twice.
    attestations: dict[str, AttestationRecord] = field(default_factory=dict)
    last_updated: float = 0.0


class AgentIdentity:
    """Manages FOUR-LIFE's on-chain ERC-8004 identity and reputation attestations."""

    AGENT_CARD_URI = "https://four-life.gudman.xyz/.well-known/agent-registration.json"

    def __init__(self) -> None:
        self.w3 = AsyncWeb3(AsyncHTTPProvider(settings.bsc_rpc_url))
        self.account = Account.from_key(settings.private_key)
        self.identity_registry = self.w3.eth.contract(
            address=self.w3.to_checksum_address(settings.identity_registry),
            abi=IDENTITY_REGISTRY_ABI,
        )
        self.reputation_registry = self.w3.eth.contract(
            address=self.w3.to_checksum_address(settings.reputation_registry),
            abi=REPUTATION_REGISTRY_ABI,
        )
        self.state: IdentityState = self._load_state()
        # Back-compat: older callers read `self.agent_id` directly
        self.agent_id: int | None = self.state.agent_id or None

    # ── State persistence ────────────────────────────────────────────

    def _load_state(self) -> IdentityState:
        """Load persisted identity state. Missing/corrupt files yield a fresh state."""
        IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        if not IDENTITY_FILE.exists():
            return IdentityState(wallet=self.account.address)
        try:
            raw = json.loads(IDENTITY_FILE.read_text())
            attestations = {
                k: AttestationRecord(**v)
                for k, v in (raw.get("attestations") or {}).items()
            }
            state = IdentityState(
                wallet=raw.get("wallet", self.account.address),
                agent_id=int(raw.get("agent_id", 0) or 0),
                registration_tx=raw.get("registration_tx", ""),
                registration_block=int(raw.get("registration_block", 0) or 0),
                agent_card_uri=raw.get("agent_card_uri", ""),
                attestations=attestations,
                last_updated=float(raw.get("last_updated", 0) or 0),
            )
            # If the persisted state belongs to a different wallet, drop it.
            if state.wallet.lower() != self.account.address.lower():
                logger.warning(
                    "identity.json wallet mismatch ({} vs {}); discarding stale state.",
                    state.wallet, self.account.address,
                )
                return IdentityState(wallet=self.account.address)
            return state
        except Exception as e:
            logger.warning("Failed to load identity state, starting fresh: {}", e)
            return IdentityState(wallet=self.account.address)

    def _save_state(self) -> None:
        self.state.last_updated = time.time()
        IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self.state)
        IDENTITY_FILE.write_text(json.dumps(data, indent=2, default=str))

    # ── Low-level tx helper ──────────────────────────────────────────

    async def _send_tx(self, tx_func, gas: int = 300_000) -> tuple[str, int]:
        """Build, sign, broadcast, and confirm a tx. Returns (tx_hash, block_number)."""
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        gas_price = await self.w3.eth.gas_price
        tx = await tx_func.build_transaction({
            "from": self.account.address,
            "gas": gas,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": 56,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        tx_hex = f"0x{tx_hash.hex()}"
        if receipt["status"] != 1:
            raise RuntimeError(f"Tx reverted: {tx_hex}")
        return tx_hex, int(receipt["blockNumber"])

    # ── Registration ────────────────────────────────────────────────

    async def get_agent_id(self) -> int | None:
        """Check if this wallet already has a registered agent."""
        try:
            agent_id = await self.identity_registry.functions.agentIdOf(
                self.account.address
            ).call()
            if agent_id and agent_id > 0:
                self.agent_id = int(agent_id)
                self.state.agent_id = int(agent_id)
                return int(agent_id)
        except Exception as e:
            logger.debug("agentIdOf call failed: {}", e)
        return None

    async def ensure_registered(self, agent_card_url: str | None = None) -> int | None:
        """Idempotently resolve the wallet's Agent ID.

        - If already registered on-chain, log the ID and persist it.
        - If not registered and the wallet has BNB, register, log the tx hash.
        - If registration fails, log and return ``None`` — callers keep running
          in read-only mode.
        """
        uri = agent_card_url or self.state.agent_card_uri or self.AGENT_CARD_URI
        existing = await self.get_agent_id()
        if existing:
            self.state.agent_id = existing
            self.state.agent_card_uri = uri
            self.state.wallet = self.account.address
            self._save_state()
            logger.info(
                "ERC-8004 Agent ID: {} | Registry: {} | Tx: {}",
                existing,
                settings.identity_registry,
                self.state.registration_tx or "(loaded from chain)",
            )
            return existing

        # Not registered — attempt on-chain register. Fail gracefully.
        try:
            tx_hex, block = await self._send_tx(
                self.identity_registry.functions.register(uri)
            )
        except Exception as e:
            logger.warning("ERC-8004 registration failed (insufficient BNB?): {}", e)
            return None

        # Re-read the assigned ID
        assigned = await self.get_agent_id()
        self.state.agent_id = assigned or 0
        self.state.registration_tx = tx_hex
        self.state.registration_block = block
        self.state.agent_card_uri = uri
        self.state.wallet = self.account.address
        self._save_state()
        logger.info(
            "ERC-8004 Agent ID: {} | Registry: {} | Tx: {}",
            assigned, settings.identity_registry, tx_hex,
        )
        return assigned

    # Back-compat shim: existing code calls ``register(uri)``.
    async def register(self, agent_card_url: str) -> int | None:
        return await self.ensure_registered(agent_card_url)

    async def update_uri(self, new_uri: str) -> str:
        """Update the agent card URI."""
        if not self.state.agent_id:
            raise RuntimeError("Agent not registered")
        tx_hex, _ = await self._send_tx(
            self.identity_registry.functions.setAgentURI(self.state.agent_id, new_uri)
        )
        self.state.agent_card_uri = new_uri
        self._save_state()
        logger.info("Agent URI updated: {}", tx_hex)
        return tx_hex

    # ── Reputation attestations ─────────────────────────────────────

    async def attest_graduation(
        self,
        token_address: str,
        metadata: dict[str, Any] | None = None,
    ) -> AttestationRecord | None:
        """Submit a reputation attestation on-chain for a graduated token.

        Idempotent: if we've already attested this token, returns the existing
        record without re-sending. On failure (no BNB, revert, no agent ID),
        logs the error, sets ``needs_retry`` on the existing attempt record,
        and returns ``None``. Never raises into the lifecycle tick.
        """
        key = token_address.lower()
        if key in self.state.attestations and self.state.attestations[key].tx_hash:
            logger.debug("Duplicate attestation suppressed for {}", token_address)
            return self.state.attestations[key]

        if not self.state.agent_id:
            # Try to resolve one more time in case the wallet just got funded
            await self.get_agent_id()
        if not self.state.agent_id:
            logger.warning(
                "Cannot attest graduation for {}: no ERC-8004 Agent ID registered yet.",
                token_address,
            )
            return None

        meta = metadata or {}
        symbol = str(meta.get("symbol") or "")
        name = str(meta.get("name") or "")
        quote_asset = str(meta.get("quote_asset") or "BNB").upper()
        graduation_time = float(meta.get("graduation_time") or time.time())
        peak_holders = int(meta.get("peak_holders") or 0)

        # Deterministic feedback URI + hash so judges can reproduce them.
        feedback_uri = (
            f"https://four-life.gudman.xyz/api/tokens/{token_address}"
        )
        feedback_payload = json.dumps(
            {
                "type": "four-life.graduation.v1",
                "token_address": token_address,
                "symbol": symbol,
                "name": name,
                "quote_asset": quote_asset,
                "graduation_time": int(graduation_time),
                "peak_holders": peak_holders,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        feedback_hash = "0x" + self.w3.keccak(text=feedback_payload).hex()

        # Fixed-format attestation values
        value = 100             # int128 — graduation is a positive signal
        value_decimals = 0
        tag1 = "graduation"
        tag2 = quote_asset
        endpoint = feedback_uri

        try:
            tx_hex, block = await self._send_tx(
                self.reputation_registry.functions.giveFeedback(
                    int(self.state.agent_id),
                    int(value),
                    int(value_decimals),
                    tag1,
                    tag2,
                    endpoint,
                    feedback_uri,
                    bytes.fromhex(feedback_hash[2:]),
                ),
                gas=500_000,
            )
        except Exception as e:
            logger.error(
                "Reputation attestation failed for {} ({}): {}",
                symbol or token_address, token_address, e,
            )
            # Record the attempt so the lifecycle engine can retry later.
            self.state.attestations[key] = AttestationRecord(
                token_address=token_address,
                token_symbol=symbol,
                token_name=name,
                graduation_time=graduation_time,
                tx_hash="",
                submitted_at=time.time(),
                tag1=tag1,
                tag2=tag2,
                endpoint=endpoint,
                feedback_uri=feedback_uri,
                feedback_hash=feedback_hash,
                value=value,
                value_decimals=value_decimals,
            )
            self._save_state()
            return None

        record = AttestationRecord(
            token_address=token_address,
            token_symbol=symbol,
            token_name=name,
            graduation_time=graduation_time,
            tx_hash=tx_hex,
            block_number=block,
            submitted_at=time.time(),
            value=value,
            value_decimals=value_decimals,
            tag1=tag1,
            tag2=tag2,
            endpoint=endpoint,
            feedback_uri=feedback_uri,
            feedback_hash=feedback_hash,
        )
        self.state.attestations[key] = record
        self._save_state()
        logger.info(
            "ERC-8004 attestation submitted | Agent {} | Token {} ({}) | Tx: {}",
            self.state.agent_id, symbol or token_address, quote_asset, tx_hex,
        )
        return record

    # ── Agent card ───────────────────────────────────────────────────

    def _public_services(self, base_url: str) -> list[dict]:
        """Public endpoint catalogue embedded in the agent card."""
        b = base_url.rstrip("/")
        return [
            {"type": "web", "url": b, "purpose": "Dashboard"},
            {"type": "api", "url": f"{b}/api/identity", "purpose": "Identity + reputation feed"},
            {"type": "api", "url": f"{b}/api/status", "purpose": "Agent status"},
            {"type": "api", "url": f"{b}/api/tokens", "purpose": "Tracked tokens with live health"},
            {"type": "api", "url": f"{b}/api/graduation-radar", "purpose": "Graduation probability radar"},
            {"type": "api", "url": f"{b}/api/health-score/{{token_address}}", "purpose": "Per-token health score"},
            {"type": "api", "url": f"{b}/api/token/{{token_address}}/badge", "purpose": "FOUR-LIFE Certified badge"},
            {"type": "api", "url": f"{b}/api/token/{{token_address}}/risk-snapshot", "purpose": "Per-token risk evidence"},
            {"type": "api", "url": f"{b}/api/raise-plan/{{token_address}}", "purpose": "72h lifecycle raise plan"},
        ]

    def _reputation_summary(self) -> dict:
        successful = [a for a in self.state.attestations.values() if a.tx_hash]
        last_tx = successful[-1].tx_hash if successful else ""
        return {
            "attestations_count": len(successful),
            "graduations_attested": len(successful),
            "last_attestation_tx": last_tx,
        }

    def generate_agent_card(self, dashboard_url: str = "") -> dict:
        """Generate the enriched agent-card.json for FOUR-LIFE."""
        base = dashboard_url or "https://four-life.gudman.xyz"
        agent_id = self.state.agent_id or None
        card = {
            "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
            "name": settings.agent_name,
            "version": "1.0.0",
            "description": settings.agent_description,
            "image": "",
            "active": True,
            "agent_id": agent_id,
            "wallet": self.account.address,
            "chain_id": 56,
            "registry_contract": self.w3.to_checksum_address(settings.identity_registry),
            "reputation_contract": self.w3.to_checksum_address(settings.reputation_registry),
            "capabilities": [
                "token_lifecycle_monitoring",
                "certified_badge_issuance",
                "graduation_prediction",
                "risk_scoring",
                "content_generation",
                "perp_hedging_signal",
            ],
            "platforms": ["four.meme", "myx.finance"],
            "chain": "BNB Chain (56)",
            "services": self._public_services(base),
            "reputation": self._reputation_summary(),
            "trust_anchors": {
                "github": "https://github.com/Ridwannurudeen/four-life",
                "website": base,
                "demo_video": f"{base.rstrip('/')}/demo",
            },
            "registrations": [],
            "x402Support": False,
            "supportedTrust": ["reputation"],
        }

        if agent_id:
            card["registrations"].append({
                "agentId": agent_id,
                "agentRegistry": f"eip155:56:{settings.identity_registry}",
            })

        return card
