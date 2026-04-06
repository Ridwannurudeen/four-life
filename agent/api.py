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
    if not agent.myx:
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
    if not agent.myx_strategy:
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


# ── Manual Controls ──────────────────────────────────────────────────

@app.post("/api/agent/start")
async def start_agent():
    """Start the agent loop."""
    import asyncio
    if not agent.running:
        asyncio.create_task(agent.run())
        return {"status": "started"}
    return {"status": "already running"}


@app.post("/api/agent/stop")
async def stop_agent():
    """Stop the agent loop."""
    await agent.stop()
    return {"status": "stopped"}
