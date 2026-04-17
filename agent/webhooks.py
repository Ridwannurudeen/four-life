"""Outbound webhooks for tier-transition events.

Consumers register a URL + event list. When FOUR-LIFE observes a qualifying event
(currently `badge.tier_changed`), we POST a signed JSON payload to the URL and retry
on failure with exponential backoff. Persistence is a small SQLite file at
`data/webhooks.db`, kept separate from history so subscription/delivery churn does
not contend with the snapshot write path.

Signing format — same shape as Stripe-style signed webhooks:

    X-FourLife-Signature: t=<unix_ts>,v1=<hex_hmac_sha256(f"{ts}.{body}", secret)>

Consumers verify by recomputing the HMAC with the shared secret returned at subscribe
time. The secret is shown **once** — we never return it again.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx
from loguru import logger


WEBHOOK_DIR = Path(__file__).parent.parent / "data"
WEBHOOK_FILE = WEBHOOK_DIR / "webhooks.db"

EVENT_BADGE_TIER_CHANGED = "badge.tier_changed"
EVENT_PROTECTION_LEVEL_CHANGED = "protection.level_changed"
SUPPORTED_EVENTS = frozenset({EVENT_BADGE_TIER_CHANGED, EVENT_PROTECTION_LEVEL_CHANGED})

# Retry schedule (seconds from first attempt) — fail-fast then widen.
# Delivery is considered dead after we exhaust the schedule.
RETRY_SCHEDULE_SECONDS = (30, 120, 900)  # 30s, 2m, 15m
MAX_DELIVERY_ATTEMPTS = len(RETRY_SCHEDULE_SECONDS) + 1  # 4 total tries

# Auto-disable a subscription when the number of consecutive dead deliveries
# reaches this threshold. The subscription stays in the DB but no new events fire.
AUTO_DISABLE_CONSECUTIVE_FAILURES = 10

HTTP_TIMEOUT_SECONDS = 10


SCHEMA = """
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    events_json TEXT NOT NULL,
    token_filter TEXT,
    created_at INTEGER NOT NULL,
    created_by TEXT,
    disabled_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_subs_active ON webhook_subscriptions (disabled_at)
    WHERE disabled_at IS NULL;

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_json TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    response_body TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at INTEGER,
    created_at INTEGER NOT NULL,
    delivered_at INTEGER,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_deliveries_sub ON webhook_deliveries (subscription_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deliveries_pending ON webhook_deliveries (status, next_retry_at);
"""


@dataclass
class Subscription:
    id: str
    url: str
    events: list[str]
    token_filter: str | None
    created_at: int
    created_by: str | None
    disabled_at: int | None

    def is_active(self) -> bool:
        return self.disabled_at is None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "token_filter": self.token_filter,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "disabled_at": self.disabled_at,
            "active": self.is_active(),
        }


@dataclass
class Delivery:
    id: int
    subscription_id: str
    event_type: str
    event_id: str
    url: str
    status: str
    http_status: int | None
    attempts: int
    next_retry_at: int | None
    created_at: int
    delivered_at: int | None
    last_error: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "url": self.url,
            "status": self.status,
            "http_status": self.http_status,
            "attempts": self.attempts,
            "next_retry_at": self.next_retry_at,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "last_error": self.last_error,
        }


class WebhookStore:
    """Persistent subscription + delivery store. Thread-safe for writes."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else WEBHOOK_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ── Subscriptions ────────────────────────────────────────────────

    def subscribe(
        self,
        *,
        url: str,
        events: list[str],
        token_filter: str | None = None,
        created_by: str | None = None,
        now: int | None = None,
    ) -> tuple[Subscription, str]:
        """Register a new subscription and return (subscription, shared_secret).

        The secret is returned once and never retrievable again. Consumers store it
        and use it to verify HMAC signatures on delivered webhook payloads.
        """
        for e in events:
            if e not in SUPPORTED_EVENTS:
                raise ValueError(f"Unsupported event type: {e}")
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must be an absolute http(s) URL")

        sub_id = "whs_" + uuid.uuid4().hex[:20]
        secret = "whsec_" + secrets.token_urlsafe(32)
        created_at = now if now is not None else int(time.time())
        token_key = token_filter.lower() if token_filter else None

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO webhook_subscriptions
                        (id, url, secret, events_json, token_filter, created_at, created_by, disabled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        sub_id,
                        url,
                        secret,
                        json.dumps(list(events), separators=(",", ":")),
                        token_key,
                        created_at,
                        created_by,
                    ),
                )
                conn.commit()

        return (
            Subscription(
                id=sub_id,
                url=url,
                events=list(events),
                token_filter=token_key,
                created_at=created_at,
                created_by=created_by,
                disabled_at=None,
            ),
            secret,
        )

    def list_subscriptions(self, *, include_disabled: bool = False) -> list[Subscription]:
        query = "SELECT id, url, events_json, token_filter, created_at, created_by, disabled_at FROM webhook_subscriptions"
        if not include_disabled:
            query += " WHERE disabled_at IS NULL"
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_subscription(r) for r in rows]

    def get_subscription(self, sub_id: str) -> Subscription | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, url, events_json, token_filter, created_at, created_by, disabled_at "
                "FROM webhook_subscriptions WHERE id = ?",
                (sub_id,),
            ).fetchone()
        return _row_to_subscription(row) if row else None

    def _get_subscription_secret(self, sub_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT secret FROM webhook_subscriptions WHERE id = ?",
                (sub_id,),
            ).fetchone()
        return row["secret"] if row else None

    def delete_subscription(self, sub_id: str) -> bool:
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM webhook_subscriptions WHERE id = ?", (sub_id,))
                conn.commit()
                return cur.rowcount > 0

    def disable_subscription(self, sub_id: str, *, now: int | None = None) -> None:
        ts = now if now is not None else int(time.time())
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE webhook_subscriptions SET disabled_at = ? WHERE id = ? AND disabled_at IS NULL",
                    (ts, sub_id),
                )
                conn.commit()

    # ── Matching ─────────────────────────────────────────────────────

    def subscriptions_for_event(
        self,
        *,
        event_type: str,
        token_address: str | None,
    ) -> list[Subscription]:
        """Return active subscriptions that should receive this event."""
        token_key = (token_address or "").lower() if token_address else None
        subs = self.list_subscriptions(include_disabled=False)
        matched: list[Subscription] = []
        for s in subs:
            if event_type not in s.events:
                continue
            if s.token_filter and token_key and s.token_filter != token_key:
                continue
            matched.append(s)
        return matched

    # ── Deliveries ───────────────────────────────────────────────────

    def enqueue_delivery(
        self,
        *,
        subscription: Subscription,
        event_type: str,
        event: dict,
        now: int | None = None,
    ) -> int:
        """Create a pending delivery row. Returns the delivery id."""
        ts = now if now is not None else int(time.time())
        event_id = event.get("id") or ("evt_" + uuid.uuid4().hex[:20])
        event = {**event, "id": event_id, "type": event_type, "created_at": ts}

        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO webhook_deliveries
                        (subscription_id, event_type, event_id, event_json, url,
                         status, attempts, next_retry_at, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)
                    """,
                    (
                        subscription.id,
                        event_type,
                        event_id,
                        json.dumps(event, separators=(",", ":")),
                        subscription.url,
                        ts,
                        ts,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)

    def list_deliveries(self, subscription_id: str, *, limit: int = 50) -> list[Delivery]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM webhook_deliveries WHERE subscription_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (subscription_id, limit),
            ).fetchall()
        return [_row_to_delivery(r) for r in rows]

    def get_delivery(self, delivery_id: int) -> Delivery | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM webhook_deliveries WHERE id = ?",
                (int(delivery_id),),
            ).fetchone()
        return _row_to_delivery(row) if row else None

    def get_delivery_payload(self, delivery_id: int) -> tuple[dict, str] | None:
        """Return (event, subscription_secret) for dispatch. None if missing."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT d.event_json, d.subscription_id, s.secret "
                "FROM webhook_deliveries d JOIN webhook_subscriptions s "
                "ON s.id = d.subscription_id WHERE d.id = ?",
                (int(delivery_id),),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["event_json"]), row["secret"]

    def mark_delivery_attempt(
        self,
        delivery_id: int,
        *,
        status: str,
        http_status: int | None = None,
        response_body: str | None = None,
        last_error: str | None = None,
        next_retry_at: int | None = None,
        delivered_at: int | None = None,
    ) -> None:
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE webhook_deliveries SET
                        status = ?,
                        http_status = COALESCE(?, http_status),
                        response_body = COALESCE(?, response_body),
                        attempts = attempts + 1,
                        next_retry_at = ?,
                        delivered_at = COALESCE(?, delivered_at),
                        last_error = COALESCE(?, last_error)
                    WHERE id = ?
                    """,
                    (
                        status,
                        http_status,
                        response_body,
                        next_retry_at,
                        delivered_at,
                        last_error,
                        int(delivery_id),
                    ),
                )
                conn.commit()

    def consecutive_dead_count(self, subscription_id: str) -> int:
        """How many of the most recent deliveries for this subscription are 'dead'?
        Counting resets on the first non-dead delivery."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status FROM webhook_deliveries WHERE subscription_id = ? "
                "ORDER BY created_at DESC LIMIT 100",
                (subscription_id,),
            ).fetchall()
        count = 0
        for r in rows:
            if r["status"] == "dead":
                count += 1
            else:
                break
        return count


