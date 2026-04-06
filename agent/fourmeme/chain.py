"""On-chain operations — TokenManager2 interactions on BNB Chain."""

import json
from pathlib import Path
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.contract import AsyncContract
from eth_account import Account
from loguru import logger

from agent.config import settings

# TokenManager2 ABI — minimal subset for create/buy/sell/query
TOKEN_MANAGER_ABI = json.loads("""[
    {
        "inputs": [{"name": "createArg", "type": "bytes"}, {"name": "signature", "type": "bytes"}],
        "name": "createToken",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "token", "type": "address"}],
        "name": "buyTokenAMAP",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "token", "type": "address"}, {"name": "minAmount", "type": "uint256"}],
        "name": "buyToken",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "minFunds", "type": "uint256"}
        ],
        "name": "sellToken",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "token", "type": "address"}],
        "name": "getCurrentPrice",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "bnbAmount", "type": "uint256"}
        ],
        "name": "quoteBuy",
        "outputs": [
            {"name": "tokenAmount", "type": "uint256"},
            {"name": "fee", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "tokenAmount", "type": "uint256"}
        ],
        "name": "quoteSell",
        "outputs": [
            {"name": "bnbAmount", "type": "uint256"},
            {"name": "fee", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "token", "type": "address"},
            {"indexed": true, "name": "creator", "type": "address"},
            {"indexed": false, "name": "name", "type": "string"},
            {"indexed": false, "name": "symbol", "type": "string"}
        ],
        "name": "TokenCreate",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "token", "type": "address"},
            {"indexed": true, "name": "buyer", "type": "address"},
            {"indexed": false, "name": "amount", "type": "uint256"},
            {"indexed": false, "name": "cost", "type": "uint256"}
        ],
        "name": "TokenPurchase",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "token", "type": "address"},
            {"indexed": true, "name": "seller", "type": "address"},
            {"indexed": false, "name": "amount", "type": "uint256"},
            {"indexed": false, "name": "revenue", "type": "uint256"}
        ],
        "name": "TokenSale",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "token", "type": "address"},
            {"indexed": true, "name": "pair", "type": "address"}
        ],
        "name": "LiquidityAdded",
        "type": "event"
    }
]""")

TOKEN_MANAGER_ADDRESS = "0x5c952063c7fc8610FFDB798152D69F0B9550762b"


class FourMemeChain:
    """On-chain interactions with Four.meme's TokenManager2."""

    def __init__(self) -> None:
        self.w3 = AsyncWeb3(AsyncHTTPProvider(settings.bsc_rpc_url))
        self.account = Account.from_key(settings.private_key)
        self.contract: AsyncContract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(TOKEN_MANAGER_ADDRESS),
            abi=TOKEN_MANAGER_ABI,
        )

    async def _send_tx(self, tx_func, value_wei: int = 0) -> str:
        """Build, sign, and send a transaction. Returns tx hash."""
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
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
        hex_hash = tx_hash.hex()
        logger.info("Tx sent: 0x{}", hex_hash)

        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"Tx reverted: 0x{hex_hash}")
        logger.info("Tx confirmed: 0x{}", hex_hash)
        return f"0x{hex_hash}"

    # ── Token Creation ────────────────────────────────────────────────

    async def create_token(
        self,
        create_arg: str,
        signature: str,
        dev_buy_bnb: float = 0.0,
    ) -> str:
        """Create token on-chain via TokenManager2.

        Args:
            create_arg: Hex-encoded createArg from Four.meme API
            signature: Server signature from Four.meme API
            dev_buy_bnb: Optional BNB to buy as creator (sniper protection)

        Returns:
            Transaction hash
        """
        creation_fee = self.w3.to_wei(0.005, "ether")
        dev_buy_wei = self.w3.to_wei(dev_buy_bnb, "ether") if dev_buy_bnb > 0 else 0
        total_value = creation_fee + dev_buy_wei

        create_arg_bytes = bytes.fromhex(create_arg.replace("0x", ""))
        sig_bytes = bytes.fromhex(signature.replace("0x", ""))

        tx_func = self.contract.functions.createToken(create_arg_bytes, sig_bytes)
        tx_hash = await self._send_tx(tx_func, value_wei=total_value)
        logger.info("Token created! tx: {}", tx_hash)
        return tx_hash

    # ── Trading ───────────────────────────────────────────────────────

    async def buy_token(self, token_address: str, bnb_amount: float) -> str:
        """Buy tokens with BNB."""
        value_wei = self.w3.to_wei(bnb_amount, "ether")
        addr = self.w3.to_checksum_address(token_address)
        tx_func = self.contract.functions.buyTokenAMAP(addr)
        return await self._send_tx(tx_func, value_wei=value_wei)

    async def sell_token(
        self, token_address: str, amount: int, min_bnb: float = 0
    ) -> str:
        """Sell tokens for BNB."""
        addr = self.w3.to_checksum_address(token_address)
        min_funds = self.w3.to_wei(min_bnb, "ether")
        tx_func = self.contract.functions.sellToken(addr, amount, min_funds)
        return await self._send_tx(tx_func)

    # ── Queries ───────────────────────────────────────────────────────

    async def get_price(self, token_address: str) -> int:
        """Get current token price in wei."""
        addr = self.w3.to_checksum_address(token_address)
        return await self.contract.functions.getCurrentPrice(addr).call()

    async def quote_buy(self, token_address: str, bnb_amount: float) -> dict:
        """Quote a buy — how many tokens for X BNB."""
        addr = self.w3.to_checksum_address(token_address)
        value_wei = self.w3.to_wei(bnb_amount, "ether")
        token_amount, fee = await self.contract.functions.quoteBuy(addr, value_wei).call()
        return {"token_amount": token_amount, "fee": fee}

    async def quote_sell(self, token_address: str, token_amount: int) -> dict:
        """Quote a sell — how much BNB for X tokens."""
        addr = self.w3.to_checksum_address(token_address)
        bnb_amount, fee = await self.contract.functions.quoteSell(addr, token_amount).call()
        return {"bnb_amount": bnb_amount, "fee": fee}

    # ── Events ────────────────────────────────────────────────────────

    async def get_recent_creates(self, from_block: int, to_block: str = "latest") -> list[dict]:
        """Get recent TokenCreate events."""
        events = await self.contract.events.TokenCreate.get_logs(
            from_block=from_block, to_block=to_block
        )
        return [
            {
                "token": e.args.token,
                "creator": e.args.creator,
                "name": e.args.name,
                "symbol": e.args.symbol,
                "block": e.blockNumber,
                "tx_hash": e.transactionHash.hex(),
            }
            for e in events
        ]

    async def get_token_trades(
        self, token_address: str, from_block: int, to_block: str = "latest"
    ) -> dict:
        """Get buy/sell events for a token."""
        addr = self.w3.to_checksum_address(token_address)
        buys = await self.contract.events.TokenPurchase.get_logs(
            from_block=from_block,
            to_block=to_block,
            argument_filters={"token": addr},
        )
        sells = await self.contract.events.TokenSale.get_logs(
            from_block=from_block,
            to_block=to_block,
            argument_filters={"token": addr},
        )
        return {
            "buys": [
                {
                    "buyer": e.args.buyer,
                    "amount": e.args.amount,
                    "cost": e.args.cost,
                    "block": e.blockNumber,
                }
                for e in buys
            ],
            "sells": [
                {
                    "seller": e.args.seller,
                    "amount": e.args.amount,
                    "revenue": e.args.revenue,
                    "block": e.blockNumber,
                }
                for e in sells
            ],
        }

    async def get_block_number(self) -> int:
        return await self.w3.eth.block_number
