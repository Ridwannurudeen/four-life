"""FastAPI server — dashboard backend + agent-card endpoint."""

import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.agent import FourLifeAgent


agent: FourLifeAgent | None = None


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


app = FastAPI(title="FOUR-LIFE Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Agent Card (ERC-8004 discovery) ──────────────────────────────────

@app.get("/.well-known/agent-registration.json")
async def agent_card():
    if not agent:
        return JSONResponse({"name": "FOUR-LIFE", "status": "not configured"})
    card = agent.identity.generate_agent_card()
    return JSONResponse(card)


# ── Agent Status ─────────────────────────────────────────────────────

@app.get("/api/status")
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

@app.get("/api/tokens")
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


@app.get("/api/tokens/{address}")
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

@app.get("/api/memory")
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

@app.get("/api/actions")
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


# ── MYX V2 Perps ─────────────────────────────────────────────────────

@app.get("/api/myx/status")
async def myx_status():
    if not agent or not agent.myx:
        return {"enabled": False, "reason": "MYX not configured"}
    try:
        markets = await agent.myx.get_markets()
        return {
            "enabled": True,
            "markets_count": len(markets),
            "markets": markets[:10],
        }
    except Exception as e:
        return {"enabled": True, "error": str(e)}


@app.get("/api/myx/signal/{token_address}")
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
        return {"signal": signal}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/myx/portfolio")
async def myx_portfolio():
    """Get hedge portfolio summary across all tokens."""
    if not agent or not agent.hedge_manager:
        return {"enabled": False, "reason": "MYX not configured"}
    return agent.hedge_manager.get_portfolio_summary()


@app.get("/api/myx/positions/{token_address}")
async def myx_positions(token_address: str):
    """Get all hedge positions for a specific token."""
    if not agent or not agent.hedge_manager:
        return {"enabled": False, "reason": "MYX not configured"}
    return {
        "token_address": token_address,
        "positions": agent.hedge_manager.get_token_positions(token_address),
    }


@app.post("/api/myx/evaluate/{token_address}")
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

@app.get("/api/health-score/{token_address}")
async def public_health_score(token_address: str):
    """Public health score for any Four.meme token.

    Integration-ready: Four.meme can embed this on token pages.
    Returns health score, graduation probability, risk metrics, and suggested actions.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        from agent.fourmeme.monitor import TokenHealth, TokenMonitor
        from agent.fourmeme.chain import FourMemeChain

        # Check if already tracked
        health = agent.monitor.state.tokens.get(token_address)

        if not health:
            # Create a temporary monitor for this token
            chain = agent.chain
            current_block = await chain.get_block_number()

            # Get token info from Four.meme API
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

            name = token_info.get("name", "") if token_info else ""
            symbol = token_info.get("shortName", "") if token_info else ""
            holders = int(token_info.get("hold", 0)) if token_info else 0
            progress = float(token_info.get("progress", 0)) if token_info else 0
            volume = float(token_info.get("volume", 0)) if token_info else 0

            # Build a health snapshot from available data
            health_score = 0.0
            grad_prob = 0.0

            # Score based on available metrics
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

            return {
                "token_address": token_address,
                "name": name,
                "symbol": symbol,
                "health_score": round(health_score, 1),
                "graduation_probability": round(grad_prob * 100, 1),
                "holders": holders,
                "curve_progress": round(progress * 100, 1),
                "volume_bnb": round(volume, 4),
                "risk_factors": [],
                "suggested_action": "Track this token with FOUR-LIFE for detailed lifecycle management.",
                "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
            }

        # Already tracked — return full metrics
        risk_factors = []
        if health.top_holder_pct > 30:
            risk_factors.append(f"High whale concentration: top holder owns {health.top_holder_pct:.1f}%")
        if health.buy_sell_ratio < 1:
            risk_factors.append(f"Sell pressure exceeding buys: ratio {health.buy_sell_ratio:.2f}")
        if health.holder_velocity < 1 and health.age_hours > 2:
            risk_factors.append("Low holder growth velocity")

        suggested = "No action needed."
        if health.top_holder_pct > 30:
            suggested = "Post transparency update showing holder distribution."
        elif health.curve_progress_pct < 25 and health.age_hours > 12:
            suggested = "Increase community engagement — post memes and milestone updates."
        elif health.curve_progress_pct > 70:
            suggested = "Push for graduation — coordinate community buying pressure."

        return {
            "token_address": token_address,
            "name": health.name,
            "symbol": health.symbol,
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
            "risk_factors": risk_factors,
            "suggested_action": suggested,
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/raise-plan/{token_address}")
async def generate_raise_plan(token_address: str):
    """Generate a 72-hour lifecycle raise plan for a token.

    AI creates an actionable phased plan: 0-30min, 1-6h, 6-24h, 24-72h, post-graduation.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        from agent.brain.llm import get_llm

        # Get token info
        health = agent.monitor.state.tokens.get(token_address)
        health_context = ""
        if health:
            health_context = f"""
Token: {health.name} ({health.symbol})
Current Phase: {health.phase}
Age: {health.age_hours:.1f}h
Health Score: {health.health_score}/100
Holders: {health.unique_buyers}
Buy/Sell Ratio: {health.buy_sell_ratio:.2f}
Top Holder: {health.top_holder_pct:.1f}%
Bonding Curve: {health.curve_progress_pct:.1f}%
"""
        else:
            health_context = f"Token address: {token_address} (not currently tracked — no live metrics available)"

        plan = await get_llm().chat_json([{
            "role": "user",
            "content": f"""You are FOUR-LIFE, an AI lifecycle agent for Four.meme tokens on BNB Chain.

Generate a 72-hour Raise Plan for this token. The plan should help it graduate (reach 18 BNB bonding curve).

{health_context}

Create a phased action plan in JSON:
{{
  "token_address": "{token_address}",
  "phases": [
    {{
      "name": "Launch (0-30 min)",
      "actions": ["action 1", "action 2", ...],
      "content_suggestions": ["tweet idea", ...],
      "risk_checks": ["thing to monitor", ...]
    }},
    {{
      "name": "Nurture (1-6 hours)",
      "actions": [...],
      "content_suggestions": [...],
      "risk_checks": [...]
    }},
    {{
      "name": "Defend (6-24 hours)",
      "actions": [...],
      "content_suggestions": [...],
      "risk_checks": [...]
    }},
    {{
      "name": "Accelerate (24-72 hours)",
      "actions": [...],
      "content_suggestions": [...],
      "risk_checks": [...]
    }},
    {{
      "name": "Post-Graduation",
      "actions": [...],
      "content_suggestions": [...],
      "risk_checks": [...]
    }}
  ],
  "graduation_strategy": "one sentence summary of the best path to graduation",
  "risk_assessment": "key risks and how to mitigate them"
}}

Be specific and actionable. No vague advice. Reference actual metrics where available."""
        }])

        return {"plan": plan, "powered_by": "FOUR-LIFE | four-life.gudman.xyz"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/graduation-radar")
async def graduation_radar(limit: int = 20):
    """Public Graduation Radar — ranks active Four.meme tokens by graduation probability.

    Useful for traders and creators to discover high-potential tokens.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    try:
        # Get hot tokens from Four.meme
        hot_tokens = await agent.api.get_trending()
        new_tokens = await agent.api.get_new_tokens(page_size=limit)

        # Merge and deduplicate
        seen = set()
        all_tokens = []
        for t in hot_tokens + new_tokens:
            addr = t.get("tokenAddress", "")
            if addr and addr not in seen:
                seen.add(addr)
                holders = int(t.get("hold", 0))
                progress = float(t.get("progress", 0))
                volume = float(t.get("volume", 0))
                increase = float(t.get("increase", 0))

                # Calculate scores
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

                all_tokens.append({
                    "token_address": addr,
                    "name": t.get("name", ""),
                    "symbol": t.get("shortName", ""),
                    "holders": holders,
                    "curve_progress": round(progress * 100, 1),
                    "volume_bnb": round(volume, 2),
                    "increase_pct": round(increase * 100, 1),
                    "health_score": round(min(100, health_score), 1),
                    "graduation_probability": round(min(100, grad_prob * 100), 1),
                    "status": t.get("status", ""),
                })

        # Sort by graduation probability descending
        all_tokens.sort(key=lambda x: x["graduation_probability"], reverse=True)

        return {
            "radar": all_tokens[:limit],
            "total_scanned": len(all_tokens),
            "timestamp": time.time(),
            "powered_by": "FOUR-LIFE | four-life.gudman.xyz",
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Manual Controls ──────────────────────────────────────────────────

@app.post("/api/agent/start")
async def start_agent():
    """Start the agent loop."""
    import asyncio
    if not agent:
        return {"error": "Agent not configured"}
    if not agent.running:
        asyncio.create_task(agent.run())
        return {"status": "started"}
    return {"status": "already running"}


@app.post("/api/agent/stop")
async def stop_agent():
    """Stop the agent loop."""
    if not agent:
        return {"error": "Agent not configured"}
    await agent.stop()
    return {"status": "stopped"}


# ── Manual Token Management ──────────────────────────────────────────

@app.post("/api/agent/think")
async def manual_think():
    """Run one THINK cycle — always generates a concept for manual creation."""
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    from agent.brain.llm import get_llm

    # Get market data
    trending = await agent.api.get_trending()
    try:
        recent = await agent.api.get_new_tokens()
    except Exception:
        recent = []

    # Analyze narratives
    market_analysis = await agent.narrative.analyze_market(trending, recent)
    narrative = market_analysis.get("recommended_narrative", {})
    narrative_name = narrative.get("name", "trending meme") if isinstance(narrative, dict) else str(narrative)

    # Generate concept
    existing_names = [lr.name for lr in agent.memory.memory.launches]
    concept = await agent.narrative.generate_concept(narrative_name, existing_names)
    concept["narrative"] = narrative_name
    concept["market_analysis"] = market_analysis

    return {
        "concept": concept,
        "message": "Concept ready. Create this token on four.meme, then POST to /api/agent/track with the token address.",
    }


@app.post("/api/agent/track")
async def manual_track(data: dict):
    """Track an existing token for lifecycle management.

    Body: {"token_address": "0x...", "name": "TokenName", "symbol": "TKN", "concept": {...}}
    Use this after manually creating a token on four.meme.
    """
    if not agent:
        return JSONResponse({"error": "Agent not configured"}, status_code=503)

    token_address = data.get("token_address")
    name = data.get("name", "")
    symbol = data.get("symbol", "")
    concept = data.get("concept", {"name": name, "symbol": symbol, "personality": "Degen crypto energy"})

    if not token_address:
        return JSONResponse({"error": "token_address required"}, status_code=400)

    from agent.memory.store import LaunchRecord
    import time

    current_block = await agent.chain.get_block_number()

    await agent.monitor.track_token(
        token_address, name=name, symbol=symbol,
        creator=agent.chain.account.address, created_block=current_block,
    )

    agent.memory.record_launch(LaunchRecord(
        token_address=token_address,
        name=name,
        symbol=symbol,
        narrative=concept.get("narrative", ""),
        concept=concept,
        launched_at=time.time(),
        launch_block=current_block,
    ))

    agent.active_concepts[token_address] = concept

    return {
        "status": "tracking",
        "token_address": token_address,
        "name": name,
        "symbol": symbol,
        "message": "Token is now being managed by FOUR-LIFE lifecycle engine.",
    }
