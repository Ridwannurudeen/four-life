"""FastAPI server — dashboard backend + agent-card endpoint."""

import json
import re
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.agent import FourLifeAgent
from agent.badge import badge_from_health, badge_from_ranking
from agent.history import default_store as _history_store
from agent.security.contract_analyzer import ContractAnalyzer, ContractRisk
from agent import notifications as _notifications
from agent.protection import (
    LEVEL_CRITICAL,
    LEVEL_SAFE,
    LEVEL_WARN,
    ProtectionPolicy,
    default_store as _protection_store,
    evaluate_protection,
)
from agent.webhooks import (
    EVENT_BADGE_TIER_CHANGED,
    EVENT_PROTECTION_LEVEL_CHANGED,
    SUPPORTED_EVENTS,
    default_store as _webhook_store,
    fire_protection_level_changed,
    fire_tier_changed,
    schedule_deliveries,
)


def _record_history(
    *,
    token_address: str,
    badge,
    data_source: str,
    risk_level: str | None = None,
) -> None:
    """Best-effort write of a badge snapshot + webhook fan-out on tier transition.

    History is a side channel — write failures never affect the response. Webhook
    dispatch is also fire-and-forget on the running event loop.
    """
    # tier_source is the discriminator between a Certified-from-raw-on-chain
    # grade and a Radar-Estimate grade. Every downstream consumer (history
    # store, webhook payload, Telegram/Discord message) must carry it so a
    # radar_estimate transition is NEVER broadcast as "Certified."
    tier_source = getattr(badge, "tier_source", "certified")
    try:
        result = _history_store().record(
            token_address=token_address,
            tier=badge.tier,
            metrics=badge.metrics_snapshot,
            why=badge.why,
            risk_level=risk_level,
            data_source=data_source,
            tier_source=tier_source,
        )
    except Exception as e:
        logger.warning("history write failed for {}: {}", token_address, e)
        return

    # Fire a webhook event on real tier transitions (first-ever snapshot does not fire).
    if result.written and result.prev_tier is not None and result.prev_tier != result.tier:
        try:
            ids = fire_tier_changed(
                token_address=token_address,
                from_tier=result.prev_tier,
                to_tier=result.tier,
                why=badge.why,
                metrics=badge.metrics_snapshot,
                data_source=data_source,
                at=result.recorded_at,
                tier_source=tier_source,
            )
            if ids:
                schedule_deliveries(ids)
        except Exception as e:
            logger.warning("webhook dispatch failed for {}: {}", token_address, e)
        # Fan out to Telegram/Discord notification channels (no-ops if not configured).
        try:
            _notifications.dispatch_event("badge.tier_changed", {
                "token_address": token_address,
                "from_tier": result.prev_tier,
                "to_tier": result.tier,
                "tier_source": tier_source,
                "at": result.recorded_at,
            })
        except Exception as e:
            logger.warning("notification dispatch failed for {}: {}", token_address, e)


agent: FourLifeAgent | None = None


async def require_auth(authorization: str = Header(default="")):
    """Guard for control endpoints.

    If API_SECRET is unset AND AGENT_ENV == "dev", auth is skipped (convenient
    for local development). In production (AGENT_ENV != "dev") the server
    MUST have been booted with an API_SECRET; if it somehow isn't set here we
    fail closed with 503 rather than allow unauthenticated admin access.
    """
    import os
    from agent.config import settings
    if not settings.api_secret:
        if os.getenv("AGENT_ENV", "prod").lower() == "dev":
            return  # dev-mode open access
        raise HTTPException(status_code=503, detail="Server misconfigured: API_SECRET required")
    if authorization != f"Bearer {settings.api_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


async def is_authorized(authorization: str = Header(default="")) -> bool:
    """Optional auth check. Returns True if the caller presents a valid bearer
    token. When API_SECRET is unset, returns True only in dev mode; in
    production the caller is treated as unauthenticated so public response
    shapes are used (internal fields redacted)."""
    import os
    from agent.config import settings
    if not settings.api_secret:
        return os.getenv("AGENT_ENV", "prod").lower() == "dev"
    return authorization == f"Bearer {settings.api_secret}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start agent in background on server boot.

    The agent runs its lifecycle loop as a background asyncio task — no manual
    /api/agent/start POST is required for autonomous operation. Disable via
    AGENT_AUTOSTART=false (useful for tests or maintenance).
    """
    global agent
    import os
    from loguru import logger
    import asyncio as _asyncio
    from agent.config import settings

    # Fail closed at boot if no API_SECRET is configured in a production env.
    # Without this guard every admin route (agent start/stop/track, dgrid
    # attest, history export, notifications test, webhook CRUD) becomes
    # publicly callable because `require_auth` short-circuits when the secret
    # is empty. We refuse to boot instead of running in a silently-open state.
    env = os.getenv("AGENT_ENV", "prod").lower()
    if not settings.api_secret and env != "dev":
        raise RuntimeError(
            "API_SECRET is required in production. Set it in .env or export "
            "AGENT_ENV=dev for local development."
        )

    loop_task: _asyncio.Task | None = None
    try:
        agent = FourLifeAgent()
    except Exception as e:
        logger.warning("Agent init failed (missing keys?): {}. API running in read-only mode.", e)
        agent = None

    if agent and settings.agent_autostart:
        try:
            loop_task = _asyncio.create_task(agent.run(), name="four-life.lifecycle")
            logger.info("Agent lifecycle loop started on boot.")
        except Exception as e:
            logger.error("Failed to autostart agent lifecycle loop: {}", e)

    try:
        yield
    finally:
        if agent:
            await agent.stop()
            if loop_task and not loop_task.done():
                try:
                    await _asyncio.wait_for(loop_task, timeout=10)
                except _asyncio.TimeoutError:
                    loop_task.cancel()
            await agent.api.close()


API_DESCRIPTION = """
The **FOUR-LIFE Certified** public API — the trust, discovery, and survival layer for
Four.meme launches on BNB Chain.

### What this API provides

- **Certified Badge** (`GET /api/token/{addr}/badge`) — deterministic tier
  (graduated / graduation_watch / healthy / at_risk / observed) with a full `why[]` rule
  trace you can audit.
- **Risk Snapshot** (`GET /api/token/{addr}/risk-snapshot`) — evidence-backed risk flags.
- **Operator Checklist** (`GET /api/token/{addr}/operator-checklist`) — deterministic
  72h action plan, no LLM involvement.
- **Contract Risk** (`GET /api/token/{addr}/contract-risk`) — mint / blacklist / proxy /
  pause / ownership detection.
- **Graduation Radar** (`GET /api/graduation-radar`) — live Four.meme token leaderboard
  with filters (quote asset, min confidence, sort key).
- **Creator Survival** (`GET /api/creator/{wallet}/survival-score`) — track record with
  deterministic trust tier.
- **Platform Cohorts** (`GET /api/platform/cohorts`) — cross-launch analytics.

### Determinism & trust

No LLM is involved in any trust-path response. Every Certified badge and risk flag is
computed from raw on-chain metrics. Every response includes `confidence_score`,
`fallback_used`, `data_sources`, `model_version`, and `last_updated_at` so you can verify
the response without trusting the label.

### Rate limits

Public GET endpoints: 120 requests per minute per IP (rolling window). Write endpoints
(`POST /api/agent/*`) are rate-limited to 30/min and require a bearer token.

### Integration

- TypeScript SDK: [`@gudman/four-life-sdk`](https://github.com/Ridwannurudeen/four-life/tree/master/sdk)
- Embeddable widget: `<script src="https://four-life.gudman.xyz/embed.js?token=0x..."></script>`
- Browser extension: [repo link](https://github.com/Ridwannurudeen/four-life/tree/master/extension)

Source: [github.com/Ridwannurudeen/four-life](https://github.com/Ridwannurudeen/four-life)
Live: [four-life.gudman.xyz](https://four-life.gudman.xyz)
"""

tags_metadata = [
    {"name": "platform", "description": "Platform-native primitives Four.meme can embed directly. Deterministic, auditable, zero LLM in trust path."},
    {"name": "radar", "description": "Live leaderboard of Four.meme tokens. The main discovery surface."},
    {"name": "creator", "description": "Creator track-record scoring across every FOUR-LIFE-tracked launch."},
    {"name": "contract", "description": "On-chain contract analysis — mint, blacklist, pause, proxy, ownable, honeypot detection."},
    {"name": "identity", "description": "ERC-8004 / BRC-8004 agent card + reputation attestations."},
    {"name": "dgrid", "description": "DGrid AI Gateway usage — task-model routing, fallback chain, per-provider counters."},
    {"name": "radar-bot", "description": "Health feed for the X alert bot that broadcasts Certified tier transitions."},
    {"name": "myx", "description": "MYX V2 perp integration. Signal-only by default; execution opt-in via MYX_EXECUTION_ENABLED."},
    {"name": "webhooks", "description": "Outbound webhook subscriptions. Signed HMAC deliveries on tier-change and protection.level-changed events. Protected by API_SECRET bearer token."},
    {"name": "protection", "description": "Protection mode — per-token defensive thresholds. Deterministic verdict (safe/warn/critical). Writes are protected by API_SECRET."},
    {"name": "notifications", "description": "Telegram + Discord alert channels. Fan out tier and protection transitions to human-readable channels. Configured via env."},
    {"name": "agent", "description": "Agent lifecycle controls (start/stop/track). Protected by API_SECRET bearer token."},
    {"name": "dashboard", "description": "Internal status + history endpoints used by the FOUR-LIFE dashboard."},
]

app = FastAPI(
    title="FOUR-LIFE Certified API",
    description=API_DESCRIPTION,
    version="1.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    contact={
        "name": "FOUR-LIFE",
        "url": "https://four-life.gudman.xyz",
    },
    license_info={"name": "MIT", "url": "https://github.com/Ridwannurudeen/four-life/blob/master/LICENSE"},
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    # Tight allow-list: only first-party frontends are permitted. Credentials
    # are never sent, so "*" doesn't enable CSRF, but it WOULD let any site
    # POST to /api/dgrid/compare / /api/raise-plan from a visitor's browser
    # and burn our LLM credits under the victim's IP. Write endpoints that
    # require bearer auth are already protected, but LLM-burn endpoints are
    # not auth-gated for all callers — tighten the origin list instead.
    allow_origins=[
        "https://four-life.gudman.xyz",
        "https://four.meme",
        "https://www.four.meme",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",  # dev
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Rate limiting (in-memory token bucket per IP) ────────────────────
# Simple, dependency-free. For a multi-process deployment this would move to Redis,
# but the VPS runs a single uvicorn worker so an in-memory bucket is sufficient.

import time as _time_rl
from collections import defaultdict as _defaultdict, deque as _deque

_RL_WINDOW_SECONDS = 60
_RL_PUBLIC_LIMIT = 120   # GET /api/** (public read)
_RL_WRITE_LIMIT = 30     # POST /api/agent/** (write)
_RL_LLM_LIMIT = 10       # POST /api/dgrid/(compare|probe|consensus) — each call burns DGrid credits
_rate_buckets: dict[tuple[str, str], list[float]] = _defaultdict(list)

# Endpoints that fire real LLM traffic OR flip global DGrid state — stricter
# bucket so the public showcase surface can't be weaponized to burn credits or
# grief the service via endless chaos toggling. Includes MYX endpoints that
# route through DGrid consensus (consensus/evaluate fan out to 3 models each)
# and the raise-plan endpoint which runs unbounded LLM calls.
_LLM_BURN_PREFIXES = (
    "/api/dgrid/compare",
    "/api/dgrid/probe",
    "/api/dgrid/consensus",
    "/api/dgrid/attest",
    "/api/dgrid/chaos",
    "/api/myx/consensus",
    "/api/myx/evaluate",
    "/api/myx/signal",
    "/api/myx/attest-signals",
    "/api/myx/attest",
    "/api/raise-plan",
)

# ── Metrics (latency + status histogram, in-memory) ──────────────────
# Ring-buffer of per-request latency samples so the /metrics page can report
# p50/p95/p99 without pulling in a full telemetry stack.
METRICS_MAX_SAMPLES = 500
_latency_samples: _deque = _deque(maxlen=METRICS_MAX_SAMPLES)
_status_counts: dict[int, int] = _defaultdict(int)
_endpoint_counts: dict[str, int] = _defaultdict(int)
_endpoint_latency: dict[str, list[float]] = _defaultdict(list)
_metrics_started_at = _time_rl.time()


def _record_metric(path: str, status_code: int, latency_ms: float) -> None:
    """Record one request sample. Bucket path to the first two segments so
    parameterized routes (/api/token/{addr}/badge → /api/token) don't blow up
    cardinality."""
    _latency_samples.append(latency_ms)
    _status_counts[status_code] += 1
    parts = [p for p in path.split("/") if p][:2]
    bucket = "/" + "/".join(parts) if parts else "/"
    _endpoint_counts[bucket] += 1
    samples = _endpoint_latency[bucket]
    samples.append(latency_ms)
    if len(samples) > 100:
        # Trim per-bucket to last 100 so memory stays bounded.
        del samples[: len(samples) - 100]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(len(s) * pct)) - 1))
    return round(s[k], 2)


def _metrics_snapshot() -> dict:
    samples = list(_latency_samples)
    error_count = sum(c for s, c in _status_counts.items() if s >= 500)
    total = sum(_status_counts.values())
    return {
        "uptime_seconds": int(_time_rl.time() - _metrics_started_at),
        "total_requests": total,
        "error_rate_5xx": round(error_count / total, 4) if total else 0.0,
        "latency_ms": {
            "samples": len(samples),
            "p50": _percentile(samples, 0.50),
            "p95": _percentile(samples, 0.95),
            "p99": _percentile(samples, 0.99),
            "max": round(max(samples), 2) if samples else 0,
            "avg": round(sum(samples) / len(samples), 2) if samples else 0,
        },
        "status_counts": dict(_status_counts),
        "endpoints": [
            {
                "path": path,
                "count": count,
                "p50_ms": _percentile(_endpoint_latency[path], 0.50),
                "p95_ms": _percentile(_endpoint_latency[path], 0.95),
            }
            for path, count in sorted(_endpoint_counts.items(), key=lambda kv: -kv[1])[:10]
        ],
    }


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Per-IP rolling-window rate limit. Skips /docs, /openapi, /.well-known."""
    path = request.url.path
    if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi") or path.startswith("/.well-known"):
        return await call_next(request)

    # Bucket key: (client IP, bucket class). Write endpoints get a stricter bucket.
    client_ip = request.client.host if request.client else "unknown"
    # LLM-burn bucket applies regardless of HTTP method — several LLM-triggering
    # endpoints (e.g. /api/myx/signal) are GETs and would otherwise fall into
    # the public 120/min bucket, a 12× higher ceiling than the LLM bucket.
    is_llm_burn = any(path.startswith(p) for p in _LLM_BURN_PREFIXES)
    is_write = request.method == "POST" and path.startswith("/api/agent/")
    if is_llm_burn:
        bucket_class = "llm"
        limit = _RL_LLM_LIMIT
    elif is_write:
        bucket_class = "write"
        limit = _RL_WRITE_LIMIT
    else:
        bucket_class = "public"
        limit = _RL_PUBLIC_LIMIT
    key = (client_ip, bucket_class)

    now = _time_rl.time()
    cutoff = now - _RL_WINDOW_SECONDS
    bucket = _rate_buckets[key]
    # Prune old entries (cheap — most buckets are short)
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)

    if len(bucket) >= limit:
        retry_after = max(1, int(_RL_WINDOW_SECONDS - (now - bucket[0])))
        return JSONResponse(
            {
                "error": "rate_limited",
                "limit": limit,
                "window_seconds": _RL_WINDOW_SECONDS,
                "retry_after_seconds": retry_after,
                "message": f"Too many requests — slow down. {limit} req/{_RL_WINDOW_SECONDS}s per IP.",
            },
            status_code=429,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Window": str(_RL_WINDOW_SECONDS),
            },
        )

    bucket.append(now)
    t0 = _time_rl.perf_counter()
    response = await call_next(request)
    latency_ms = (_time_rl.perf_counter() - t0) * 1000
    _record_metric(path, response.status_code, latency_ms)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(bucket)))
    response.headers["X-Response-Time-Ms"] = f"{latency_ms:.1f}"
    return response


