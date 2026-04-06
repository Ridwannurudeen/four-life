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
        """Authenticate via wallet signature.

        Four.meme uses two auth paths:
        1. New path: /mapi/defi/v3/public/wallet-direct/wallet/address/sign (Binance wallet)
        2. Legacy path: /v1/public/user/login/nonce → /v1/public/user/login

        We try legacy first, fall back to new path.
        The meme-web-access header is used for API auth on the /meme-api base.
        """
        import time

        # Try legacy auth first (from four-meme-agent reference)
        try:
            resp = await self._client.get(
                "/v1/public/user/login/nonce",
                params={"walletAddress": self.address.lower()},
            )
            if resp.status_code == 200:
                nonce = resp.json()["data"]
                message = f"You are sign in Meme {nonce}"
                signable = encode_defunct(text=message)
                signed = self.account.sign_message(signable)
                signature = signed.signature.hex()
                if not signature.startswith("0x"):
                    signature = f"0x{signature}"

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
                logger.info("Authenticated with Four.meme (legacy) as {}", self.address)
                return self.access_token
        except Exception as e:
            logger.debug("Legacy auth failed: {}, trying new path", e)

        # New auth path via /mapi/defi/
        ts = str(int(time.time() * 1000))
        message = f"Welcome to four.meme!\n\nThis request will not trigger a blockchain transaction or cost any gas fees.\n\nAuthentication nonce: {ts}"
        signable = encode_defunct(text=message)
        signed = self.account.sign_message(signable)
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Use a separate client for the /mapi auth endpoint
        async with httpx.AsyncClient(timeout=30) as auth_client:
            resp = await auth_client.get(
                "https://four.meme/mapi/defi/v3/public/wallet-direct/wallet/address/sign",
                params={
                    "address": self.address.lower(),
                    "signature": signature,
                    "message": message,
                    "timestamp": ts,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") or data.get("code") == "000000":
                    self.access_token = data.get("data", {}).get("token", "")
                    if self.access_token:
                        logger.info("Authenticated with Four.meme (new) as {}", self.address)
                        return self.access_token

        # If both fail, we can still use public endpoints + on-chain operations
        logger.warning("Four.meme auth failed — running in public-only mode. "
                       "Token creation will use on-chain directly.")
        self.access_token = "public-only"
        return self.access_token

    @property
    def _auth_headers(self) -> dict:
        if not self.access_token or self.access_token == "public-only":
            return {"Content-Type": "application/json"}
        return {
            "Authorization": f"Bearer {self.access_token}",
            "meme-web-access": self.access_token,
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
        """Get hot tokens on Four.meme."""
        resp = await self._client.post(
            "/v1/public/token/ranking",
            json={"pageNo": 1, "pageSize": 20, "type": "HOT"},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

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
