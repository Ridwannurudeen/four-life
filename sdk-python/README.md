# four-life

Python SDK for the **[FOUR-LIFE Certified](https://four-life.gudman.xyz)** trust layer — Four.meme token grading, risk snapshots, creator scores, protection mode, and signed webhooks.

Zero runtime magic. Pure HTTP + HMAC. Works in any Python 3.9+ runtime.

## Install

```bash
pip install four-life
```

## Quick start

```python
from four_life import FourLife

fl = FourLife()

# Deterministic trust tier for any Four.meme token
badge = fl.get_badge("0xabc...")
print(badge["badge"]["tier"])            # "graduation_watch"
print(badge["badge"]["why"][0]["rule"])  # "curve_advanced"

# Live Graduation Radar
radar = fl.get_graduation_radar(limit=20, min_confidence="high")
for entry in radar["radar"]:
    print(entry["symbol"], entry["confidence_score"], entry["graduation_probability"])

# Creator ledger — survival rate across every tracked launch
score = fl.get_creator_score("0xcreator...")
print(score["trust_tier"], score["graduation_rate"])
```

## Async

```python
import asyncio
from four_life import AsyncFourLife

async def main():
    async with AsyncFourLife() as fl:
        badge = await fl.get_badge("0xabc...")
        print(badge["badge"]["tier"])

asyncio.run(main())
```

## Write endpoints (require an `API_SECRET` bearer token)

```python
fl = FourLife(api_secret="your-deployment-secret")

# Track a token you just launched
fl.track_token(
    token_address="0xabc...",
    name="My Token",
    symbol="MYT",
    quote_asset="BNB",
)

# Configure Protection Mode with stricter defaults
fl.set_protection_policy(
    "0xabc...",
    max_whale_concentration=25.0,
    critical_contract_risk=50,
)

# Create a webhook subscription — the secret is returned ONCE
sub = fl.create_webhook(
    url="https://your-service/fourlife-webhook",
    events=["badge.tier_changed", "protection.level_changed"],
)
secret = sub["secret"]  # store this now; it is not retrievable later
```

## Verify webhook signatures

```python
from four_life import verify_webhook_signature

# Inside your HTTP handler
def handle(request):
    body = request.get_data(as_text=True)          # RAW body, not parsed JSON
    header = request.headers["X-FourLife-Signature"]
    if not verify_webhook_signature(
        secret=MY_SECRET,
        body=body,
        signature_header=header,
    ):
        return ("bad signature", 401)
    # ...dispatch the event...
    return ("ok", 200)
```

## History + replay

```python
# Every snapshot ever recorded for a token
history = fl.get_history("0xabc...", limit=100)
for snap in history["snapshots"]:
    print(snap["recorded_at"], snap["tier"])

# Only the boundary rows (tier actually changed)
transitions = fl.get_history("0xabc...", transitions_only=True)

# Diff since timestamp
diff = fl.get_diff("0xabc...", since=1776000000)
print(diff["tier_changes"])

# Bulk export — streams NDJSON for large backfills
for snap in fl.iter_history_export():
    process(snap)
```

## Watch a token (poll-based, sync)

```python
def on_change(badge):
    print("tier:", badge["badge"]["tier"])

unwatch = fl.watch_token("0xabc...", on_change, interval_seconds=60)
# ... later
unwatch()
```

## Full surface

| Method | Endpoint |
|--------|----------|
| `get_badge(addr)` | `GET /api/token/{addr}/badge` |
| `get_risk_snapshot(addr)` | `GET /api/token/{addr}/risk-snapshot` |
| `get_operator_checklist(addr)` | `GET /api/token/{addr}/operator-checklist` |
| `get_contract_risk(addr)` | `GET /api/token/{addr}/contract-risk` |
| `get_health_score(addr)` | `GET /api/health-score/{addr}` |
| `get_graduation_radar(...)` | `GET /api/graduation-radar` |
| `get_platform_cohorts()` | `GET /api/platform/cohorts` |
| `get_creator_score(wallet)` | `GET /api/creator/{wallet}/survival-score` |
| `get_creators_leaderboard(...)` | `GET /api/creators/leaderboard` |
| `get_identity()` | `GET /api/identity` |
| `get_dgrid_stats()` | `GET /api/dgrid/stats` |
| `get_history(addr, ...)` | `GET /api/token/{addr}/history` |
| `get_diff(addr, since=...)` | `GET /api/token/{addr}/diff` |
| `get_tokens_with_history()` | `GET /api/history/tokens` |
| `iter_history_export(...)` | `GET /api/history/export.ndjson` (streaming) |
| `get_protection_policy(addr)` | `GET /api/protection/{addr}` |
| `set_protection_policy(addr, ...)` | `PUT /api/protection/{addr}` (auth) |
| `delete_protection_policy(addr)` | `DELETE /api/protection/{addr}` (auth) |
| `list_protection_policies()` | `GET /api/protection` |
| `create_webhook(url=..., events=...)` | `POST /api/webhooks` (auth) |
| `list_webhooks()` | `GET /api/webhooks` (auth) |
| `delete_webhook(id)` | `DELETE /api/webhooks/{id}` (auth) |
| `list_webhook_deliveries(id)` | `GET /api/webhooks/{id}/deliveries` (auth) |
| `get_notifications_status()` | `GET /api/notifications/status` |
| `send_test_notification()` | `POST /api/notifications/test` (auth) |
| `track_token(...)` | `POST /api/agent/track` (auth) |
| `generate_raise_plan(addr)` | `POST /api/raise-plan/{addr}` |
| `watch_token(addr, cb)` | 60s poll on `get_badge`, returns `unwatch()` |

Every method has an awaitable `AsyncFourLife` equivalent with identical arguments.

## Links

- FOUR-LIFE: https://four-life.gudman.xyz
- Webhooks reference: https://four-life.gudman.xyz/webhooks
- OpenAPI docs: https://four-life.gudman.xyz/docs
- Source: https://github.com/Ridwannurudeen/four-life

## License

MIT.
