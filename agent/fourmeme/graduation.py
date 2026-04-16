"""Pair-aware graduation target registry.

Sources graduation thresholds live from Four.meme's `/public/config` API. Each Four.meme
quote asset (BNB, USD1, USDT, USDC, CAKE, ...) has a different `totalBAmount` — the raise
needed to graduate a token launched against that pair.

The registry caches the config for 10 minutes and exposes a typed lookup. Unknown quote
assets return `confidence="low"` with no fabricated target — callers must handle this
explicitly rather than fall back to a silent default.
"""

import time
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger


CONFIG_URL = "https://four.meme/meme-api/v1/public/config"
CACHE_TTL_SECONDS = 600  # 10 minutes


@dataclass
class GraduationTarget:
    """The graduation threshold for a given Four.meme quote asset."""

    quote_asset: str          # e.g. "BNB", "USD1", "USDT"
    target_amount: float       # e.g. 18.0 (BNB) or 12000.0 (USD1)
    b0_amount: float           # virtual starting reserve, used for curve-progress math
    confidence: str            # "high" (from live config), "medium" (cached), "low" (unknown)
    source: str                # "fourmeme_config", "cache", "fallback"
    fetched_at: float          # epoch seconds
    status: str = "PUBLISH"    # PUBLISH | INIT | HIDE


class GraduationRegistry:
    """Caches and serves pair-aware graduation thresholds from Four.meme's public config."""

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = http_client
        self._owns_client = http_client is None
        self._cache: dict[str, GraduationTarget] = {}
        self._last_fetch: float = 0.0

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15,
                headers={"User-Agent": "four-life-agent/1.0.0"},
            )
        return self._client

    async def refresh(self) -> None:
        """Fetch the latest config from Four.meme and update the cache."""
        client = await self._ensure_client()
        resp = await client.get(CONFIG_URL)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        fetched = time.time()
        new_cache: dict[str, GraduationTarget] = {}
        for entry in data:
            symbol = entry.get("symbol", "").upper()
            if not symbol:
                continue
            try:
                target_amount = float(entry.get("totalBAmount", 0))
                b0_amount = float(entry.get("b0Amount", 0))
            except (TypeError, ValueError):
                continue
            if target_amount <= 0:
                continue
            new_cache[symbol] = GraduationTarget(
                quote_asset=symbol,
                target_amount=target_amount,
                b0_amount=b0_amount,
                confidence="high",
                source="fourmeme_config",
                fetched_at=fetched,
                status=entry.get("status", "PUBLISH"),
            )

        self._cache = new_cache
        self._last_fetch = fetched
        logger.info(
            "Graduation registry refreshed: {} quote assets from Four.meme config",
            len(new_cache),
        )

    async def get(self, quote_asset: str) -> GraduationTarget:
        """Get the graduation target for a quote asset.

        Returns a `GraduationTarget` with `confidence="low"` for unknown assets — never
        fabricates a number. Callers must check `confidence` before using `target_amount`.
        """
        asset = (quote_asset or "").upper()

        # Refresh if cache is stale or empty
        if not self._cache or (time.time() - self._last_fetch) > CACHE_TTL_SECONDS:
            try:
                await self.refresh()
            except Exception as e:
                logger.warning("Graduation config refresh failed: {}", e)

        if asset in self._cache:
            target = self._cache[asset]
            # If we served from a stale cache, downgrade confidence
            if (time.time() - target.fetched_at) > CACHE_TTL_SECONDS:
                return GraduationTarget(
                    quote_asset=target.quote_asset,
                    target_amount=target.target_amount,
                    b0_amount=target.b0_amount,
                    confidence="medium",
                    source="cache",
                    fetched_at=target.fetched_at,
                    status=target.status,
                )
            return target

        # Unknown quote asset — don't fabricate
        return GraduationTarget(
            quote_asset=asset or "UNKNOWN",
            target_amount=0.0,
            b0_amount=0.0,
            confidence="low",
            source="fallback",
            fetched_at=time.time(),
            status="UNKNOWN",
        )

    def known_assets(self) -> list[str]:
        return sorted(self._cache.keys())

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()


# Module-level singleton (lazy)
_registry: Optional[GraduationRegistry] = None


def get_registry() -> GraduationRegistry:
    global _registry
    if _registry is None:
        _registry = GraduationRegistry()
    return _registry
