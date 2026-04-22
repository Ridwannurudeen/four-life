"""MYX V2 perpetual trading integration.

Provides AI-powered perp trading for tokens launched by FOUR-LIFE on Four.meme.
Qualifies for the MYX Finance bounty ($5K).

Flow:
1. After token launches on Four.meme and gains traction, create a perp market on MYX V2
2. Seed initial liquidity toward the $20K TVL activation threshold
3. AI agent provides trading signals across spot (Four.meme) + perps (MYX)
4. Demonstrates hedging strategies (long spot, short perp for risk management)

Note: MYX V2 permissionless factory may require coordination with MYX team
for pair activation. The integration is built to work once the pair is live.
"""

import json
from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account
from loguru import logger

from agent.config import settings

# MYX V2 contract ABIs (subset for trading + liquidity)
ROUTER_ABI = json.loads("""[
    {
        "inputs": [{"components": [
            {"name": "account", "type": "address"},
            {"name": "pairIndex", "type": "uint256"},
            {"name": "tradeType", "type": "uint8"},
            {"name": "collateral", "type": "int256"},
            {"name": "openPrice", "type": "uint256"},
            {"name": "isLong", "type": "bool"},
            {"name": "sizeAmount", "type": "uint256"},
            {"name": "maxSlippage", "type": "uint256"},
            {"name": "paymentType", "type": "uint8"},
            {"name": "networkFeeAmount", "type": "uint256"}
        ], "name": "request", "type": "tuple"}],
        "name": "createIncreaseOrder",
        "outputs": [{"name": "orderId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"components": [
            {"name": "account", "type": "address"},
            {"name": "pairIndex", "type": "uint256"},
            {"name": "tradeType", "type": "uint8"},
            {"name": "collateral", "type": "int256"},
            {"name": "triggerPrice", "type": "uint256"},
            {"name": "sizeAmount", "type": "uint256"},
            {"name": "isLong", "type": "bool"},
            {"name": "maxSlippage", "type": "uint256"},
            {"name": "paymentType", "type": "uint8"},
            {"name": "networkFeeAmount", "type": "uint256"}
        ], "name": "request", "type": "tuple"}],
        "name": "createDecreaseOrder",
        "outputs": [{"name": "orderId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "indexToken", "type": "address"},
            {"name": "stableToken", "type": "address"},
            {"name": "indexAmount", "type": "uint256"},
            {"name": "stableAmount", "type": "uint256"},
            {"name": "tokens", "type": "address[]"},
            {"name": "updateData", "type": "bytes[]"},
            {"name": "publishTimes", "type": "uint64[]"}
        ],
        "name": "addLiquidity",
        "outputs": [
            {"name": "mintAmount", "type": "uint256"},
            {"name": "slipToken", "type": "address"},
            {"name": "slipAmount", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "data", "type": "bytes[]"}],
        "name": "multicall",
        "outputs": [{"name": "results", "type": "bytes[]"}],
        "stateMutability": "payable",
        "type": "function"
    }
]""")

POOL_ABI = json.loads("""[
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "pairIndex", "type": "uint256"},
            {"name": "isLong", "type": "bool"}
        ],
        "name": "getPosition",
        "outputs": [{"components": [
            {"name": "account", "type": "address"},
            {"name": "pairIndex", "type": "uint256"},
            {"name": "isLong", "type": "bool"},
            {"name": "collateral", "type": "int256"},
            {"name": "positionAmount", "type": "uint256"},
            {"name": "averagePrice", "type": "uint256"},
            {"name": "fundingFeeTracker", "type": "int256"}
        ], "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "indexToken", "type": "address"},
            {"name": "stableToken", "type": "address"}
        ],
        "name": "getPairIndex",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]""")

# MYX API base
MYX_API = "https://api.myx.finance"