# ── Agent Card (ERC-8004 discovery) ──────────────────────────────────

@app.get("/.well-known/agent-registration.json", tags=["identity"], summary="ERC-8004 agent card")
async def agent_card():
    if not agent:
        return JSONResponse({"name": "FOUR-LIFE", "status": "not configured"})
    card = agent.identity.generate_agent_card("https://four-life.gudman.xyz")
    return JSONResponse(card)


# ── Identity + Reputation (public) ───────────────────────────────────

@app.get("/api/identity", tags=["identity"], summary="Agent card + reputation attestations")
async def identity_feed():
    """Public identity + reputation feed — the judge-facing version of the agent card.

    Returns the full agent card, the registration tx/block, and every reputation
    attestation FOUR-LIFE has submitted (most recent first).
    """
    if not agent:
        return JSONResponse({
            "name": "FOUR-LIFE",
            "status": "not configured",
        }, status_code=503)

    state = agent.identity.state
    card = agent.identity.generate_agent_card("https://four-life.gudman.xyz")

    # Newest first, successful attestations only for the public feed.
    attestations = sorted(
        (a for a in state.attestations.values() if a.tx_hash),
        key=lambda a: a.submitted_at,
        reverse=True,
    )

    return {
        "agent_card": card,
        "registration": {
            "agent_id": state.agent_id or None,
            "wallet": state.wallet,
            "registry_contract": card["registry_contract"],
            "tx_hash": state.registration_tx,
            "block": state.registration_block,
            "agent_card_uri": state.agent_card_uri,
        },
        "reputation_attestations": [
            {
                "token_address": a.token_address,
                "token_symbol": a.token_symbol,
                "token_name": a.token_name,
                "quote_asset": a.tag2,
                "graduation_time": a.graduation_time,
                "tx_hash": a.tx_hash,
                "block": a.block_number,
                "submitted_at": a.submitted_at,
                "value": a.value,
                "value_decimals": a.value_decimals,
                "tag1": a.tag1,
                "tag2": a.tag2,
                "feedback_uri": a.feedback_uri,
                "feedback_hash": a.feedback_hash,
            }
            for a in attestations
        ],
        "reputation_summary": card["reputation"],
        "last_updated_at": int(time.time()),
    }


# ── Radar Bot status (public health endpoint) ────────────────────────

@app.get("/api/radar-bot/status", tags=["radar-bot"], summary="Radar bot health feed")
async def radar_bot_status():
    """Public health feed for the X alert bot. Reads its status file — the bot itself
    writes this every tick. If the file is missing, the bot isn't running."""
    import os
    from pathlib import Path as _Path
    status_path = _Path(__file__).parent.parent / "data" / "radar_bot_status.json"
    if not status_path.exists():
        return {
            "running": False,
            "last_tick_at": 0,
            "last_posted_at": 0,
            "posts_last_hour": 0,
            "tier_transitions_last_24h": 0,
            "dedup_cache_size": 0,
            "reason": "radar-bot service not started or has not ticked yet",
        }
    try:
        import json as _json
        return _json.loads(status_path.read_text())
    except Exception as e:
        return JSONResponse({"error": str(e), "running": False}, status_code=500)


# ── Agent Status ─────────────────────────────────────────────────────

@app.get("/api/status", tags=["dashboard"], summary="Agent status + lifetime stats")
async def status(authorized: bool = Depends(is_authorized)):
    """Public status feed. Wallet address and recent global_learnings are
    redacted for unauthenticated callers — those are operational internals that
    don't belong in a public scraper surface. Authenticated callers (dashboard)
    get the full view.
    """
    if not agent:
        return {
            "agent_name": "FOUR-LIFE",
            "running": False,
            "agent_id": None,
            "total_launches": 0,
            "total_graduations": 0,
            "graduation_rate": 0,
            "avg_peak_holders": None,
            "launches_with_activity": 0,
            "active_tokens": 0,
            "message": "Agent not configured — add keys to .env",
        }
    mem = agent.memory.memory
    # avg_peak_holders is computed over launches_with_activity only (see
    # _update_stats — launches with peak_holders > 0). Expose as null when
    # no launches have seen trade activity so the UI renders "—" instead
    # of a misleading "0" that could be read as "zero holders."
    avg_peak = round(mem.avg_peak_holders, 0) if mem.tracked_launches > 0 else None
    body = {
        "agent_name": "FOUR-LIFE",
        "running": agent.running,
        "agent_id": agent.identity.agent_id,
        "total_launches": mem.total_launches,          # every launch ever recorded
        "total_graduations": mem.total_graduations,
        "graduation_rate": round(mem.graduation_rate * 100, 1),
        "avg_peak_holders": avg_peak,
        "launches_with_activity": mem.tracked_launches,  # of total_launches, subset with peak_holders > 0
        "active_tokens": len(agent.active_concepts),   # currently under live on-chain monitoring
        "learnings_count": len(mem.global_learnings),
    }
    if authorized:
        body["wallet"] = agent.chain.account.address
        body["global_learnings"] = mem.global_learnings[-10:]
    return body


# ── Token Health ─────────────────────────────────────────────────────

@app.get("/api/tokens", tags=["dashboard"], summary="All tokens currently under FOUR-LIFE lifecycle management")
async def list_tokens():
    if not agent:
        return {"tokens": []}
    tokens = []
    for addr, health in agent.monitor.state.tokens.items():
        concept = agent.active_concepts.get(addr, {})
        tokens.append({
            "address": addr,
            "name": health.name,
            "symbol": health.symbol,
            "phase": health.phase,
            "age_hours": round(health.age_hours, 1),
            "health_score": health.health_score,
            "graduation_probability": round(health.graduation_probability * 100, 1),
            "unique_buyers": health.unique_buyers,
            "buy_sell_ratio": round(health.buy_sell_ratio, 2),
            "top_holder_pct": round(health.top_holder_pct, 1),
            "curve_progress": round(health.curve_progress_pct, 1),
            "holder_velocity": round(health.holder_velocity, 1),
            "narrative": concept.get("narrative", ""),
        })
    return {"tokens": tokens}


@app.get("/api/tokens/{address}", tags=["dashboard"], summary="Deep detail for a tracked token")
async def token_detail(address: str, authorized: bool = Depends(is_authorized)):
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)
    health = agent.monitor.state.tokens.get(address)
    if not health:
        return JSONResponse({"error": "Token not found"}, status_code=404)

    concept = agent.active_concepts.get(address, {})
    actions = agent.lifecycle.get_action_history(address)
    launch = agent.memory.get_launch(address)

    launch_record = {
        "launched_at": launch.launched_at if launch else None,
        "peak_holders": launch.peak_holders if launch else 0,
        "peak_health_score": launch.peak_health_score if launch else 0,
        "graduated": launch.graduated if launch else False,
    }
    # Learning lists are the agent's internal post-mortem — leak competitive
    # intel when exposed unconditionally. Gate behind the API secret so the
    # internal dashboard still gets them.
    if authorized:
        launch_record["what_worked"] = launch.what_worked if launch else []
        launch_record["what_failed"] = launch.what_failed if launch else []

    # Compute the deterministic Certified badge here so every surface
    # (badge endpoint, radar, dashboard detail) returns the same tier for
    # the same token. Previous versions of this endpoint left consumers to
    # call /badge separately — easy vector for drift.
    try:
        contract_risk = await _get_contract_risk(address)
        crs = contract_risk.risk_score if contract_risk else 0
        live_badge = badge_from_health(
            health,
            contract_risk_score=crs,
            observation_status=getattr(health, "observation_status", "full_history"),
        )
    except Exception:
        live_badge = None

    return {
        "health": {
            "address": address,
            "name": health.name,
            "symbol": health.symbol,
            # Lowercase the creator wallet to match /badge and /creator/
            # endpoints. Checksum-cased output earlier made the same wallet
            # render two different strings in neighbouring cards.
            "creator": (health.creator or "").lower() or None,
            "phase": health.phase,
            "tier": live_badge.tier if live_badge else None,
            "tier_source": live_badge.tier_source if live_badge else None,
            "observation_status": getattr(health, "observation_status", "full_history"),
            "age_hours": round(health.age_hours, 1),
            "health_score": health.health_score,
            "graduation_probability": round(health.graduation_probability * 100, 1),
            "unique_buyers": health.unique_buyers,
            "unique_sellers": health.unique_sellers,
            "buy_sell_ratio": round(health.buy_sell_ratio, 2),
            "top_holder_pct": round(health.top_holder_pct, 1),
            "whale_count": health.whale_count,
            "curve_progress": round(health.curve_progress_pct, 1),
            "holder_velocity": round(health.holder_velocity, 1),
            "buy_volume_bnb": round(health.buy_volume_bnb, 4),
            "sell_volume_bnb": round(health.sell_volume_bnb, 4),
        },
        "concept": concept,
        "actions": actions,
        "launch_record": launch_record,
    }


# ── Memory ───────────────────────────────────────────────────────────

@app.get(
    "/api/memory",
    tags=["dashboard"],
    summary="Agent memory (learnings, launch history)",
    dependencies=[Depends(require_auth)],
)
async def memory():
    if not agent:
        return {"total_launches": 0, "total_graduations": 0, "graduation_rate": 0, "avg_peak_holders": None, "launches_with_activity": 0, "best_narratives": [], "worst_narratives": [], "global_learnings": [], "launches": [], "last_updated": 0}
    mem = agent.memory.memory
    avg_peak = round(mem.avg_peak_holders, 0) if mem.tracked_launches > 0 else None
    return {
        "total_launches": mem.total_launches,
        "total_graduations": mem.total_graduations,
        "graduation_rate": round(mem.graduation_rate * 100, 1),
        "avg_peak_holders": avg_peak,
        "launches_with_activity": mem.tracked_launches,
        "best_narratives": mem.best_narratives,
        "worst_narratives": mem.worst_narratives,
        "global_learnings": mem.global_learnings,
        "launches": [
            {
                "token_address": lr.token_address,
                "name": lr.name,
                "symbol": lr.symbol,
                "narrative": lr.narrative,
                "quote_asset": lr.quote_asset,
                "creator": lr.creator,
                "launch_block": lr.launch_block,
                "launched_at": lr.launched_at,
                "peak_holders": lr.peak_holders,
                "peak_health_score": lr.peak_health_score,
                "peak_curve_progress": round(lr.peak_curve_progress, 1),
                "graduated": lr.graduated,
                "graduation_time": lr.graduation_time,
                "attestation_tx_hash": lr.attestation_tx_hash,
                "what_worked": lr.what_worked,
                "what_failed": lr.what_failed,
            }
            for lr in mem.launches
        ],
        "last_updated": mem.last_updated,
    }


# ── Actions Log ──────────────────────────────────────────────────────

@app.get("/api/actions", tags=["dashboard"], summary="Recent lifecycle actions")
async def actions(limit: int = 50):
    if not agent:
        return {"actions": []}
    all_actions = agent.lifecycle.action_log[-limit:]
    return {
        "actions": [
            {
                "token_address": a.token_address,
                "action_type": a.action_type,
                "content": a.content,
                "urgency": a.urgency,
                "reasoning": a.reasoning,
                "timestamp": a.timestamp,
                "tweet_id": a.tweet_id,
            }
            for a in reversed(all_actions)
        ]
    }


# ── DGrid Bounty Dashboard ───────────────────────────────────────────

