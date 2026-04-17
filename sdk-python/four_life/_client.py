"""FOUR-LIFE Certified API client — sync + async."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional, Union

import httpx

__all__ = [
    "FourLife",
    "AsyncFourLife",
    "FourLifeError",
    "DEFAULT_API_BASE",
    "SDK_VERSION",
]


DEFAULT_API_BASE = "https://four-life.gudman.xyz"
SDK_VERSION = "0.1.0"
_USER_AGENT = f"four-life-sdk-python/{SDK_VERSION}"

_VALID_TIERS = {"graduated", "graduation_watch", "healthy", "at_risk", "observed"}


class FourLifeError(RuntimeError):
    """Raised on API errors, network failures, or malformed inputs.

    Attributes:
        status: HTTP status code if the server responded (None for transport errors).
        body: Parsed JSON response body, or the raw text if parsing failed.
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _normalize_address(addr: str) -> str:
    if not addr:
        raise FourLifeError("Token/creator address is required")
    if not (isinstance(addr, str) and addr.startswith("0x") and len(addr) == 42):
        raise FourLifeError(f"Invalid address: {addr!r}")
    return addr.lower()


def _build_radar_params(
    *,
    limit: Optional[int],
    quote_asset: Optional[str],
    min_confidence: Optional[str],
    sort_by: Optional[str],
) -> dict[str, str]:
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(int(limit))
    if quote_asset is not None:
        params["quote_asset"] = quote_asset
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    if sort_by is not None:
        params["sort_by"] = sort_by
    return params


def _build_leaderboard_params(
    *,
    sort_by: Optional[str],
    trust_tier: Optional[str],
    min_launches: Optional[int],
    limit: Optional[int],
) -> dict[str, str]:
    params: dict[str, str] = {}
    if sort_by is not None:
        params["sort_by"] = sort_by
    if trust_tier is not None:
        params["trust_tier"] = trust_tier
    if min_launches is not None:
        params["min_launches"] = str(int(min_launches))
    if limit is not None:
        params["limit"] = str(int(limit))
    return params


def _build_history_params(
    *,
    limit: Optional[int],
    since: Optional[int],
    transitions_only: Optional[bool],
) -> dict[str, str]:
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(int(limit))
    if since is not None:
        params["since"] = str(int(since))
    if transitions_only is not None:
        params["transitions_only"] = "true" if transitions_only else "false"
    return params


