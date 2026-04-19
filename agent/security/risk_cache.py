"""Shared contract-risk cache for the API and the lifecycle engine.

The API and the lifecycle engine both need an up-to-date contract risk score for
every tracked token: the API serves it on `/api/token/{addr}/badge` and
`/api/token/{addr}/risk-snapshot`, and the engine feeds it into the Protection
Mode verdict each tick. If they use different caches the engine goes silent on
contract risk (hardcoded 0) while the API fetches it lazily on public reads —
which is the gap the production audit flagged.

This module owns one in-memory cache (TTL = 10 min) and one analyzer instance,
so both callers see the same data.
"""

from __future__ import annotations

import time

from loguru import logger

from agent.security.contract_analyzer import ContractAnalyzer, ContractRisk

CONTRACT_RISK_TTL_SECONDS = 600

_cache: dict[str, tuple[float, ContractRisk]] = {}
_analyzer: ContractAnalyzer | None = None


def _get_analyzer(w3, bscscan_api_key: str = "") -> ContractAnalyzer:
    """Return (and memoize) the analyzer. w3 must come from an agent.chain."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContractAnalyzer(w3, bscscan_api_key=bscscan_api_key)
    return _analyzer


async def get_contract_risk(
    token_address: str,
    w3,
    bscscan_api_key: str = "",
) -> ContractRisk | None:
    """Fetch (or return cached) contract risk. None on analyzer failure.

    Uses a single module-level cache shared by the API and the lifecycle
    engine so every caller sees the same risk score within the TTL window.
    """
    key = token_address.lower()
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < CONTRACT_RISK_TTL_SECONDS:
        return cached[1]

    analyzer = _get_analyzer(w3, bscscan_api_key=bscscan_api_key)
    try:
        risk = await analyzer.analyze(token_address)
    except Exception as e:
        logger.warning("contract-risk analyze failed for {}: {}", token_address, e)
        return None
    _cache[key] = (now, risk)
    return risk


def peek_contract_risk(token_address: str) -> ContractRisk | None:
    """Return the cached ContractRisk without triggering a fresh fetch.

    Used by callers that cannot afford to block (hot paths, light reads). If
    the cache is empty for this token, returns None and the caller decides
    whether to spawn an async refresh.
    """
    cached = _cache.get(token_address.lower())
    if not cached:
        return None
    if time.time() - cached[0] >= CONTRACT_RISK_TTL_SECONDS:
        return None
    return cached[1]


def clear_cache() -> None:
    """Test helper — not used in production."""
    _cache.clear()