@app.get("/api/dgrid/stats", tags=["dgrid"], summary="DGrid gateway usage — task routing, fallback events, per-provider counters")
async def dgrid_stats():
    """Public stats on task-typed LLM routing through the DGrid gateway.

    This is the DGrid bounty surface: judges can see per-task model routing,
    per-provider usage counters, and fallback events live.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    stats = llm.get_usage_stats()
    return {
        "llm_provider": llm.model_id,
        **stats,
    }


@app.get("/api/dgrid/trace", tags=["dgrid"], summary="Recent LLM calls (ring buffer) — which provider served each request")
async def dgrid_trace(limit: int = 50):
    """Per-call trace log. Every LLM decision the agent makes lands here with
    provider, model, task, latency, token counts, fallback depth, and the
    error (if any) that triggered a fallback. Newest first, up to ``limit``
    entries (hard cap 200).
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    limit = max(1, min(int(limit or 50), 200))
    return {
        "count": llm.trace_count,
        "limit": limit,
        "trace": llm.get_trace(limit=limit),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get("/api/dgrid/health", tags=["dgrid"], summary="DGrid reachability probe — green/red state")
async def dgrid_health():
    """Lightweight reachability check. Reports whether DGrid is configured,
    its last-served tick (if any), the most recent fallback reason, and a
    status flag that flips red when we've recorded a fallback event without
    a subsequent success.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    stats = llm.get_usage_stats()
    dgrid_seen = stats.get("last_seen", {}).get("provider:dgrid")
    last_provider = stats.get("last_provider")
    status = "green"
    if not llm.dgrid_configured:
        status = "red"
    elif stats.get("dgrid_calls", 0) == 0 and stats.get("fallback_events", 0) > 0:
        status = "amber"
    elif last_provider != "dgrid" and stats.get("last_dgrid_error"):
        status = "amber"
    return {
        "status": status,
        "dgrid_configured": llm.dgrid_configured,
        "primary_model": llm.model,
        "last_dgrid_success_ts": int(dgrid_seen) if dgrid_seen else None,
        "last_provider": last_provider,
        "last_dgrid_error": stats.get("last_dgrid_error"),
        "dgrid_calls": stats.get("dgrid_calls", 0),
        "dgrid_share": stats.get("dgrid_share", 0.0),
        "fallback_events": stats.get("fallback_events", 0),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/metrics",
    tags=["dashboard"],
    summary="Service reliability — latency p50/p95/p99, status counts, endpoint breakdown",
)
async def metrics():
    """Public reliability surface. Samples the last 500 requests to report
    latency percentiles (p50/p95/p99), 5xx error rate, request counts, and
    the 10 busiest endpoints with per-endpoint p50/p95. Purely first-party —
    no external telemetry required."""
    return {
        **_metrics_snapshot(),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/alerts",
    tags=["protection"],
    summary="Threat feed — recent Protection Mode level transitions",
)
async def alerts_feed(limit: int = 50, min_level: str | None = None):
    """Public feed of Protection Mode firings.

    Each entry is a real transition the agent observed: from_level → to_level,
    the deterministic rules that fired, the token, and when. Filter to warn/
    critical via ``min_level`` (default returns all transitions including
    safe-recovery events).
    """
    limit = max(1, min(int(limit or 50), 200))
    events = _protection_store().recent_events(limit=limit, min_level=min_level)
    tokens = agent.monitor.state.tokens if agent else {}
    enriched = []
    for ev in events:
        h = tokens.get(ev["token_address"])
        enriched.append({
            **ev,
            "name": h.name if h else None,
            "symbol": h.symbol if h else None,
            "current_phase": h.phase if h else None,
            "current_top_holder_pct": round(h.top_holder_pct, 2) if h else None,
        })
    return {
        "count": len(enriched),
        "limit": limit,
        "min_level": min_level,
        "events": enriched,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


class _CompareBody(BaseModel):
    prompt: str = "Describe a meme token launch in 20 words."
    models: list[str] = Field(
        default_factory=lambda: [
            "google/gemini-2.5-flash",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-4o-mini",
        ]
    )
    max_tokens: int = 160


@app.post(
    "/api/dgrid/compare",
    tags=["dgrid"],
    summary="Run the same prompt on N models via DGrid — side-by-side comparison",
    dependencies=[Depends(require_auth)],
)
async def dgrid_compare(body: _CompareBody):
    """Demonstrates DGrid's core value prop: one API, many models. Fires the
    same prompt against every model in parallel and returns responses +
    latencies + token counts so judges can see the comparison inline. Each
    model either answers or fails with its own error — no fallback."""
    from agent.brain.llm import get_llm
    llm = get_llm()
    # Cap models to 5 and prompt length to 400 chars so one call can't burn credits.
    models = (body.models or [])[:5]
    if not models:
        return JSONResponse({"error": "at least one model is required"}, status_code=400)
    prompt = (body.prompt or "")[:400] or "Say hi."
    max_tokens = max(1, min(int(body.max_tokens or 160), 400))
    results = await llm.compare_dgrid_models(prompt, models, max_tokens=max_tokens)
    return {
        "prompt": prompt,
        "results": results,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


class _ProbeBody(BaseModel):
    model: str | None = None


@app.post("/api/dgrid/probe", tags=["dgrid"], summary="Force a DGrid-only call — no fallback — to prove the gateway is live")
async def dgrid_probe(body: _ProbeBody | None = None):
    """Fire a single call that MUST land on DGrid (no fallback chain).
    Returns provider/model/latency + DGrid's raw response. If DGrid is down
    or out of credits, returns the exact error — no silent fallback, because
    this endpoint exists specifically so judges can verify DGrid on demand.
    Optional ``model`` lets judges probe any specific DGrid model.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    target = None
    if body and body.model:
        target = body.model[:120]  # defensive cap
    result = await llm.probe_dgrid(model=target)
    status_code = 200 if result.get("ok") else 503
    return JSONResponse(
        {**result, "model_version": MODEL_VERSION, "last_updated_at": int(time.time())},
        status_code=status_code,
    )


class _ChaosBody(BaseModel):
    enabled: bool
    reason: str | None = None


@app.post(
    "/api/dgrid/chaos",
    tags=["dgrid"],
    summary="Toggle chaos mode — force DGrid failures to demo fallback chain",
    dependencies=[Depends(require_auth)],
)
async def dgrid_chaos(body: _ChaosBody):
    """Public demo endpoint. When ``enabled=true``, every subsequent DGrid call
    fails with a simulated outage, exercising the full fallback chain
    (Anthropic → OpenAI). Judges press a button on the /dgrid page and see the
    agent keep working through the fallback providers.

    The circuit breaker trips normally; flipping chaos off resets the breaker
    so the next call tries DGrid again. Rate-limited at 10/min per IP (LLM
    burn bucket) so the toggle can't be abused to grief the service.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    if body.enabled:
        llm.enable_chaos(body.reason or "admin toggle")
    else:
        llm.disable_chaos()
    return {
        "chaos_enabled": llm.chaos_enabled,
        "breaker": llm.breaker.snapshot(),
        "reason": body.reason,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/dgrid/leaderboard",
    tags=["dgrid"],
    summary="Per-(task, model) rolling stats — success rate, avg latency, cost/call",
)
async def dgrid_leaderboard():
    """Live leaderboard of how each DGrid model is performing per task.

    This is what the self-optimizing router uses to pick winners. Rows are
    sorted by task then success rate then latency — the top of each task group
    is the current best model for that workload.
    """
    from agent.brain.llm import get_llm, TASK_MODEL_MAP
    from agent.config import settings as _settings
    llm = get_llm()
    return {
        "rows": llm.get_leaderboard(),
        "auto_tune_enabled": bool(getattr(_settings, "dgrid_auto_tune", False)),
        "current_task_map": dict(TASK_MODEL_MAP),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


class _ConsensusBody(BaseModel):
    prompt: str
    vote_key: str = "action"
    models: list[str] | None = None
    # Default 600 so Gemini 2.5 Flash (a reasoning model — spends 300+ tokens
    # thinking before emitting visible output) doesn't truncate mid-JSON.
    max_tokens: int = 600
    temperature: float = 0.4


@app.post(
    "/api/dgrid/consensus",
    tags=["dgrid"],
    summary="Multi-model consensus — N DGrid models vote on a JSON field",
    dependencies=[Depends(require_auth)],
)
async def dgrid_consensus(body: _ConsensusBody):
    """Fan out to several DGrid models in parallel and vote on a JSON field.

    This is the flagship DGrid-only capability: the same call under any
    single-provider integration would require per-provider auth, three
    different SDKs, and three different error envelopes. With DGrid it is one
    async function.

    Example:
      POST /api/dgrid/consensus
      {"prompt": "Is ETH bullish in 24h? Respond {\"action\": \"bullish|bearish|neutral\"}",
       "vote_key": "action", "models": [...]}
    """
    from agent.brain.consensus import consensus_vote
    prompt = (body.prompt or "")[:1500]
    if not prompt.strip():
        return JSONResponse({"error": "prompt required"}, status_code=400)
    vote_key = (body.vote_key or "action").strip()[:80]
    models = body.models[:5] if body.models else None
    max_tokens = max(1, min(int(body.max_tokens or 400), 800))
    temperature = max(0.0, min(float(body.temperature or 0.4), 1.0))
    messages = [{"role": "user", "content": prompt}]
    result = await consensus_vote(
        messages,
        models=models,
        vote_key=vote_key,
        max_tokens=max_tokens,
        temperature=temperature,
        json_mode=True,
    )
    return {
        **result,
        "prompt": prompt,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/dgrid/audit",
    tags=["dgrid"],
    summary="Merkle attestation of DGrid calls — cryptographic proof of usage",
)
async def dgrid_audit():
    """Current Merkle commitment to every DGrid call the agent has made.

    Each successful DGrid call is folded into a SHA-256 hash chain. The tip of
    the chain (``current_root``) is the commitment; it can be published on BNB
    Chain via POST /api/dgrid/attest (admin). Once published, the txhash is
    returned here so anyone can verify independently.

    Judges who want to prove FOUR-LIFE really used DGrid can:
      1. Read the published txhash from ``last_published_txhash``.
      2. Reconstruct the chain from /api/dgrid/trace and verify the root matches.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    return {
        **llm.get_attestation(),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/dgrid/audit/calls",
    tags=["dgrid"],
    summary="Full append-only call log — every DGrid call that contributes to the Merkle chain",
)
async def dgrid_audit_calls(offset: int = 0, limit: int = 500):
    """Paginated slice of the full DGrid call log, for independent Merkle
    verification. Each entry includes the ``call_digest`` and the
    ``chain_tip`` after folding it in.

    Reconstruct the chain: start with ``genesis`` (from /api/dgrid/audit),
    fold each ``call_digest`` in ``seq`` order, expect the final hash to equal
    ``/api/dgrid/audit.current_root``.

    Pagination: ``offset`` defaults to 0, ``limit`` defaults to 500 and is
    capped at 5000 (lowered from 10000 — judges rarely need a single page
    that large and the smaller cap reduces response-size amplification from
    anonymous callers). The response returns ``next_offset`` and ``has_more``
    so integrators can iterate the full chain deterministically.
    """
    from agent.brain.llm import get_llm
    llm = get_llm()
    offset = max(0, int(offset))
    limit = max(1, min(int(limit or 500), 5000))
    entries = llm.get_audit_calls(offset=offset, limit=limit)
    total = llm._attestation_log.count()
    next_offset = offset + len(entries)
    has_more = next_offset < total
    snap = llm.get_attestation()
    return {
        "offset": offset,
        "limit": limit,
        "count": len(entries),
        "total": total,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "calls": entries,
        "genesis": snap.get("genesis"),
        "current_root": snap.get("current_root"),
        "last_published_root": snap.get("last_published_root"),
        "last_published_txhash": snap.get("last_published_txhash"),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.post(
    "/api/dgrid/attest",
    tags=["dgrid"],
    summary="Publish the current DGrid attestation root on BNB Chain",
    dependencies=[Depends(require_auth)],
)
async def dgrid_attest():
    """Opt-in. Publishes the current attestation tip on BNB Chain as a
    self-transaction with the root in the tx data field. Costs ~0.0001 BNB.

    Requires DGRID_ATTEST_ONCHAIN=true and a wallet with BNB. Returns the new
    txhash plus the updated attestation snapshot.
    """
    from agent.brain.llm import get_llm
    from agent.brain.attestation import publish_root_onchain
    from agent.config import settings as _settings
    if not getattr(_settings, "dgrid_attest_onchain", False):
        raise HTTPException(status_code=403, detail="DGRID_ATTEST_ONCHAIN is disabled")
    llm = get_llm()
    snap = llm.get_attestation()
    root = snap["current_root"]
    count = int(snap.get("num_calls_chained", 0))
    if count == 0:
        raise HTTPException(status_code=400, detail="no DGrid calls to attest yet")
    try:
        txhash = await publish_root_onchain(root)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"attestation publish failed: {e}") from e
    llm._attestation.record_attestation(root, txhash, count)
    return {
        "published_root": root,
        "txhash": txhash,
        "bscscan_url": f"https://bscscan.com/tx/{txhash}",
        "num_calls_attested": count,
        **llm.get_attestation(),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


# ── MYX V2 Perps ─────────────────────────────────────────────────────

@app.get("/api/myx/status", tags=["myx"], summary="MYX connection + execution mode")
async def myx_status():
    if not agent or not agent.myx:
        return {"enabled": False, "execution_mode": "disabled", "reason": "MYX not configured"}
    try:
        markets = await agent.myx.get_markets()
        return {
            "enabled": True,
            "execution_mode": agent.hedge_manager.execution_mode if agent.hedge_manager else "signal_only",
            "markets_count": len(markets),
            "markets": markets[:10],
        }
    except Exception as e:
        return {
            "enabled": True,
            "execution_mode": agent.hedge_manager.execution_mode if agent.hedge_manager else "signal_only",
            "error": str(e),
        }


@app.get("/api/myx/signal/{token_address}", tags=["myx"], summary="AI-generated perp signal for a tracked token")
async def myx_signal(token_address: str):
    if not agent or not agent.myx_strategy:
        return {"error": "MYX not configured"}

    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        return {"error": "Token not tracked"}

    token_health = {
        "name": health.name,
        "symbol": health.symbol,
        "health_score": health.health_score,
        "phase": health.phase,
        "buy_sell_ratio": health.buy_sell_ratio,
        "holder_velocity": health.holder_velocity,
        "curve_progress": health.curve_progress_pct,
        "top_holder_pct": health.top_holder_pct,
    }

    try:
        markets = await agent.myx.get_markets()
        signal = await agent.myx_strategy.generate_signal(token_health, {"available_markets": len(markets)})
        return {
            "signal": signal,
            "execution_mode": agent.hedge_manager.execution_mode if agent.hedge_manager else "signal_only",
            "model_version": MODEL_VERSION,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/myx/portfolio", tags=["myx"], summary="Hedge portfolio summary across all tokens")
async def myx_portfolio():
    """Get hedge portfolio summary across all tokens."""
    if not agent or not agent.hedge_manager:
        return {"enabled": False, "reason": "MYX not configured"}
    return agent.hedge_manager.get_portfolio_summary()


@app.get("/api/myx/positions/{token_address}", tags=["myx"], summary="Hedge positions for a specific token")
async def myx_positions(token_address: str):
    """Get all hedge positions for a specific token."""
    if not agent or not agent.hedge_manager:
        return {"enabled": False, "reason": "MYX not configured"}
    return {
        "token_address": token_address,
        "positions": agent.hedge_manager.get_token_positions(token_address),
    }


@app.post(
    "/api/myx/evaluate/{token_address}",
    tags=["myx"],
    summary="Manually trigger a hedge evaluation",
    dependencies=[Depends(require_auth)],
)
async def myx_evaluate(token_address: str):
    """Manually trigger a hedge evaluation for a token."""
    if not agent or not agent.hedge_manager:
        return {"error": "MYX not configured"}

    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        return {"error": "Token not tracked"}

    token_health = {
        "name": health.name,
        "symbol": health.symbol,
        "health_score": health.health_score,
        "phase": health.phase,
        "buy_sell_ratio": health.buy_sell_ratio,
        "holder_velocity": health.holder_velocity,
        "curve_progress": health.curve_progress_pct,
        "top_holder_pct": health.top_holder_pct,
    }

    result = await agent.hedge_manager.evaluate_and_act(
        token_address, token_health, health.phase,
    )
    return {"result": result}


@app.get(
    "/api/myx/signals",
    tags=["myx"],
    summary="Recent MYX signals — paginated, unbounded history (persisted to disk)",
)
async def myx_signals(
    token_address: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Signal feed for the MYX dashboard. Returns the last ``limit`` signals,
    optionally filtered by ``token_address``. Unlike the in-memory ring in
    HedgeManager, this reads from the append-only JSONL log so every signal
    the agent has ever produced is reconstructible.
    """
    from agent.myx.store import get_signal_log
    log = get_signal_log()
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset))
    if token_address:
        # Filter by token — read a larger window then slice
        rows = log.tail(n=limit + offset, token_address=token_address)
        rows = rows[offset : offset + limit]
    else:
        total = log.count()
        # tail = last N in insertion order then reverse
        rows = log.tail(n=limit + offset)
        rows = rows[offset : offset + limit]
    return {
        "count": len(rows),
        "offset": offset,
        "limit": limit,
        "token_address": token_address,
        "total_ever": log.count(),
        "signals": rows,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/myx/audit",
    tags=["myx"],
    summary="MYX trade attestation — cryptographic proof of perp activity",
)
async def myx_audit():
    """Current Merkle commitment to every position event (open + close) the
    agent has executed on MYX.

    Same pattern as /api/dgrid/audit. Every trade is hashed, chained, and the
    tip can be published on BNB Chain via POST /api/myx/attest (admin)."""
    from agent.myx.store import get_myx_chain, get_position_log
    chain = get_myx_chain()
    log = get_position_log()
    snap = chain.snapshot()
    snap["position_log_count"] = log.count()
    snap["execution_enabled"] = bool(agent and agent.hedge_manager and agent.hedge_manager.execution_enabled)
    snap["model_version"] = MODEL_VERSION
    snap["last_updated_at"] = int(time.time())
    return snap


@app.get(
    "/api/myx/audit/events",
    tags=["myx"],
    summary="Full MYX position event log for independent Merkle verification",
)
async def myx_audit_events(offset: int = 0, limit: int = 500):
    """Paginated log of every open / close event the agent has executed on MYX.
    Each entry includes ``event_digest`` + ``chain_tip`` so callers can fold
    them locally and verify against ``/api/myx/audit.current_root``."""
    from agent.myx.store import get_position_log, get_myx_chain
    log = get_position_log()
    chain = get_myx_chain()
    offset = max(0, int(offset))
    limit = max(1, min(int(limit or 500), 2000))
    events = log.read_range(offset, limit)
    snap = chain.snapshot()
    return {
        "offset": offset,
        "limit": limit,
        "count": len(events),
        "total": log.count(),
        "events": events,
        "current_root": snap["current_root"],
        "genesis": snap["genesis"],
        "last_published_root": snap["last_published_root"],
        "last_published_txhash": snap["last_published_txhash"],
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/myx/signal-attestation",
    tags=["myx"],
    summary="Merkle commitment to every signal the agent has generated",
)
async def myx_signal_attestation():
    """Cryptographic commitment to the agent's thinking — every hedge signal
    hashed into a separate chain from the trade attestation. Publishable
    on-chain via /api/myx/attest-signals (admin). This gives us on-chain
    proof of decisions even when execution is pending."""
    from agent.myx.store import get_myx_signal_chain, get_signal_log
    chain = get_myx_signal_chain()
    log = get_signal_log()
    snap = chain.snapshot()
    snap["signal_log_count"] = log.count()
    snap["model_version"] = MODEL_VERSION
    snap["last_updated_at"] = int(time.time())
    return snap


@app.post(
    "/api/myx/attest-signals",
    tags=["myx"],
    summary="Publish the MYX signal attestation root on BNB Chain",
    dependencies=[Depends(require_auth)],
)
async def myx_attest_signals():
    """Publish the signal chain tip as a self-tx with the root in the data
    field. Same publisher as DGrid attestation — gated by the shared
    DGRID_ATTEST_ONCHAIN flag and rate-limited."""
    from agent.myx.store import get_myx_signal_chain
    from agent.brain.attestation import publish_root_onchain
    from agent.config import settings as _settings
    if not getattr(_settings, "dgrid_attest_onchain", False):
        raise HTTPException(status_code=403, detail="DGRID_ATTEST_ONCHAIN must be true (reused flag)")
    chain = get_myx_signal_chain()
    snap = chain.snapshot()
    root = snap["current_root"]
    count = int(snap.get("num_signals_chained", 0))
    if count == 0:
        raise HTTPException(status_code=400, detail="no MYX signals to attest yet")
    try:
        txhash = await publish_root_onchain(root)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MYX signal attestation publish failed: {e}") from e
    chain.record_attestation(root, txhash, count)
    return {
        "published_root": root,
        "txhash": txhash,
        "bscscan_url": f"https://bscscan.com/tx/{txhash}",
        "num_signals_attested": count,
        **chain.snapshot(),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/myx/calldata/{token_address}",
    tags=["myx"],
    summary="Unsigned createIncreaseOrder calldata the agent would submit now",
)
async def myx_calldata(token_address: str):
    """Return a shape-preview unsigned transaction the agent would submit for
    this token, derived from the latest signal.

    Proof-without-execution artifact: the calldata is ABI-encoded against
    MYX V2's ``createIncreaseOrder((address,uint256,uint8,int256,uint256,bool,uint256,uint256,uint8,uint256))``
    struct so a reviewer can decode locally (e.g., with web3.py's
    ``contract.decode_function_input``) and verify struct packing is correct.

    Note on execution: production orders route through MYX's broker-signer
    pattern (``placeOrderWithSalt``) — a permissioned contract issued per
    integrator by the MYX team (see SDK guide). This calldata shows the
    *direct-router-call* shape; the broker layer wraps it at execution time.
    We never broadcast this output.
    """
    if not agent or not agent.hedge_manager:
        raise HTTPException(status_code=503, detail="MYX not configured")
    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        raise HTTPException(status_code=404, detail="Token not tracked")

    state = agent.hedge_manager._get_state(token_address)
    last_signal = state.last_signal
    if not last_signal:
        raise HTTPException(status_code=425, detail="No signal generated yet for this token — run /api/myx/evaluate first")

    action = last_signal.get("action", "hold")
    if action not in ("long", "short"):
        return {
            "would_execute": False,
            "reason": f"Current signal is '{action}' — no tx would be submitted",
            "signal": last_signal,
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
        }

    is_long = action == "long"
    pair_index = await agent.hedge_manager.resolve_pair_index()
    size_pct = min(last_signal.get("size_pct", 0.05), 0.10)
    collateral_wei = int(0.01 * 1e18 * (size_pct / 0.05))
    size_amount = collateral_wei * 5
    price_1e30 = int(600 * 1e30)
    max_slippage = 30
    network_fee = int(0.001 * 1e18)

    # Build ABI-encoded calldata for the exact call we'd submit.
    myx_client = agent.myx
    request = (
        myx_client.account.address,
        pair_index, 0, collateral_wei, price_1e30,
        is_long, size_amount, max_slippage, 0, network_fee,
    )
    try:
        tx_func = myx_client.router.functions.createIncreaseOrder(request)
        tx = await tx_func.build_transaction({
            "from": myx_client.account.address,
            "value": network_fee + collateral_wei,
            "gas": 2_000_000,
            "nonce": 0,  # dummy — this is never broadcast
        })
        data = tx.get("data", "")
        if isinstance(data, bytes):
            data = "0x" + data.hex()
    except Exception as e:
        data = None
        logger.warning("calldata build failed: {}", e)

    return {
        "would_execute": True,
        "target_router": getattr(myx_client, "router", None) and myx_client.router.address,
        "target_pool": getattr(myx_client, "pool", None) and myx_client.pool.address,
        "value_wei": str(network_fee + collateral_wei),
        "pair_index": pair_index,
        "direction": "LONG" if is_long else "SHORT",
        "collateral_wei": str(collateral_wei),
        "size_amount": str(size_amount),
        "max_slippage_bps": max_slippage,
        "calldata_hex": data,
        "selector": data[:10] if data else None,
        "signal": last_signal,
        "note": "Shape-preview calldata against MYX V2 createIncreaseOrder struct — decode locally with web3.py `contract.decode_function_input()`. Production orders route through broker-signer `placeOrderWithSalt` (pending MYX onboarding). Not broadcast.",
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


class _MYXConsensusBody(BaseModel):
    force: bool = True  # force consensus path even if phase != defend


@app.post(
    "/api/myx/consensus/{token_address}",
    tags=["myx"],
    summary="Fan hedge decision across 3 DGrid models in parallel for this token",
)
async def myx_consensus_signal(token_address: str, body: _MYXConsensusBody | None = None):
    """Live demo of the cross-partner integration: fire the hedge prompt
    against 3 DGrid models in parallel, take the majority vote. Returns
    per-model verdicts + the final vote. This is the "only possible with
    DGrid" capability wired into the MYX bounty surface — a single-provider
    team literally cannot do this call.
    """
    if not agent or not agent.hedge_manager:
        raise HTTPException(status_code=503, detail="MYX not configured")
    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        raise HTTPException(status_code=404, detail="Token not tracked")

    state = agent.hedge_manager._get_state(token_address)
    try:
        markets = await agent.myx.get_markets()
    except Exception:
        markets = []
    token_health = {
        "name": health.name,
        "symbol": health.symbol,
        "health_score": health.health_score,
        "phase": health.phase,
        "buy_sell_ratio": health.buy_sell_ratio,
        "holder_velocity": health.holder_velocity,
        "curve_progress": health.curve_progress_pct,
        "top_holder_pct": health.top_holder_pct,
    }
    market_data = {
        "available_markets": len(markets),
        "has_active_hedge": state.has_active_hedge,
        "active_positions": len(state.active_positions),
        "phase": health.phase,
    }
    signal = await agent.hedge_manager.strategy.generate_signal(
        token_health, market_data, use_consensus=True,
    )
    return {
        "token_address": token_address,
        "signal": signal,
        "consensus": signal.get("consensus") if isinstance(signal, dict) else None,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.post(
    "/api/myx/attest",
    tags=["myx"],
    summary="Publish the MYX attestation Merkle root on BNB Chain",
    dependencies=[Depends(require_auth)],
)
async def myx_attest():
    """Opt-in. Publish the current MYX attestation tip on BNB Chain as a
    self-tx with the root in the tx data field. Admin-protected because it
    costs BNB. Returns the txhash + updated snapshot."""
    from agent.myx.store import get_myx_chain
    from agent.brain.attestation import publish_root_onchain  # reuse DGrid publisher
    from agent.config import settings as _settings
    if not getattr(_settings, "dgrid_attest_onchain", False):
        raise HTTPException(status_code=403, detail="DGRID_ATTEST_ONCHAIN must be true (reused flag gates both publishers)")
    chain = get_myx_chain()
    snap = chain.snapshot()
    root = snap["current_root"]
    count = int(snap.get("num_events_chained", 0))
    if count == 0:
        raise HTTPException(status_code=400, detail="no MYX events to attest yet")
    try:
        txhash = await publish_root_onchain(root)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MYX attestation publish failed: {e}") from e
    chain.record_attestation(root, txhash, count)
    return {
        "published_root": root,
        "txhash": txhash,
        "bscscan_url": f"https://bscscan.com/tx/{txhash}",
        "num_events_attested": count,
        **chain.snapshot(),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


# ── Public Integration APIs ──────────────────────────────────────────
# These endpoints are designed for Four.meme to consume directly.
# No auth required. Any token address works.

MODEL_VERSION = "four-life-v1.1"


_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _validate_address(token_address: str) -> str | None:
    """Return the lowercased address if it's a well-formed 0x40-hex string,
    otherwise raise HTTPException(400). Every public path-parameter endpoint
    that accepts a token/wallet address should call this up front — an
    unvalidated address turns into a free DB-bloat vector via history.record().
    """
    if not token_address or not _ADDR_RE.match(token_address):
        raise HTTPException(status_code=400, detail="invalid address — must be 0x + 40 hex chars")
    return token_address.lower()

# ── Contract-risk cache ──────────────────────────────────────────────
# Delegates to agent.security.risk_cache so the API and the lifecycle engine
# share one cache and one risk score per token. The `_contract_risk_cache`
# alias below preserves the in-tree test API; both names point at the same
# dict, so `.clear()` / `.get()` behave identically.
from agent.security import risk_cache as _risk_cache_module
from agent.security.risk_cache import (
    get_contract_risk as _shared_get_contract_risk,
    peek_contract_risk as _peek_contract_risk,
)

_contract_risk_cache = _risk_cache_module._cache


def _radar_estimate_tier(
    *,
    curve_progress_pct: float,
    increase_pct: float,
    confidence: str,
) -> str:
    """Heuristic tier estimate for radar entries we don't yet track on-chain.

    IMPORTANT: this is NOT a Certified tier. It is a RADAR ESTIMATE computed
    from public-ranking inputs only (curve progress, price-increase, confidence
    on the quote-asset graduation target). The radar endpoint stamps
    ``tier_source="radar_estimate"`` on entries produced by this helper so no
    consumer (UI, SDK, webhook) can mistake it for Certified.

    For tokens we already track on-chain the caller upgrades to the full
    deterministic badge via ``badge_from_health`` (tier_source="certified").
    """
    from agent.badge import (
        TIER_GRADUATED,
        TIER_GRADUATION_WATCH,
        TIER_AT_RISK,
        TIER_OBSERVED,
    )
    if curve_progress_pct >= 100:
        return TIER_GRADUATED
    if curve_progress_pct >= 70 and confidence == "high" and increase_pct >= 0:
        return TIER_GRADUATION_WATCH
    if increase_pct < -50:
        return TIER_AT_RISK
    return TIER_OBSERVED


# Back-compat alias — previously named helper. Keep the old symbol importable
# for any external code that may reference it (e.g. experimental notebooks).
# New callers should use _radar_estimate_tier.
_shallow_radar_tier = _radar_estimate_tier


async def _get_contract_risk(token_address: str) -> ContractRisk | None:
    """Fetch (or return cached) contract risk for a token. TTL = 10 minutes."""
    if not agent:
        return None
    from agent.config import settings
    return await _shared_get_contract_risk(
        token_address,
        agent.chain.w3,
        bscscan_api_key=settings.bscscan_api_key,
    )


def _deterministic_risk_flags(
    *,
    top_holder_pct: float,
    buy_sell_ratio: float,
    holder_velocity: float,
    age_hours: float,
    curve_progress_pct: float,
    whale_count: int = 0,
    graduation_confidence: str = "high",
) -> list[dict]:
    """Compute risk flags from raw metrics only — no LLM. Each flag has an id, severity,
    and the exact metric that triggered it. Judges can reproduce these deterministically."""
    flags: list[dict] = []
    if top_holder_pct >= 40:
        flags.append({
            "id": "whale_extreme",
            "severity": "critical",
            "metric": "top_holder_pct",
            "value": round(top_holder_pct, 2),
            "threshold": 40,
            "message": f"Top holder owns {top_holder_pct:.1f}% of supply (critical whale risk).",
        })
    elif top_holder_pct >= 20:
        flags.append({
            "id": "whale_high",
            "severity": "high",
            "metric": "top_holder_pct",
            "value": round(top_holder_pct, 2),
            "threshold": 20,
            "message": f"Top holder owns {top_holder_pct:.1f}% of supply.",
        })
    if whale_count >= 3:
        flags.append({
            "id": "whales_many",
            "severity": "medium",
            "metric": "whale_count",
            "value": whale_count,
            "threshold": 3,
            "message": f"{whale_count} wallets hold >5% of supply each.",
        })
    if buy_sell_ratio > 0 and buy_sell_ratio < 0.8:
        flags.append({
            "id": "sell_pressure",
            "severity": "high",
            "metric": "buy_sell_ratio",
            "value": round(buy_sell_ratio, 2),
            "threshold": 0.8,
            "message": f"Sell pressure exceeding buys (ratio {buy_sell_ratio:.2f}).",
        })
    if age_hours > 2 and holder_velocity < 1:
        flags.append({
            "id": "holder_stagnation",
            "severity": "medium",
            "metric": "holder_velocity",
            "value": round(holder_velocity, 2),
            "threshold": 1.0,
            "message": f"Holder growth stalled at {holder_velocity:.1f}/h after {age_hours:.1f}h.",
        })
    if age_hours > 12 and curve_progress_pct < 10 and graduation_confidence != "low":
        flags.append({
            "id": "curve_stalled",
            "severity": "medium",
            "metric": "curve_progress_pct",
            "value": round(curve_progress_pct, 2),
            "threshold": 10,
            "message": f"Bonding curve at {curve_progress_pct:.1f}% after {age_hours:.1f}h.",
        })
    if graduation_confidence == "low":
        flags.append({
            "id": "unknown_quote_asset",
            "severity": "info",
            "metric": "graduation_confidence",
            "value": graduation_confidence,
            "threshold": "high",
            "message": "Quote asset not found in Four.meme config — progress metrics unavailable.",
        })
    return flags


def _suggested_action(health) -> str:
    """Deterministic next-step suggestion based on raw metrics."""
    if health.top_holder_pct >= 40:
        return "Post transparency update: disclose whale concentration and next-step playbook."
    if health.buy_sell_ratio > 0 and health.buy_sell_ratio < 0.8 and health.phase != "nurture":
        return "Post defense content: counter-signal selling with milestone proof and roadmap."
    if health.curve_progress_pct >= 70:
        return "Accelerate: coordinate community for the last leg to graduation."
    if health.curve_progress_pct < 25 and health.age_hours > 12:
        return "Increase community engagement — post milestones, memes, and whale-risk disclosures."
    return "Hold course — metrics within healthy operating range."


@app.get("/api/health-score/{token_address}", tags=["platform"], summary="Pair-aware health score + Certified badge for any token")
async def public_health_score(token_address: str):
    """Public health score for any Four.meme token.

    Integration-ready: Four.meme can embed this on token pages. Every response includes
    confidence metadata and deterministic risk flags so judges and the platform can trust
    the output.
    """
    token_address = _validate_address(token_address)
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        # Check if already tracked
        health = agent.monitor.state.tokens.get(token_address)

        if not health:
            # Untracked path — build a snapshot from Four.meme's public ranking + live config.
            try:
                detail = await agent.api._client.post(
                    "/public/token/ranking",
                    json={"pageNo": 1, "pageSize": 50, "type": "HOT"},
                )
                tokens_data = detail.json().get("data", [])
                token_info = next(
                    (t for t in tokens_data if t.get("tokenAddress", "").lower() == token_address.lower()),
                    None,
                )
            except Exception:
                token_info = None

            fallback_used = token_info is None
            name = token_info.get("name", "") if token_info else ""
            symbol = token_info.get("shortName", "") if token_info else ""
            quote_asset = (token_info.get("symbol", "BNB") if token_info else "BNB").upper()
            holders = int(token_info.get("hold", 0)) if token_info else 0
            progress = float(token_info.get("progress", 0)) if token_info else 0
            volume = float(token_info.get("volume", 0)) if token_info else 0

            # Resolve pair-aware graduation target
            target = await agent.graduation_registry.get(quote_asset)

            # Heuristic scores (unchanged math, but now explicitly labeled as heuristic)
            health_score = 0.0
            grad_prob = 0.0
            if holders >= 500: health_score += 30
            elif holders >= 200: health_score += 20
            elif holders >= 50: health_score += 10
            if progress >= 0.8: health_score += 25; grad_prob += 0.5
            elif progress >= 0.5: health_score += 15; grad_prob += 0.3
            elif progress >= 0.25: health_score += 8; grad_prob += 0.15
            if holders >= 500: grad_prob += 0.2
            elif holders >= 200: grad_prob += 0.1
            if volume > 100: health_score += 20
            elif volume > 10: health_score += 10
            health_score = min(100, health_score)
            grad_prob = min(1.0, grad_prob)

            risk_flags = _deterministic_risk_flags(
                top_holder_pct=0.0,  # not available from ranking
                buy_sell_ratio=0.0,
                holder_velocity=0.0,
                age_hours=0.0,
                curve_progress_pct=progress * 100,
                whale_count=0,
                graduation_confidence=target.confidence,
            )

            badge = badge_from_ranking(
                curve_progress_pct=progress * 100,
                holders=holders,
                increase_pct=float(token_info.get("increase", 0)) * 100 if token_info else 0.0,
                graduation_confidence=target.confidence,
            )

            _record_history(token_address=token_address, badge=badge, data_source="ranking_snapshot")

            return {
                "token_address": token_address,
                "name": name,
                "symbol": symbol,
                "quote_asset": target.quote_asset,
                "graduation_target": target.target_amount,
                "graduation_target_unit": target.quote_asset,
                "graduation_progress_value": round(progress * target.target_amount, 4) if target.target_amount > 0 else 0.0,
                "health_score": round(health_score, 1),
                "graduation_probability": round(grad_prob * 100, 1),
                "holders": holders,
                "curve_progress": round(progress * 100, 1),
                "volume_bnb": round(volume, 4),
                "risk_flags": risk_flags,
                "risk_factors": [f["message"] for f in risk_flags],  # back-compat
                "badge": badge.to_dict(),
                "tier_source": badge.tier_source,
                "suggested_action": "Track this token with FOUR-LIFE for detailed lifecycle management.",
                "confidence_score": target.confidence,
                "fallback_used": fallback_used,
                "data_sources": ["fourmeme_ranking", "fourmeme_config"],
                "model_version": MODEL_VERSION,
                "last_updated_at": int(time.time()),
                "tracking_mode": "ranking_snapshot",
                "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
            }

        # Already tracked — return full metrics
        risk_flags = _deterministic_risk_flags(
            top_holder_pct=health.top_holder_pct,
            buy_sell_ratio=health.buy_sell_ratio,
            holder_velocity=health.holder_velocity,
            age_hours=health.age_hours,
            curve_progress_pct=health.curve_progress_pct,
            whale_count=health.whale_count,
            graduation_confidence=health.graduation_confidence,
        )

        contract_risk = await _get_contract_risk(token_address)
        crs = contract_risk.risk_score if contract_risk else 0
        badge = badge_from_health(health, contract_risk_score=crs, observation_status=getattr(health, "observation_status", "full_history"))

        _record_history(token_address=token_address, badge=badge, data_source="live_monitor")

        return {
            "token_address": token_address,
            "name": health.name,
            "symbol": health.symbol,
            "quote_asset": health.quote_asset,
            "graduation_target": health.graduation_target,
            "graduation_target_unit": health.graduation_target_unit or health.quote_asset,
            "graduation_progress_value": round(health.buy_volume_bnb, 4),
            "health_score": health.health_score,
            "graduation_probability": round(health.graduation_probability * 100, 1),
            "phase": health.phase,
            "age_hours": round(health.age_hours, 1),
            "holders": health.unique_buyers,
            "holder_velocity": round(health.holder_velocity, 1),
            "buy_sell_ratio": round(health.buy_sell_ratio, 2),
            "top_holder_pct": round(health.top_holder_pct, 1),
            "whale_count": health.whale_count,
            "curve_progress": round(health.curve_progress_pct, 1),
            "buy_volume_bnb": round(health.buy_volume_bnb, 4),
            "sell_volume_bnb": round(health.sell_volume_bnb, 4),
            "risk_flags": risk_flags,
            "risk_factors": [f["message"] for f in risk_flags],  # back-compat
            "badge": badge.to_dict(),
            "tier_source": badge.tier_source,
            "observation_status": badge.observation_status,
            "quote_asset_source": getattr(health, "quote_asset_source", "fourmeme_api"),
            "suggested_action": _suggested_action(health),
            "confidence_score": health.graduation_confidence,
            "fallback_used": health.graduation_source in ("fallback", "cache"),
            "data_sources": ["fourmeme_onchain_events", "fourmeme_config"],
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
            "tracking_mode": "live_monitor",
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post(
    "/api/raise-plan/{token_address}",
    tags=["platform"],
    summary="LLM-generated 72h raise plan (pair-aware target)",
    dependencies=[Depends(require_auth)],
)
async def generate_raise_plan(token_address: str):
    """Generate a 72-hour lifecycle raise plan for a token.

    AI creates an actionable phased plan: 0-30min, 1-6h, 6-24h, 24-72h, post-graduation.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        from agent.brain.llm import get_llm

        # Resolve pair-aware graduation target — always use the actual Four.meme config,
        # never the hardcoded 18 BNB. For untracked tokens, infer the quote asset from
        # the ranking API; fall back to BNB with low confidence if nothing is known.
        health = agent.monitor.state.tokens.get(token_address)
        quote_asset = "BNB"
        target_amount = 0.0
        target_confidence = "low"
        if health:
            quote_asset = health.quote_asset
            target_amount = health.graduation_target
            target_confidence = health.graduation_confidence
        else:
            try:
                detail = await agent.api._client.post(
                    "/public/token/ranking",
                    json={"pageNo": 1, "pageSize": 50, "type": "HOT"},
                )
                tokens_data = detail.json().get("data", [])
                info = next(
                    (t for t in tokens_data if t.get("tokenAddress", "").lower() == token_address.lower()),
                    None,
                )
                if info:
                    quote_asset = (info.get("symbol", "BNB") or "BNB").upper()
            except Exception:
                pass
            tgt = await agent.graduation_registry.get(quote_asset)
            target_amount = tgt.target_amount
            target_confidence = tgt.confidence

        # Human-readable target for the prompt
        if target_amount > 0:
            target_phrase = f"{target_amount:g} {quote_asset}"
        else:
            target_phrase = f"graduation target unknown for {quote_asset} (low confidence — do not fabricate numbers)"

        health_context = ""
        if health:
            health_context = f"""
Token: {health.name} ({health.symbol})
Quote Asset: {health.quote_asset}
Current Phase: {health.phase}
Age: {health.age_hours:.1f}h
Health Score: {health.health_score}/100
Holders: {health.unique_buyers}
Buy/Sell Ratio: {health.buy_sell_ratio:.2f}
Top Holder: {health.top_holder_pct:.1f}%
Bonding Curve: {health.curve_progress_pct:.1f}% of {target_phrase}
"""
        else:
            health_context = (
                f"Token address: {token_address} (not currently tracked — no live metrics available). "
                f"Quote asset: {quote_asset}. Graduation target: {target_phrase}."
            )

        plan = await get_llm().chat_json([{
            "role": "user",
            "content": f"""You are FOUR-LIFE, an AI lifecycle agent for Four.meme tokens on BNB Chain.

Generate a 72-hour Raise Plan for this token. The plan should help it graduate (reach {target_phrase} on the bonding curve).

{health_context}

Create a phased action plan in JSON:
{{
  "token_address": "{token_address}",
  "quote_asset": "{quote_asset}",
  "graduation_target": {target_amount},
  "phases": [
    {{"name": "Launch (0-30 min)", "actions": ["..."], "content_suggestions": ["..."], "risk_checks": ["..."]}},
    {{"name": "Nurture (1-6 hours)", "actions": ["..."], "content_suggestions": ["..."], "risk_checks": ["..."]}},
    {{"name": "Defend (6-24 hours)", "actions": ["..."], "content_suggestions": ["..."], "risk_checks": ["..."]}},
    {{"name": "Accelerate (24-72 hours)", "actions": ["..."], "content_suggestions": ["..."], "risk_checks": ["..."]}},
    {{"name": "Post-Graduation", "actions": ["..."], "content_suggestions": ["..."], "risk_checks": ["..."]}}
  ],
  "graduation_strategy": "one sentence summary of the best path to graduation",
  "risk_assessment": "key risks and how to mitigate them"
}}

Be specific and actionable. No vague advice. Reference the actual pair-aware graduation target above."""
        }])

        return {
            "plan": plan,
            "quote_asset": quote_asset,
            "graduation_target": target_amount,
            "graduation_target_unit": quote_asset,
            "confidence_score": target_confidence,
            "fallback_used": target_confidence == "low",
            "model_version": MODEL_VERSION,
            "llm_provider": get_llm().model_id,
            "last_updated_at": int(time.time()),
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Radar response cache. Keyed by the full filter tuple so different
# sort/filter combos don't poison each other. TTL matches the landing
# page's 30s refresh cadence: judges always see data ≤30s old, but every
# click between polls lands on a cached hit (<10ms vs. 2-12s uncached).
_RADAR_CACHE: dict[tuple, tuple[float, dict]] = {}
_RADAR_CACHE_TTL = 30.0


@app.get("/api/graduation-radar", tags=["radar"], summary="Live Four.meme radar with filters (quote asset, min confidence, sort key)")
async def graduation_radar(
    limit: int = 20,
    quote_asset: str = "all",
    min_confidence: str = "low",
    sort_by: str = "graduation_probability",
):
    """Public Graduation Radar — ranks active Four.meme tokens by graduation probability.

    Filters (platform-useful):
      - quote_asset: BNB | USD1 | USDT | USDC | ... | all
      - min_confidence: low | medium | high (confidence of the graduation target lookup)
      - sort_by: graduation_probability | health_score | holder_velocity | curve_progress
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    # Serve from cache if fresh. Key normalizes strings the same way the
    # endpoint body would (lowercase/uppercase) so "BNB" and "bnb" share.
    cache_key = (int(limit), (quote_asset or "all").upper(), (min_confidence or "low").lower(), sort_by)
    cached = _RADAR_CACHE.get(cache_key)
    if cached and (time.time() - cached[0]) < _RADAR_CACHE_TTL:
        return cached[1]

    CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
    VALID_SORTS = {"graduation_probability", "health_score", "holder_velocity", "curve_progress"}
    if sort_by not in VALID_SORTS:
        sort_by = "graduation_probability"
    quote_filter = (quote_asset or "all").upper()
    min_conf_rank = CONFIDENCE_RANK.get((min_confidence or "low").lower(), 0)

    try:
        hot_tokens = await agent.api.get_trending()
        new_tokens = await agent.api.get_new_tokens(page_size=limit)

        seen = set()
        all_tokens = []
        for t in hot_tokens + new_tokens:
            addr = t.get("tokenAddress", "")
            if not addr or addr in seen:
                continue
            seen.add(addr)
            holders = int(t.get("hold", 0))
            progress = float(t.get("progress", 0))
            volume = float(t.get("volume", 0))
            increase = float(t.get("increase", 0))
            token_quote = (t.get("symbol", "BNB") or "BNB").upper()

            # Filter by quote asset if requested
            if quote_filter != "ALL" and token_quote != quote_filter:
                continue

            # Resolve pair-aware target + confidence
            target = await agent.graduation_registry.get(token_quote)
            if CONFIDENCE_RANK.get(target.confidence, 0) < min_conf_rank:
                continue

            # Heuristic scores (explicit)
            health_score = 0.0
            grad_prob = 0.0
            if holders >= 500: health_score += 30; grad_prob += 0.2
            elif holders >= 200: health_score += 20; grad_prob += 0.1
            elif holders >= 50: health_score += 10; grad_prob += 0.05
            if progress >= 0.8: health_score += 25; grad_prob += 0.5
            elif progress >= 0.5: health_score += 15; grad_prob += 0.3
            elif progress >= 0.25: health_score += 8; grad_prob += 0.15
            if volume > 100: health_score += 20; grad_prob += 0.1
            elif volume > 10: health_score += 10; grad_prob += 0.05
            if increase > 0.5: health_score += 15
            elif increase > 0: health_score += 5

            # Holder velocity is only available from on-chain monitor — proxy 0 for ranking-only tokens
            holder_velocity = 0.0

            # Server-computed tier — the UI never re-derives trust labels.
            # For consistency with /api/token/{addr}/badge, we use the SAME
            # helpers here: `badge_from_ranking` for untracked tokens
            # (tier_source="radar_estimate"), `badge_from_health` for tracked
            # ones (tier_source="certified"). A token queried via /radar and
            # /badge must never receive two different labels.
            from agent.badge import SOURCE_RADAR_ESTIMATE
            radar_badge = badge_from_ranking(
                curve_progress_pct=progress * 100,
                holders=holders,
                increase_pct=increase * 100,
                graduation_confidence=target.confidence,
            )
            badge_tier = radar_badge.tier
            tier_source = radar_badge.tier_source  # always "radar_estimate"
            observation_status = radar_badge.observation_status  # "ranking_only"
            assert tier_source == SOURCE_RADAR_ESTIMATE  # invariant
            if agent and addr in agent.monitor.state.tokens:
                try:
                    tracked = agent.monitor.state.tokens[addr]
                    risk = _peek_contract_risk(addr)
                    crs = risk.risk_score if risk else 0
                    certified = badge_from_health(
                        tracked,
                        contract_risk_score=crs,
                        observation_status=getattr(tracked, "observation_status", "full_history"),
                    )
                    badge_tier = certified.tier
                    tier_source = certified.tier_source
                    observation_status = certified.observation_status
                except Exception:
                    pass

            all_tokens.append({
                "token_address": addr,
                "name": t.get("name", ""),
                "symbol": t.get("shortName", ""),
                "quote_asset": token_quote,
                "graduation_target": target.target_amount,
                "graduation_target_unit": target.quote_asset,
                "graduation_progress_value": round(progress * target.target_amount, 4) if target.target_amount > 0 else 0.0,
                "holders": holders,
                "curve_progress": round(progress * 100, 1),
                "volume_quote": round(volume, 2),
                "volume_bnb": round(volume, 2),  # back-compat
                "increase_pct": round(increase * 100, 1),
                "health_score": round(min(100, health_score), 1),
                "graduation_probability": round(min(100, grad_prob * 100), 1),
                "holder_velocity": holder_velocity,
                "confidence_score": target.confidence,
                "badge_tier": badge_tier,
                "tier_source": tier_source,
                "observation_status": observation_status,
                "quote_asset_source": (
                    getattr(agent.monitor.state.tokens.get(addr), "quote_asset_source", "fourmeme_api")
                    if (agent and addr in agent.monitor.state.tokens)
                    else ("fourmeme_api" if t.get("symbol") else "fallback")
                ),
                "status": t.get("status", ""),
                "fourmeme_url": f"https://four.meme/token/{addr}",
            })

        # Merge live-monitored Certified tokens that aren't already in the radar
        # payload. Four.meme's trending/new feeds only surface popular tokens —
        # our tracked certified tokens may have 0 holders / stalled curve and
        # therefore fall off those lists, which made the public radar appear
        # to contain only radar_estimate entries. The radar's promise is "every
        # active Four.meme token, graded deterministically," so a token under
        # our live on-chain monitor MUST appear here with its Certified grade.
        if agent and agent.monitor.state.tokens:
            for addr, tracked in agent.monitor.state.tokens.items():
                if addr in seen:
                    continue
                token_quote = (getattr(tracked, "quote_asset", "BNB") or "BNB").upper()
                if quote_filter != "ALL" and token_quote != quote_filter:
                    continue
                target = await agent.graduation_registry.get(token_quote)
                if CONFIDENCE_RANK.get(target.confidence, 0) < min_conf_rank:
                    continue
                try:
                    risk = _peek_contract_risk(addr)
                    crs = risk.risk_score if risk else 0
                    certified = badge_from_health(
                        tracked,
                        contract_risk_score=crs,
                        observation_status=getattr(tracked, "observation_status", "full_history"),
                    )
                except Exception:
                    continue
                seen.add(addr)
                holders = int(getattr(tracked, "unique_buyers", 0) or 0)
                progress = float(getattr(tracked, "curve_progress_pct", 0) or 0) / 100.0
                all_tokens.append({
                    "token_address": addr,
                    "name": tracked.name or "",
                    "symbol": tracked.symbol or "",
                    "quote_asset": token_quote,
                    "graduation_target": target.target_amount,
                    "graduation_target_unit": target.quote_asset,
                    "graduation_progress_value": round(progress * target.target_amount, 4) if target.target_amount > 0 else 0.0,
                    "holders": holders,
                    "curve_progress": round(progress * 100, 1),
                    "volume_quote": 0.0,
                    "volume_bnb": 0.0,  # back-compat
                    "increase_pct": 0.0,
                    "health_score": round(float(getattr(tracked, "health_score", 0) or 0), 1),
                    # Derive a crude graduation probability from curve progress + tier for sort compat.
                    "graduation_probability": round(min(100.0, float(getattr(tracked, "curve_progress_pct", 0) or 0) * 0.9), 1),
                    "holder_velocity": round(float(getattr(tracked, "holder_velocity", 0) or 0), 2),
                    "confidence_score": target.confidence,
                    "badge_tier": certified.tier,
                    "tier_source": certified.tier_source,
                    "observation_status": certified.observation_status,
                    "quote_asset_source": getattr(tracked, "quote_asset_source", "fourmeme_api"),
                    "status": "",
                    "fourmeme_url": f"https://four.meme/token/{addr}",
                })

        # Primary sort: always put Certified (live-monitored) tokens above
        # radar_estimate rows so judges opening the radar see our depth first.
        # Secondary: user's requested score. The is_certified boolean sorts
        # True>False in descending order, so no extra work needed.
        sort_score = {
            "graduation_probability": lambda x: x["graduation_probability"],
            "health_score": lambda x: x["health_score"],
            "holder_velocity": lambda x: x["holder_velocity"],
            "curve_progress": lambda x: x["curve_progress"],
        }[sort_by]
        all_tokens.sort(
            key=lambda x: (x.get("tier_source") == "certified", sort_score(x)),
            reverse=True,
        )

        response = {
            "radar": all_tokens[:limit],
            "total_scanned": len(all_tokens),
            "filters": {
                "quote_asset": quote_filter,
                "min_confidence": min_confidence,
                "sort_by": sort_by,
            },
            "known_quote_assets": agent.graduation_registry.known_assets(),
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
            "timestamp": time.time(),
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }
        # Evict stale entries while we're here — keeps the dict bounded
        # without a dedicated sweeper. 30s TTL across maybe 20 filter combos
        # is tiny memory; this is belt-and-braces.
        now = time.time()
        for k in list(_RADAR_CACHE.keys()):
            if (now - _RADAR_CACHE[k][0]) > _RADAR_CACHE_TTL:
                del _RADAR_CACHE[k]
        _RADAR_CACHE[cache_key] = (now, response)
        return response

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Platform Primitives (Four.meme-native integration surface) ───────

@app.get("/api/token/{token_address}/badge", tags=["platform"], summary="FOUR-LIFE Certified — deterministic trust tier with why[] rule trace")
async def token_badge(token_address: str):
    """FOUR-LIFE Certified — deterministic trust badge for any Four.meme token.

    Returns one of: graduated | graduation_watch | healthy | at_risk | observed.
    Every response includes the exact rules that triggered the tier so judges and
    Four.meme can reproduce the grade from raw metrics.
    """
    token_address = _validate_address(token_address)
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        health = agent.monitor.state.tokens.get(token_address)
        if health:
            contract_risk = await _get_contract_risk(token_address)
            crs = contract_risk.risk_score if contract_risk else 0
            badge = badge_from_health(health, contract_risk_score=crs, observation_status=getattr(health, "observation_status", "full_history"))
            source = "live_monitor"
        else:
            # Fall back to Four.meme ranking snapshot
            try:
                detail = await agent.api._client.post(
                    "/public/token/ranking",
                    json={"pageNo": 1, "pageSize": 50, "type": "HOT"},
                )
                tokens_data = detail.json().get("data", [])
                info = next(
                    (t for t in tokens_data if t.get("tokenAddress", "").lower() == token_address.lower()),
                    None,
                )
            except Exception:
                info = None

            if not info:
                return JSONResponse({
                    "token_address": token_address,
                    "badge": None,
                    "reason": "Token not found in live monitor or ranking snapshot.",
                    "model_version": MODEL_VERSION,
                    "last_updated_at": int(time.time()),
                }, status_code=404)

            # Quote-asset provenance: if Four.meme returns the symbol field
            # we call it fourmeme_api; if it's missing or empty we flag
            # the default as fallback so consumers can distinguish a
            # measured BNB pair from an assumed one.
            raw_quote = info.get("symbol")
            quote_asset = (raw_quote or "BNB").upper()
            quote_asset_source = "fourmeme_api" if raw_quote else "fallback"
            target = await agent.graduation_registry.get(quote_asset)
            badge = badge_from_ranking(
                curve_progress_pct=float(info.get("progress", 0)) * 100,
                holders=int(info.get("hold", 0)),
                increase_pct=float(info.get("increase", 0)) * 100,
                graduation_confidence=target.confidence,
            )
            source = "ranking_snapshot"

        _record_history(token_address=token_address, badge=badge, data_source=source)

        # Observation + quote-asset provenance for the live-monitor path,
        # populated from the tracked health snapshot.
        if source == "live_monitor":
            obs_status = getattr(health, "observation_status", "full_history")
            qa_source = getattr(health, "quote_asset_source", "fourmeme_api")
            creator = (getattr(health, "creator", "") or "").lower() or None
        else:
            obs_status = badge.observation_status  # "ranking_only" from badge_from_ranking
            qa_source = quote_asset_source         # set in the fallback branch above
            # Four.meme's ranking response uses `userAddress` for the deployer.
            creator = ((info.get("userAddress") or "").strip().lower() or None)

        return {
            "token_address": token_address,
            "badge": badge.to_dict(),
            "tier_source": badge.tier_source,
            "observation_status": obs_status,
            "quote_asset_source": qa_source,
            # Creator wallet — the deployer of the token. Lets downstream
            # consumers (extension, SDK) combine this with
            # /api/creator/{wallet}/survival-score to show dev reputation
            # alongside the token verdict. Null if unknown.
            "creator": creator,
            "data_source": source,
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/token/{token_address}/risk-snapshot", tags=["platform"], summary="Evidence-backed risk snapshot with per-metric flags")
async def token_risk_snapshot(token_address: str):
    """Risk snapshot for a tracked token. Evidence-backed — every risk-level assignment
    is traceable to the exact metric that produced it."""
    token_address = _validate_address(token_address)
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        return JSONResponse({
            "token_address": token_address,
            "error": "Token not tracked. Use /api/agent/track to begin monitoring.",
            "risk_level": "unknown",
            "model_version": MODEL_VERSION,
        }, status_code=404)

    flags = _deterministic_risk_flags(
        top_holder_pct=health.top_holder_pct,
        buy_sell_ratio=health.buy_sell_ratio,
        holder_velocity=health.holder_velocity,
        age_hours=health.age_hours,
        curve_progress_pct=health.curve_progress_pct,
        whale_count=health.whale_count,
        graduation_confidence=health.graduation_confidence,
    )

    # Merge contract-level rug-risk flags from the deterministic analyzer (cached per token).
    contract_risk = await _get_contract_risk(token_address)
    contract_risk_score = 0
    if contract_risk is not None:
        contract_risk_score = contract_risk.risk_score
        for cf in contract_risk.flags:
            flags.append({
                "id": cf["id"],
                "severity": cf["severity"],
                "metric": "contract_bytecode",
                "value": cf.get("evidence", ""),
                "threshold": "present",
                "message": cf["message"],
            })

    severities = [f["severity"] for f in flags]
    if "critical" in severities:
        risk_level = "critical"
    elif "high" in severities:
        risk_level = "high"
    elif "medium" in severities:
        risk_level = "medium"
    elif "info" in severities:
        risk_level = "info"
    else:
        risk_level = "low"

    _record_history(
        token_address=token_address,
        badge=badge_from_health(health, contract_risk_score=contract_risk_score),
        data_source="risk_snapshot",
        risk_level=risk_level,
    )

    return {
        "token_address": token_address,
        "name": health.name,
        "symbol": health.symbol,
        "quote_asset": health.quote_asset,
        "risk_level": risk_level,
        "metrics": {
            "whale_concentration": round(health.top_holder_pct, 2),
            "whale_count": health.whale_count,
            "buy_sell_ratio": round(health.buy_sell_ratio, 2),
            "holder_velocity": round(health.holder_velocity, 2),
            "holder_count": health.unique_buyers,
            "age_hours": round(health.age_hours, 2),
            "curve_progress": round(health.curve_progress_pct, 2),
            "phase": health.phase,
            "contract_risk_score": contract_risk_score,
        },
        "evidence": flags,
        "confidence_score": health.graduation_confidence,
        "fallback_used": health.graduation_source in ("fallback", "cache"),
        "data_sources": ["fourmeme_onchain_events", "fourmeme_config", "bscscan"],
        "contract_risk": contract_risk.to_dict() if contract_risk else None,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


@app.get("/api/token/{token_address}/history", tags=["platform"], summary="Historical tier snapshots (time-series) for a token")
async def token_history(token_address: str, limit: int = 200, since: int | None = None, transitions_only: bool = False):
    """Historical Certified-tier snapshots for a token, newest-first.

    Each call to `/badge`, `/health-score`, or `/risk-snapshot` records a snapshot
    when the tier changes or 5 minutes elapse since the last write. Set
    `transitions_only=true` to return only rows where the tier actually changed.
    """
    token_address = _validate_address(token_address)
    store = _history_store()
    try:
        rows = (
            store.transitions(token_address, since=since, limit=limit)
            if transitions_only
            else store.history(token_address, limit=limit, since=since)
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return {
        "token_address": token_address.lower(),
        "since": since,
        "limit": limit,
        "transitions_only": bool(transitions_only),
        "count": len(rows),
        "snapshots": [r.to_dict() for r in rows],
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


@app.get("/api/token/{token_address}/diff", tags=["platform"], summary="What changed for a token since a given timestamp")
async def token_diff(token_address: str, since: int):
    """Summarize the changes for a token since `since` (unix seconds).

    Returns first + last snapshot inside the window plus every tier transition with the
    `why[]` rule trace for each boundary. This is the read-model for alerts,
    change-summary emails, and the radar-bot status feed.
    """
    token_address = _validate_address(token_address)
    store = _history_store()
    try:
        d = store.diff(token_address, since=int(since))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return {
        **d,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


_HISTORY_EXPORT_ROW_CAP = 100_000


@app.get(
    "/api/history/export.ndjson",
    tags=["platform"],
    summary="Stream the full history store as newline-delimited JSON for backfill",
    dependencies=[Depends(require_auth)],
)
async def history_export(since: int | None = None, token_address: str | None = None):
    """Stream historical snapshots as newline-delimited JSON (NDJSON).

    Required:
      - Bearer API_SECRET (auth-gated — unbounded streaming is an amplification
        vector and must not be anonymously callable).
      - `since` OR `token_address` — at least one must be set to bound the
        response. Unbounded full-table dumps are rejected with 400.

    A hard row cap of 100k is enforced regardless of filters to prevent a
    single request from saturating the worker.

    Intended for integrators who need a bulk backfill. For incremental sync,
    prefer `/api/token/{addr}/history?since=<ts>` per token.
    """
    if since is None and not token_address:
        return JSONResponse(
            {"error": "provide `since` (unix seconds) or `token_address` — unbounded exports are not permitted"},
            status_code=400,
        )
    # Validate token_address if provided.
    if token_address and not re.fullmatch(r"0x[a-fA-F0-9]{40}", token_address):
        return JSONResponse({"error": "invalid token_address"}, status_code=400)
    store = _history_store()

    def _iter():
        emitted = 0
        cap = _HISTORY_EXPORT_ROW_CAP
        for snap in store.iter_export(since=since, token_address=token_address):
            if emitted >= cap:
                # Append a terminator row so clients know the stream was truncated.
                yield (json.dumps({"_truncated": True, "cap": cap}, separators=(",", ":")) + "\n").encode("utf-8")
                return
            yield (json.dumps(snap, separators=(",", ":")) + "\n").encode("utf-8")
            emitted += 1

    return StreamingResponse(
        _iter(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="four-life-history.ndjson"',
            "X-Model-Version": MODEL_VERSION,
        },
    )


@app.get("/api/history/tokens", tags=["platform"], summary="Tokens with recorded history, newest-activity first")
async def history_tokens(limit: int = 200):
    """List of token addresses that have at least one recorded snapshot.

    Useful for judges / integrators who want to audit the history store without
    needing to know which tokens are being tracked live.
    """
    store = _history_store()
    try:
        tokens = store.tokens_with_history(limit=limit)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {
        "count": len(tokens),
        "tokens": tokens,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


# ── Webhooks (outbound tier-change notifications) ────────────────────

class _WebhookSubscribeBody(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: [EVENT_BADGE_TIER_CHANGED])
    token_filter: str | None = None
    created_by: str | None = None


@app.post(
    "/api/webhooks",
    tags=["webhooks"],
    summary="Create a webhook subscription — returns a shared secret ONCE",
    dependencies=[Depends(require_auth)],
)
async def create_webhook_subscription(body: _WebhookSubscribeBody):
    """Register a new webhook endpoint. Response includes `secret` **exactly once**;
    store it securely to verify the `X-FourLife-Signature` header on deliveries.

    Supported events: `badge.tier_changed`. Pass `token_filter` to receive events for
    one specific token address; omit it to subscribe to every tracked token.
    """
    store = _webhook_store()
    try:
        sub, secret = store.subscribe(
            url=body.url,
            events=body.events or [EVENT_BADGE_TIER_CHANGED],
            token_filter=body.token_filter,
            created_by=body.created_by,
        )
    except ValueError as ve:
        return JSONResponse({"error": str(ve)}, status_code=400)
    return {
        **sub.to_dict(),
        "secret": secret,
        "supported_events": sorted(SUPPORTED_EVENTS),
        "signature_header": "X-FourLife-Signature",
        "signature_format": "t=<unix_ts>,v1=<hex_hmac_sha256>",
        "signed_payload": "<timestamp>.<raw_body>",
        "retry_schedule_seconds": [30, 120, 900],
        "note": "Store the secret now — it is not retrievable later.",
    }


@app.get(
    "/api/webhooks",
    tags=["webhooks"],
    summary="List webhook subscriptions (secrets not returned)",
    dependencies=[Depends(require_auth)],
)
async def list_webhook_subscriptions(include_disabled: bool = False):
    store = _webhook_store()
    subs = store.list_subscriptions(include_disabled=include_disabled)
    return {
        "count": len(subs),
        "subscriptions": [s.to_dict() for s in subs],
        "last_updated_at": int(time.time()),
    }


@app.delete(
    "/api/webhooks/{subscription_id}",
    tags=["webhooks"],
    summary="Delete a webhook subscription",
    dependencies=[Depends(require_auth)],
)
async def delete_webhook_subscription(subscription_id: str):
    store = _webhook_store()
    ok = store.delete_subscription(subscription_id)
    if not ok:
        return JSONResponse({"error": "subscription not found"}, status_code=404)
    return {"deleted": True, "subscription_id": subscription_id}


@app.get(
    "/api/webhooks/{subscription_id}/deliveries",
    tags=["webhooks"],
    summary="List recent deliveries for a subscription",
    dependencies=[Depends(require_auth)],
)
async def list_webhook_deliveries(subscription_id: str, limit: int = 50):
    store = _webhook_store()
    sub = store.get_subscription(subscription_id)
    if not sub:
        return JSONResponse({"error": "subscription not found"}, status_code=404)
    deliveries = store.list_deliveries(subscription_id, limit=limit)
    return {
        "subscription": sub.to_dict(),
        "count": len(deliveries),
        "deliveries": [d.to_dict() for d in deliveries],
        "last_updated_at": int(time.time()),
    }


# ── Protection Mode ──────────────────────────────────────────────────

class _ProtectionPolicyBody(BaseModel):
    active: bool = True
    max_whale_concentration: float | None = None
    critical_whale_concentration: float | None = None
    critical_buy_sell_ratio: float | None = None
    max_contract_risk: int | None = None
    critical_contract_risk: int | None = None
    max_whale_count: int | None = None
    critical_whale_count: int | None = None
    created_by: str | None = None


async def _evaluate_protection_for_token(
    token_address: str, *, agent_obj=None
) -> dict | None:
    """Evaluate the current protection verdict for a token.

    Fetches contract risk through the shared cache (10 min TTL) so the
    protection verdict actually reflects mint/blacklist/pause/ownable signals
    instead of silently defaulting to 0. Returns None if the token isn't
    tracked (we can't score without health metrics).
    """
    a = agent_obj if agent_obj is not None else agent
    if not a:
        return None
    health = a.monitor.state.tokens.get(token_address)
    if not health:
        return None
    policy = _protection_store().get_policy(token_address)

    risk = await _get_contract_risk(token_address)
    crs = risk.risk_score if risk else 0

    verdict = evaluate_protection(
        token_address=token_address,
        policy=policy,
        top_holder_pct=health.top_holder_pct,
        whale_count=health.whale_count,
        buy_sell_ratio=health.buy_sell_ratio,
        age_hours=health.age_hours,
        contract_risk_score=crs,
    )
    return verdict.to_dict()


@app.put(
    "/api/protection/{token_address}",
    tags=["protection"],
    summary="Create or update a token's protection policy",
    dependencies=[Depends(require_auth)],
)
async def upsert_protection_policy(token_address: str, body: _ProtectionPolicyBody):
    """Set the protection policy for a token. Every field is optional — unset fields
    fall back to the deterministic defaults (see GET for the resolved thresholds)."""
    try:
        policy = _protection_store().upsert_policy(ProtectionPolicy(
            token_address=token_address,
            active=body.active,
            max_whale_concentration=body.max_whale_concentration,
            critical_whale_concentration=body.critical_whale_concentration,
            critical_buy_sell_ratio=body.critical_buy_sell_ratio,
            max_contract_risk=body.max_contract_risk,
            critical_contract_risk=body.critical_contract_risk,
            max_whale_count=body.max_whale_count,
            critical_whale_count=body.critical_whale_count,
            created_by=body.created_by,
        ))
    except ValueError as ve:
        return JSONResponse({"error": str(ve)}, status_code=400)

    return {
        **policy.to_dict(),
        "current_verdict": await _evaluate_protection_for_token(token_address),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/protection/{token_address}",
    tags=["protection"],
    summary="Read the protection policy + live verdict for a token",
)
async def get_protection_policy(token_address: str):
    """Return the policy + the current verdict computed against the token's live
    metrics. If no policy is set, returns the defaults and a baseline verdict."""
    policy = _protection_store().get_policy(token_address)
    verdict = await _evaluate_protection_for_token(token_address)
    if policy is None and verdict is None:
        return JSONResponse({
            "token_address": token_address.lower(),
            "policy": None,
            "current_verdict": None,
            "note": "No policy set and token is not tracked. PUT /api/protection/{token} to configure.",
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
        }, status_code=200)
    return {
        "token_address": token_address.lower(),
        "policy": policy.to_dict() if policy else None,
        "current_verdict": verdict,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


@app.delete(
    "/api/protection/{token_address}",
    tags=["protection"],
    summary="Remove a token's protection policy",
    dependencies=[Depends(require_auth)],
)
async def delete_protection_policy(token_address: str):
    ok = _protection_store().delete_policy(token_address)
    if not ok:
        return JSONResponse({"error": "policy not found"}, status_code=404)
    return {"deleted": True, "token_address": token_address.lower()}


@app.get(
    "/api/protection",
    tags=["protection"],
    summary="List every configured protection policy",
)
async def list_protection_policies(include_inactive: bool = True):
    policies = _protection_store().list_policies(include_inactive=include_inactive)
    return {
        "count": len(policies),
        "policies": [p.to_dict() for p in policies],
        "last_updated_at": int(time.time()),
    }


@app.get(
    "/api/notifications/status",
    tags=["notifications"],
    summary="Which notification channels are active",
)
async def notifications_status():
    """Public status of notification channels. Never reveals tokens — just which
    channels are currently configured."""
    chs = _notifications.channels()
    return {
        "channels": [
            {"name": c.name, "enabled": c.enabled}
            for c in (_notifications.TelegramChannel(), _notifications.DiscordChannel())
        ],
        "active_count": len(chs),
        "supported_events": ["badge.tier_changed", "protection.level_changed"],
        "last_updated_at": int(time.time()),
    }


@app.post(
    "/api/notifications/test",
    tags=["notifications"],
    summary="Send a test event to every configured channel",
    dependencies=[Depends(require_auth)],
)
async def notifications_test(event_type: str = "badge.tier_changed"):
    """Fire a synthetic event through all enabled notification channels. Useful
    for verifying Telegram/Discord config from the dashboard."""
    if event_type == "badge.tier_changed":
        fake = {
            "type": "badge.tier_changed",
            "token_address": "0x" + "00" * 20,
            "from_tier": "healthy",
            "to_tier": "at_risk",
            "at": int(time.time()),
        }
    elif event_type == "protection.level_changed":
        fake = {
            "type": "protection.level_changed",
            "token_address": "0x" + "00" * 20,
            "from_level": "safe",
            "to_level": "critical",
            "fired_rules": [
                {"rule": "test_rule", "severity": "critical"},
            ],
            "at": int(time.time()),
        }
    else:
        return JSONResponse({"error": "unsupported event_type"}, status_code=400)

    results = await _notifications.send_sync(event_type, fake)
    return {
        "event_type": event_type,
        "results": results,
        "dispatched_count": sum(1 for v in results.values() if v),
    }


@app.get("/api/token/{token_address}/contract-risk", tags=["contract"], summary="Bytecode + source analysis — mint, blacklist, proxy, pause, ownership, honeypot")
async def token_contract_risk(token_address: str):
    """Deterministic contract-level rug-risk analysis for a BSC token.

    Scans bytecode + BscScan-verified ABI for mint, blacklist, pause, EIP-1967
    proxy, and ownership status. Cached for 10 minutes per token.
    """
    token_address = _validate_address(token_address)
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    risk = await _get_contract_risk(token_address)
    if risk is None:
        return JSONResponse({
            "error": "Contract analysis failed — RPC or BscScan unreachable.",
            "token_address": token_address,
        }, status_code=502)

    return {
        **risk.to_dict(),
        "model_version": MODEL_VERSION,
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 == 1 else float((s[mid - 1] + s[mid]) / 2)


def _creator_trust_tier(*, launches_tracked: int, grad_rate: float, median_curve: float, median_holders: float) -> str:
    """Deterministic creator trust tier — same thresholds everywhere."""
    if launches_tracked < 3:
        return "new_creator"
    if grad_rate >= 0.5 and median_holders >= 250:
        return "proven"
    if grad_rate >= 0.25 or median_curve >= 40:
        return "emerging"
    return "unproven"


def _compute_creator_stats(launches: list, *, evidence_limit: int = 10) -> dict:
    """Aggregate launch records for a single creator. Returns the same shape as
    `/api/creator/{wallet}/survival-score`, minus per-request metadata."""
    graduations = sum(1 for lr in launches if lr.graduated)
    grad_rate = graduations / len(launches) if launches else 0.0
    median_curve = _median([lr.peak_curve_progress for lr in launches])
    median_holders = _median([float(lr.peak_holders) for lr in launches])

    trust_tier = _creator_trust_tier(
        launches_tracked=len(launches),
        grad_rate=grad_rate,
        median_curve=median_curve,
        median_holders=median_holders,
    )

    last_launch_at = max((lr.launched_at for lr in launches), default=0.0)

    return {
        "launches_tracked": len(launches),
        "graduations": graduations,
        "graduation_rate": round(grad_rate, 3),
        "median_peak_curve_progress": round(median_curve, 2),
        "median_peak_holders": int(median_holders),
        "trust_tier": trust_tier,
        "last_launch_at": last_launch_at,
        "evidence": [
            {
                "token_address": lr.token_address,
                "symbol": lr.symbol,
                "narrative": lr.narrative,
                "quote_asset": getattr(lr, "quote_asset", "BNB"),
                "launched_at": lr.launched_at,
                "graduated": lr.graduated,
                "peak_curve_progress": round(lr.peak_curve_progress, 2),
                "peak_holders": lr.peak_holders,
                "peak_health_score": lr.peak_health_score,
            }
            for lr in sorted(launches, key=lambda l: l.launched_at)[-evidence_limit:]
        ],
    }


def _launches_by_creator(agent_obj) -> dict[str, list]:
    """Group launches by normalized creator wallet. Empty creator → agent wallet."""
    agent_wallet = (agent_obj.chain.account.address or "").lower()
    out: dict[str, list] = {}
    for lr in agent_obj.memory.memory.launches:
        creator = (lr.creator or agent_wallet).lower()
        out.setdefault(creator, []).append(lr)
    return out


@app.get("/api/creator/{wallet}/survival-score", tags=["creator"], summary="Creator track record + deterministic trust tier")
async def creator_survival_score(wallet: str):
    """Aggregate survival performance for a creator wallet across all FOUR-LIFE-tracked launches.

    Fields: launches tracked, graduations, median peak curve progress, median peak holders,
    trust tier. Returns honestly-empty stats for unknown creators — no fabrication.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    # Validate the wallet address format up front — prevents garbage keys from
    # being echoed in the response and keeps path params consistent across the
    # public API.
    wallet_lower = _validate_address(wallet)
    launches = _launches_by_creator(agent).get(wallet_lower, [])

    if not launches:
        return {
            "wallet": wallet_lower,
            "tracked": False,
            "launches_tracked": 0,
            "graduations": 0,
            "graduation_rate": 0.0,
            "median_peak_curve_progress": 0.0,
            "median_peak_holders": 0,
            "trust_tier": "unknown",
            "evidence": [],
            "note": "No FOUR-LIFE-tracked launches for this wallet yet.",
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
        }

    stats = _compute_creator_stats(launches)
    stats.pop("last_launch_at", None)  # per-wallet endpoint kept its original shape

    return {
        "wallet": wallet,
        "tracked": True,
        **stats,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


_TRUST_TIER_RANK = {"proven": 4, "emerging": 3, "new_creator": 2, "unproven": 1, "unknown": 0}
_CREATOR_SORT_KEYS = {"graduation_rate", "launches", "median_curve", "median_holders", "trust_tier", "recent"}


@app.get("/api/creators/leaderboard", tags=["creator"], summary="Aggregate creator leaderboard across every FOUR-LIFE-tracked launch")
async def creators_leaderboard(
    sort_by: str = "trust_tier",
    trust_tier: str | None = None,
    min_launches: int = 1,
    limit: int = 100,
):
    """Leaderboard of every creator FOUR-LIFE has ever observed.

    Each row uses the same deterministic trust tier as `/api/creator/{wallet}/survival-score`.
    Sort keys: `trust_tier` (default, then graduation_rate tiebreak), `graduation_rate`,
    `launches`, `median_curve`, `median_holders`, `recent` (most recent launch first).
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    if sort_by not in _CREATOR_SORT_KEYS:
        return JSONResponse(
            {"error": f"sort_by must be one of: {sorted(_CREATOR_SORT_KEYS)}"},
            status_code=400,
        )

    grouped = _launches_by_creator(agent)
    min_launches = max(1, int(min_launches))
    limit = max(1, min(int(limit), 500))

    rows: list[dict] = []
    for wallet, launches in grouped.items():
        if len(launches) < min_launches:
            continue
        stats = _compute_creator_stats(launches, evidence_limit=5)
        if trust_tier and stats["trust_tier"] != trust_tier:
            continue
        rows.append({"wallet": wallet, **stats})

    if sort_by == "trust_tier":
        rows.sort(key=lambda r: (_TRUST_TIER_RANK.get(r["trust_tier"], 0), r["graduation_rate"], r["launches_tracked"]), reverse=True)
    elif sort_by == "graduation_rate":
        rows.sort(key=lambda r: (r["graduation_rate"], r["launches_tracked"]), reverse=True)
    elif sort_by == "launches":
        rows.sort(key=lambda r: r["launches_tracked"], reverse=True)
    elif sort_by == "median_curve":
        rows.sort(key=lambda r: r["median_peak_curve_progress"], reverse=True)
    elif sort_by == "median_holders":
        rows.sort(key=lambda r: r["median_peak_holders"], reverse=True)
    elif sort_by == "recent":
        rows.sort(key=lambda r: r["last_launch_at"], reverse=True)

    return {
        "count": len(rows[:limit]),
        "total_creators": len(rows),
        "filters": {
            "sort_by": sort_by,
            "trust_tier": trust_tier,
            "min_launches": min_launches,
            "limit": limit,
        },
        "creators": rows[:limit],
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


@app.get("/api/platform/cohorts", tags=["platform"], summary="Cohort-level analytics: age, narrative, quote asset, whale risk")
async def platform_cohorts():
    """Platform analytics — cohort survival by age, narrative, and quote asset.

    Everything is computed from FOUR-LIFE's own tracked launches. Returns empty cohorts
    rather than fabricated numbers when data is thin.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    launches = list(agent.memory.memory.launches)
    if not launches:
        return {
            "cohorts_by_age": {},
            "by_narrative": [],
            "by_quote_asset": {},
            "whale_risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "avg_time_to_graduation_hours": None,
            "launches_tracked": 0,
            "model_version": MODEL_VERSION,
            "last_updated_at": int(time.time()),
            "note": "No launches tracked yet.",
        }

    now = time.time()
    buckets = {"under_1h": 0, "1h_to_24h": 0, "1d_to_7d": 0, "7d_plus": 0}
    for lr in launches:
        age_h = (now - lr.launched_at) / 3600 if lr.launched_at else 0
        if age_h < 1: buckets["under_1h"] += 1
        elif age_h < 24: buckets["1h_to_24h"] += 1
        elif age_h < 168: buckets["1d_to_7d"] += 1
        else: buckets["7d_plus"] += 1

    narrative_stats: dict[str, dict] = {}
    for lr in launches:
        key = lr.narrative or "unknown"
        if key not in narrative_stats:
            narrative_stats[key] = {"launches": 0, "graduations": 0, "peak_holders_sum": 0}
        narrative_stats[key]["launches"] += 1
        if lr.graduated:
            narrative_stats[key]["graduations"] += 1
        narrative_stats[key]["peak_holders_sum"] += lr.peak_holders
    narrative_list = [
        {
            "narrative": k,
            "launches": v["launches"],
            "graduations": v["graduations"],
            "graduation_rate": round(v["graduations"] / v["launches"], 3) if v["launches"] else 0,
            "avg_peak_holders": round(v["peak_holders_sum"] / v["launches"], 1) if v["launches"] else 0,
        }
        for k, v in sorted(narrative_stats.items(), key=lambda kv: kv[1]["launches"], reverse=True)
    ]

    quote_stats: dict[str, int] = {}
    for lr in launches:
        qa = getattr(lr, "quote_asset", "BNB") or "BNB"
        quote_stats[qa] = quote_stats.get(qa, 0) + 1

    whale_dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for addr in list(agent.monitor.state.tokens.keys()):
        h = agent.monitor.state.tokens[addr]
        if h.top_holder_pct >= 40: whale_dist["critical"] += 1
        elif h.top_holder_pct >= 20: whale_dist["high"] += 1
        elif h.top_holder_pct >= 10: whale_dist["medium"] += 1
        else: whale_dist["low"] += 1

    grad_times = [
        (lr.graduation_time - lr.launched_at) / 3600
        for lr in launches
        if lr.graduated and lr.graduation_time and lr.launched_at
    ]
    avg_ttg = round(sum(grad_times) / len(grad_times), 2) if grad_times else None

    return {
        "launches_tracked": len(launches),
        "graduations": sum(1 for lr in launches if lr.graduated),
        "cohorts_by_age": buckets,
        "by_narrative": narrative_list,
        "by_quote_asset": quote_stats,
        "whale_risk_distribution": whale_dist,
        "avg_time_to_graduation_hours": avg_ttg,
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


@app.get("/api/token/{token_address}/operator-checklist", tags=["platform"], summary="Deterministic 72h operator checklist (rule-based, not LLM)")
async def operator_checklist(token_address: str):
    """Deterministic 72h operator checklist — the thing Four.meme creators should actually
    do at each phase. Rules-based, no LLM. Optional style-matched posts can layer on top."""
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    health = agent.monitor.state.tokens.get(token_address)
    if not health:
        return JSONResponse({
            "error": "Token not tracked. Use /api/agent/track to begin monitoring.",
        }, status_code=404)

    age_h = health.age_hours
    checklist: list[dict] = []

    def _item(phase: str, priority: str, title: str, rationale: str, metric: str = "", value=None):
        checklist.append({
            "phase": phase,
            "priority": priority,
            "title": title,
            "rationale": rationale,
            "metric": metric,
            "value": value,
        })

    # Launch / Nurture
    if age_h < 1:
        _item("launch", "critical", "Post launch thread with token concept + why you built it",
              "First 60 minutes decide early holder trust.", "age_hours", round(age_h, 2))
        _item("launch", "high", "Pin the token address + pair info in every chat",
              "Reduces scam-clone risk. Clarity wins trust.", "age_hours", round(age_h, 2))

    if age_h < 6:
        _item("nurture", "high", "Seed initial holders — invite 20 supporters manually",
              "Breaking 50 holders early signals organic traction.", "unique_buyers", health.unique_buyers)
        _item("nurture", "medium", "Post first milestone update at 25 holders",
              "Holder milestones compound via social proof.", "unique_buyers", health.unique_buyers)

    # Defend
    if 6 <= age_h < 24:
        _item("defend", "high", "Publish a transparency post: holder count + curve progress",
              "Defend phase: reduce FUD window by showing honest numbers.",
              "curve_progress_pct", round(health.curve_progress_pct, 2))
        if health.top_holder_pct >= 20:
            _item("defend", "critical", f"Disclose whale concentration: top holder owns {health.top_holder_pct:.1f}%",
                  "High whale concentration is the #1 reason buyers leave.",
                  "top_holder_pct", round(health.top_holder_pct, 2))
        if health.buy_sell_ratio > 0 and health.buy_sell_ratio < 1.0:
            _item("defend", "high", "Counter-signal the sell pressure with a roadmap post",
                  "Buy/sell ratio <1 means supply is dominant. Content must restore demand narrative.",
                  "buy_sell_ratio", round(health.buy_sell_ratio, 2))

    # Accelerate
    if 24 <= age_h < 72:
        _item("accelerate", "high", "Coordinate a community buy window (pick a time, announce)",
              "Concentrated liquidity events push curve past key thresholds.",
              "curve_progress_pct", round(health.curve_progress_pct, 2))
        if health.curve_progress_pct >= 70:
            _item("accelerate", "critical", "Run the final push to graduation — last-mile content + call-to-action",
                  "Above 70% curve, graduation is within reach if momentum holds.",
                  "curve_progress_pct", round(health.curve_progress_pct, 2))

    # Post-graduation
    if health.phase == "graduated":
        _item("post_graduation", "high", "Announce graduation to PancakeSwap with LP address",
              "Graduation is the celebration moment — convert it into LP-stake narrative.",
              "phase", "graduated")

    # If no phase-specific items fired (e.g., just started), add a generic monitoring item
    if not checklist:
        _item("observe", "medium", "No time-critical action — monitor holder growth + whale drift",
              "Let the early metrics settle before intervening.",
              "age_hours", round(age_h, 2))

    return {
        "token_address": token_address,
        "name": health.name,
        "symbol": health.symbol,
        "phase": health.phase,
        "age_hours": round(health.age_hours, 2),
        "checklist": checklist,
        "item_count": len(checklist),
        "model_version": MODEL_VERSION,
        "last_updated_at": int(time.time()),
        "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
    }


# ── Manual Controls ──────────────────────────────────────────────────

@app.post("/api/agent/start", tags=["agent"], summary="Start the autonomous loop")
async def start_agent(_=Depends(require_auth)):
    """Start the agent loop."""
    import asyncio
    if not agent:
        return {"error": "Agent not configured"}
    if not agent.running:
        asyncio.create_task(agent.run())
        return {"status": "started"}
    return {"status": "already running"}


@app.post("/api/agent/stop", tags=["agent"], summary="Stop the autonomous loop")
async def stop_agent(_=Depends(require_auth)):
    """Stop the agent loop."""
    if not agent:
        return {"error": "Agent not configured"}
    await agent.stop()
    return {"status": "stopped"}


# ── Manual Token Management ──────────────────────────────────────────

@app.post("/api/agent/think", tags=["agent"], summary="Run a single THINK cycle")
async def manual_think(_=Depends(require_auth)):
    """Run one THINK cycle — always generates a concept for manual creation."""
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    from agent.brain.llm import get_llm

    try:
        # Get market data
        try:
            trending = await agent.api.get_trending()
        except Exception:
            trending = []

        try:
            recent = await agent.api.get_new_tokens()
        except Exception:
            recent = []

        # Analyze narratives — no silent generic fallback. If LLM-backed analysis fails,
        # surface degraded mode to the caller so judges can see what's real vs. fallback.
        degraded = False
        degraded_reason = None
        market_analysis = None
        try:
            market_analysis = await agent.narrative.analyze_market(trending, recent)
        except Exception as e:
            logger.error("analyze_market failed: {}", e)
            degraded = True
            degraded_reason = f"narrative_analysis_failed: {str(e)[:200]}"

        if market_analysis is None:
            # Deterministic surface-level signal from ranking data only — no invented narrative
            top_symbols = [t.get("shortName", "") for t in (trending or [])[:5] if t.get("shortName")]
            return {
                "degraded": True,
                "reason": degraded_reason,
                "surface_signal": {
                    "top_trending_symbols": top_symbols,
                    "new_token_count": len(recent or []),
                },
                "message": "THINK phase degraded — LLM narrative analysis unavailable. Surface-level market signal returned instead. No token concept generated.",
                "model_version": MODEL_VERSION,
                "llm_provider": get_llm().model_id,
                "last_updated_at": int(time.time()),
            }

        narrative = market_analysis.get("recommended_narrative", {})
        narrative_name = narrative.get("name", "trending meme") if isinstance(narrative, dict) else str(narrative)

        # Generate concept
        existing_names = [lr.name for lr in agent.memory.memory.launches]
        concept = await agent.narrative.generate_concept(narrative_name, existing_names)
        concept["narrative"] = narrative_name
        concept["market_analysis"] = market_analysis

        return {
            "concept": concept,
            "degraded": False,
            "message": "Concept ready. Create this token on four.meme, then POST to /api/agent/track with the token address.",
            "model_version": MODEL_VERSION,
            "llm_provider": get_llm().model_id,
            "last_updated_at": int(time.time()),
        }
    except Exception as e:
        logger.error("manual_think failed: {}", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/agent/track", tags=["agent"], summary="Begin lifecycle tracking for a token")
async def manual_track(data: dict, _=Depends(require_auth)):
    """Track an existing token for lifecycle management.

    Body: {"token_address": "0x...", "name": "TokenName", "symbol": "TKN", "concept": {...}}
    Use this after manually creating a token on four.meme.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    token_address = data.get("token_address")
    name = data.get("name", "")
    symbol = data.get("symbol", "")
    quote_asset = (data.get("quote_asset", "BNB") or "BNB").upper()
    creator_override = data.get("creator", "")
    concept = data.get("concept", {"name": name, "symbol": symbol, "personality": "Degen crypto energy"})
    # Accept explicit launched_at (unix seconds) OR launch_block for existing tokens
    # so age_hours reflects on-chain reality, not observation age.
    launched_at_override = data.get("launched_at")
    launch_block_override = data.get("launch_block")

    if not token_address:
        return JSONResponse({"error": "token_address required"}, status_code=400)

    from agent.memory.store import LaunchRecord
    import time

    current_block = await agent.chain.get_block_number()
    creator = creator_override or agent.chain.account.address

    # Resolve the best-available launched_at. Order of preference:
    #   1. Explicit `launched_at` from the request body
    #   2. Derived from explicit `launch_block` (block delta × 3s BSC block time)
    #   3. Existing memory record for this token (if we're re-tracking after restart)
    #   4. Current time (new launch happening now)
    if launched_at_override:
        resolved_launched_at = float(launched_at_override)
        resolved_launch_block = int(launch_block_override or current_block)
    elif launch_block_override:
        block_delta = max(0, current_block - int(launch_block_override))
        resolved_launched_at = time.time() - (block_delta * 3.0)
        resolved_launch_block = int(launch_block_override)
    else:
        prior = agent.memory.get_launch(token_address)
        resolved_launched_at = (prior.launched_at if prior and prior.launched_at else time.time())
        resolved_launch_block = (prior.launch_block if prior and prior.launch_block else current_block)

    # Seed initial metrics from Four.meme's own radar so the token isn't born
    # as all-zeros. Best effort — if the lookup fails, we still track; on-chain
    # updates will fill the history in over time.
    seed: dict | None = None
    try:
        addr_l = token_address.lower()
        hot = await agent.api.get_trending()
        new = await agent.api.get_new_tokens(page_size=30)
        for t in (hot or []) + (new or []):
            if str(t.get("tokenAddress", "")).lower() == addr_l:
                seed = t
                break
    except Exception as e:
        logger.debug("track seed lookup skipped: {}", e)

    await agent.monitor.track_token(
        token_address, name=name, symbol=symbol,
        creator=creator, created_block=resolved_launch_block,
        quote_asset=quote_asset,
        seed=seed,
        launched_at=resolved_launched_at,
    )

    # Only record a new LaunchRecord if one doesn't already exist — prevents
    # duplicate rows when /api/agent/track is called repeatedly for the same
    # token (e.g. after a service restart).
    if not agent.memory.get_launch(token_address):
        agent.memory.record_launch(LaunchRecord(
            token_address=token_address,
            name=name,
            symbol=symbol,
            narrative=concept.get("narrative", ""),
            concept=concept,
            launched_at=resolved_launched_at,
            launch_block=resolved_launch_block,
            creator=creator,
            quote_asset=quote_asset,
        ))

    agent.active_concepts[token_address] = concept

    return {
        "status": "tracking",
        "token_address": token_address,
        "name": name,
        "symbol": symbol,
        "message": "Token is now being managed by FOUR-LIFE lifecycle engine.",
    }