def _build_protection_payload(
    *,
    active: bool,
    max_whale_concentration: Optional[float],
    critical_whale_concentration: Optional[float],
    critical_buy_sell_ratio: Optional[float],
    max_contract_risk: Optional[int],
    critical_contract_risk: Optional[int],
    max_whale_count: Optional[int],
    critical_whale_count: Optional[int],
    created_by: Optional[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"active": bool(active)}
    if max_whale_concentration is not None:
        payload["max_whale_concentration"] = float(max_whale_concentration)
    if critical_whale_concentration is not None:
        payload["critical_whale_concentration"] = float(critical_whale_concentration)
    if critical_buy_sell_ratio is not None:
        payload["critical_buy_sell_ratio"] = float(critical_buy_sell_ratio)
    if max_contract_risk is not None:
        payload["max_contract_risk"] = int(max_contract_risk)
    if critical_contract_risk is not None:
        payload["critical_contract_risk"] = int(critical_contract_risk)
    if max_whale_count is not None:
        payload["max_whale_count"] = int(max_whale_count)
    if critical_whale_count is not None:
        payload["critical_whale_count"] = int(critical_whale_count)
    if created_by is not None:
        payload["created_by"] = str(created_by)
    return payload


class _BaseClient:
    """Shared configuration for sync + async clients."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_API_BASE).rstrip("/")
        self.api_secret = api_secret
        self.timeout = float(timeout)

    def _default_headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        if self.api_secret:
            h["Authorization"] = f"Bearer {self.api_secret}"
        return h


def _handle_response(resp: httpx.Response, path: str) -> Any:
    text = resp.text
    try:
        body: Any = resp.json() if text else None
    except ValueError:
        body = text
    if resp.status_code >= 400:
        raise FourLifeError(
            f"FOUR-LIFE API {resp.status_code} at {path}",
            status=resp.status_code,
            body=body,
        )
    return body


# ── Sync client ───────────────────────────────────────────────────────


class FourLife(_BaseClient):
    """Synchronous client for the FOUR-LIFE Certified API.

    Usage:
        fl = FourLife()
        badge = fl.get_badge("0xabc...")

    Pass ``api_secret=`` for write endpoints (track_token, protection policies,
    webhook management). Leave empty when the API is in open-dev mode.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 20.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        super().__init__(base_url=base_url, api_secret=api_secret, timeout=timeout)
        self._owned = client is None
        self._client = client or httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def __enter__(self) -> "FourLife":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        json: Any = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self._client.request(
                method, url, headers=self._default_headers(), params=params, json=json,
            )
        except httpx.TimeoutException as exc:
            raise FourLifeError(f"Request timed out at {path}: {exc}") from exc
        except httpx.RequestError as exc:
            raise FourLifeError(f"Request failed at {path}: {exc}") from exc
        return _handle_response(resp, path)

    # ── Public reads ────────────────────────────────────────────────

    def get_badge(self, token_address: str) -> dict:
        """GET /api/token/{token}/badge"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/token/{addr}/badge")

    def get_risk_snapshot(self, token_address: str) -> dict:
        """GET /api/token/{token}/risk-snapshot"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/token/{addr}/risk-snapshot")

    def get_operator_checklist(self, token_address: str) -> dict:
        """GET /api/token/{token}/operator-checklist"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/token/{addr}/operator-checklist")

    def get_contract_risk(self, token_address: str) -> dict:
        """GET /api/token/{token}/contract-risk"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/token/{addr}/contract-risk")

    def get_health_score(self, token_address: str) -> dict:
        """GET /api/health-score/{token}"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/health-score/{addr}")

    def get_graduation_radar(
        self,
        *,
        limit: Optional[int] = None,
        quote_asset: Optional[str] = None,
        min_confidence: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> dict:
        """GET /api/graduation-radar"""
        params = _build_radar_params(
            limit=limit, quote_asset=quote_asset,
            min_confidence=min_confidence, sort_by=sort_by,
        )
        return self._request("GET", "/api/graduation-radar", params=params)

    def get_platform_cohorts(self) -> dict:
        """GET /api/platform/cohorts"""
        return self._request("GET", "/api/platform/cohorts")

    def get_creator_score(self, wallet: str) -> dict:
        """GET /api/creator/{wallet}/survival-score"""
        addr = _normalize_address(wallet)
        return self._request("GET", f"/api/creator/{addr}/survival-score")

    def get_creators_leaderboard(
        self,
        *,
        sort_by: Optional[str] = None,
        trust_tier: Optional[str] = None,
        min_launches: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """GET /api/creators/leaderboard"""
        params = _build_leaderboard_params(
            sort_by=sort_by, trust_tier=trust_tier,
            min_launches=min_launches, limit=limit,
        )
        return self._request("GET", "/api/creators/leaderboard", params=params)

    def get_identity(self) -> dict:
        """GET /api/identity"""
        return self._request("GET", "/api/identity")

    def get_dgrid_stats(self) -> dict:
        """GET /api/dgrid/stats"""
        return self._request("GET", "/api/dgrid/stats")

    # ── History ─────────────────────────────────────────────────────

    def get_history(
        self,
        token_address: str,
        *,
        limit: Optional[int] = None,
        since: Optional[int] = None,
        transitions_only: Optional[bool] = None,
    ) -> dict:
        """GET /api/token/{token}/history"""
        addr = _normalize_address(token_address)
        params = _build_history_params(
            limit=limit, since=since, transitions_only=transitions_only,
        )
        return self._request("GET", f"/api/token/{addr}/history", params=params)

    def get_diff(self, token_address: str, *, since: int) -> dict:
        """GET /api/token/{token}/diff?since=..."""
        addr = _normalize_address(token_address)
        return self._request(
            "GET", f"/api/token/{addr}/diff", params={"since": str(int(since))},
        )

    def get_tokens_with_history(self, *, limit: Optional[int] = None) -> dict:
        """GET /api/history/tokens"""
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(int(limit))
        return self._request("GET", "/api/history/tokens", params=params)

    def iter_history_export(
        self,
        *,
        since: Optional[int] = None,
        token_address: Optional[str] = None,
    ) -> Iterator[dict]:
        """Stream the full history export as parsed snapshot dicts.

        GET /api/history/export.ndjson — memory-flat for large DBs.
        """
        import json as _json

        params: dict[str, str] = {}
        if since is not None:
            params["since"] = str(int(since))
        if token_address is not None:
            params["token_address"] = _normalize_address(token_address)

        url = f"{self.base_url}/api/history/export.ndjson"
        with self._client.stream(
            "GET", url, headers=self._default_headers(), params=params,
        ) as resp:
            if resp.status_code >= 400:
                body = resp.read().decode("utf-8", errors="replace")
                raise FourLifeError(
                    f"FOUR-LIFE API {resp.status_code} at /api/history/export.ndjson",
                    status=resp.status_code,
                    body=body,
                )
            for line in resp.iter_lines():
                if not line:
                    continue
                yield _json.loads(line)

    # ── Protection Mode ─────────────────────────────────────────────

    def get_protection_policy(self, token_address: str) -> dict:
        """GET /api/protection/{token}"""
        addr = _normalize_address(token_address)
        return self._request("GET", f"/api/protection/{addr}")

    def set_protection_policy(
        self,
        token_address: str,
        *,
        active: bool = True,
        max_whale_concentration: Optional[float] = None,
        critical_whale_concentration: Optional[float] = None,
        critical_buy_sell_ratio: Optional[float] = None,
        max_contract_risk: Optional[int] = None,
        critical_contract_risk: Optional[int] = None,
        max_whale_count: Optional[int] = None,
        critical_whale_count: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        """PUT /api/protection/{token} — requires api_secret.

        Unset thresholds fall back to the server-side defaults.
        """
        addr = _normalize_address(token_address)
        payload = _build_protection_payload(
            active=active,
            max_whale_concentration=max_whale_concentration,
            critical_whale_concentration=critical_whale_concentration,
            critical_buy_sell_ratio=critical_buy_sell_ratio,
            max_contract_risk=max_contract_risk,
            critical_contract_risk=critical_contract_risk,
            max_whale_count=max_whale_count,
            critical_whale_count=critical_whale_count,
            created_by=created_by,
        )
        return self._request("PUT", f"/api/protection/{addr}", json=payload)

    def delete_protection_policy(self, token_address: str) -> dict:
        """DELETE /api/protection/{token} — requires api_secret."""
        addr = _normalize_address(token_address)
        return self._request("DELETE", f"/api/protection/{addr}")

    def list_protection_policies(self, *, include_inactive: bool = True) -> dict:
        """GET /api/protection"""
        params = {"include_inactive": "true" if include_inactive else "false"}
        return self._request("GET", "/api/protection", params=params)

    # ── Webhooks ────────────────────────────────────────────────────

    def create_webhook(
        self,
        *,
        url: str,
        events: Optional[Iterable[str]] = None,
        token_filter: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        """POST /api/webhooks — requires api_secret.

        The response contains a ``secret`` returned **exactly once**. Store it securely.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise FourLifeError("url must be an absolute http(s) URL")
        payload: dict[str, Any] = {
            "url": url,
            "events": list(events) if events is not None else ["badge.tier_changed"],
        }
        if token_filter is not None:
            payload["token_filter"] = _normalize_address(token_filter)
        if created_by is not None:
            payload["created_by"] = str(created_by)
        return self._request("POST", "/api/webhooks", json=payload)

    def list_webhooks(self, *, include_disabled: bool = False) -> dict:
        """GET /api/webhooks — requires api_secret."""
        params = {"include_disabled": "true" if include_disabled else "false"}
        return self._request("GET", "/api/webhooks", params=params)

    def delete_webhook(self, subscription_id: str) -> dict:
        """DELETE /api/webhooks/{id} — requires api_secret."""
        if not subscription_id:
            raise FourLifeError("subscription_id is required")
        return self._request("DELETE", f"/api/webhooks/{subscription_id}")

    def list_webhook_deliveries(
        self, subscription_id: str, *, limit: Optional[int] = None,
    ) -> dict:
        """GET /api/webhooks/{id}/deliveries — requires api_secret."""
        if not subscription_id:
            raise FourLifeError("subscription_id is required")
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(int(limit))
        return self._request(
            "GET", f"/api/webhooks/{subscription_id}/deliveries", params=params,
        )

    # ── Notifications ───────────────────────────────────────────────

    def get_notifications_status(self) -> dict:
        """GET /api/notifications/status"""
        return self._request("GET", "/api/notifications/status")

    def send_test_notification(
        self, *, event_type: str = "badge.tier_changed",
    ) -> dict:
        """POST /api/notifications/test — requires api_secret."""
        return self._request(
            "POST", "/api/notifications/test",
            params={"event_type": event_type},
        )

    # ── Agent write ops ─────────────────────────────────────────────

    def generate_raise_plan(self, token_address: str) -> dict:
        """POST /api/raise-plan/{token} — LLM-generated 72h raise plan."""
        addr = _normalize_address(token_address)
        return self._request("POST", f"/api/raise-plan/{addr}")

    def track_token(
        self,
        *,
        token_address: str,
        name: str = "",
        symbol: str = "",
        quote_asset: str = "BNB",
        creator: Optional[str] = None,
        concept: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        """POST /api/agent/track — begin lifecycle tracking. Requires api_secret."""
        payload: dict[str, Any] = {
            "token_address": _normalize_address(token_address),
            "name": name or "",
            "symbol": symbol or "",
            "quote_asset": (quote_asset or "BNB").upper(),
        }
        if creator is not None:
            payload["creator"] = _normalize_address(creator)
        if concept is not None:
            payload["concept"] = dict(concept)
        return self._request("POST", "/api/agent/track", json=payload)

    # ── Polling helpers ─────────────────────────────────────────────

    def watch_token(
        self,
        token_address: str,
        on_update: Callable[[dict], None],
        *,
        interval_seconds: float = 60.0,
        on_error: Optional[Callable[[Exception], bool]] = None,
    ) -> Callable[[], None]:
        """Poll the badge every ``interval_seconds``, calling ``on_update`` with each result.

        Runs in a daemon thread. Returns an ``unwatch`` callable to stop polling.
        If ``on_error`` is provided and returns False, polling stops.
        """
        stop_event = threading.Event()

        def _loop() -> None:
            while not stop_event.is_set():
                try:
                    badge = self.get_badge(token_address)
                    if not stop_event.is_set():
                        on_update(badge)
                except Exception as exc:  # noqa: BLE001 — caller-controlled continuation
                    cont = True
                    if on_error is not None:
                        cont = bool(on_error(exc))
                    if not cont:
                        break
                stop_event.wait(timeout=interval_seconds)

        thread = threading.Thread(target=_loop, daemon=True, name="four-life-watch")
        thread.start()

        def unwatch() -> None:
            stop_event.set()

        return unwatch


# ── Async client ─────────────────────────────────────────────────────


class AsyncFourLife(_BaseClient):
    """Async variant of :class:`FourLife`. Same surface, awaitable methods.

    Usage:
        async with AsyncFourLife() as fl:
            badge = await fl.get_badge("0xabc...")
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 20.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(base_url=base_url, api_secret=api_secret, timeout=timeout)
        self._owned = client is None
        self._client = client or httpx.AsyncClient(timeout=self.timeout)

    async def aclose(self) -> None:
        if self._owned:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncFourLife":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        json: Any = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = await self._client.request(
                method, url, headers=self._default_headers(), params=params, json=json,
            )
        except httpx.TimeoutException as exc:
            raise FourLifeError(f"Request timed out at {path}: {exc}") from exc
        except httpx.RequestError as exc:
            raise FourLifeError(f"Request failed at {path}: {exc}") from exc
        return _handle_response(resp, path)

    # Reads
    async def get_badge(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/token/{_normalize_address(token_address)}/badge")

    async def get_risk_snapshot(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/token/{_normalize_address(token_address)}/risk-snapshot")

    async def get_operator_checklist(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/token/{_normalize_address(token_address)}/operator-checklist")

    async def get_contract_risk(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/token/{_normalize_address(token_address)}/contract-risk")

    async def get_health_score(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/health-score/{_normalize_address(token_address)}")

    async def get_graduation_radar(
        self,
        *,
        limit: Optional[int] = None,
        quote_asset: Optional[str] = None,
        min_confidence: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> dict:
        params = _build_radar_params(
            limit=limit, quote_asset=quote_asset,
            min_confidence=min_confidence, sort_by=sort_by,
        )
        return await self._request("GET", "/api/graduation-radar", params=params)

    async def get_platform_cohorts(self) -> dict:
        return await self._request("GET", "/api/platform/cohorts")

    async def get_creator_score(self, wallet: str) -> dict:
        return await self._request("GET", f"/api/creator/{_normalize_address(wallet)}/survival-score")

    async def get_creators_leaderboard(
        self,
        *,
        sort_by: Optional[str] = None,
        trust_tier: Optional[str] = None,
        min_launches: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        params = _build_leaderboard_params(
            sort_by=sort_by, trust_tier=trust_tier,
            min_launches=min_launches, limit=limit,
        )
        return await self._request("GET", "/api/creators/leaderboard", params=params)

    async def get_identity(self) -> dict:
        return await self._request("GET", "/api/identity")

    async def get_dgrid_stats(self) -> dict:
        return await self._request("GET", "/api/dgrid/stats")

    # History
    async def get_history(
        self,
        token_address: str,
        *,
        limit: Optional[int] = None,
        since: Optional[int] = None,
        transitions_only: Optional[bool] = None,
    ) -> dict:
        addr = _normalize_address(token_address)
        return await self._request(
            "GET", f"/api/token/{addr}/history",
            params=_build_history_params(
                limit=limit, since=since, transitions_only=transitions_only,
            ),
        )

    async def get_diff(self, token_address: str, *, since: int) -> dict:
        addr = _normalize_address(token_address)
        return await self._request(
            "GET", f"/api/token/{addr}/diff", params={"since": str(int(since))},
        )

    async def get_tokens_with_history(self, *, limit: Optional[int] = None) -> dict:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(int(limit))
        return await self._request("GET", "/api/history/tokens", params=params)

    # Protection
    async def get_protection_policy(self, token_address: str) -> dict:
        return await self._request("GET", f"/api/protection/{_normalize_address(token_address)}")

    async def set_protection_policy(
        self,
        token_address: str,
        *,
        active: bool = True,
        max_whale_concentration: Optional[float] = None,
        critical_whale_concentration: Optional[float] = None,
        critical_buy_sell_ratio: Optional[float] = None,
        max_contract_risk: Optional[int] = None,
        critical_contract_risk: Optional[int] = None,
        max_whale_count: Optional[int] = None,
        critical_whale_count: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        addr = _normalize_address(token_address)
        payload = _build_protection_payload(
            active=active,
            max_whale_concentration=max_whale_concentration,
            critical_whale_concentration=critical_whale_concentration,
            critical_buy_sell_ratio=critical_buy_sell_ratio,
            max_contract_risk=max_contract_risk,
            critical_contract_risk=critical_contract_risk,
            max_whale_count=max_whale_count,
            critical_whale_count=critical_whale_count,
            created_by=created_by,
        )
        return await self._request("PUT", f"/api/protection/{addr}", json=payload)

    async def delete_protection_policy(self, token_address: str) -> dict:
        return await self._request("DELETE", f"/api/protection/{_normalize_address(token_address)}")

    async def list_protection_policies(self, *, include_inactive: bool = True) -> dict:
        params = {"include_inactive": "true" if include_inactive else "false"}
        return await self._request("GET", "/api/protection", params=params)

    # Webhooks
    async def create_webhook(
        self,
        *,
        url: str,
        events: Optional[Iterable[str]] = None,
        token_filter: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise FourLifeError("url must be an absolute http(s) URL")
        payload: dict[str, Any] = {
            "url": url,
            "events": list(events) if events is not None else ["badge.tier_changed"],
        }
        if token_filter is not None:
            payload["token_filter"] = _normalize_address(token_filter)
        if created_by is not None:
            payload["created_by"] = str(created_by)
        return await self._request("POST", "/api/webhooks", json=payload)

    async def list_webhooks(self, *, include_disabled: bool = False) -> dict:
        params = {"include_disabled": "true" if include_disabled else "false"}
        return await self._request("GET", "/api/webhooks", params=params)

    async def delete_webhook(self, subscription_id: str) -> dict:
        if not subscription_id:
            raise FourLifeError("subscription_id is required")
        return await self._request("DELETE", f"/api/webhooks/{subscription_id}")

    async def list_webhook_deliveries(
        self, subscription_id: str, *, limit: Optional[int] = None,
    ) -> dict:
        if not subscription_id:
            raise FourLifeError("subscription_id is required")
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(int(limit))
        return await self._request(
            "GET", f"/api/webhooks/{subscription_id}/deliveries", params=params,
        )

    # Notifications
    async def get_notifications_status(self) -> dict:
        return await self._request("GET", "/api/notifications/status")

    async def send_test_notification(
        self, *, event_type: str = "badge.tier_changed",
    ) -> dict:
        return await self._request(
            "POST", "/api/notifications/test", params={"event_type": event_type},
        )

    # Agent writes
    async def generate_raise_plan(self, token_address: str) -> dict:
        addr = _normalize_address(token_address)
        return await self._request("POST", f"/api/raise-plan/{addr}")

    async def track_token(
        self,
        *,
        token_address: str,
        name: str = "",
        symbol: str = "",
        quote_asset: str = "BNB",
        creator: Optional[str] = None,
        concept: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "token_address": _normalize_address(token_address),
            "name": name or "",
            "symbol": symbol or "",
            "quote_asset": (quote_asset or "BNB").upper(),
        }
        if creator is not None:
            payload["creator"] = _normalize_address(creator)
        if concept is not None:
            payload["concept"] = dict(concept)
        return await self._request("POST", "/api/agent/track", json=payload)
