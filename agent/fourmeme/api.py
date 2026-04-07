"""Four.meme REST API client — auth, token creation, image upload.

Auth flow (from four-meme-community/four-meme-ai reference):
1. POST /private/user/nonce/generate  → nonce
2. Sign "You are sign in Meme {nonce}" with wallet
3. POST /private/user/login/dex       → accessToken
4. Use header: meme-web-access: {accessToken}
"""

import time

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from loguru import logger

from agent.config import settings

BASE_URL = "https://four.meme/meme-api/v1"


class FourMemeAPI:
    """Client for Four.meme's REST API."""

    def __init__(self) -> None:
        self.account = Account.from_key(settings.private_key)
        self.address = self.account.address
        self.access_token: str | None = None
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=60,
            headers={
                "User-Agent": "four-life-agent/1.0.0",
                "Origin": "https://four.meme",
                "Referer": "https://four.meme/",
            },
        )

    # ── Auth ──────────────────────────────────────────────────────────

    async def login(self) -> str:
        """Authenticate via wallet signature. Returns access token."""
        # Step 1: get nonce
        resp = await self._client.post(
            "/private/user/nonce/generate",
            json={
                "accountAddress": self.address,
                "verifyType": "LOGIN",
                "networkCode": "BSC",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("code")) not in ("0", "000000"):
            raise RuntimeError(f"Nonce failed: {data}")
        nonce = data["data"]

        # Step 2: sign message
        message = f"You are sign in Meme {nonce}"
        signable = encode_defunct(text=message)
        signed = self.account.sign_message(signable)
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: login
        resp = await self._client.post(
            "/private/user/login/dex",
            json={
                "region": "WEB",
                "langType": "EN",
                "loginIp": "",
                "inviteCode": "",
                "verifyInfo": {
                    "address": self.address,
                    "networkCode": "BSC",
                    "signature": signature,
                    "verifyType": "LOGIN",
                },
                "walletName": "MetaMask",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("code")) not in ("0", "000000"):
            raise RuntimeError(f"Login failed: {data}")
        self.access_token = data["data"]
        logger.info("Authenticated with Four.meme as {}", self.address)
        return self.access_token

    @property
    def _auth_headers(self) -> dict:
        if not self.access_token:
            raise RuntimeError("Not authenticated — call login() first")
        return {"meme-web-access": self.access_token}

    # ── Token Creation ────────────────────────────────────────────────

    async def upload_image(self, image_bytes: bytes, filename: str = "token.png") -> str:
        """Upload token image. Returns the hosted image URL."""
        resp = await self._client.post(
            "/private/token/upload",
            headers=self._auth_headers,
            files={"file": (filename, image_bytes, "image/png")},
        )
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("code")) not in ("0", "000000"):
            raise RuntimeError(f"Upload failed: {data}")
        img_url = data["data"]
        logger.info("Uploaded image: {}", img_url)
        return img_url

    async def prepare_token(
        self,
        name: str,
        symbol: str,
        description: str,
        img_url: str,
        label: str = "AI",
        twitter: str = "",
        telegram: str = "",
        website: str = "",
        pre_sale_bnb: float = 0,
    ) -> dict:
        """Prepare token creation — returns createArg and signature for on-chain call.

        Returns:
            dict with 'create_arg', 'signature' for TokenManager2.createToken()
        """
        # Get platform config for raisedToken details
        config = await self.get_config()
        bnb_config = next((c for c in config if c.get("symbol") == "BNB"), config[0])

        total_supply = int(bnb_config.get("totalAmount", 1_000_000_000))
        raised_amount = float(bnb_config.get("totalBAmount", 24))

        body = {
            "name": name,
            "shortName": symbol,
            "symbol": bnb_config.get("symbol", "BNB"),
            "desc": description,
            "label": label,
            "imgUrl": img_url,
            "totalSupply": total_supply,
            "raisedAmount": raised_amount,
            "raisedToken": bnb_config.get("symbolAddress", ""),
            "saleRate": 0,
            "launchTime": int(time.time() * 1000),
            "dexType": "PANCAKE_SWAP",
            "preSale": str(pre_sale_bnb),
            "feePlan": False,
        }
        if twitter:
            body["twitterUrl"] = twitter
        if telegram:
            body["telegramUrl"] = telegram
        if website:
            body["webUrl"] = website

        resp = await self._client.post(
            "/private/token/create",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("code")) not in ("0", "000000"):
            raise RuntimeError(f"Create failed: {data}")

        result = data["data"]
        create_arg = result["createArg"]
        signature = result["signature"]

        # Convert to hex if base64
        if not create_arg.startswith("0x"):
            import base64
            create_arg = "0x" + base64.b64decode(create_arg).hex()
        if not signature.startswith("0x"):
            import base64
            signature = "0x" + base64.b64decode(signature).hex()

        logger.info("Token prepared: {} ({})", name, symbol)
        return {"create_arg": create_arg, "signature": signature}

    # ── Market Data ───────────────────────────────────────────────────

    async def get_trending(self) -> list[dict]:
        """Get hot tokens on Four.meme."""
        resp = await self._client.post(
            "/public/token/ranking",
            json={"pageNo": 1, "pageSize": 20, "type": "HOT"},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_new_tokens(self, page_size: int = 20) -> list[dict]:
        """Get newly created tokens on Four.meme."""
        resp = await self._client.post(
            "/public/token/ranking",
            json={"pageNo": 1, "pageSize": page_size, "type": "NEW"},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_config(self) -> list[dict]:
        """Get platform config (supported symbols, fees, etc)."""
        resp = await self._client.get("/public/config")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_token_ranking(self) -> list[dict]:
        """Get token ranking."""
        resp = await self._client.post(
            "/public/token/ranking",
            json={"pageNo": 1, "pageSize": 20, "type": "HOT"},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def search_tokens(self, keyword: str) -> list[dict]:
        """Search tokens by name/symbol."""
        resp = await self._client.get(
            "/public/token/search",
            params={"keyword": keyword},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
