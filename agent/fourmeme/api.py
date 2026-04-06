"""Four.meme REST API client — auth, token creation, image upload."""

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from loguru import logger

from agent.config import settings


class FourMemeAPI:
    """Client for Four.meme's REST API."""

    def __init__(self) -> None:
        self.base = settings.fourmeme_api_base.rstrip("/")
        self.account = Account.from_key(settings.private_key)
        self.address = self.account.address
        self.access_token: str | None = None
        self._client = httpx.AsyncClient(timeout=30)

    # ── Auth ──────────────────────────────────────────────────────────

    async def login(self) -> str:
        """Authenticate via wallet signature. Returns JWT access token."""
        # Step 1: get nonce
        resp = await self._client.get(
            f"{self.base}/public/user/login/nonce",
            params={"address": self.address},
        )
        resp.raise_for_status()
        nonce = resp.json()["data"]["nonce"]

        # Step 2: sign message
        message = f"You are sign in Meme {nonce}"
        signable = encode_defunct(text=message)
        signed = self.account.sign_message(signable)
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: login
        resp = await self._client.post(
            f"{self.base}/public/user/login",
            json={
                "address": self.address,
                "signature": signature,
                "nonce": nonce,
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
        return {"Authorization": f"Bearer {self.access_token}"}

    # ── Token Creation ────────────────────────────────────────────────

    async def upload_image(self, image_bytes: bytes, filename: str = "token.png") -> str:
        """Upload token image. Returns the hosted image URL."""
        resp = await self._client.post(
            f"{self.base}/private/tool/upload",
            headers=self._auth_headers,
            files={"file": (filename, image_bytes, "image/png")},
        )
        resp.raise_for_status()
        image_url = resp.json()["data"]["imageUrl"]
        logger.info("Uploaded image: {}", image_url)
        return image_url

    async def prepare_token(
        self,
        name: str,
        symbol: str,
        description: str,
        image_url: str,
        total_supply: int = 1_000_000_000,
        launch_mode: int = 0,
    ) -> dict:
        """Prepare token creation — returns createArg and signature for on-chain call.

        Args:
            name: Token name
            symbol: Token ticker
            description: Token description
            image_url: URL from upload_image()
            total_supply: Fixed at 1B for Four.meme
            launch_mode: 0=Free, 1=Fair/X Mode

        Returns:
            dict with 'createArg' and 'signature' for TokenManager2.createToken()
        """
        resp = await self._client.post(
            f"{self.base}/private/token/create",
            headers=self._auth_headers,
            json={
                "name": name,
                "symbol": symbol,
                "description": description,
                "imageUrl": image_url,
                "totalSupply": str(total_supply),
                "launchMode": launch_mode,
            },
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        logger.info("Token prepared: {} ({})", name, symbol)
        return {
            "create_arg": data["createArg"],
            "signature": data["signature"],
        }

    # ── Market Data ───────────────────────────────────────────────────

    async def get_token_list(self, page: int = 1, size: int = 20) -> list[dict]:
        """Get list of tokens on Four.meme."""
        resp = await self._client.get(
            f"{self.base}/public/token/list",
            params={"page": page, "size": size},
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("list", [])

    async def get_token_detail(self, token_address: str) -> dict:
        """Get detailed info for a specific token."""
        resp = await self._client.get(
            f"{self.base}/public/token/detail",
            params={"address": token_address},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_trending(self) -> list[dict]:
        """Get trending tokens on Four.meme."""
        resp = await self._client.get(f"{self.base}/public/token/trending")
        resp.raise_for_status()
        return resp.json().get("data", [])

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