# MYX V2 BSC mainnet addresses (sourced from the official SDK at
# github.com/myx-protocol/myx-trade, src/config/address/BSC_MAINET_NET.ts).
#
# Architecture — verified by reading the SDK source:
#
#   User's wallet
#        │ (1) approve collateral token
#        ▼
#   TRADING_ROUTER ── approval target ── 0xb0c56a23…
#        ▲
#        │ (2) broker submits order on user's behalf via placeOrderWithSalt
#        │
#   BrokerSigner ── MYX-team-issued per integrator (permissioned)
#        │ (3) call flows into core
#        ▼
#   ORDER_MANAGER 0x8d38a857…  →  POSITION_MANAGER 0x04218C23…  →  BASE_POOL 0x6a775E90…
#        │                                                           │
#        ▼                                                           ▼
#   ORACLE 0xAdD60e47…                                        QUOTE_POOL 0x73b2dcfd…
#
# Without a MYX-team-issued broker address, placeOrderWithSalt has no target
# and on-chain execution is blocked by design. We wire the approval target
# (TRADING_ROUTER), the manager + pools (for reads, event indexing, calldata
# preview) and wait for broker onboarding before flipping
# MYX_EXECUTION_ENABLED.
MYX_ADDRESSES_BSC = {
    "TRADING_ROUTER":    "0xb0c56a233535971b8903497f98b90Cf53aE77A13",
    "ORDER_MANAGER":     "0x8d38a857390E1586481cF8994F4feBc315D0249b",
    "POSITION_MANAGER":  "0x04218C23f89cAA2E4395a7Bd94410057705D1184",
    "POOL_MANAGER":      "0x04218C23f89cAA2E4395a7Bd94410057705D1184",
    "BASE_POOL":         "0x6a775E908629eFC6357b3d89E5528524a6f378Dd",
    "QUOTE_POOL":        "0x73b2dcfdc7dC78a7A51B778E93c09FC173923BcE",
    "ORACLE":            "0xAdD60e47D2C5e7d57B1e5a3F9d24dE43933b8A7A",
    "FORWARDER":         "0xD0894e09317F455dd698A706bb62D783e95aA7Ad",
    "EIP7702_DELEGATION": "0x798860BbBC6e011C5508f92a102ee53a44cECfb7",
    "MARKET_MANAGER":    "0x98Af86B194ce82cac650C87F45e5B9f7A4A40AB2",
    "DATA_PROVIDER":     "0x96955bE362b35846c2E7b9B40fC961080DCBbA67",
    # USDC on BSC (MYX's collateral token; note: this is actually BSC's USDT
    # contract, which MYX labels USDC for consistency across chains).
    "USDC":              "0x55d398326f99059fF775485246999027B3197955",
}


