"""FastAPI server — dashboard backend + agent-card endpoint."""

import json
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.agent import FourLifeAgent
from agent.badge import badge_from_health, badge_from_ranking
from agent.security.contract_analyzer import ContractAnalyzer, ContractRisk


agent: FourLifeAgent | None = None


async def require_auth(authorization: str = Header(default="")):
    """Guard for control endpoints. Skip if API_SECRET is not set."""
    from agent.config import settings
    if not settings.api_secret:
        return  # No auth configured — allow (dev mode)
    if authorization != f"Bearer {settings.api_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start agent in background on server boot."""
    global agent
    try:
        agent = FourLifeAgent()
    except Exception as e:
        from loguru import logger
        logger.warning("Agent init failed (missing keys?): {}. API running in read-only mode.", e)
        agent = None
    yield
    if agent:
        await agent.stop()
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

- TypeScript SDK: [`@four-life/sdk`](https://github.com/Ridwannurudeen/four-life/tree/master/sdk)
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
    # "*" is safe here because we never send cookies (allow_credentials defaults to False).
    # Write endpoints (POST /api/agent/*) stay protected by the API_SECRET bearer check in
    # require_auth() — widening origins does not bypass that.
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Rate limiting (in-memory token bucket per IP) ────────────────────
# Simple, dependency-free. For a multi-process deployment this would move to Redis,
# but the VPS runs a single uvicorn worker so an in-memory bucket is sufficient.

import time as _time_rl
from collections import defaultdict as _defaultdict

_RL_WINDOW_SECONDS = 60
_RL_PUBLIC_LIMIT = 120   # GET /api/** (public read)
_RL_WRITE_LIMIT = 30     # POST /api/agent/** (write)
_rate_buckets: dict[tuple[str, str], list[float]] = _defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Per-IP rolling-window rate limit. Skips /docs, /openapi, /.well-known."""
    path = request.url.path
    if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi") or path.startswith("/.well-known"):
        return await call_next(request)

    # Bucket key: (client IP, bucket class). Write endpoints get a stricter bucket.
    client_ip = request.client.host if request.client else "unknown"
    is_write = request.method == "POST" and path.startswith("/api/agent/")
    bucket_class = "write" if is_write else "public"
    limit = _RL_WRITE_LIMIT if is_write else _RL_PUBLIC_LIMIT
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
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(bucket)))
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
async def status():
    if not agent:
        return {
            "agent_name": "FOUR-LIFE",
            "running": False,
            "agent_id": None,
            "wallet": "",
            "total_launches": 0,
            "total_graduations": 0,
            "graduation_rate": 0,
            "avg_peak_holders": 0,
            "active_tokens": 0,
            "global_learnings": [],
            "message": "Agent not configured — add keys to .env",
        }
    mem = agent.memory.memory
    return {
        "agent_name": "FOUR-LIFE",
        "running": agent.running,
        "agent_id": agent.identity.agent_id,
        "wallet": agent.chain.account.address,
        "total_launches": mem.total_launches,
        "total_graduations": mem.total_graduations,
        "graduation_rate": round(mem.graduation_rate * 100, 1),
        "avg_peak_holders": round(mem.avg_peak_holders, 0),
        "active_tokens": len(agent.active_concepts),
        "global_learnings": mem.global_learnings[-10:],
    }


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
async def token_detail(address: str):
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)
    health = agent.monitor.state.tokens.get(address)
    if not health:
        return JSONResponse({"error": "Token not found"}, status_code=404)

    concept = agent.active_concepts.get(address, {})
    actions = agent.lifecycle.get_action_history(address)
    launch = agent.memory.get_launch(address)

    return {
        "health": {
            "address": address,
            "name": health.name,
            "symbol": health.symbol,
            "phase": health.phase,
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
        "launch_record": {
            "launched_at": launch.launched_at if launch else None,
            "peak_holders": launch.peak_holders if launch else 0,
            "peak_health_score": launch.peak_health_score if launch else 0,
            "graduated": launch.graduated if launch else False,
            "what_worked": launch.what_worked if launch else [],
            "what_failed": launch.what_failed if launch else [],
        },
    }


# ── Memory ───────────────────────────────────────────────────────────

@app.get("/api/memory", tags=["dashboard"], summary="Agent memory (learnings, launch history)")
async def memory():
    if not agent:
        return {"total_launches": 0, "total_graduations": 0, "graduation_rate": 0, "avg_peak_holders": 0, "best_narratives": [], "worst_narratives": [], "global_learnings": [], "launches": [], "last_updated": 0}
    mem = agent.memory.memory
    return {
        "total_launches": mem.total_launches,
        "total_graduations": mem.total_graduations,
        "graduation_rate": round(mem.graduation_rate * 100, 1),
        "avg_peak_holders": round(mem.avg_peak_holders, 0),
        "best_narratives": mem.best_narratives,
        "worst_narratives": mem.worst_narratives,
        "global_learnings": mem.global_learnings,
        "launches": [
            {
                "name": lr.name,
                "symbol": lr.symbol,
                "narrative": lr.narrative,
                "launched_at": lr.launched_at,
                "peak_holders": lr.peak_holders,
                "peak_health_score": lr.peak_health_score,
                "peak_curve_progress": round(lr.peak_curve_progress, 1),
                "graduated": lr.graduated,
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


@app.post("/api/myx/evaluate/{token_address}", tags=["myx"], summary="Manually trigger a hedge evaluation")
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


# ── Public Integration APIs ──────────────────────────────────────────
# These endpoints are designed for Four.meme to consume directly.
# No auth required. Any token address works.

MODEL_VERSION = "four-life-v1.1"

# ── Contract-risk cache (10 min TTL, in-memory) ──────────────────────
CONTRACT_RISK_TTL_SECONDS = 600
_contract_risk_cache: dict[str, tuple[float, ContractRisk]] = {}


async def _get_contract_risk(token_address: str) -> ContractRisk | None:
    """Fetch (or return cached) contract risk for a token. TTL = 10 minutes."""
    if not agent:
        return None
    key = token_address.lower()
    cached = _contract_risk_cache.get(key)
    now = time.time()
    if cached and now - cached[0] < CONTRACT_RISK_TTL_SECONDS:
        return cached[1]

    from agent.config import settings
    analyzer = ContractAnalyzer(agent.chain.w3, bscscan_api_key=settings.bscscan_api_key)
    try:
        risk = await analyzer.analyze(token_address)
    except Exception as e:
        logger.warning("contract analyze failed for {}: {}", token_address, e)
        return None
    _contract_risk_cache[key] = (now, risk)
    return risk


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
        badge = badge_from_health(health, contract_risk_score=crs)

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


@app.post("/api/raise-plan/{token_address}", tags=["platform"], summary="LLM-generated 72h raise plan (pair-aware target)")
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
                "status": t.get("status", ""),
                "fourmeme_url": f"https://four.meme/token/{addr}",
            })

        sort_keys = {
            "graduation_probability": lambda x: x["graduation_probability"],
            "health_score": lambda x: x["health_score"],
            "holder_velocity": lambda x: x["holder_velocity"],
            "curve_progress": lambda x: x["curve_progress"],
        }
        all_tokens.sort(key=sort_keys[sort_by], reverse=True)

        return {
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
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        health = agent.monitor.state.tokens.get(token_address)
        if health:
            contract_risk = await _get_contract_risk(token_address)
            crs = contract_risk.risk_score if contract_risk else 0
            badge = badge_from_health(health, contract_risk_score=crs)
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

            quote_asset = (info.get("symbol", "BNB") or "BNB").upper()
            target = await agent.graduation_registry.get(quote_asset)
            badge = badge_from_ranking(
                curve_progress_pct=float(info.get("progress", 0)) * 100,
                holders=int(info.get("hold", 0)),
                increase_pct=float(info.get("increase", 0)) * 100,
                graduation_confidence=target.confidence,
            )
            source = "ranking_snapshot"

        return {
            "token_address": token_address,
            "badge": badge.to_dict(),
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


@app.get("/api/token/{token_address}/contract-risk", tags=["contract"], summary="Bytecode + source analysis — mint, blacklist, proxy, pause, ownership, honeypot")
async def token_contract_risk(token_address: str):
    """Deterministic contract-level rug-risk analysis for a BSC token.

    Scans bytecode + BscScan-verified ABI for mint, blacklist, pause, EIP-1967
    proxy, and ownership status. Cached for 10 minutes per token.
    """
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


@app.get("/api/creator/{wallet}/survival-score", tags=["creator"], summary="Creator track record + deterministic trust tier")
async def creator_survival_score(wallet: str):
    """Aggregate survival performance for a creator wallet across all FOUR-LIFE-tracked launches.

    Fields: launches tracked, graduations, median peak curve progress, median peak holders,
    trust tier. Returns honestly-empty stats for unknown creators — no fabrication.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    wallet_lower = wallet.lower()
    # Gather all launches for this creator. Empty `creator` field defaults to agent wallet.
    agent_wallet = (agent.chain.account.address or "").lower()
    launches = []
    for lr in agent.memory.memory.launches:
        creator = (lr.creator or agent_wallet).lower()
        if creator == wallet_lower:
            launches.append(lr)

    if not launches:
        return {
            "wallet": wallet,
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

    def _median(xs: list[float]) -> float:
        if not xs:
            return 0.0
        s = sorted(xs)
        n = len(s)
        mid = n // 2
        return float(s[mid]) if n % 2 == 1 else float((s[mid - 1] + s[mid]) / 2)

    graduations = sum(1 for lr in launches if lr.graduated)
    grad_rate = graduations / len(launches) if launches else 0.0
    median_curve = _median([lr.peak_curve_progress for lr in launches])
    median_holders = _median([float(lr.peak_holders) for lr in launches])

    # Deterministic trust tier
    if len(launches) < 3:
        trust_tier = "new_creator"
    elif grad_rate >= 0.5 and median_holders >= 250:
        trust_tier = "proven"
    elif grad_rate >= 0.25 or median_curve >= 40:
        trust_tier = "emerging"
    else:
        trust_tier = "unproven"

    return {
        "wallet": wallet,
        "tracked": True,
        "launches_tracked": len(launches),
        "graduations": graduations,
        "graduation_rate": round(grad_rate, 3),
        "median_peak_curve_progress": round(median_curve, 2),
        "median_peak_holders": int(median_holders),
        "trust_tier": trust_tier,
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
            for lr in launches[-10:]  # most recent 10 for transparency
        ],
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

    if not token_address:
        return JSONResponse({"error": "token_address required"}, status_code=400)

    from agent.memory.store import LaunchRecord
    import time

    current_block = await agent.chain.get_block_number()
    creator = creator_override or agent.chain.account.address

    await agent.monitor.track_token(
        token_address, name=name, symbol=symbol,
        creator=creator, created_block=current_block,
        quote_asset=quote_asset,
    )

    agent.memory.record_launch(LaunchRecord(
        token_address=token_address,
        name=name,
        symbol=symbol,
        narrative=concept.get("narrative", ""),
        concept=concept,
        launched_at=time.time(),
        launch_block=current_block,
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