def _row_to_subscription(row: sqlite3.Row) -> Subscription:
    return Subscription(
        id=row["id"],
        url=row["url"],
        events=json.loads(row["events_json"]) if row["events_json"] else [],
        token_filter=row["token_filter"],
        created_at=int(row["created_at"]),
        created_by=row["created_by"],
        disabled_at=int(row["disabled_at"]) if row["disabled_at"] is not None else None,
    )


def _row_to_delivery(row: sqlite3.Row) -> Delivery:
    return Delivery(
        id=int(row["id"]),
        subscription_id=row["subscription_id"],
        event_type=row["event_type"],
        event_id=row["event_id"],
        url=row["url"],
        status=row["status"],
        http_status=int(row["http_status"]) if row["http_status"] is not None else None,
        attempts=int(row["attempts"]),
        next_retry_at=int(row["next_retry_at"]) if row["next_retry_at"] is not None else None,
        created_at=int(row["created_at"]),
        delivered_at=int(row["delivered_at"]) if row["delivered_at"] is not None else None,
        last_error=row["last_error"],
    )


# ── Signing ────────────────────────────────────────────────────────────

def sign_payload(*, secret: str, body: str, timestamp: int) -> str:
    """Compute the value for the X-FourLife-Signature header."""
    signed_data = f"{timestamp}.{body}".encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), signed_data, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify_signature(
    *,
    secret: str,
    body: str,
    signature_header: str,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify a signature header produced by `sign_payload`. Returns True iff valid
    and within the tolerance window."""
    now_ts = now if now is not None else int(time.time())
    parts = {}
    for seg in signature_header.split(","):
        if "=" in seg:
            k, v = seg.split("=", 1)
            parts[k.strip()] = v.strip()
    t = parts.get("t")
    v1 = parts.get("v1")
    if not t or not v1:
        return False
    try:
        t_int = int(t)
    except ValueError:
        return False
    if abs(now_ts - t_int) > tolerance_seconds:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), f"{t_int}.{body}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, v1)


# ── Dispatcher ─────────────────────────────────────────────────────────

# Test hook: if set, dispatcher uses this instead of a real httpx client.
# Signature: async fn(url: str, body: str, headers: dict) -> (status_code: int, text: str)
_TRANSPORT_OVERRIDE: Callable[..., Any] | None = None


def set_transport_override(fn: Callable[..., Any] | None) -> None:
    global _TRANSPORT_OVERRIDE
    _TRANSPORT_OVERRIDE = fn


async def _post_once(url: str, body: str, headers: dict[str, str]) -> tuple[int, str]:
    if _TRANSPORT_OVERRIDE is not None:
        return await _TRANSPORT_OVERRIDE(url, body, headers)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, content=body, headers=headers)
        return resp.status_code, resp.text[:2000]


async def deliver(store: WebhookStore, delivery_id: int) -> None:
    """Attempt delivery with retries. Marks the delivery 'success' on any 2xx,
    'pending' with a next_retry_at while retries remain, and 'dead' when exhausted.

    Runs to completion (does NOT return early on retryable failures). This coroutine
    is meant to be fire-and-forget inside a running event loop.
    """
    payload = store.get_delivery_payload(delivery_id)
    if not payload:
        return
    event, secret = payload
    body = json.dumps(event, separators=(",", ":"))

    d = store.get_delivery(delivery_id)
    if not d:
        return
    url = d.url

    for attempt_index in range(MAX_DELIVERY_ATTEMPTS):
        now_ts = int(time.time())
        sig = sign_payload(secret=secret, body=body, timestamp=now_ts)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FOUR-LIFE-Webhooks/1.0",
            "X-FourLife-Signature": sig,
            "X-FourLife-Event": str(event.get("type", "")),
            "X-FourLife-Delivery": str(event.get("id", "")),
        }
        try:
            status_code, response_text = await _post_once(url, body, headers)
        except Exception as e:
            status_code, response_text = 0, f"transport_error: {e}"

        succeeded = 200 <= int(status_code) < 300
        if succeeded:
            store.mark_delivery_attempt(
                delivery_id,
                status="success",
                http_status=int(status_code),
                response_body=response_text,
                next_retry_at=None,
                delivered_at=int(time.time()),
            )
            return

        # Failure path
        is_last = attempt_index >= MAX_DELIVERY_ATTEMPTS - 1
        if is_last:
            store.mark_delivery_attempt(
                delivery_id,
                status="dead",
                http_status=int(status_code) or None,
                response_body=response_text,
                last_error=f"exhausted_after_{MAX_DELIVERY_ATTEMPTS}_attempts",
                next_retry_at=None,
            )
            # Auto-disable noisy subscriptions
            sub_id = None
            d = store.get_delivery(delivery_id)
            if d:
                sub_id = d.subscription_id
            if sub_id and store.consecutive_dead_count(sub_id) >= AUTO_DISABLE_CONSECUTIVE_FAILURES:
                store.disable_subscription(sub_id)
                logger.warning(
                    "webhook subscription {} auto-disabled after {} consecutive dead deliveries",
                    sub_id, AUTO_DISABLE_CONSECUTIVE_FAILURES,
                )
            return

        delay = RETRY_SCHEDULE_SECONDS[attempt_index]
        store.mark_delivery_attempt(
            delivery_id,
            status="pending",
            http_status=int(status_code) or None,
            response_body=response_text,
            last_error=f"http_{status_code}",
            next_retry_at=int(time.time()) + delay,
        )
        await asyncio.sleep(delay)


# ── High-level trigger + module singleton ──────────────────────────────

_default_store: WebhookStore | None = None
_default_lock = threading.Lock()


def default_store() -> WebhookStore:
    global _default_store
    if _default_store is None:
        with _default_lock:
            if _default_store is None:
                _default_store = WebhookStore()
    return _default_store


def fire_tier_changed(
    *,
    token_address: str,
    from_tier: str,
    to_tier: str,
    why: list[dict],
    metrics: dict,
    data_source: str | None = None,
    at: int | None = None,
    store: WebhookStore | None = None,
) -> list[int]:
    """Enqueue `badge.tier_changed` deliveries for every matching active subscription.

    Returns the list of delivery IDs created. Callers schedule actual HTTP POSTs via
    `schedule_deliveries()` on the running event loop.
    """
    s = store or default_store()
    ts = at if at is not None else int(time.time())
    token_key = (token_address or "").lower()
    event = {
        "token_address": token_key,
        "from_tier": from_tier,
        "to_tier": to_tier,
        "at": ts,
        "why": why,
        "metrics": metrics,
        "data_source": data_source,
    }
    subs = s.subscriptions_for_event(
        event_type=EVENT_BADGE_TIER_CHANGED, token_address=token_key,
    )
    delivery_ids: list[int] = []
    for sub in subs:
        did = s.enqueue_delivery(
            subscription=sub,
            event_type=EVENT_BADGE_TIER_CHANGED,
            event=event,
            now=ts,
        )
        delivery_ids.append(did)
    return delivery_ids


def fire_protection_level_changed(
    *,
    token_address: str,
    from_level: str | None,
    to_level: str,
    fired_rules: list[dict],
    recommended_actions: list[str],
    thresholds: dict,
    at: int | None = None,
    store: WebhookStore | None = None,
) -> list[int]:
    """Enqueue `protection.level_changed` deliveries for every matching subscription."""
    s = store or default_store()
    ts = at if at is not None else int(time.time())
    token_key = (token_address or "").lower()
    event = {
        "token_address": token_key,
        "from_level": from_level,
        "to_level": to_level,
        "at": ts,
        "fired_rules": fired_rules,
        "recommended_actions": recommended_actions,
        "thresholds": thresholds,
    }
    subs = s.subscriptions_for_event(
        event_type=EVENT_PROTECTION_LEVEL_CHANGED, token_address=token_key,
    )
    delivery_ids: list[int] = []
    for sub in subs:
        did = s.enqueue_delivery(
            subscription=sub,
            event_type=EVENT_PROTECTION_LEVEL_CHANGED,
            event=event,
            now=ts,
        )
        delivery_ids.append(did)
    return delivery_ids


def schedule_deliveries(delivery_ids: Iterable[int], *, store: WebhookStore | None = None) -> None:
    """Fire-and-forget dispatch for a batch of delivery ids. No-op outside an event loop."""
    s = store or default_store()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for did in delivery_ids:
        loop.create_task(deliver(s, did))