class MYXClient:
    """MYX V2 perpetual trading client for BNB Chain."""

    def __init__(
        self,
        router_address: str = "",
        pool_address: str = "",
    ) -> None:
        self.w3 = AsyncWeb3(AsyncHTTPProvider(settings.bsc_rpc_url))
        self.account = Account.from_key(settings.private_key)
        self.router_address = router_address
        self.pool_address = pool_address

        if router_address:
            self.router = self.w3.eth.contract(
                address=self.w3.to_checksum_address(router_address),
                abi=ROUTER_ABI,
            )
        if pool_address:
            self.pool = self.w3.eth.contract(
                address=self.w3.to_checksum_address(pool_address),
                abi=POOL_ABI,
            )

    async def _send_tx(self, tx_func, value_wei: int = 0) -> str:
        """Sign + broadcast + await receipt under the shared wallet-tx lock.

        The agent's wallet funds attestation publishing, identity registration,
        four.meme launches AND MYX orders. Without the shared lock, two
        concurrent broadcasts read the same nonce and BSC drops one. Uses the
        "pending" nonce tag to avoid double-spending a freshly-submitted tx.
        """
        from agent.brain.attestation import get_wallet_tx_lock
        async with get_wallet_tx_lock():
            nonce = await self.w3.eth.get_transaction_count(self.account.address, "pending")
            gas_price = await self.w3.eth.gas_price
            tx = await tx_func.build_transaction({
                "from": self.account.address,
                "value": value_wei,
                "gas": 500_000,
                "gasPrice": gas_price,
                "nonce": nonce,
                "chainId": 56,
            })
            signed = self.account.sign_transaction(tx)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                raise RuntimeError(f"MYX tx reverted: 0x{tx_hash.hex()}")
            return f"0x{tx_hash.hex()}"

    # ── Market Data ───────────────────────────────────────────────────

    async def get_markets(self) -> list[dict]:
        """Get all available trading pairs from MYX API."""
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{MYX_API}/v2/quote/market/contracts")
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def get_pair_index(self, index_token: str, stable_token: str) -> int:
        """Get the pair index for a token pair."""
        idx = self.w3.to_checksum_address(index_token)
        stb = self.w3.to_checksum_address(stable_token)
        return await self.pool.functions.getPairIndex(idx, stb).call()

    # ── Trading ───────────────────────────────────────────────────────

    async def open_position(
        self,
        pair_index: int,
        is_long: bool,
        collateral_wei: int,
        size_amount: int,
        price_1e30: int,
        max_slippage: int = 30,  # 0.3%
    ) -> str:
        """Open a perpetual position.

        Args:
            pair_index: Market pair index from getPairIndex()
            is_long: True for long, False for short
            collateral_wei: Collateral amount in 1e18
            size_amount: Position size in 1e18
            price_1e30: Open price in 1e30 precision
            max_slippage: Slippage tolerance (100 = 1%)

        Returns:
            Transaction hash
        """
        # TradeType: 0=MARKET, 1=LIMIT
        # PaymentType: 0=ETH (BNB), 1=COLLATERAL
        request = (
            self.account.address,  # account
            pair_index,            # pairIndex
            0,                     # tradeType (MARKET)
            collateral_wei,        # collateral
            price_1e30,            # openPrice
            is_long,               # isLong
            size_amount,           # sizeAmount
            max_slippage,          # maxSlippage
            0,                     # paymentType (ETH/BNB)
            self.w3.to_wei(0.001, "ether"),  # networkFeeAmount
        )

        tx_func = self.router.functions.createIncreaseOrder(request)
        tx_hash = await self._send_tx(tx_func, value_wei=self.w3.to_wei(0.001, "ether"))
        logger.info("MYX position opened: {} pair={} long={}", tx_hash, pair_index, is_long)
        return tx_hash

    async def close_position(
        self,
        pair_index: int,
        is_long: bool,
        size_amount: int,
        price_1e30: int,
        max_slippage: int = 30,
    ) -> str:
        """Close a perpetual position."""
        request = (
            self.account.address,
            pair_index,
            0,  # MARKET
            0,  # collateral (0 = close full)
            price_1e30,
            size_amount,
            is_long,
            max_slippage,
            0,  # ETH payment
            self.w3.to_wei(0.001, "ether"),
        )

        tx_func = self.router.functions.createDecreaseOrder(request)
        tx_hash = await self._send_tx(tx_func, value_wei=self.w3.to_wei(0.001, "ether"))
        logger.info("MYX position closed: {} pair={}", tx_hash, pair_index)
        return tx_hash

    async def get_position(self, pair_index: int, is_long: bool) -> dict:
        """Get current position info."""
        pos = await self.pool.functions.getPosition(
            self.account.address, pair_index, is_long
        ).call()
        return {
            "account": pos[0],
            "pair_index": pos[1],
            "is_long": pos[2],
            "collateral": pos[3],
            "position_amount": pos[4],
            "average_price": pos[5],
            "funding_fee_tracker": pos[6],
        }

    # ── Liquidity ─────────────────────────────────────────────────────

    async def add_liquidity(
        self,
        index_token: str,
        stable_token: str,
        index_amount: int,
        stable_amount: int,
    ) -> str:
        """Add liquidity to a MYX V2 pool to seed a perp market.

        This helps reach the $20K TVL activation threshold.
        """
        idx = self.w3.to_checksum_address(index_token)
        stb = self.w3.to_checksum_address(stable_token)

        tx_func = self.router.functions.addLiquidity(
            idx, stb, index_amount, stable_amount,
            [],  # oracle tokens (empty for now)
            [],  # update data
            [],  # publish times
        )
        tx_hash = await self._send_tx(tx_func)
        logger.info("MYX liquidity added: {} idx={} stb={}", tx_hash, index_token, stable_token)
        return tx_hash


