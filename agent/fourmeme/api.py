"""Four.meme REST API client — auth, token creation, image upload.

Auth flow (from four-meme-agent reference):
1. GET  /v1/public/user/login/nonce?walletAddress=0x...  → nonce
2. Sign "You are sign in Meme {nonce}" with wallet
3. POST /v1/public/user/login  → accessToken
"""

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from loguru import logger

from agent.config import settings

BASE_URL = "https://four.meme/meme-api"


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
        """Authenticate via wallet signature. Returns JWT access token."""
        # Step 1: get nonce
        resp = await self._client.get(
            "/v1/public/user/login/nonce",
            params={"walletAddress": self.address.lower()},
        )
        resp.raise_for_status()
        nonce = resp.json()["data"]

        # Step 2: sign message
        message = f"You are sign in Meme {nonce}"
        signable = encode_defunct(text=message)
        signed = self.account.sign_message(signable)
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: login
        resp = await self._client.post(
            "/v1/public/user/login",
            json={
                "walletAddress": self.address.lower(),
                "signature": signature,
                "nonce": nonce,
                "loginType": "ETH",
            },
        )
        resp.raise_for_status()
        self.access_token = resp.json()["data"]["accessToken"]
        logger.info("Authenticated with Four.meme as {}", self.address)
        return self.access_token

    @property
    def _auth_headers(self) -> dict:
        if not self.access_token:
            raise RuntimeError("Not authenticated — call login() first")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ── Token Creation ────────────────────────────────────────────────

    async def upload_image(self, image_bytes: bytes, filename: str = "token.png") -> str:
        """Upload token image. Returns the hosted image URL."""
        headers = self._auth_headers
        headers.pop("Content-Type", None)  # Let httpx set multipart boundary

        resp = await self._client.post(
            "/v1/private/tool/upload",
            headers=headers,
            files={"file": (filename, image_bytes, "image/png")},
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data["data"]["url"]
        logger.info("Uploaded image: {}", image_url)
        return image_url

    async def prepare_token(
        self,
        name: str,
        symbol: str,
        description: str,
        img_url: str,
        raised_token_symbol: str = "BNB",
        twitter: str = "",
        telegram: str = "",
        website: str = "",
    ) -> dict:
        """Prepare token creation — returns createArg and signature for on-chain call.

        Returns:
            dict with 'createArg' and 'signature' for TokenManager2.createToken()
        """
        resp = await self._client.post(
            "/v1/private/token/create",
            headers=self._auth_headers,
            json={
                "name": name,
                "symbol": symbol,
                "description": description,
                "imgUrl": img_url,
                "twitter": twitter,
                "telegram": telegram,
                "website": website,
                "raisedTokenSymbol": raised_token_symbol,
                "raisedAmount": "0",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"Four.meme API error: {data.get('msg', data)}")
        result = data["data"]
        logger.info("Token prepared: {} ({})", name, symbol)
        return {
            "create_arg": result["createArg"],
            "signature": result["signature"],
        }

    # ── Market Data ───────────────────────────────────────────────────

    async def get_trending(self) -> list[dict]:
        """Get trending/active tokens on Four.meme."""
        resp = await self._client.get(
            "/v1/public/ticker",
            params={"pageNo": 1, "pageSize": 20, "status": "TRADING"},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("list", data) if isinstance(data, dict) else data

    async def get_token_detail(self, token_address: str) -> dict:
        """Get detailed info for a specific token."""
        resp = await self._client.get(
            "/v1/public/token/detail",
            params={"address": token_address},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_config(self) -> list[dict]:
        """Get platform config (supported symbols, fees, etc)."""
        resp = await self._client.get("/v1/public/config")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def search_tokens(self, keyword: str) -> list[dict]:
        """Search tokens by name/symbol."""
        resp = await self._client.get(
            "/v1/public/token/search",
            params={"keyword": keyword},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_token_ranking(self) -> list[dict]:
        """Get token ranking."""
        resp = await self._client.get("/v1/public/token/ranking")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_my_tokens(self) -> list[dict]:
        """Get tokens created by this wallet."""
        resp = await self._client.get(
            "/v1/private/token/my/list",
            headers=self._auth_headers,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("list", [])

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
