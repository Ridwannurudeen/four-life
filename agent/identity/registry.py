"""ERC-8004 on-chain identity registration and reputation."""

import json
from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account
from loguru import logger

from agent.config import settings

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

# BRC8004 ReputationRegistry on BSC mainnet
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


class AgentIdentity:
    """Manages FOUR-LIFE's on-chain ERC-8004 identity."""

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
        self.agent_id: int | None = None

    async def _send_tx(self, tx_func) -> str:
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        gas_price = await self.w3.eth.gas_price
        tx = await tx_func.build_transaction({
            "from": self.account.address,
            "gas": 300_000,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": 56,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"Tx reverted: 0x{tx_hash.hex()}")
        return f"0x{tx_hash.hex()}"

    async def get_agent_id(self) -> int | None:
        """Check if this wallet already has a registered agent."""
        try:
            agent_id = await self.identity_registry.functions.agentIdOf(
                self.account.address
            ).call()
            if agent_id > 0:
                self.agent_id = agent_id
                return agent_id
        except Exception:
            pass
        return None

    async def register(self, agent_card_url: str) -> int:
        """Register FOUR-LIFE as an ERC-8004 agent.

        Args:
            agent_card_url: URL to the agent-card.json file

        Returns:
            The assigned agent ID
        """
        existing = await self.get_agent_id()
        if existing:
            logger.info("Agent already registered with ID {}", existing)
            self.agent_id = existing
            return existing

        tx_hash = await self._send_tx(
            self.identity_registry.functions.register(agent_card_url)
        )
        logger.info("Agent registered! tx: {}", tx_hash)

        self.agent_id = await self.get_agent_id()
        logger.info("Agent ID: {}", self.agent_id)
        return self.agent_id

    async def update_uri(self, new_uri: str) -> str:
        """Update the agent card URI."""
        if not self.agent_id:
            raise RuntimeError("Agent not registered")
        tx_hash = await self._send_tx(
            self.identity_registry.functions.setAgentURI(self.agent_id, new_uri)
        )
        logger.info("Agent URI updated: {}", tx_hash)
        return tx_hash

    def generate_agent_card(self, dashboard_url: str = "") -> dict:
        """Generate the agent-card.json for FOUR-LIFE."""
        card = {
            "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
            "name": settings.agent_name,
            "description": settings.agent_description,
            "image": "",
            "active": True,
            "services": [],
            "capabilities": [
                "token-creation",
                "lifecycle-management",
                "content-generation",
                "market-analysis",
                "perp-trading",
            ],
            "platforms": ["four.meme", "myx.finance"],
            "chain": "BNB Chain (56)",
            "registrations": [],
            "x402Support": False,
            "supportedTrust": ["reputation"],
        }

        if dashboard_url:
            card["services"].append({"type": "web", "url": dashboard_url})

        if self.agent_id:
            card["registrations"].append({
                "agentId": self.agent_id,
                "agentRegistry": f"eip155:56:{settings.identity_registry}",
            })

        return card