class MYXStrategy:
    """AI-powered trading strategy for MYX perps.

    Demonstrates how FOUR-LIFE uses perps for:
    1. Hedging — long spot on Four.meme, short perp on MYX
    2. Trading signals — AI analyzes market conditions for entry/exit
    3. Risk management — automated position sizing and stop-losses
    """

    def __init__(self, myx: MYXClient) -> None:
        self.myx = myx

    async def generate_signal(
        self,
        token_health: dict,
        market_data: dict,
        *,
        use_consensus: bool = False,
    ) -> dict:
        """Generate a trading signal based on token health + market conditions.

        When ``use_consensus=True`` (e.g. for DEFEND-phase high-stakes decisions),
        the same prompt fans out across multiple DGrid models in parallel and
        votes on the action — reducing single-model bias on trades that move
        real capital. On consensus failure we fall back to the single-model
        path so signals keep flowing.

        Returns:
            dict with 'action' (long|short|close|hold), 'confidence', 'reasoning',
            'size_pct' (of available capital). Consensus path also attaches a
            ``consensus`` sub-dict with per-model verdicts for auditability.
        """
        from agent.brain.llm import get_llm

        prompt = f"""You are FOUR-LIFE's perp trading module on MYX V2.

TOKEN HEALTH (Four.meme spot market):
{json.dumps(token_health, indent=2, default=str)}

MYX MARKET DATA:
{json.dumps(market_data, indent=2, default=str)}

Generate a perpetual trading signal:
- If the token is gaining momentum on Four.meme (health rising, holders growing), consider longing the perp to amplify gains
- If the token shows weakness (sell pressure, whale concentration), consider shorting as a hedge
- If you already have a position and conditions changed, consider closing

Respond in JSON: {{"action": "long"|"short"|"close"|"hold", "confidence": float, "reasoning": str, "size_pct": float}}

size_pct is what % of available capital to use (0.01 = 1%, max 0.1 = 10%).
Be conservative. This is risk management, not gambling."""

        if use_consensus:
            # Route DEFEND / high-stakes decisions through 3-model consensus.
            # If consensus gives us a usable full_response we return it
            # unchanged (with vote metadata); otherwise fall back to single
            # model so signals never dry up.
            from agent.brain.consensus import consensus_vote, DEFAULT_CONSENSUS_MODELS
            result = await consensus_vote(
                [{"role": "user", "content": prompt}],
                models=DEFAULT_CONSENSUS_MODELS,
                vote_key="action",
                max_tokens=1500,
                temperature=0.35,
                json_mode=True,
            )
            verdict = result.get("final_verdict")
            full: dict | None = None
            if verdict is not None:
                for r in result.get("results", []):
                    if r.get("ok") and str(r.get("verdict")) == str(verdict):
                        f = r.get("full_response") or {}
                        if isinstance(f, dict) and f.get("action"):
                            full = f
                            break
            if full is not None:
                # Attach consensus metadata so the trace / endpoint can show it.
                full["consensus"] = {
                    "method": result.get("method"),
                    "confidence": result.get("confidence"),
                    "tally": result.get("tally"),
                    "models_queried": result.get("models_queried"),
                    "models_succeeded": result.get("models_succeeded"),
                    "total_latency_ms": result.get("total_latency_ms"),
                }
                return full
            # Consensus failed to produce a usable full response — fall back.

        return await get_llm().chat_json_task(
            [{"role": "user", "content": prompt}],
            task="risk",
            # Gemini 2.5 Flash (the default risk-task model) burns 300-1500
            # tokens on invisible reasoning before emitting the visible JSON.
            # 1500 gives the model room to think AND finish the answer; raising
            # further has negligible cost impact (cheap model) but prevents the
            # mid-JSON truncation that produced "Unterminated string" errors.
            max_tokens=1500,
        )
